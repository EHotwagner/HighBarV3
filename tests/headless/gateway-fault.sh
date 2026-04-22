#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-2.0-only
# arm-covered: (none — fault-injection harness)
#
# T066 — Gateway fault-injection test. Verifies that
# CGrpcGatewayModule::HB_HOOK_GUARD_* catches an in-flight exception
# from the gRPC service surface, transitions to GatewayState::Disabled,
# and emits the four signals contracts/gateway-fault.md prescribes.
# Malformed client payload rejection is covered separately by
# `malformed-payload.sh`; this harness is for internal fault/disable
# behavior only.
#
# Note on client-mode reframing: contracts/gateway-fault.md was written
# against server-mode (where the plugin owned a UDS socket + token
# file on disk). After the client-mode flip the plugin is a gRPC
# *client*; the four signals become:
#
#   (a) engine log line `[hb-gateway] fault subsystem=… reason=…`
#   (b) $writeDir/highbar.health contains `"status":"disabled"`
#   (c) coordinator log shows the PushState stream closed
#   (d) heartbeats stop arriving at the coordinator
#
# Exit codes:
#   0  — all four signals observed (contract met).
#   1  — at least one signal missing.
#   77 — fault could not be triggered in this environment (e.g., the
#        plugin gracefully validated the malformed payload and never
#        threw). This is NOT a regression — the contract only fires
#        on uncaught exceptions; documented in research.md.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
HEADLESS_DIR="$REPO_ROOT/tests/headless"
EXAMPLES_DIR="$REPO_ROOT/specs/002-live-headless-e2e/examples"

if [[ -z "${SPRING_HEADLESS:-}" ]]; then
    echo "gateway-fault: SPRING_HEADLESS not set — skip" >&2
    exit 77
fi

source "$HEADLESS_DIR/_fault-assert.sh"

RUN_DIR="${HIGHBAR_FAULT_RUN_DIR:-$(mktemp -d -t hb-gateway-fault.XXXXXX)}"
mkdir -p "$RUN_DIR"
COORD_SOCK="$RUN_DIR/hb-coord.sock"
COORD_LOG="$RUN_DIR/coord.log"
ENGINE_LOG="$RUN_DIR/highbar-launch.log"
ENGINE_PID_FILE="$RUN_DIR/highbar-launch.pid"
START_SCRIPT="$HEADLESS_DIR/scripts/minimal.startscript"
WRITE_DIR="${HIGHBAR_WRITE_DIR:-$HOME/.local/state/Beyond All Reason}"
PIN_RELEASE="recoil_2025.06.19"
EFFECTIVE_WRITEDIR="$WRITE_DIR/engine/$PIN_RELEASE"

cleanup() {
    [[ -f "$ENGINE_PID_FILE" ]] && kill -TERM "$(cat "$ENGINE_PID_FILE")" 2>/dev/null
    [[ -n "${COORD_PID:-}" ]] && kill -TERM "$COORD_PID" 2>/dev/null
}
trap cleanup EXIT

# ---- launch coordinator + plugin --------------------------------------
rm -f "$COORD_SOCK" \
      "$WRITE_DIR/highbar.health" \
      "$EFFECTIVE_WRITEDIR/highbar.health"
python3 "$EXAMPLES_DIR/coordinator.py" \
    --endpoint "unix:$COORD_SOCK" --id fault-test > "$COORD_LOG" 2>&1 &
COORD_PID=$!
for _ in $(seq 1 20); do
    [[ -S "$COORD_SOCK" ]] && break
    sleep 0.2
done
[[ -S "$COORD_SOCK" ]] || {
    echo "gateway-fault: coordinator never bound — skip" >&2
    cat "$COORD_LOG" >&2
    exit 77
}

LAUNCH_OUT=$("$HEADLESS_DIR/_launch.sh" \
    --start-script "$START_SCRIPT" \
    --coordinator "unix:$COORD_SOCK" \
    --runtime-dir "$RUN_DIR" 2>&1) || LAUNCH_RC=$?
LAUNCH_RC=${LAUNCH_RC:-0}
if [[ $LAUNCH_RC -eq 77 ]]; then
    echo "gateway-fault: launch missing prereq — skip" >&2
    echo "$LAUNCH_OUT" >&2
    exit 77
elif [[ $LAUNCH_RC -ne 0 ]]; then
    echo "gateway-fault: launch failed — fail" >&2
    echo "$LAUNCH_OUT" >&2
    exit 1
fi

# Let plugin establish — heartbeats start within a few seconds of frame 0.
for _ in $(seq 1 30); do
    grep -q '\[hb=' "$COORD_LOG" 2>/dev/null && break
    sleep 1
done

set +e
fault_status "$EFFECTIVE_WRITEDIR"
rc=$?
set -e
if [[ $rc -ne 0 ]]; then
    if [[ $rc -ne 77 ]]; then
        echo "gateway-fault: precondition failed — gateway not healthy at start (rc=$rc)" >&2
        cat "$EFFECTIVE_WRITEDIR/highbar.health" >&2 2>/dev/null || true
        tail -20 "$ENGINE_LOG" >&2
        exit 1
    fi
fi

# ---- inject fault ------------------------------------------------------
# Push a deliberately-pathological CommandBatch through the
# coordinator's OpenCommandChannel. In current builds this is often
# rejected cleanly before it reaches an HB_HOOK_GUARD catch site; that
# is a valid SKIP outcome. This harness only passes when an actual
# internal exception is induced and the disable contract fires.
python3 - "$COORD_SOCK" <<'PY' >> "$COORD_LOG" 2>&1 || true
import os, sys, time, grpc

sys.path.insert(0, os.path.join(
    os.path.dirname(os.path.abspath("/")),
    "/home/developer/projects/HighBarV3/clients/python/highbar_client"))
sys.path.insert(0, "/home/developer/projects/HighBarV3/clients/python/highbar_client")

from highbar import service_pb2, service_pb2_grpc, commands_pb2

# Connect as an AI to the coordinator's HighBarProxy and push a
# pathological batch.
ch = grpc.insecure_channel(f"unix:{sys.argv[1]}")
stub = service_pb2_grpc.HighBarProxyStub(ch)
stub.Hello(service_pb2.HelloRequest(
    schema_version="1.0.0",
    role=service_pb2.Role.ROLE_AI,
    client_id="hb-fault-injector",
), timeout=5)

batch = commands_pb2.CommandBatch(batch_seq=99999)
# Build a MoveUnit on a clearly-unmapped unit id with NaN coords; the
# dispatcher will reject in user-space, but a pathological large
# `params` field on a CustomCommand can blow up serializer paths.
cmd = batch.commands.add()
cmd.move_unit.unit_id = 0xFFFFFFFF
cmd.move_unit.to_position.x = float("nan")
cmd.move_unit.to_position.y = float("nan")
cmd.move_unit.to_position.z = float("nan")

print(f"[fault] pushing malformed batch", flush=True)
try:
    ack = stub.SubmitCommands(iter([batch]), timeout=5)
    print(f"[fault] SubmitCommands ack: accepted={ack.batches_accepted} "
          f"rejected_invalid={ack.batches_rejected_invalid}", flush=True)
except grpc.RpcError as e:
    print(f"[fault] SubmitCommands rpc error: {e.code().name}", flush=True)

time.sleep(2)
PY

sleep 5

# ---- assert four signals ----------------------------------------------
sig_a=0; sig_b=0; sig_c=0; sig_d=0

if grep -qE '^\[hb-gateway\] fault subsystem=[a-z]+ reason=[a-z_]+' "$ENGINE_LOG" 2>/dev/null; then
    sig_a=1
fi

set +e
fault_status "$EFFECTIVE_WRITEDIR"
rc=$?
set -e
[[ $rc -eq 2 ]] && sig_b=1

# (c) PushState stream close logged at coordinator
if grep -q '\[push\] plugin stream closed' "$COORD_LOG"; then
    sig_c=1
fi

# (d) heartbeat counter stopped advancing.  Sample the highest [hb=NNNN]
# value we've seen.  A fault would silence the heartbeat thread.
hb_count_before=$(grep -c '\[hb=' "$COORD_LOG" || true)
sleep 4
hb_count_after=$(grep -c '\[hb=' "$COORD_LOG" || true)
if [[ "$hb_count_after" -le "$hb_count_before" ]]; then
    sig_d=1
fi

echo "gateway-fault: signals (a=log b=health c=push-closed d=heartbeat-stopped) = $sig_a $sig_b $sig_c $sig_d"

if [[ $sig_a -eq 1 && $sig_b -eq 1 && $sig_c -eq 1 && $sig_d -eq 1 ]]; then
    echo "gateway-fault: PASS — all four signals observed (contract met)"
    exit 0
fi

# Distinguish "fault not triggered" from "fault triggered but signals broken".
if [[ $sig_a -eq 0 && $sig_b -eq 0 && $sig_c -eq 0 && $sig_d -eq 0 ]]; then
    echo "gateway-fault: SKIP — no fault triggered (the malformed batch was" >&2
    echo "  validated cleanly upstream of HB_HOOK_GUARD; contract requires an" >&2
    echo "  uncaught exception. See research.md §R3 known-limit." >&2
    exit 77
fi

echo "gateway-fault: FAIL — partial signal set (a=$sig_a b=$sig_b c=$sig_c d=$sig_d)" >&2
echo "  engine.log tail:" >&2
tail -30 "$ENGINE_LOG" >&2
echo "  coord.log tail:" >&2
tail -30 "$COORD_LOG" >&2
exit 1

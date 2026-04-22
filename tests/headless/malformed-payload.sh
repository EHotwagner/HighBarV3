#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-2.0-only
#
# T067 — malformed payload resilience test.
# arm-covered: move_unit
#
# Sends a structurally invalid MoveUnit batch (non-finite coordinates)
# through HighBarProxy.SubmitCommands and asserts:
#   1. the proxy returns INVALID_ARGUMENT
#   2. the batch is not forwarded to the plugin command channel
#   3. the gateway does not disable itself
#   4. heartbeats continue after the rejection
#
# Exit codes:
#   0  — malformed payload rejected cleanly, gateway remains healthy
#   1  — malformed payload was accepted, faulted the gateway, or health
#        signals regressed
#   77 — prerequisite missing

set -uo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
HEADLESS_DIR="$REPO_ROOT/tests/headless"
EXAMPLES_DIR="$REPO_ROOT/specs/002-live-headless-e2e/examples"

# shellcheck source=tests/headless/_fault-assert.sh
source "$HEADLESS_DIR/_fault-assert.sh"

if [[ ! -x "$HEADLESS_DIR/_launch.sh" ]]; then
    echo "malformed-payload: _launch.sh missing — skip" >&2
    exit 77
fi
if [[ ! -f "$EXAMPLES_DIR/coordinator.py" ]]; then
    echo "malformed-payload: coordinator.py missing — skip" >&2
    exit 77
fi
if ! command -v python3 >/dev/null 2>&1; then
    echo "malformed-payload: python3 missing — skip" >&2
    exit 77
fi
if ! python3 -c "import grpc" 2>/dev/null; then
    echo "malformed-payload: grpcio missing — skip" >&2
    exit 77
fi

PYPROTO_DIR="${HIGHBAR_PYPROTO:-/tmp/hb-run/pyproto}"
if [[ ! -d "$PYPROTO_DIR/highbar" ]]; then
    mkdir -p "$PYPROTO_DIR/highbar"
    if ! python3 -m grpc_tools.protoc -I "$REPO_ROOT/proto" \
            --python_out="$PYPROTO_DIR" \
            --grpc_python_out="$PYPROTO_DIR" \
            "$REPO_ROOT/proto/highbar/"*.proto 2>/dev/null; then
        echo "malformed-payload: proto codegen failed — skip" >&2
        exit 77
    fi
    touch "$PYPROTO_DIR/highbar/__init__.py"
fi

RUN_DIR="${HIGHBAR_RUN_DIR:-/tmp/hb-run}"
mkdir -p "$RUN_DIR"
COORD_SOCK="$RUN_DIR/hb-coord.sock"
COORD_LOG="$RUN_DIR/coord.log"
ENGINE_LOG="$RUN_DIR/highbar-launch.log"
ENGINE_PID_FILE="$RUN_DIR/highbar-launch.pid"
START_SCRIPT="$HEADLESS_DIR/scripts/minimal.startscript"
WRITE_DIR="${HIGHBAR_WRITE_DIR:-$HOME/.local/state/Beyond All Reason}"
EFFECTIVE_WRITEDIR="$WRITE_DIR/engine/recoil_2025.06.19"
CLIENT_LOG="$RUN_DIR/malformed-payload.log"

cleanup() {
    [[ -f "$ENGINE_PID_FILE" ]] && kill -TERM "$(cat "$ENGINE_PID_FILE")" 2>/dev/null
    [[ -n "${COORD_PID:-}" ]] && kill -TERM "$COORD_PID" 2>/dev/null
}
trap cleanup EXIT

rm -f "$COORD_SOCK"
python3 "$EXAMPLES_DIR/coordinator.py" \
    --endpoint "unix:$COORD_SOCK" --id malformed-payload \
    > "$COORD_LOG" 2>&1 &
COORD_PID=$!
for _ in $(seq 1 20); do
    [[ -S "$COORD_SOCK" ]] && break
    sleep 0.2
done
if [[ ! -S "$COORD_SOCK" ]]; then
    echo "malformed-payload: coordinator did not bind — skip" >&2
    cat "$COORD_LOG" >&2
    exit 77
fi

LAUNCH_OUT=$("$HEADLESS_DIR/_launch.sh" \
    --start-script "$START_SCRIPT" \
    --coordinator "unix:$COORD_SOCK" \
    --runtime-dir "$RUN_DIR" 2>&1)
LAUNCH_RC=$?
if [[ $LAUNCH_RC -eq 77 ]]; then
    echo "malformed-payload: _launch.sh prereq missing — skip" >&2
    echo "$LAUNCH_OUT" >&2
    exit 77
elif [[ $LAUNCH_RC -ne 0 ]]; then
    echo "malformed-payload: _launch.sh failed — fail" >&2
    echo "$LAUNCH_OUT" >&2
    exit 1
fi

for _ in $(seq 1 30); do
    if grep -q '\[hb-gateway\] startup' "$ENGINE_LOG" 2>/dev/null; then break; fi
    sleep 1
done
if ! grep -q '\[hb-gateway\] startup' "$ENGINE_LOG"; then
    echo "malformed-payload: gateway startup banner not seen — fail" >&2
    tail -50 "$ENGINE_LOG" >&2
    exit 1
fi

for _ in $(seq 1 30); do
    if grep -q '\[hb=' "$COORD_LOG" 2>/dev/null; then break; fi
    sleep 1
done
hb_before=$(grep -c '\[hb=' "$COORD_LOG" || true)

PYTHONPATH="$PYPROTO_DIR" timeout 30 python3 - "$COORD_SOCK" > "$CLIENT_LOG" 2>&1 <<'PYEOF'
import sys
import threading
import time

import grpc
from highbar import service_pb2, service_pb2_grpc, commands_pb2

endpoint = "unix:" + sys.argv[1]
ch = grpc.insecure_channel(endpoint)
stub = service_pb2_grpc.HighBarProxyStub(ch)

hello = stub.Hello(service_pb2.HelloRequest(
    schema_version="1.0.0",
    role=service_pb2.Role.ROLE_AI,
), timeout=5)
print(f"[mp] Hello OK session={hello.session_id}", flush=True)

shared = {"updates": 0, "err": None}

def watch():
    try:
        for update in stub.StreamState(
                service_pb2.StreamStateRequest(resume_from_seq=0),
                timeout=20):
            shared["updates"] += 1
            if shared["updates"] >= 5:
                return
    except grpc.RpcError as e:
        shared["err"] = e.code().name

t = threading.Thread(target=watch, daemon=True)
t.start()

deadline = time.time() + 10
while time.time() < deadline and shared["updates"] == 0:
    time.sleep(0.2)

batch = commands_pb2.CommandBatch(batch_seq=1, target_unit_id=1)
cmd = batch.commands.add()
cmd.move_unit.unit_id = 1
cmd.move_unit.to_position.x = float("nan")
cmd.move_unit.to_position.y = 0.0
cmd.move_unit.to_position.z = 0.0

try:
    ack = stub.SubmitCommands(iter([batch]), timeout=5)
    print(f"[mp] ERROR unexpected ack accepted={ack.batches_accepted} "
          f"rejected_invalid={ack.batches_rejected_invalid}", flush=True)
    raise SystemExit(1)
except grpc.RpcError as e:
    print(f"[mp] SubmitCommands rpc error: {e.code().name} "
          f"details={e.details()}", flush=True)
    if e.code() != grpc.StatusCode.INVALID_ARGUMENT:
        raise SystemExit(1)

time.sleep(2)
print(f"[mp] updates={shared['updates']} err={shared['err']}", flush=True)
if shared["updates"] == 0:
    raise SystemExit(1)
if shared["err"] is not None:
    raise SystemExit(1)
PYEOF
CLIENT_RC=$?
if [[ $CLIENT_RC -ne 0 ]]; then
    echo "malformed-payload: client check failed — fail" >&2
    cat "$CLIENT_LOG" >&2
    exit 1
fi

hb_after=$(grep -c '\[hb=' "$COORD_LOG" || true)
if [[ "$hb_after" -le "$hb_before" ]]; then
    echo "malformed-payload: heartbeats did not advance after rejection — fail" >&2
    tail -50 "$COORD_LOG" >&2
    exit 1
fi

if grep -q '\[cmd-ch\] forwarding batch seq=1' "$COORD_LOG"; then
    echo "malformed-payload: invalid batch was forwarded to plugin — fail" >&2
    tail -50 "$COORD_LOG" >&2
    exit 1
fi

if grep -qE '^\[hb-gateway\] fault subsystem=' "$ENGINE_LOG" 2>/dev/null; then
    echo "malformed-payload: malformed payload faulted the gateway — fail" >&2
    tail -50 "$ENGINE_LOG" >&2
    exit 1
fi

set +e
fault_status "$EFFECTIVE_WRITEDIR"
fs=$?
set -e
if [[ $fs -eq 2 ]]; then
    echo "malformed-payload: gateway disabled after malformed payload — fail" >&2
    exit 1
fi

if ! grep -q '^\[mp\] SubmitCommands rpc error: INVALID_ARGUMENT' "$CLIENT_LOG"; then
    echo "malformed-payload: INVALID_ARGUMENT was not observed — fail" >&2
    cat "$CLIENT_LOG" >&2
    exit 1
fi

echo "malformed-payload: PASS invalid=INVALID_ARGUMENT hb_before=$hb_before hb_after=$hb_after"

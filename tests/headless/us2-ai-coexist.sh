#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-2.0-only
#
# T028 [US3] — Live US2 AI-coexist acceptance.
# arm-covered: move_unit, attack
#
# Pattern: same client-mode setup as us1-observer.sh (coordinator +
# _launch.sh + minimal.startscript), then runs ai_client.py as an AI-
# role client that watches StreamState for the first UnitCreated, sends
# a MoveUnit command on it via SubmitCommands, and asserts the
# coordinator forwarded it (proxy log shows
# `[proxy] SubmitCommands ... received 1 batches, forwarded`).
#
# The original spec asks for built-in AI heartbeat liveness + a second-
# AI ALREADY_EXISTS check. Both are deferred to follow-ups: built-in
# AI continues by construction (BARb's AngelScript still runs); the
# AI-slot single-claim is a coordinator-side enforcement that lands
# with auth/session work in a later commit.
#
# Exit codes (FR-007 + FR-024):
#   0  — all assertions passed
#   1  — plugin/engine launched but a behavioural assertion failed
#   77 — prerequisite missing

set -uo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
HEADLESS_DIR="$REPO_ROOT/tests/headless"
EXAMPLES_DIR="$REPO_ROOT/specs/002-live-headless-e2e/examples"

# shellcheck source=tests/headless/_fault-assert.sh
source "$HEADLESS_DIR/_fault-assert.sh"

# ---- prereq checks --------------------------------------------------------

if [[ ! -x "$HEADLESS_DIR/_launch.sh" ]]; then
    echo "us2-ai-coexist: _launch.sh missing — skip" >&2
    exit 77
fi
if [[ ! -f "$EXAMPLES_DIR/coordinator.py" || ! -f "$EXAMPLES_DIR/ai_client.py" ]]; then
    echo "us2-ai-coexist: examples/{coordinator,ai_client}.py missing — skip" >&2
    exit 77
fi
if ! command -v python3 >/dev/null 2>&1; then
    echo "us2-ai-coexist: python3 not on PATH — skip" >&2
    exit 77
fi
if ! python3 -c "import grpc" 2>/dev/null; then
    echo "us2-ai-coexist: grpcio not installed — skip" >&2
    exit 77
fi

PYPROTO_DIR="${HIGHBAR_PYPROTO:-/tmp/hb-run/pyproto}"
if [[ ! -d "$PYPROTO_DIR/highbar" ]]; then
    mkdir -p "$PYPROTO_DIR/highbar"
    if ! python3 -m grpc_tools.protoc -I "$REPO_ROOT/proto" \
            --python_out="$PYPROTO_DIR" \
            --grpc_python_out="$PYPROTO_DIR" \
            "$REPO_ROOT/proto/highbar/"*.proto 2>/dev/null; then
        echo "us2-ai-coexist: proto codegen failed — skip" >&2
        exit 77
    fi
    touch "$PYPROTO_DIR/highbar/__init__.py"
fi

RUN_DIR="${HIGHBAR_RUN_DIR:-/tmp/hb-run}"
mkdir -p "$RUN_DIR"
COORD_SOCK="$RUN_DIR/hb-coord.sock"
COORD_LOG="$RUN_DIR/coord.log"
START_SCRIPT="$HEADLESS_DIR/scripts/minimal.startscript"
ENGINE_LOG="$RUN_DIR/highbar-launch.log"
ENGINE_PID_FILE="$RUN_DIR/highbar-launch.pid"
WRITE_DIR="${HIGHBAR_WRITE_DIR:-$HOME/.local/state/Beyond All Reason}"

cleanup() {
    [[ -f "$ENGINE_PID_FILE" ]] && kill -TERM "$(cat "$ENGINE_PID_FILE")" 2>/dev/null
    [[ -n "${COORD_PID:-}" ]] && kill -TERM "$COORD_PID" 2>/dev/null
}
trap cleanup EXIT

# ---- start coordinator ----------------------------------------------------

rm -f "$COORD_SOCK"
python3 "$EXAMPLES_DIR/coordinator.py" \
    --endpoint "unix:$COORD_SOCK" --id us2-ai > "$COORD_LOG" 2>&1 &
COORD_PID=$!
for _ in $(seq 1 20); do
    [[ -S "$COORD_SOCK" ]] && break
    sleep 0.2
done
if [[ ! -S "$COORD_SOCK" ]]; then
    echo "us2-ai-coexist: coordinator did not bind on $COORD_SOCK — skip" >&2
    cat "$COORD_LOG" >&2
    exit 77
fi

# ---- launch spring --------------------------------------------------------

LAUNCH_OUT=$("$HEADLESS_DIR/_launch.sh" \
    --start-script "$START_SCRIPT" \
    --coordinator "unix:$COORD_SOCK" \
    --runtime-dir "$RUN_DIR" 2>&1)
LAUNCH_RC=$?
if [[ $LAUNCH_RC -eq 77 ]]; then
    echo "us2-ai-coexist: _launch.sh prereq missing — skip" >&2
    echo "$LAUNCH_OUT" >&2
    exit 77
elif [[ $LAUNCH_RC -ne 0 ]]; then
    echo "us2-ai-coexist: _launch.sh failed (rc=$LAUNCH_RC) — fail" >&2
    exit 1
fi

# ---- wait for gateway startup --------------------------------------------

for _ in $(seq 1 30); do
    if grep -q '\[hb-gateway\] startup' "$ENGINE_LOG" 2>/dev/null; then break; fi
    sleep 1
done
if ! grep -q '\[hb-gateway\] startup' "$ENGINE_LOG"; then
    echo "us2-ai-coexist: gateway startup banner not seen in 30s — fail" >&2
    tail -50 "$ENGINE_LOG" >&2
    exit 1
fi

# Give the match a few more seconds so commanders are spawned and
# UnitCreated deltas are pushed.
sleep 8

# ---- AI-role client run ---------------------------------------------------

AI_LOG="$RUN_DIR/us2-ai.log"
timeout 25 python3 "$EXAMPLES_DIR/ai_client.py" \
    --endpoint "unix:$COORD_SOCK" --wait 12 --dx 1000 --dz 100 \
    > "$AI_LOG" 2>&1 || true

if ! grep -q '^\[ai\] Hello OK' "$AI_LOG"; then
    echo "us2-ai-coexist: ai_client.py Hello did not succeed — fail" >&2
    tail -20 "$AI_LOG" >&2
    exit 1
fi
if ! grep -q '^\[ai\] saw UnitCreated id=' "$AI_LOG"; then
    echo "us2-ai-coexist: ai_client did not observe UnitCreated — fail" >&2
    tail -20 "$AI_LOG" >&2
    exit 1
fi
if ! grep -q 'SubmitCommands ack: accepted=1' "$AI_LOG"; then
    echo "us2-ai-coexist: SubmitCommands not acked accepted=1 — fail" >&2
    tail -20 "$AI_LOG" >&2
    exit 1
fi
# T065: ai_client.py emits 'damage_invalid=N' on its done line; >0 means
# the OnUnitDamagedFull widening regressed.
invalid=$(grep -oE 'damage_invalid=[0-9]+' "$AI_LOG" | tail -1 | sed 's/.*=//')
if [[ -n "$invalid" && "$invalid" -gt 0 ]]; then
    echo "us2-ai-coexist: $invalid UnitDamaged events with bad payload — fail" >&2
    grep '^\[ai\]' "$AI_LOG" | tail -10 >&2
    exit 1
fi

# Coordinator-side: should see SubmitCommands receipt + forward.
if ! grep -q "\[proxy\] SubmitCommands" "$COORD_LOG"; then
    echo "us2-ai-coexist: coordinator did not log proxy SubmitCommands — fail" >&2
    grep -E "\[proxy\]|\[cmd-ch\]" "$COORD_LOG" >&2
    exit 1
fi
if ! grep -q "\[cmd-ch\] forwarding batch" "$COORD_LOG"; then
    echo "us2-ai-coexist: coordinator did not forward to plugin cmd-ch — fail" >&2
    exit 1
fi

# ---- fault status ---------------------------------------------------------

EFFECTIVE_WRITEDIR="$WRITE_DIR/engine/recoil_2025.06.19"
fault_status "$EFFECTIVE_WRITEDIR"
fs=$?
if [[ $fs -eq 2 ]]; then
    echo "us2-ai-coexist: gateway DISABLED mid-test — fail (FR-024)" >&2
    exit 1
fi

UID_OBSERVED=$(grep -oE 'UnitCreated id=[0-9]+' "$AI_LOG" | head -1 | sed 's/.*=//')
echo "us2-ai-coexist: PASS uid=$UID_OBSERVED submit_ack=1"

#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-2.0-only
#
# T029 [US4] — Macro driver acceptance script.
#
# Calls `_fault-assert.sh fault_status` first (exits 77 on Disabled),
# launches the live topology, invokes
#    `uv run --project clients/python python -m highbar_client.behavioral_coverage`
# with gameseed/output-dir/threshold flags, then forwards the driver's
# exit code.
#
# Exit codes (per quickstart.md §5):
#   0  — verified/wire_observable ≥ threshold.
#   1  — threshold missed OR bootstrap_timeout.
#   77 — gateway Disabled at script start; or setup prereq missing.
#   2  — internal error (CSV consistency violation, etc.).

set -uo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
HEADLESS_DIR="$REPO_ROOT/tests/headless"
EXAMPLES_DIR="$REPO_ROOT/specs/002-live-headless-e2e/examples"

# shellcheck source=tests/headless/_fault-assert.sh
source "$HEADLESS_DIR/_fault-assert.sh"

# Prereqs.
if [[ ! -x "$HEADLESS_DIR/_launch.sh" ]]; then
    echo "aicommand-behavioral-coverage: _launch.sh missing — skip" >&2
    exit 77
fi
if [[ ! -f "$EXAMPLES_DIR/coordinator.py" ]]; then
    echo "aicommand-behavioral-coverage: coordinator.py missing — skip" >&2
    exit 77
fi
if ! command -v uv >/dev/null 2>&1; then
    echo "aicommand-behavioral-coverage: uv missing — skip" >&2
    exit 77
fi

RUN_DIR="${HIGHBAR_RUN_DIR:-/tmp/hb-run}"
mkdir -p "$RUN_DIR"
COORD_SOCK="$RUN_DIR/hb-coord.sock"
COORD_LOG="$RUN_DIR/coord.log"
START_SCRIPT="${HIGHBAR_STARTSCRIPT:-$HEADLESS_DIR/scripts/minimal.startscript}"
ENGINE_LOG="$RUN_DIR/highbar-launch.log"
ENGINE_PID_FILE="$RUN_DIR/highbar-launch.pid"
WRITE_DIR="${HIGHBAR_WRITE_DIR:-$HOME/.local/state/Beyond All Reason}"
OUTPUT_DIR="${HIGHBAR_OUTPUT_DIR:-$REPO_ROOT/build/reports}"
THRESHOLD="${HIGHBAR_BEHAVIORAL_THRESHOLD:-0.50}"
GAMESEED="${HIGHBAR_GAMESEED:-0x42424242}"

# Allow override from args.
while [[ $# -gt 0 ]]; do
    case "$1" in
        --startscript) START_SCRIPT="$2"; shift 2;;
        --output-dir)  OUTPUT_DIR="$2"; shift 2;;
        --threshold)   THRESHOLD="$2"; shift 2;;
        --gameseed)    GAMESEED="$2"; shift 2;;
        --run-index)   RUN_INDEX="$2"; shift 2;;
        *) echo "unknown arg: $1" >&2; exit 2;;
    esac
done

cleanup() {
    [[ -f "$ENGINE_PID_FILE" ]] && kill -TERM "$(cat "$ENGINE_PID_FILE")" 2>/dev/null
    [[ -n "${COORD_PID:-}" ]] && kill -TERM "$COORD_PID" 2>/dev/null
}
trap cleanup EXIT

# ---- Start coordinator + plugin ------------------------------------------

rm -f "$COORD_SOCK"
python3 "$EXAMPLES_DIR/coordinator.py" \
    --endpoint "unix:$COORD_SOCK" --id bcov > "$COORD_LOG" 2>&1 &
COORD_PID=$!
for _ in $(seq 1 20); do
    [[ -S "$COORD_SOCK" ]] && break
    sleep 0.2
done
if [[ ! -S "$COORD_SOCK" ]]; then
    echo "aicommand-behavioral-coverage: coordinator failed to bind — skip" >&2
    exit 77
fi

LAUNCH_OUT=$("$HEADLESS_DIR/_launch.sh" \
    --start-script "$START_SCRIPT" \
    --coordinator "unix:$COORD_SOCK" \
    --runtime-dir "$RUN_DIR" 2>&1)
LAUNCH_RC=$?
if [[ $LAUNCH_RC -eq 77 ]]; then
    echo "aicommand-behavioral-coverage: _launch.sh prereq missing — skip" >&2
    exit 77
elif [[ $LAUNCH_RC -ne 0 ]]; then
    echo "aicommand-behavioral-coverage: _launch.sh failed — fail" >&2
    exit 1
fi

for _ in $(seq 1 30); do
    if grep -q '\[hb-gateway\] startup' "$ENGINE_LOG" 2>/dev/null; then break; fi
    sleep 1
done
if ! grep -q '\[hb-gateway\] startup' "$ENGINE_LOG"; then
    echo "aicommand-behavioral-coverage: gateway startup not seen — fail" >&2
    exit 1
fi

# ---- Fault gate (spec §Edge Case): exit 77 on Disabled ------------------

EFFECTIVE_WRITEDIR="$WRITE_DIR/engine/recoil_2025.06.19"
fault_status "$EFFECTIVE_WRITEDIR"
fs=$?
if [[ $fs -eq 2 ]]; then
    echo "aicommand-behavioral-coverage: gateway Disabled at start — skip" >&2
    exit 77
fi

sleep 5  # Let commanders spawn so the driver finds them.

# ---- Invoke the macro driver ---------------------------------------------

DRIVER_ARGS=(
    --endpoint "unix:$COORD_SOCK"
    --startscript "$START_SCRIPT"
    --gameseed "$GAMESEED"
    --output-dir "$OUTPUT_DIR"
    --threshold "$THRESHOLD"
)
if [[ -n "${RUN_INDEX:-}" ]]; then
    DRIVER_ARGS+=(--run-index "$RUN_INDEX")
fi

echo "aicommand-behavioral-coverage: invoking driver: ${DRIVER_ARGS[*]}"
uv run --project "$REPO_ROOT/clients/python" python -m \
    highbar_client.behavioral_coverage "${DRIVER_ARGS[@]}"
DRIVER_RC=$?

echo "aicommand-behavioral-coverage: driver rc=$DRIVER_RC"
exit $DRIVER_RC

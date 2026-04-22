#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-2.0-only

set -uo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
HEADLESS_DIR="$REPO_ROOT/tests/headless"
EXAMPLES_DIR="$REPO_ROOT/specs/002-live-headless-e2e/examples"

# shellcheck source=tests/headless/_fault-assert.sh
source "$HEADLESS_DIR/_fault-assert.sh"

if [[ ! -x "$HEADLESS_DIR/_launch.sh" ]]; then
    echo "itertesting: _launch.sh missing — skip" >&2
    exit 77
fi
if [[ ! -f "$EXAMPLES_DIR/coordinator.py" ]]; then
    echo "itertesting: coordinator.py missing — skip" >&2
    exit 77
fi
if ! command -v uv >/dev/null 2>&1; then
    echo "itertesting: uv missing — skip" >&2
    exit 77
fi

RUN_DIR="${HIGHBAR_RUN_DIR:-/tmp/hb-run-itertesting}"
mkdir -p "$RUN_DIR"
COORD_SOCK="$RUN_DIR/hb-coord.sock"
COORD_LOG="$RUN_DIR/coord.log"
START_SCRIPT="${HIGHBAR_STARTSCRIPT:-$HEADLESS_DIR/scripts/minimal.startscript}"
CHEAT_STARTSCRIPT="${HIGHBAR_ITERTESTING_CHEAT_STARTSCRIPT:-$HEADLESS_DIR/scripts/cheats.startscript}"
ENGINE_LOG="$RUN_DIR/highbar-launch.log"
ENGINE_PID_FILE="$RUN_DIR/highbar-launch.pid"
WRITE_DIR="${HIGHBAR_WRITE_DIR:-$HOME/.local/state/Beyond All Reason}"
REPORTS_DIR="${HIGHBAR_ITERTESTING_REPORTS_DIR:-$REPO_ROOT/reports/itertesting}"
MAX_RUNS="${HIGHBAR_ITERTESTING_MAX_IMPROVEMENT_RUNS:-0}"
THRESHOLD="${HIGHBAR_BEHAVIORAL_THRESHOLD:-0.50}"
GAMESEED="${HIGHBAR_GAMESEED:-0x42424242}"

cleanup() {
    [[ -f "$ENGINE_PID_FILE" ]] && kill -TERM "$(cat "$ENGINE_PID_FILE")" 2>/dev/null
    [[ -n "${COORD_PID:-}" ]] && kill -TERM "$COORD_PID" 2>/dev/null
}
trap cleanup EXIT

rm -f "$COORD_SOCK"
python3 "$EXAMPLES_DIR/coordinator.py" \
    --endpoint "unix:$COORD_SOCK" --id bcov > "$COORD_LOG" 2>&1 &
COORD_PID=$!
for _ in $(seq 1 20); do
    [[ -S "$COORD_SOCK" ]] && break
    sleep 0.2
done
if [[ ! -S "$COORD_SOCK" ]]; then
    echo "itertesting: coordinator failed to bind — skip" >&2
    exit 77
fi

LAUNCH_OUT=$("$HEADLESS_DIR/_launch.sh" \
    --start-script "$START_SCRIPT" \
    --coordinator "unix:$COORD_SOCK" \
    --runtime-dir "$RUN_DIR" 2>&1)
LAUNCH_RC=$?
if [[ $LAUNCH_RC -eq 77 ]]; then
    echo "itertesting: _launch.sh prereq missing — skip" >&2
    exit 77
elif [[ $LAUNCH_RC -ne 0 ]]; then
    echo "itertesting: _launch.sh failed — fail" >&2
    exit 1
fi

for _ in $(seq 1 30); do
    if grep -q '\[hb-gateway\] startup' "$ENGINE_LOG" 2>/dev/null; then break; fi
    sleep 1
done
if ! grep -q '\[hb-gateway\] startup' "$ENGINE_LOG"; then
    echo "itertesting: gateway startup not seen — fail" >&2
    exit 1
fi

EFFECTIVE_WRITEDIR="$WRITE_DIR/engine/recoil_2025.06.19"
fault_status "$EFFECTIVE_WRITEDIR"
fs=$?
if [[ $fs -eq 2 ]]; then
    echo "itertesting: gateway Disabled at start — skip" >&2
    exit 77
fi

sleep 5

ARGS=(
    itertesting
    --endpoint "unix:$COORD_SOCK"
    --startscript "$START_SCRIPT"
    --reports-dir "$REPORTS_DIR"
    --max-improvement-runs "$MAX_RUNS"
    --threshold "$THRESHOLD"
    --gameseed "$GAMESEED"
    --cheat-startscript "$CHEAT_STARTSCRIPT"
)

if [[ "${HIGHBAR_ITERTESTING_ALLOW_CHEAT_ESCALATION:-false}" == "true" ]]; then
    ARGS+=(--allow-cheat-escalation)
fi

echo "itertesting: invoking live campaign: ${ARGS[*]}"
uv run --project "$REPO_ROOT/clients/python" python -m highbar_client.behavioral_coverage "${ARGS[@]}" "$@"

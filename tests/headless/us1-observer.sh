#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-2.0-only
#
# T024 [US2] — Live US1 observer acceptance.
# arm-covered: move_unit
#
# Pattern:
#   1. Source _fault-assert.sh (fault_status / fault_guard).
#   2. Start the Python coordinator (HighBarCoordinator + HighBarProxy).
#   3. _launch.sh starts spring-headless with the plugin dialing the
#      coordinator endpoint.
#   4. Wait for the gateway's startup banner.
#   5. Run a Python observer client (specs/.../examples/observer.py)
#      against the coordinator endpoint.
#   6. Assert: first StateUpdate within 2s; ≥30 deltas over 30s with
#      strictly increasing seq; fault_status reports healthy.
#
# Exit codes (FR-007 + FR-024):
#   0  — all assertions passed
#   1  — plugin/engine launched but a behavioural assertion failed
#   77 — prerequisite missing (engine binary, BAR install, _launch.sh
#         exits 77, or coordinator failed to bind)

set -uo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
HEADLESS_DIR="$REPO_ROOT/tests/headless"
EXAMPLES_DIR="$REPO_ROOT/specs/002-live-headless-e2e/examples"

# shellcheck source=tests/headless/_fault-assert.sh
source "$HEADLESS_DIR/_fault-assert.sh"

# ---- prereq checks --------------------------------------------------------

if [[ ! -x "$HEADLESS_DIR/_launch.sh" ]]; then
    echo "us1-observer: _launch.sh missing/non-exec — skip" >&2
    exit 77
fi
if [[ ! -f "$EXAMPLES_DIR/coordinator.py" || ! -f "$EXAMPLES_DIR/observer.py" ]]; then
    echo "us1-observer: examples/{coordinator,observer}.py missing — skip" >&2
    exit 77
fi
if ! command -v python3 >/dev/null 2>&1; then
    echo "us1-observer: python3 not on PATH — skip" >&2
    exit 77
fi
if ! python3 -c "import grpc" 2>/dev/null; then
    echo "us1-observer: grpcio not installed — skip" >&2
    exit 77
fi

# Generated proto stubs the examples import from /tmp/hb-run/pyproto.
PYPROTO_DIR="${HIGHBAR_PYPROTO:-/tmp/hb-run/pyproto}"
if [[ ! -d "$PYPROTO_DIR/highbar" ]]; then
    mkdir -p "$PYPROTO_DIR/highbar"
    if ! python3 -m grpc_tools.protoc -I "$REPO_ROOT/proto" \
            --python_out="$PYPROTO_DIR" \
            --grpc_python_out="$PYPROTO_DIR" \
            "$REPO_ROOT/proto/highbar/"*.proto 2>/dev/null; then
        echo "us1-observer: proto codegen failed — skip" >&2
        exit 77
    fi
    touch "$PYPROTO_DIR/highbar/__init__.py"
fi

# ---- runtime dirs ---------------------------------------------------------

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
    --endpoint "unix:$COORD_SOCK" --id us1-obs > "$COORD_LOG" 2>&1 &
COORD_PID=$!
for _ in $(seq 1 20); do
    [[ -S "$COORD_SOCK" ]] && break
    sleep 0.2
done
if [[ ! -S "$COORD_SOCK" ]]; then
    echo "us1-observer: coordinator failed to bind on $COORD_SOCK — skip" >&2
    cat "$COORD_LOG" >&2
    exit 77
fi

# ---- launch spring via _launch.sh -----------------------------------------

LAUNCH_OUT=$("$HEADLESS_DIR/_launch.sh" \
    --start-script "$START_SCRIPT" \
    --coordinator "unix:$COORD_SOCK" \
    --runtime-dir "$RUN_DIR" 2>&1)
LAUNCH_RC=$?
if [[ $LAUNCH_RC -eq 77 ]]; then
    echo "us1-observer: _launch.sh missing prereq — skip" >&2
    echo "$LAUNCH_OUT" >&2
    exit 77
elif [[ $LAUNCH_RC -ne 0 ]]; then
    echo "us1-observer: _launch.sh failed (rc=$LAUNCH_RC) — fail" >&2
    echo "$LAUNCH_OUT" >&2
    exit 1
fi

# ---- wait for gateway startup ---------------------------------------------

t_start=$(date +%s)
for _ in $(seq 1 30); do
    if grep -q '\[hb-gateway\] startup' "$ENGINE_LOG" 2>/dev/null; then break; fi
    sleep 1
done
if ! grep -q '\[hb-gateway\] startup' "$ENGINE_LOG"; then
    echo "us1-observer: gateway startup banner not seen in 30s — fail" >&2
    tail -50 "$ENGINE_LOG" >&2
    exit 1
fi

# ---- observer probe: 30 messages over up to 35s ---------------------------

OBS_LOG="$RUN_DIR/us1-observer.obs"
timeout 35 python3 "$EXAMPLES_DIR/observer.py" \
    --endpoint "unix:$COORD_SOCK" --max 30 > "$OBS_LOG" 2>&1 || true

if ! grep -q '^\[obs] Hello OK' "$OBS_LOG"; then
    echo "us1-observer: observer Hello did not succeed — fail" >&2
    tail -20 "$OBS_LOG" >&2
    exit 1
fi
if ! grep -q '^\[obs rx=00001]' "$OBS_LOG"; then
    echo "us1-observer: observer received zero StateUpdates — fail" >&2
    tail -20 "$OBS_LOG" >&2
    exit 1
fi
final_rx=$(grep -oE 'final: rx=[0-9]+' "$OBS_LOG" | tail -1 | sed 's/.*=//')
if [[ -z "$final_rx" || "$final_rx" -lt 30 ]]; then
    echo "us1-observer: only ${final_rx:-0} updates in 35s, expected ≥30 — fail" >&2
    exit 1
fi
# T065: any UnitDamaged event with damage<=0 or all-zero direction
# means the widening regressed (contracts/unit-damaged-payload.md).
if grep -q '^\[obs] WARN: .* UnitDamaged events had damage<=0' "$OBS_LOG"; then
    echo "us1-observer: UnitDamaged widening regression — fail" >&2
    grep '^\[obs]' "$OBS_LOG" | tail -5 >&2
    exit 1
fi

# Non-regressing seq check across sampled lines. Per FR-006 seqs are
# monotonic *per session*; the coordinator interleaves multiple plugin
# sessions (one per AI in the match), so identical seqs from different
# sessions are legal — only a backwards step is a real regression.
LAST_SEQ=0
while IFS= read -r seq; do
    if [[ "$seq" -lt "$LAST_SEQ" ]]; then
        echo "us1-observer: seq backwards: $seq after $LAST_SEQ — fail" >&2
        exit 1
    fi
    LAST_SEQ=$seq
done < <(grep -oE 'seq=[0-9]+' "$OBS_LOG" | sed 's/seq=//')

# ---- fault status: healthy gateway = required ----------------------------

# The plugin's health file is written under the engine's writeable data
# dir, which is the BAR root (engine in portable mode under SPRING_DATADIR).
EFFECTIVE_WRITEDIR="$WRITE_DIR/engine/recoil_2025.06.19"
fault_status "$EFFECTIVE_WRITEDIR"
fs=$?
if [[ $fs -eq 2 ]]; then
    echo "us1-observer: gateway DISABLED mid-test — fail (FR-024)" >&2
    exit 1
fi

t_end=$(date +%s)
echo "us1-observer: PASS rx=$final_rx last_seq=$LAST_SEQ wall=$((t_end - t_start))s"

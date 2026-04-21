#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-2.0-only
# arm-covered: (none — observer-only; no SubmitCommands issued)
#
# T062 — UDS latency bench. Constitution V gate: p99 ≤ 500µs on
# a round trip from the plugin's PushState send timestamp to the
# external client's receipt via the coordinator.
#
# Architecture (matches the live system after the client-mode flip):
#
#     plugin  --PushState (UDS)-->  coordinator  --StreamState (UDS)-->  bench_latency.py
#
# StateUpdate.send_monotonic_ns is stamped in
# CoordinatorClient::PushStateUpdate; the coordinator forwards
# StateUpdates unchanged; bench_latency.py computes (recv_ns - send_ns)
# per sample and reports p50/p99/max.
#
# Exits:
#   0  — bench ran and p99 within 500µs.
#   1  — bench ran but p99 exceeded 500µs (Constitution V breach).
#   77 — prerequisites missing (skip).

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
HEADLESS_DIR="$REPO_ROOT/tests/headless"
EXAMPLES_DIR="$REPO_ROOT/specs/002-live-headless-e2e/examples"
BENCH="$REPO_ROOT/tests/bench/bench_latency.py"
REPORTS_DIR="$REPO_ROOT/build/reports"
REPORT_FILE="$REPORTS_DIR/latency-uds-p99.txt"

# ---- prereqs -----------------------------------------------------------
if [[ -z "${SPRING_HEADLESS:-}" ]]; then
    echo "latency-uds: SPRING_HEADLESS not set — skip" >&2
    exit 77
fi
[[ -x "$BENCH" ]] || chmod +x "$BENCH"
[[ -f "$EXAMPLES_DIR/coordinator.py" ]] || {
    echo "latency-uds: coordinator example missing — skip" >&2
    exit 77
}

RUN_DIR="${HIGHBAR_BENCH_RUN_DIR:-$(mktemp -d -t hb-latency-uds.XXXXXX)}"
mkdir -p "$RUN_DIR" "$REPORTS_DIR"
COORD_SOCK="$RUN_DIR/hb-coord.sock"
COORD_LOG="$RUN_DIR/coord.log"
BENCH_LOG="$RUN_DIR/bench.log"
ENGINE_LOG="$RUN_DIR/highbar-launch.log"
ENGINE_PID_FILE="$RUN_DIR/highbar-launch.pid"
START_SCRIPT="$HEADLESS_DIR/scripts/minimal.startscript"

cleanup() {
    [[ -f "$ENGINE_PID_FILE" ]] && kill -TERM "$(cat "$ENGINE_PID_FILE")" 2>/dev/null
    [[ -n "${COORD_PID:-}" ]] && kill -TERM "$COORD_PID" 2>/dev/null
}
trap cleanup EXIT

# ---- coordinator -------------------------------------------------------
rm -f "$COORD_SOCK"
python3 "$EXAMPLES_DIR/coordinator.py" \
    --endpoint "unix:$COORD_SOCK" --id bench-uds > "$COORD_LOG" 2>&1 &
COORD_PID=$!
for _ in $(seq 1 20); do
    [[ -S "$COORD_SOCK" ]] && break
    sleep 0.2
done
[[ -S "$COORD_SOCK" ]] || {
    echo "latency-uds: coordinator failed to bind — skip" >&2
    cat "$COORD_LOG" >&2
    exit 77
}

# ---- spring-headless ---------------------------------------------------
LAUNCH_OUT=$("$HEADLESS_DIR/_launch.sh" \
    --start-script "$START_SCRIPT" \
    --coordinator "unix:$COORD_SOCK" \
    --runtime-dir "$RUN_DIR" 2>&1) || LAUNCH_RC=$?
LAUNCH_RC=${LAUNCH_RC:-0}
if [[ $LAUNCH_RC -eq 77 ]]; then
    echo "latency-uds: _launch.sh missing prereq — skip" >&2
    echo "$LAUNCH_OUT" >&2
    exit 77
elif [[ $LAUNCH_RC -ne 0 ]]; then
    echo "latency-uds: _launch.sh failed (rc=$LAUNCH_RC) — fail" >&2
    echo "$LAUNCH_OUT" >&2
    exit 1
fi

# Let PushState stream open.
for _ in $(seq 1 30); do
    grep -q '\[hb-gateway\] startup' "$ENGINE_LOG" 2>/dev/null && break
    sleep 1
done

# ---- bench -------------------------------------------------------------
set +e
python3 "$BENCH" \
    --transport uds --endpoint "$COORD_SOCK" \
    --duration-sec "${HIGHBAR_BENCH_DURATION:-30}" \
    --samples "${HIGHBAR_BENCH_SAMPLES:-1000}" \
    --budget-us 500 \
    --output "$REPORT_FILE" \
    > "$BENCH_LOG" 2>&1
rc=$?
set -e

cat "$BENCH_LOG"
case $rc in
    0)  echo "latency-uds: PASS"; exit 0 ;;
    1)  echo "latency-uds: FAIL — Constitution V breach"; exit 1 ;;
    77) echo "latency-uds: SKIP — bench could not produce samples"; exit 77 ;;
    *)  echo "latency-uds: unexpected exit $rc"; exit "$rc" ;;
esac

#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-2.0-only
# arm-covered: (none — observer-only; no SubmitCommands issued)
#
# T063 — loopback TCP latency bench. Constitution V gate: p99 ≤ 1500µs
# round-trip from plugin's PushState send timestamp to external-client
# receipt via the coordinator's TCP endpoint.
#
# Same architecture as latency-uds.sh but the coordinator binds loopback
# TCP instead of a UDS path. bench_latency.py speaks insecure gRPC TCP.
#
# Exits:
#   0  — p99 ≤ 1500µs.
#   1  — p99 > 1500µs (Constitution V breach).
#   77 — prerequisites missing.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
HEADLESS_DIR="$REPO_ROOT/tests/headless"
EXAMPLES_DIR="$REPO_ROOT/specs/002-live-headless-e2e/examples"
BENCH="$REPO_ROOT/tests/bench/bench_latency.py"
REPORTS_DIR="$REPO_ROOT/build/reports"
REPORT_FILE="$REPORTS_DIR/latency-tcp-p99.txt"

if [[ -z "${SPRING_HEADLESS:-}" ]]; then
    echo "latency-tcp: SPRING_HEADLESS not set — skip" >&2
    exit 77
fi
[[ -f "$EXAMPLES_DIR/coordinator.py" ]] || {
    echo "latency-tcp: coordinator example missing — skip" >&2
    exit 77
}

RUN_DIR="${HIGHBAR_BENCH_RUN_DIR:-$(mktemp -d -t hb-latency-tcp.XXXXXX)}"
mkdir -p "$RUN_DIR" "$REPORTS_DIR"
TCP_BIND="${HIGHBAR_TCP_BIND:-127.0.0.1:50521}"
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

# ---- coordinator (TCP) -------------------------------------------------
python3 "$EXAMPLES_DIR/coordinator.py" \
    --endpoint "$TCP_BIND" --id bench-tcp > "$COORD_LOG" 2>&1 &
COORD_PID=$!
for _ in $(seq 1 30); do
    if (exec 3<>/dev/tcp/${TCP_BIND%:*}/${TCP_BIND##*:}) 2>/dev/null; then
        exec 3<&-; exec 3>&-; break
    fi
    sleep 0.2
done
if ! (exec 3<>/dev/tcp/${TCP_BIND%:*}/${TCP_BIND##*:}) 2>/dev/null; then
    echo "latency-tcp: coordinator failed to bind $TCP_BIND — skip" >&2
    cat "$COORD_LOG" >&2
    exit 77
fi
exec 3<&-; exec 3>&- || true

# ---- spring-headless ---------------------------------------------------
LAUNCH_OUT=$("$HEADLESS_DIR/_launch.sh" \
    --start-script "$START_SCRIPT" \
    --coordinator "$TCP_BIND" \
    --runtime-dir "$RUN_DIR" 2>&1) || LAUNCH_RC=$?
LAUNCH_RC=${LAUNCH_RC:-0}
if [[ $LAUNCH_RC -eq 77 ]]; then
    echo "latency-tcp: _launch.sh missing prereq — skip" >&2
    echo "$LAUNCH_OUT" >&2
    exit 77
elif [[ $LAUNCH_RC -ne 0 ]]; then
    echo "latency-tcp: _launch.sh failed (rc=$LAUNCH_RC) — fail" >&2
    echo "$LAUNCH_OUT" >&2
    exit 1
fi

for _ in $(seq 1 30); do
    grep -q '\[hb-gateway\] startup' "$ENGINE_LOG" 2>/dev/null && break
    sleep 1
done

# ---- bench -------------------------------------------------------------
set +e
python3 "$BENCH" \
    --transport tcp --endpoint "$TCP_BIND" \
    --duration-sec "${HIGHBAR_BENCH_DURATION:-30}" \
    --samples "${HIGHBAR_BENCH_SAMPLES:-1000}" \
    --budget-us 1500 \
    --output "$REPORT_FILE" \
    > "$BENCH_LOG" 2>&1
rc=$?
set -e

cat "$BENCH_LOG"
case $rc in
    0)  echo "latency-tcp: PASS"; exit 0 ;;
    1)  echo "latency-tcp: FAIL — Constitution V breach"; exit 1 ;;
    77) echo "latency-tcp: SKIP — bench could not produce samples"; exit 77 ;;
    *)  echo "latency-tcp: unexpected exit $rc"; exit "$rc" ;;
esac

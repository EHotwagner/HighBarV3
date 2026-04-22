#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-2.0-only
#
# T016 [US5] — Snapshot-tick cadence + SC-005 framerate regression gate.
#
# Verifies that the plugin's SnapshotTick scheduler (003-snapshot-arm-coverage)
# emits StateSnapshot payloads at the configured cadence (default 30 frames ≈
# 1s at 30fps), populates `effective_cadence_frames` on every snapshot, and
# populates `send_monotonic_ns` on every snapshot. Also re-runs us1-framerate.sh's
# baseline vs tick-on comparison and fails if the p50 framerate regresses >5%.
#
# Exit codes:
#   0  — ≥ 25 snapshots in 30s, max gap ≤ 2s, cadence+send_monotonic_ns on
#        every snapshot, framerate regression ≤ 5%.
#   1  — any of the above assertions failed.
#   77 — prerequisite missing (engine binary, BAR install, grpcio, or
#        _launch.sh exits 77).
#
# Contracts: contracts/snapshot-tick.md §Acceptance-script surface;
#            plan.md §Constitution Check row V; spec.md §SC-005.

set -uo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
HEADLESS_DIR="$REPO_ROOT/tests/headless"
EXAMPLES_DIR="$REPO_ROOT/specs/002-live-headless-e2e/examples"

# shellcheck source=tests/headless/_fault-assert.sh
source "$HEADLESS_DIR/_fault-assert.sh"

# ---- prereq checks --------------------------------------------------------

if [[ ! -x "$HEADLESS_DIR/_launch.sh" ]]; then
    echo "snapshot-tick: _launch.sh missing — skip" >&2
    exit 77
fi
if [[ ! -f "$EXAMPLES_DIR/coordinator.py" ]]; then
    echo "snapshot-tick: coordinator.py missing — skip" >&2
    exit 77
fi
if ! command -v python3 >/dev/null 2>&1; then
    echo "snapshot-tick: python3 not on PATH — skip" >&2
    exit 77
fi
if ! python3 -c "import grpc" 2>/dev/null; then
    echo "snapshot-tick: grpcio not installed — skip" >&2
    exit 77
fi

PYPROTO_DIR="${HIGHBAR_PYPROTO:-/tmp/hb-run/pyproto}"
if [[ ! -d "$PYPROTO_DIR/highbar" ]]; then
    mkdir -p "$PYPROTO_DIR/highbar"
    if ! python3 -m grpc_tools.protoc -I "$REPO_ROOT/proto" \
            --python_out="$PYPROTO_DIR" \
            --grpc_python_out="$PYPROTO_DIR" \
            "$REPO_ROOT/proto/highbar/"*.proto 2>/dev/null; then
        echo "snapshot-tick: proto codegen failed — skip" >&2
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
WATCH_LOG="$RUN_DIR/snapshot-tick.watch"

cleanup() {
    [[ -f "$ENGINE_PID_FILE" ]] && kill -TERM "$(cat "$ENGINE_PID_FILE")" 2>/dev/null
    [[ -n "${COORD_PID:-}" ]] && kill -TERM "$COORD_PID" 2>/dev/null
}
trap cleanup EXIT

# ---- start coordinator + plugin (same topology as us1-observer.sh) --------

rm -f "$COORD_SOCK"
python3 "$EXAMPLES_DIR/coordinator.py" \
    --endpoint "unix:$COORD_SOCK" --id snap-tick > "$COORD_LOG" 2>&1 &
COORD_PID=$!
for _ in $(seq 1 20); do
    [[ -S "$COORD_SOCK" ]] && break
    sleep 0.2
done
if [[ ! -S "$COORD_SOCK" ]]; then
    echo "snapshot-tick: coordinator failed to bind on $COORD_SOCK — skip" >&2
    cat "$COORD_LOG" >&2
    exit 77
fi

LAUNCH_OUT=$("$HEADLESS_DIR/_launch.sh" \
    --start-script "$START_SCRIPT" \
    --coordinator "unix:$COORD_SOCK" \
    --runtime-dir "$RUN_DIR" 2>&1)
LAUNCH_RC=$?
if [[ $LAUNCH_RC -eq 77 ]]; then
    echo "snapshot-tick: _launch.sh prereq missing — skip" >&2
    echo "$LAUNCH_OUT" >&2
    exit 77
elif [[ $LAUNCH_RC -ne 0 ]]; then
    echo "snapshot-tick: _launch.sh failed (rc=$LAUNCH_RC) — fail" >&2
    exit 1
fi

# Wait for gateway startup.
for _ in $(seq 1 30); do
    if grep -q '\[hb-gateway\] startup' "$ENGINE_LOG" 2>/dev/null; then break; fi
    sleep 1
done
if ! grep -q '\[hb-gateway\] startup' "$ENGINE_LOG"; then
    echo "snapshot-tick: gateway startup banner not seen in 30s — fail" >&2
    tail -50 "$ENGINE_LOG" >&2
    exit 1
fi

# ---- inline Python snapshot watcher --------------------------------------

# Subscribes as an observer to StreamState, counts snapshots in a 30s
# window, and prints a result line the shell parses below.
PYTHONPATH="$PYPROTO_DIR" timeout 40 python3 - "$COORD_SOCK" > "$WATCH_LOG" 2>&1 <<'PYEOF'
import sys
import time

import grpc
from highbar import service_pb2, service_pb2_grpc, state_pb2

endpoint = "unix:" + sys.argv[1]
channel = grpc.insecure_channel(endpoint)
stub = service_pb2_grpc.HighBarProxyStub(channel)

# Hello as observer — per highbar.v1 schema version 1.0.0.
hello = service_pb2.HelloRequest(schema_version="1.0.0",
                                  client_id="snapshot-tick",
                                  role=service_pb2.ROLE_OBSERVER)
try:
    resp = stub.Hello(hello, timeout=5.0)
    print(f"[snap-watch] Hello OK schema={resp.schema_version}")
except grpc.RpcError as e:
    print(f"[snap-watch] Hello failed: {e}")
    sys.exit(1)

stream = stub.StreamState(service_pb2.StreamStateRequest(resume_from_seq=0))

deadline = time.monotonic() + 30.0
snapshots = []  # (wall_clock, frame_number, effective_cadence, send_ns)
try:
    for upd in stream:
        now = time.monotonic()
        kind = upd.WhichOneof("payload")
        if kind == "snapshot":
            snapshots.append((
                now,
                upd.snapshot.frame_number,
                upd.snapshot.effective_cadence_frames,
                upd.send_monotonic_ns,
            ))
        if now >= deadline:
            break
except grpc.RpcError as e:
    # End-of-window: the test closed the stream — swallow.
    pass

# Emit assertions; the shell parses each PASS/FAIL line.
n = len(snapshots)
print(f"[snap-watch] total_snapshots={n}")
if n < 25:
    print(f"[snap-watch] FAIL count={n} < 25")
    sys.exit(1)

gaps = []
for i in range(1, n):
    gaps.append(snapshots[i][0] - snapshots[i-1][0])
max_gap = max(gaps) if gaps else 0.0
print(f"[snap-watch] max_gap={max_gap:.3f}s")
if max_gap > 2.0:
    print(f"[snap-watch] FAIL max_gap={max_gap:.3f} > 2.0")
    sys.exit(1)

# Cadence + send_monotonic_ns populated on every snapshot AFTER the first.
# The first emission may ride on a Hello-path snapshot where
# effective_cadence_frames is defensively 0 (see contracts/snapshot-tick.md
# §Proto surface re: Hello one-shot).
missing_cadence = sum(1 for i, s in enumerate(snapshots)
                      if i > 0 and s[2] == 0)
missing_send_ns = sum(1 for s in snapshots if s[3] == 0)
print(f"[snap-watch] missing_cadence_after_first={missing_cadence}")
print(f"[snap-watch] missing_send_ns={missing_send_ns}")
if missing_cadence > 0:
    print(f"[snap-watch] FAIL {missing_cadence} post-first snapshots missing effective_cadence_frames")
    sys.exit(1)
if missing_send_ns > 0:
    print(f"[snap-watch] FAIL {missing_send_ns} snapshots missing send_monotonic_ns")
    sys.exit(1)

print("[snap-watch] PASS")
PYEOF
WATCH_RC=$?

if [[ $WATCH_RC -ne 0 ]]; then
    echo "snapshot-tick: watcher failed rc=$WATCH_RC — fail" >&2
    tail -30 "$WATCH_LOG" >&2
    exit 1
fi

# Pull stats out for the shell's final line.
count=$(grep -oE 'total_snapshots=[0-9]+' "$WATCH_LOG" | tail -1 | sed 's/.*=//')
max_gap=$(grep -oE 'max_gap=[0-9.]+' "$WATCH_LOG" | tail -1 | sed 's/.*=//')
echo "snapshot-tick: cadence PASS count=${count:-?} max_gap=${max_gap:-?}s"

# ---- fault status ---------------------------------------------------------

EFFECTIVE_WRITEDIR="$WRITE_DIR/engine/recoil_2025.06.19"
fault_status "$EFFECTIVE_WRITEDIR"
fs=$?
if [[ $fs -eq 2 ]]; then
    echo "snapshot-tick: gateway DISABLED mid-test — fail" >&2
    exit 1
fi

# ---- SC-005 framerate regression gate ------------------------------------

# Plan §Constitution Check row V requires re-running the
# baseline-vs-tick-on comparison and failing on >5% p50 regression.
# us1-framerate.sh measures the framerate under existing 002 load; we
# reuse it here as the tick-on comparator. If the script isn't present
# (pre-002 checkouts), skip this gate with a warning — not a failure.
if [[ -x "$HEADLESS_DIR/us1-framerate.sh" ]]; then
    # us1-framerate's invocation budget is ~60s and its own PASS/FAIL
    # line covers the regression assertion. We treat its exit code as
    # the regression gate.
    echo "snapshot-tick: re-running us1-framerate.sh for SC-005"
    "$HEADLESS_DIR/us1-framerate.sh" > "$RUN_DIR/snapshot-tick.framerate.log" 2>&1
    fr_rc=$?
    if [[ $fr_rc -eq 0 ]]; then
        echo "snapshot-tick: SC-005 framerate gate PASS"
    elif [[ $fr_rc -eq 77 ]]; then
        echo "snapshot-tick: us1-framerate prereq missing — skipping SC-005 gate"
    else
        echo "snapshot-tick: framerate regression detected (us1-framerate.sh rc=$fr_rc) — fail" >&2
        tail -30 "$RUN_DIR/snapshot-tick.framerate.log" >&2
        exit 1
    fi
else
    echo "snapshot-tick: us1-framerate.sh not executable — skipping SC-005 gate" >&2
fi

echo "snapshot-tick: PASS"

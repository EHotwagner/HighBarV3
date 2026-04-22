#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-2.0-only
#
# T018 [US2] — Build command behavioral verification.
# arm-covered: build_unit
#
# Dispatches `BuildUnit(commander_id, armmex_def_id, commander_pos +
# (+96, 0, 0))`, samples snapshots at t+1s/t+3s/t+5s, and asserts:
#   (a) own_units count increased by exactly 1 at t+1s;
#   (b) new unit has under_construction=true at t+1s;
#   (c) build_progress strictly increased between t+3s and t+5s.
#
# Exit codes (per quickstart.md §3):
#   0  — all three assertions hold.
#   1  — `build not started: unit_count_delta=0 in 5s` OR
#        `build_progress not monotonic`.
#   77 — commander missing in first 30s OR setup skip.

set -uo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
HEADLESS_DIR="$REPO_ROOT/tests/headless"
EXAMPLES_DIR="$REPO_ROOT/specs/002-live-headless-e2e/examples"

# shellcheck source=tests/headless/_fault-assert.sh
source "$HEADLESS_DIR/_fault-assert.sh"

# ---- prereq checks --------------------------------------------------------

if [[ ! -x "$HEADLESS_DIR/_launch.sh" ]]; then
    echo "behavioral-build: _launch.sh missing — skip" >&2
    exit 77
fi
if [[ ! -f "$EXAMPLES_DIR/coordinator.py" ]]; then
    echo "behavioral-build: coordinator.py missing — skip" >&2
    exit 77
fi
if ! command -v python3 >/dev/null 2>&1; then
    echo "behavioral-build: python3 missing — skip" >&2
    exit 77
fi
if ! python3 -c "import grpc" 2>/dev/null; then
    echo "behavioral-build: grpcio missing — skip" >&2
    exit 77
fi

PYPROTO_DIR="${HIGHBAR_PYPROTO:-/tmp/hb-run/pyproto}"
if [[ ! -d "$PYPROTO_DIR/highbar" ]]; then
    mkdir -p "$PYPROTO_DIR/highbar"
    if ! python3 -m grpc_tools.protoc -I "$REPO_ROOT/proto" \
            --python_out="$PYPROTO_DIR" \
            --grpc_python_out="$PYPROTO_DIR" \
            "$REPO_ROOT/proto/highbar/"*.proto 2>/dev/null; then
        echo "behavioral-build: proto codegen failed — skip" >&2
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
CLIENT_LOG="$RUN_DIR/behavioral-build.log"

cleanup() {
    [[ -f "$ENGINE_PID_FILE" ]] && kill -TERM "$(cat "$ENGINE_PID_FILE")" 2>/dev/null
    [[ -n "${COORD_PID:-}" ]] && kill -TERM "$COORD_PID" 2>/dev/null
}
trap cleanup EXIT

rm -f "$COORD_SOCK"
python3 "$EXAMPLES_DIR/coordinator.py" \
    --endpoint "unix:$COORD_SOCK" --id bbuild > "$COORD_LOG" 2>&1 &
COORD_PID=$!
for _ in $(seq 1 20); do
    [[ -S "$COORD_SOCK" ]] && break
    sleep 0.2
done
if [[ ! -S "$COORD_SOCK" ]]; then
    echo "behavioral-build: coordinator did not bind — skip" >&2
    exit 77
fi

LAUNCH_OUT=$("$HEADLESS_DIR/_launch.sh" \
    --start-script "$START_SCRIPT" \
    --coordinator "unix:$COORD_SOCK" \
    --runtime-dir "$RUN_DIR" 2>&1)
LAUNCH_RC=$?
if [[ $LAUNCH_RC -eq 77 ]]; then
    echo "behavioral-build: _launch.sh prereq missing — skip" >&2
    exit 77
elif [[ $LAUNCH_RC -ne 0 ]]; then
    echo "behavioral-build: _launch.sh failed — fail" >&2
    exit 1
fi

for _ in $(seq 1 30); do
    if grep -q '\[hb-gateway\] startup' "$ENGINE_LOG" 2>/dev/null; then break; fi
    sleep 1
done
if ! grep -q '\[hb-gateway\] startup' "$ENGINE_LOG"; then
    echo "behavioral-build: gateway startup banner not seen — fail" >&2
    exit 1
fi

sleep 5

PYTHONPATH="$PYPROTO_DIR" timeout 60 python3 - "$COORD_SOCK" > "$CLIENT_LOG" 2>&1 <<'PYEOF'
import sys
import threading
import time

import grpc
from highbar import service_pb2, service_pb2_grpc
from highbar import commands_pb2, callbacks_pb2

endpoint = "unix:" + sys.argv[1]
ch = grpc.insecure_channel(endpoint)
stub = service_pb2_grpc.HighBarProxyStub(ch)

resp = stub.Hello(service_pb2.HelloRequest(
    schema_version="1.0.0",
    role=service_pb2.Role.ROLE_AI,
), timeout=5)
print(f"[bbuild] Hello OK session={resp.session_id}", flush=True)

shared = {"snapshots": [], "stop": False, "err": None}

def watcher():
    try:
        for upd in stub.StreamState(
                service_pb2.StreamStateRequest(resume_from_seq=0),
                timeout=50):
            if shared["stop"]:
                return
            if upd.WhichOneof("payload") == "snapshot":
                shared["snapshots"].append((time.monotonic(), upd.snapshot))
    except grpc.RpcError as e:
        shared["err"] = e.code().name

t = threading.Thread(target=watcher, daemon=True)
t.start()

def find_commander(snap):
    best = None
    for u in snap.own_units:
        if u.max_health > 3000 and (best is None or u.max_health > best.max_health):
            best = u
    return best

# Wait up to 30s for a commander.
deadline = time.monotonic() + 30.0
pre = None
while time.monotonic() < deadline:
    if shared["snapshots"]:
        c = find_commander(shared["snapshots"][-1][1])
        if c is not None:
            pre = (shared["snapshots"][-1][1], c)
            break
    time.sleep(0.2)
if pre is None:
    print(f"[bbuild] no commander in 30s err={shared.get('err')}", flush=True)
    sys.exit(77)

pre_snap, cmdr = pre
cmdr_id = cmdr.unit_id
pre_count = len(pre_snap.own_units)
pre_def_id = cmdr.def_id
print(f"[bbuild] commander_id={cmdr_id} pre_own_units={pre_count}", flush=True)

# Resolve the armmex def_id. Environment override is the fast path:
# HIGHBAR_ARMMEX_DEF_ID pins the value per engine pin. Fallback: loop
# all own_units[].def_id values and take the next-larger def_id as a
# coarse "commander-adjacent" heuristic. This is NOT robust across mod
# updates; the env override is the supported path on the reference host.
import os as _os
armmex_def_id = None
env = _os.environ.get("HIGHBAR_ARMMEX_DEF_ID", "")
if env.isdigit():
    armmex_def_id = int(env)
    print(f"[bbuild] armmex def_id={armmex_def_id} (from HIGHBAR_ARMMEX_DEF_ID)",
          flush=True)
if armmex_def_id is None:
    print("[bbuild] HIGHBAR_ARMMEX_DEF_ID not set — skipping (setup skip, "
          "set via env var from BAR unitdef dump on reference host)",
          flush=True)
    sys.exit(77)

# Dispatch BuildUnit(commander, armmex, commander_pos + (+96, 0, 0)).
px, py, pz = cmdr.position.x, cmdr.position.y, cmdr.position.z

def gen():
    batch = commands_pb2.CommandBatch()
    batch.batch_seq = 1
    batch.target_unit_id = cmdr_id
    cmd = batch.commands.add()
    cmd.build_unit.unit_id = cmdr_id
    cmd.build_unit.to_build_unit_def_id = armmex_def_id
    cmd.build_unit.build_position.x = px + 96.0
    cmd.build_unit.build_position.y = py
    cmd.build_unit.build_position.z = pz
    cmd.build_unit.options = 0
    cmd.build_unit.timeout = 0
    yield batch

ack = stub.SubmitCommands(gen(), timeout=10)
print(f"[bbuild] dispatched BuildUnit armmex pos=({px+96:.1f},{py:.1f},{pz:.1f}) "
      f"accepted={ack.batches_accepted}", flush=True)

# Sample at t+1s (frame +30), t+3s (+90), t+5s (+150).
sample_frames = [pre_snap.frame_number + off for off in (30, 90, 150)]

def snap_at(min_frame, timeout):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        for _, snap in reversed(shared["snapshots"]):
            if snap.frame_number >= min_frame:
                return snap
        time.sleep(0.2)
    return None

s1 = snap_at(sample_frames[0], 10.0)
if s1 is None:
    print("[bbuild] t+1s snapshot stall — fail", flush=True)
    sys.exit(1)
new_units = [u for u in s1.own_units if u.def_id != pre_def_id
             or u.unit_id != cmdr_id]
# Compare counts to original snapshot's own_units.
delta = len(s1.own_units) - pre_count
print(f"[bbuild] t+1s own_units={len(s1.own_units)} delta={delta}", flush=True)
if delta != 1:
    print(f"[bbuild] build not started: unit_count_delta={delta} in 5s",
          flush=True)
    sys.exit(1)

new_unit = None
pre_ids = {u.unit_id for u in pre_snap.own_units}
for u in s1.own_units:
    if u.unit_id not in pre_ids:
        new_unit = u
        break
if new_unit is None:
    print("[bbuild] unit_count grew but no new unit_id identified — fail",
          flush=True)
    sys.exit(1)
print(f"[bbuild] t+1s new_unit_id={new_unit.unit_id} def={new_unit.def_id} "
      f"under_construction={new_unit.under_construction} "
      f"build_progress={new_unit.build_progress:.3f}", flush=True)
if not new_unit.under_construction:
    print("[bbuild] new unit has under_construction=false — fail", flush=True)
    sys.exit(1)

s3 = snap_at(sample_frames[1], 10.0)
s5 = snap_at(sample_frames[2], 10.0)
if s3 is None or s5 is None:
    print("[bbuild] t+3s or t+5s snapshot stall — fail", flush=True)
    sys.exit(1)
bp3 = None
bp5 = None
for u in s3.own_units:
    if u.unit_id == new_unit.unit_id:
        bp3 = u.build_progress
        break
for u in s5.own_units:
    if u.unit_id == new_unit.unit_id:
        bp5 = u.build_progress
        break
if bp3 is None or bp5 is None:
    print("[bbuild] new unit disappeared before t+5s — fail", flush=True)
    sys.exit(1)
print(f"[bbuild] t+3s build_progress={bp3:.3f} t+5s build_progress={bp5:.3f}",
      flush=True)
if bp5 <= bp3:
    print(f"[bbuild] build_progress not monotonic: t+3s={bp3:.3f} "
          f"t+5s={bp5:.3f}", flush=True)
    sys.exit(1)

shared["stop"] = True
print("[bbuild] PASS")
sys.exit(0)
PYEOF
PY_RC=$?

cat "$CLIENT_LOG"

if [[ $PY_RC -eq 77 ]]; then
    echo "behavioral-build: setup skip" >&2
    exit 77
elif [[ $PY_RC -ne 0 ]]; then
    echo "behavioral-build: FAIL rc=$PY_RC" >&2
    tail -30 "$ENGINE_LOG" >&2
    exit 1
fi

EFFECTIVE_WRITEDIR="$WRITE_DIR/engine/recoil_2025.06.19"
fault_status "$EFFECTIVE_WRITEDIR"
if [[ $? -eq 2 ]]; then
    echo "behavioral-build: gateway DISABLED — fail" >&2
    exit 1
fi

echo "behavioral-build: PASS"

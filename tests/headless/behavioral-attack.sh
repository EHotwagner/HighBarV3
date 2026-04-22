#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-2.0-only
#
# T030 [US3] — Attack command behavioral verification.
# arm-covered: attack
#
# Picks any visible enemy from snapshots, records its health, dispatches
# `AttackUnit(commander_id, enemy_id)`, samples snapshots for up to 15s,
# and asserts either (a) enemy health dropped by ≥ 1 hp at some sample
# OR (b) the enemy disappeared AND an `EnemyDestroyed` delta was observed.
#
# Exit codes (per quickstart.md §4):
#   0  — health decrease or destruction observed.
#   1  — `target_not_engaged: health unchanged after 15s`.
#   77 — `no enemy in LOS — test cannot proceed` (spec §Edge Case) or
#        setup prereq missing.

set -uo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
HEADLESS_DIR="$REPO_ROOT/tests/headless"
EXAMPLES_DIR="$REPO_ROOT/specs/002-live-headless-e2e/examples"

# shellcheck source=tests/headless/_fault-assert.sh
source "$HEADLESS_DIR/_fault-assert.sh"

if [[ ! -x "$HEADLESS_DIR/_launch.sh" ]]; then
    echo "behavioral-attack: _launch.sh missing — skip" >&2
    exit 77
fi
if [[ ! -f "$EXAMPLES_DIR/coordinator.py" ]]; then
    echo "behavioral-attack: coordinator.py missing — skip" >&2
    exit 77
fi
if ! command -v python3 >/dev/null 2>&1; then
    echo "behavioral-attack: python3 missing — skip" >&2
    exit 77
fi
if ! python3 -c "import grpc" 2>/dev/null; then
    echo "behavioral-attack: grpcio missing — skip" >&2
    exit 77
fi

PYPROTO_DIR="${HIGHBAR_PYPROTO:-/tmp/hb-run/pyproto}"
if [[ ! -d "$PYPROTO_DIR/highbar" ]]; then
    mkdir -p "$PYPROTO_DIR/highbar"
    if ! python3 -m grpc_tools.protoc -I "$REPO_ROOT/proto" \
            --python_out="$PYPROTO_DIR" \
            --grpc_python_out="$PYPROTO_DIR" \
            "$REPO_ROOT/proto/highbar/"*.proto 2>/dev/null; then
        echo "behavioral-attack: proto codegen failed — skip" >&2
        exit 77
    fi
    touch "$PYPROTO_DIR/highbar/__init__.py"
fi

RUN_DIR="${HIGHBAR_RUN_DIR:-/tmp/hb-run}"
mkdir -p "$RUN_DIR"
COORD_SOCK="$RUN_DIR/hb-coord.sock"
COORD_LOG="$RUN_DIR/coord.log"
# Allow --startscript override via T031's custom-attack.startscript if
# LOS on minimal.startscript proves too brittle.
START_SCRIPT="${HIGHBAR_ATTACK_STARTSCRIPT:-$HEADLESS_DIR/scripts/minimal.startscript}"
if [[ $# -gt 0 ]]; then
    case "$1" in
        --startscript) START_SCRIPT="$2"; shift 2;;
        *) ;;
    esac
fi
ENGINE_LOG="$RUN_DIR/highbar-launch.log"
ENGINE_PID_FILE="$RUN_DIR/highbar-launch.pid"
WRITE_DIR="${HIGHBAR_WRITE_DIR:-$HOME/.local/state/Beyond All Reason}"
CLIENT_LOG="$RUN_DIR/behavioral-attack.log"

cleanup() {
    [[ -f "$ENGINE_PID_FILE" ]] && kill -TERM "$(cat "$ENGINE_PID_FILE")" 2>/dev/null
    [[ -n "${COORD_PID:-}" ]] && kill -TERM "$COORD_PID" 2>/dev/null
}
trap cleanup EXIT

rm -f "$COORD_SOCK"
python3 "$EXAMPLES_DIR/coordinator.py" \
    --endpoint "unix:$COORD_SOCK" --id battack > "$COORD_LOG" 2>&1 &
COORD_PID=$!
for _ in $(seq 1 20); do
    [[ -S "$COORD_SOCK" ]] && break
    sleep 0.2
done
if [[ ! -S "$COORD_SOCK" ]]; then
    echo "behavioral-attack: coordinator did not bind — skip" >&2
    exit 77
fi

LAUNCH_OUT=$("$HEADLESS_DIR/_launch.sh" \
    --start-script "$START_SCRIPT" \
    --coordinator "unix:$COORD_SOCK" \
    --runtime-dir "$RUN_DIR" 2>&1)
LAUNCH_RC=$?
if [[ $LAUNCH_RC -eq 77 ]]; then
    echo "behavioral-attack: _launch.sh prereq missing — skip" >&2
    exit 77
elif [[ $LAUNCH_RC -ne 0 ]]; then
    echo "behavioral-attack: _launch.sh failed — fail" >&2
    exit 1
fi

for _ in $(seq 1 30); do
    if grep -q '\[hb-gateway\] startup' "$ENGINE_LOG" 2>/dev/null; then break; fi
    sleep 1
done
if ! grep -q '\[hb-gateway\] startup' "$ENGINE_LOG"; then
    echo "behavioral-attack: gateway startup not seen — fail" >&2
    exit 1
fi

sleep 5

PYTHONPATH="$PYPROTO_DIR" timeout 80 python3 - "$COORD_SOCK" > "$CLIENT_LOG" 2>&1 <<'PYEOF'
import sys
import threading
import time

import grpc
from highbar import service_pb2, service_pb2_grpc
from highbar import commands_pb2

endpoint = "unix:" + sys.argv[1]
ch = grpc.insecure_channel(endpoint)
stub = service_pb2_grpc.HighBarProxyStub(ch)

resp = stub.Hello(service_pb2.HelloRequest(
    schema_version="1.0.0",
    role=service_pb2.Role.ROLE_AI,
), timeout=5)
print(f"[battack] Hello OK session={resp.session_id}", flush=True)

shared = {"snapshots": [], "deltas": [], "stop": False}

def watcher():
    try:
        for upd in stub.StreamState(
                service_pb2.StreamStateRequest(resume_from_seq=0),
                timeout=70):
            if shared["stop"]:
                return
            kind = upd.WhichOneof("payload")
            if kind == "snapshot":
                shared["snapshots"].append((time.monotonic(), upd.snapshot))
            elif kind == "delta":
                for ev in upd.delta.events:
                    shared["deltas"].append(ev)
    except grpc.RpcError:
        pass

t = threading.Thread(target=watcher, daemon=True)
t.start()

def find_commander(snap):
    for u in snap.own_units:
        if u.max_health > 3000:
            return u
    return None

# Wait up to 30s for an enemy in LOS + a commander.
deadline = time.monotonic() + 30.0
commander = None
enemy = None
while time.monotonic() < deadline:
    if shared["snapshots"]:
        last = shared["snapshots"][-1][1]
        if commander is None:
            commander = find_commander(last)
        for e in last.visible_enemies:
            if e.health > 0.0:
                # Visual LOS — health populated. Radar-only blips have
                # health=0 and can't be damage-verified.
                enemy = e
                break
        if enemy is not None:
            break
    time.sleep(0.3)

if commander is None:
    print(f"[battack] no commander in 30s", flush=True)
    sys.exit(77)
if enemy is None:
    print("[battack] no enemy in LOS — test cannot proceed", flush=True)
    sys.exit(77)

print(f"[battack] enemy_id={enemy.unit_id} initial_health={enemy.health:.2f}",
      flush=True)

def gen():
    batch = commands_pb2.CommandBatch()
    batch.batch_seq = 1
    batch.target_unit_id = commander.unit_id
    cmd = batch.commands.add()
    cmd.attack.unit_id = commander.unit_id
    cmd.attack.target_unit_id = enemy.unit_id
    yield batch

ack = stub.SubmitCommands(gen(), timeout=10)
print(f"[battack] dispatched AttackUnit commander={commander.unit_id} "
      f"enemy={enemy.unit_id} accepted={ack.batches_accepted}", flush=True)

# Sample snapshots for up to 15s; pass on health drop or destruction.
end = time.monotonic() + 15.0
initial_hp = enemy.health
enemy_destroyed_delta_seen = False
verified = False
last_hp = initial_hp
while time.monotonic() < end:
    if shared["snapshots"]:
        last = shared["snapshots"][-1][1]
        still = None
        for e in last.visible_enemies:
            if e.unit_id == enemy.unit_id:
                still = e
                break
        if still is not None:
            last_hp = still.health
            if last_hp < initial_hp - 1.0:
                verified = True
                break
        else:
            # Target disappeared — check for EnemyDestroyed delta event.
            for ev in shared["deltas"]:
                kind = ev.WhichOneof("kind")
                if kind == "enemy_destroyed" \
                        and ev.enemy_destroyed.unit_id == enemy.unit_id:
                    enemy_destroyed_delta_seen = True
                    break
            if enemy_destroyed_delta_seen:
                verified = True
                break
    time.sleep(0.3)

shared["stop"] = True

if verified:
    if enemy_destroyed_delta_seen:
        print(f"[battack] target destroyed (EnemyDestroyed delta observed)",
              flush=True)
    else:
        print(f"[battack] enemy_health={last_hp:.2f} "
              f"(delta {last_hp - initial_hp:+.2f})", flush=True)
    print("[battack] PASS")
    sys.exit(0)

print(f"[battack] target_not_engaged: health unchanged after 15s "
      f"(initial={initial_hp:.2f} last={last_hp:.2f})", flush=True)
sys.exit(1)
PYEOF
PY_RC=$?

cat "$CLIENT_LOG"

if [[ $PY_RC -eq 77 ]]; then
    echo "behavioral-attack: skip (no enemy in LOS or setup miss)" >&2
    exit 77
elif [[ $PY_RC -ne 0 ]]; then
    echo "behavioral-attack: FAIL rc=$PY_RC" >&2
    exit 1
fi

EFFECTIVE_WRITEDIR="$WRITE_DIR/engine/recoil_2025.06.19"
fault_status "$EFFECTIVE_WRITEDIR"
if [[ $? -eq 2 ]]; then
    echo "behavioral-attack: gateway DISABLED — fail" >&2
    exit 1
fi

echo "behavioral-attack: PASS"

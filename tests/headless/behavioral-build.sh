#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-2.0-only
#
# T018 [US2] — Build command behavioral verification.
# arm-covered: build_unit
#
# Dispatches `BuildUnit(commander_id, armmex_def_id, commander_pos +
# (+96, 0, 0))`, runs in external-only mode by default so ambient BARb
# reissuance does not mask the probe, samples snapshots across the first
# post-dispatch window,
# and asserts:
#   (a) a new construction candidate appears within the sample window;
#   (b) that candidate enters an under-construction state; and
#   (c) build_progress increases across later snapshots.
#
# Exit codes (per quickstart.md §3):
#   0  — all three assertions hold.
#   1  — `build not started in sample window` OR
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
CALLBACK_PROXY_ENDPOINT="${HIGHBAR_CALLBACK_PROXY_ENDPOINT:-unix:$RUN_DIR/highbar-1.sock}"
TOKEN_PATH="${HIGHBAR_TOKEN_PATH:-/tmp/highbar.token}"
START_SCRIPT="$HEADLESS_DIR/scripts/minimal.startscript"
PHASE_MODE="${HIGHBAR_BEHAVIORAL_BUILD_PHASE:-2}"
ENABLE_BUILTIN="${HIGHBAR_BEHAVIORAL_BUILD_ENABLE_BUILTIN:-}"
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
HIGHBAR_CALLBACK_PROXY_ENDPOINT="$CALLBACK_PROXY_ENDPOINT" \
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

LAUNCH_ARGS=(
    --start-script "$START_SCRIPT"
    --coordinator "unix:$COORD_SOCK"
    --runtime-dir "$RUN_DIR"
    --phase "$PHASE_MODE"
)
if [[ -n "$ENABLE_BUILTIN" ]]; then
    LAUNCH_ARGS+=(--enable-builtin "$ENABLE_BUILTIN")
fi
LAUNCH_OUT=$("$HEADLESS_DIR/_launch.sh" "${LAUNCH_ARGS[@]}" 2>&1)
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

PYTHONPATH="$PYPROTO_DIR" timeout 60 python3 - "$COORD_SOCK" "$RUN_DIR/behavioral-build-outcome.json" "$TOKEN_PATH" > "$CLIENT_LOG" 2>&1 <<'PYEOF'
import json
import math
import sys
import threading
import time

import grpc
from highbar import service_pb2, service_pb2_grpc
from highbar import commands_pb2, callbacks_pb2

endpoint = "unix:" + sys.argv[1]
outcome_path = sys.argv[2]
token_path = sys.argv[3]
ch = grpc.insecure_channel(endpoint)
stub = service_pb2_grpc.HighBarProxyStub(ch)

with open(token_path, "r", encoding="utf-8") as handle:
    token = handle.read().strip()
metadata = [("x-highbar-ai-token", token)] if token else None


def emit_outcome(*, prerequisite_name, callback_path, resolved_def_id,
                 resolution_status, resolution_reason, map_source_decision,
                 dispatch_result, capability_limit_summary=None,
                 failure_reason=None):
    payload = {
        "probe_id": "behavioral-build",
        "prerequisite_name": prerequisite_name,
        "resolution_record": {
            "prerequisite_name": prerequisite_name,
            "consumer": "behavioral_build_probe",
            "callback_path": callback_path,
            "resolved_def_id": resolved_def_id,
            "resolution_status": resolution_status,
            "reason": resolution_reason,
            "recorded_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        },
        "map_source_decision": map_source_decision,
        "dispatch_result": dispatch_result,
        "capability_limit_summary": capability_limit_summary,
        "failure_reason": failure_reason,
        "completed_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    with open(outcome_path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, sort_keys=True)
        handle.write("\n")


def resolve_def_id_by_name(name):
    bulk = stub.InvokeCallback(
        callbacks_pb2.CallbackRequest(
            request_id=1,
            callback_id=callbacks_pb2.CALLBACK_GET_UNIT_DEFS,
        ),
        metadata=metadata,
        timeout=5,
    )
    if (not bulk.success) or (not bulk.result.HasField("int_array_value")):
        return None, "relay_unavailable", bulk.error_message or "bulk unit-def lookup failed"
    for index, def_id in enumerate(bulk.result.int_array_value.values, start=2):
        resp = stub.InvokeCallback(
            callbacks_pb2.CallbackRequest(
                request_id=index,
                callback_id=callbacks_pb2.CALLBACK_UNITDEF_GET_NAME,
                params=(callbacks_pb2.CallbackParam(int_value=int(def_id)),),
            ),
            metadata=metadata,
            timeout=5,
        )
        if (not resp.success) or (not resp.result.HasField("string_value")):
            continue
        if resp.result.string_value == name:
            return int(def_id), "resolved", f"resolved runtime def id for {name}"
    return None, "missing", f"runtime callback results did not include {name}"


def unit_is_under_construction(unit):
    if bool(getattr(unit, "under_construction", False)):
        return True
    build_progress = getattr(unit, "build_progress", None)
    if build_progress is None:
        return False
    try:
        progress_value = float(build_progress)
    except (TypeError, ValueError):
        return False
    return 0.0 < progress_value < 0.999


def distance_to_target(unit, target):
    pos = getattr(unit, "position", None)
    if pos is None:
        return math.inf
    dx = float(getattr(pos, "x", 0.0)) - target[0]
    dy = float(getattr(pos, "y", 0.0)) - target[1]
    dz = float(getattr(pos, "z", 0.0)) - target[2]
    return math.sqrt(dx * dx + dy * dy + dz * dz)


def distance_between_positions(a, b):
    if a is None or b is None:
        return math.inf
    dx = float(getattr(a, "x", 0.0)) - float(getattr(b, "x", 0.0))
    dy = float(getattr(a, "y", 0.0)) - float(getattr(b, "y", 0.0))
    dz = float(getattr(a, "z", 0.0)) - float(getattr(b, "z", 0.0))
    return math.sqrt(dx * dx + dy * dy + dz * dz)


def position_is_clear(target, snapshot, *, ignore_unit_ids=(), clearance_radius=96.0):
    ignored = set(ignore_unit_ids)
    for unit in getattr(snapshot, "own_units", ()):
        if unit.unit_id in ignored:
            continue
        if distance_between_positions(getattr(unit, "position", None), target) < clearance_radius:
            return False
    return True


def choose_build_position(def_name, commander, static_map, snapshot):
    if def_name == "armmex" and static_map is not None:
        ordered_spots = sorted(
            getattr(static_map, "metal_spots", ()),
            key=lambda spot: distance_between_positions(spot, commander.position),
        )
        if ordered_spots:
            for index, spot in enumerate(ordered_spots):
                if position_is_clear(
                    spot,
                    snapshot,
                    ignore_unit_ids={commander.unit_id},
                ):
                    return (
                        (float(spot.x), float(spot.y), float(spot.z)),
                        f"nearest_clear_metal_spot[{index}]",
                    )
            first = ordered_spots[0]
            return (
                (float(first.x), float(first.y), float(first.z)),
                "nearest_metal_spot[0]",
            )
    return (
        (
            float(commander.position.x) + 96.0,
            float(commander.position.y),
            float(commander.position.z),
        ),
        "commander_offset(+96,0,0)",
    )


def select_map_source_decision(static_map):
    metal_spots = tuple(getattr(static_map, "metal_spots", ()) or ())
    if metal_spots:
        return {
            "consumer": "behavioral_build_probe",
            "selected_source": "hello_static_map",
            "metal_spot_count": len(metal_spots),
            "reason": (
                "used HelloResponse.static_map because callback map inspection is "
                "unsupported or unnecessary on this host"
            ),
            "recorded_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }
    return {
        "consumer": "behavioral_build_probe",
        "selected_source": "missing",
        "metal_spot_count": 0,
        "reason": "session-start map payload unavailable for standalone probe targeting",
        "recorded_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }


def candidate_summary(unit, target):
    return (
        f"id={unit.unit_id} def={unit.def_id} "
        f"uc={1 if unit_is_under_construction(unit) else 0} "
        f"bp={float(getattr(unit, 'build_progress', 0.0)):.3f} "
        f"dist={distance_to_target(unit, target):.1f}"
    )


def log_sample(label, snap, pre_ids, target, expected_def_id):
    new_candidates = [u for u in snap.own_units if u.unit_id not in pre_ids]
    summary = ", ".join(
        candidate_summary(unit, target)
        for unit in sorted(
            new_candidates,
            key=lambda item: (
                item.def_id != expected_def_id,
                not unit_is_under_construction(item),
                distance_to_target(item, target),
                -item.unit_id,
            ),
        )[:5]
    ) or "none"
    print(
        f"[bbuild] {label} own_units={len(snap.own_units)} "
        f"delta={len(snap.own_units) - len(pre_ids)} candidates={summary}",
        flush=True,
    )


def select_new_unit(samples, pre_ids, target, expected_def_id, target_radius=192.0):
    histories = {}
    for label, snap in samples:
        for unit in snap.own_units:
            if unit.unit_id in pre_ids:
                continue
            entry = histories.setdefault(
                unit.unit_id,
                {
                    "unit_id": unit.unit_id,
                    "best_distance": math.inf,
                    "ever_matching_def": False,
                    "ever_under_construction": False,
                    "max_build_progress": 0.0,
                    "first_seen": label,
                    "latest_label": label,
                    "units": {},
                },
            )
            entry["best_distance"] = min(
                entry["best_distance"],
                distance_to_target(unit, target),
            )
            entry["ever_matching_def"] = (
                entry["ever_matching_def"] or unit.def_id == expected_def_id
            )
            entry["ever_under_construction"] = (
                entry["ever_under_construction"] or unit_is_under_construction(unit)
            )
            entry["max_build_progress"] = max(
                entry["max_build_progress"],
                float(getattr(unit, "build_progress", 0.0)),
            )
            entry["latest_label"] = label
            entry["units"][label] = unit

    if not histories:
        return None, {}

    candidates = list(histories.values())
    preferred = [
        entry
        for entry in candidates
        if entry["ever_matching_def"]
        or (
            entry["ever_under_construction"]
            and entry["best_distance"] <= target_radius
        )
    ] or candidates
    selected = max(
        preferred,
        key=lambda entry: (
            1 if entry["ever_matching_def"] and entry["ever_under_construction"] else 0,
            1 if entry["ever_matching_def"] else 0,
            1 if entry["ever_under_construction"] else 0,
            entry["max_build_progress"],
            -entry["best_distance"],
            entry["unit_id"],
        ),
    )
    return selected, histories

resp = stub.Hello(service_pb2.HelloRequest(
    schema_version="1.0.0",
    role=service_pb2.Role.ROLE_AI,
), metadata=metadata, timeout=5)
static_map = getattr(resp, "static_map", None)
map_source_decision = select_map_source_decision(static_map)
capability_limit_summary = (
    "deeper commander/build-option diagnostics are capability-limited on this host"
)
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


def wait_for_stable_own_units(shared, *, timeout=20.0, min_stable_frames=90):
    end = time.monotonic() + timeout
    baseline_snap = None
    baseline_ids = None
    baseline_frame = None
    while time.monotonic() < end:
        if not shared["snapshots"]:
            time.sleep(0.2)
            continue
        snap = shared["snapshots"][-1][1]
        unit_ids = tuple(sorted(unit.unit_id for unit in snap.own_units))
        if baseline_ids != unit_ids:
            baseline_snap = snap
            baseline_ids = unit_ids
            baseline_frame = snap.frame_number
            time.sleep(0.2)
            continue
        if (
            baseline_snap is not None
            and baseline_frame is not None
            and snap.frame_number - baseline_frame >= min_stable_frames
        ):
            return snap, "stable"
        time.sleep(0.2)
    if shared["snapshots"]:
        return shared["snapshots"][-1][1], "timeout"
    return None, "timeout"

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
pre_snap, stabilization = wait_for_stable_own_units(shared)
if pre_snap is None:
    print(f"[bbuild] own-unit stabilization unavailable err={shared.get('err')}", flush=True)
    sys.exit(1)
cmdr = find_commander(pre_snap)
if cmdr is None:
    print("[bbuild] commander missing after stabilization — fail", flush=True)
    sys.exit(1)
cmdr_id = cmdr.unit_id
pre_count = len(pre_snap.own_units)
print(
    f"[bbuild] commander_id={cmdr_id} pre_own_units={pre_count} "
    f"stabilization={stabilization} frame={pre_snap.frame_number}",
    flush=True,
)

# Resolve the armmex def_id through the same callback path used by live closeout.
armmex_def_id, resolution_status, resolution_reason = resolve_def_id_by_name("armmex")
print(f"[bbuild] prerequisite_resolution status={resolution_status} "
      f"def_id={armmex_def_id} reason={resolution_reason}", flush=True)
if armmex_def_id is None:
    emit_outcome(
        prerequisite_name="armmex",
        callback_path="InvokeCallback/armmex",
        resolved_def_id=None,
        resolution_status=resolution_status,
        resolution_reason=resolution_reason,
        map_source_decision=map_source_decision,
        dispatch_result="blocked",
        capability_limit_summary=capability_limit_summary,
        failure_reason="runtime prerequisite resolution unavailable",
    )
    print("[bbuild] runtime prerequisite resolution blocker", flush=True)
    sys.exit(77)

# Dispatch BuildUnit(commander, armmex, nearest clear metal spot when available).
target, target_reason = choose_build_position("armmex", cmdr, static_map, pre_snap)

def gen():
    batch = commands_pb2.CommandBatch()
    batch.batch_seq = 1
    batch.target_unit_id = cmdr_id
    cmd = batch.commands.add()
    cmd.build_unit.unit_id = cmdr_id
    cmd.build_unit.to_build_unit_def_id = armmex_def_id
    cmd.build_unit.build_position.x = target[0]
    cmd.build_unit.build_position.y = target[1]
    cmd.build_unit.build_position.z = target[2]
    cmd.build_unit.options = 0
    cmd.build_unit.timeout = 0
    yield batch

ack = stub.SubmitCommands(gen(), metadata=metadata, timeout=10)
print(
    f"[bbuild] dispatched BuildUnit armmex "
    f"pos=({target[0]:.1f},{target[1]:.1f},{target[2]:.1f}) "
    f"target_reason={target_reason} accepted={ack.batches_accepted}",
    flush=True,
)

# Sample at t+1s (frame +30), t+3s (+90), t+5s (+150), t+7s (+210), t+9s (+270).
sample_offsets = (
    ("t+1s", 30),
    ("t+3s", 90),
    ("t+5s", 150),
    ("t+7s", 210),
    ("t+9s", 270),
)
sample_frames = [(label, pre_snap.frame_number + off) for label, off in sample_offsets]

def snap_at(min_frame, timeout):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        for _, snap in reversed(shared["snapshots"]):
            if snap.frame_number >= min_frame:
                return snap
        time.sleep(0.2)
    return None

pre_ids = {u.unit_id for u in pre_snap.own_units}
sampled = []
for label, frame in sample_frames:
    snap = snap_at(frame, 10.0)
    if snap is None:
        emit_outcome(
            prerequisite_name="armmex",
            callback_path="InvokeCallback/armmex",
            resolved_def_id=armmex_def_id,
            resolution_status=resolution_status,
            resolution_reason=resolution_reason,
            map_source_decision=map_source_decision,
            dispatch_result="failed",
            capability_limit_summary=capability_limit_summary,
            failure_reason=f"{label} snapshot stall",
        )
        print(f"[bbuild] {label} snapshot stall — fail", flush=True)
        sys.exit(1)
    sampled.append((label, snap))
    log_sample(label, snap, pre_ids, target, armmex_def_id)

selected, _histories = select_new_unit(sampled, pre_ids, target, armmex_def_id)
if selected is None:
    emit_outcome(
        prerequisite_name="armmex",
        callback_path="InvokeCallback/armmex",
        resolved_def_id=armmex_def_id,
        resolution_status=resolution_status,
        resolution_reason=resolution_reason,
        map_source_decision=map_source_decision,
        dispatch_result="failed",
        capability_limit_summary=capability_limit_summary,
        failure_reason="build not started in sample window",
    )
    print("[bbuild] no new construction candidate identified in sample window — fail",
          flush=True)
    sys.exit(1)
if (
    not selected["ever_matching_def"]
    and selected["best_distance"] > 192.0
):
    emit_outcome(
        prerequisite_name="armmex",
        callback_path="InvokeCallback/armmex",
        resolved_def_id=armmex_def_id,
        resolution_status=resolution_status,
        resolution_reason=resolution_reason,
        map_source_decision=map_source_decision,
        dispatch_result="failed",
        capability_limit_summary=capability_limit_summary,
        failure_reason=(
            "no construction candidate near requested build position "
            f"(closest_distance={selected['best_distance']:.1f})"
        ),
    )
    print(
        "[bbuild] no construction candidate near requested build position — fail",
        flush=True,
    )
    sys.exit(1)
print(
    f"[bbuild] selected_unit id={selected['unit_id']} "
    f"first_seen={selected['first_seen']} latest={selected['latest_label']} "
    f"match_def={1 if selected['ever_matching_def'] else 0} "
    f"ever_uc={1 if selected['ever_under_construction'] else 0} "
    f"max_bp={selected['max_build_progress']:.3f} "
    f"best_dist={selected['best_distance']:.1f}",
    flush=True,
)
if not selected["ever_under_construction"]:
    emit_outcome(
        prerequisite_name="armmex",
        callback_path="InvokeCallback/armmex",
        resolved_def_id=armmex_def_id,
        resolution_status=resolution_status,
        resolution_reason=resolution_reason,
        map_source_decision=map_source_decision,
        dispatch_result="failed",
        capability_limit_summary=capability_limit_summary,
        failure_reason="construction candidate never entered under_construction state",
    )
    print("[bbuild] construction candidate never entered under_construction state — fail", flush=True)
    sys.exit(1)

progress_samples = [
    (label, float(getattr(unit, "build_progress", 0.0)))
    for label, unit in (
        (label, selected["units"].get(label))
        for label, _ in sampled
    )
    if unit is not None
]
if len(progress_samples) < 2:
    emit_outcome(
        prerequisite_name="armmex",
        callback_path="InvokeCallback/armmex",
        resolved_def_id=armmex_def_id,
        resolution_status=resolution_status,
        resolution_reason=resolution_reason,
        map_source_decision=map_source_decision,
        dispatch_result="failed",
        capability_limit_summary=capability_limit_summary,
        failure_reason="construction candidate did not persist long enough for verification",
    )
    print("[bbuild] construction candidate did not persist long enough for verification — fail", flush=True)
    sys.exit(1)
start_label, start_progress = progress_samples[0]
end_label, end_progress = progress_samples[-1]
print(
    "[bbuild] progress_samples="
    + ", ".join(f"{label}:{value:.3f}" for label, value in progress_samples),
    flush=True,
)
if end_progress <= start_progress:
    emit_outcome(
        prerequisite_name="armmex",
        callback_path="InvokeCallback/armmex",
        resolved_def_id=armmex_def_id,
        resolution_status=resolution_status,
        resolution_reason=resolution_reason,
        map_source_decision=map_source_decision,
        dispatch_result="failed",
        capability_limit_summary=capability_limit_summary,
        failure_reason=(
            "build_progress not monotonic: "
            f"{start_label}={start_progress:.3f} "
            f"{end_label}={end_progress:.3f}"
        ),
    )
    print(
        f"[bbuild] build_progress not monotonic: "
        f"{start_label}={start_progress:.3f} "
        f"{end_label}={end_progress:.3f}",
        flush=True,
    )
    sys.exit(1)

shared["stop"] = True
emit_outcome(
    prerequisite_name="armmex",
    callback_path="InvokeCallback/armmex",
    resolved_def_id=armmex_def_id,
    resolution_status=resolution_status,
    resolution_reason=resolution_reason,
    map_source_decision=map_source_decision,
    dispatch_result="verified",
    capability_limit_summary=capability_limit_summary,
)
print("[bbuild] PASS")
sys.exit(0)
PYEOF
PY_RC=$?

cat "$CLIENT_LOG"

if [[ $PY_RC -eq 77 ]]; then
    echo "behavioral-build: runtime prerequisite resolution blocker" >&2
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

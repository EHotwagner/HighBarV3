# SPDX-License-Identifier: GPL-2.0-only
"""Behavioral-coverage macro driver entrypoint.

CLI surface (FR-013): `python -m highbar_client.behavioral_coverage`.
Itertesting retry tuning surface:
`python -m highbar_client.behavioral_coverage itertesting --retry-intensity ...`.

Orchestrates Phase 1 (bootstrap plan) and Phase 2 (arm registry
dispatch + verify + reset) and emits the CSV + digest artifacts.

Live-topology helpers (session, state_stream, RequestSnapshot) are
imported lazily so `report.py`-style offline subcommands can run
without a gRPC channel.
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from .bootstrap import (
    BootstrapContext,
    DEFAULT_BOOTSTRAP_PLAN,
    Vector3,
    compute_manifest,
    fixture_classes_for_command,
    is_transport_dependent_command,
    manifest_shortages,
    supported_transport_variants,
)
from .live_failure_classification import is_channel_failure_signal
from .capabilities import CAPABILITY_TAGS
from .registry import REGISTRY, transport_compatibility_for_command, validate_registry
from .report import (
    canonical_digest,
    summarize,
    write_csv,
    write_digest,
)
from .types import (
    BehavioralTestCase,
    CoverageReportError,
    GatewayNotHealthyError,
    NotWireObservable,
    RegistryError,
    SnapshotPair,
    VerificationOutcome,
)
from ..session import TOKEN_HEADER, read_token_with_backoff

def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


class BootstrapExecutionError(RuntimeError):
    def __init__(self, message: str, *, ctx: BootstrapContext | None = None):
        super().__init__(message)
        self.ctx = ctx


# ---- argparse -----------------------------------------------------------


def _parse_args(argv: Optional[list[str]] = None) -> argparse.Namespace:
    ap = argparse.ArgumentParser(
        prog="highbar_client.behavioral_coverage",
        description=(
            "Snapshot-grounded behavioral verification of AICommand arms. "
            "Launches the 66-arm macro driver against a running gRPC "
            "gateway and emits build/reports/aicommand-behavioral-coverage."
            "{csv,digest}."
        ),
    )
    ap.add_argument("--endpoint", default=os.environ.get(
        "HIGHBAR_COORDINATOR", "unix:/tmp/hb-run/hb-coord.sock"),
        help="gRPC endpoint of the coordinator (or plugin server)")
    ap.add_argument("--startscript",
                    default="tests/headless/scripts/minimal.startscript",
                    help="path to the start-script that launched the match")
    ap.add_argument("--gameseed", default="0x42424242",
                    help="gameseed for deterministic runs (FR-008)")
    ap.add_argument("--output-dir", default="build/reports",
                    help="directory to emit the CSV + digest")
    ap.add_argument("--threshold", type=float, default=float(
        os.environ.get("HIGHBAR_BEHAVIORAL_THRESHOLD", "0.50")),
        help="verified-rate threshold (FR-007)")
    ap.add_argument("--run-index", type=int, default=0,
                    help="optional run index for reproducibility (FR-012)")
    ap.add_argument("--skip-live", action="store_true",
                    help="do not connect to a gRPC endpoint; emit a "
                         "dispatched=false / precondition_unmet CSV "
                         "and the derived digest (diagnostic use)")
    return ap.parse_args(argv)


def _collect_dry_rows() -> list[dict]:
    rows: list[dict] = []
    for arm_name, case in sorted(REGISTRY.items()):
        rows.append({
            "arm_name": arm_name,
            "category": case.category,
            "dispatched": "false",
            "verified": "na",
            "evidence": "",
            "error": "precondition_unmet",
        })
    return rows


def _collect_bootstrap_blocked_rows(detail: str, *, error: str = "precondition_unmet") -> list[dict]:
    rows: list[dict] = []
    for arm_name, case in sorted(REGISTRY.items()):
        rows.append(
            {
                "arm_name": arm_name,
                "category": case.category,
                "dispatched": "false",
                "verified": "na",
                "evidence": detail,
                "error": error,
            }
        )
    return rows


def _metadata_row(arm_name: str, **payload: Any) -> dict[str, Any]:
    row = {
        "arm_name": arm_name,
        "category": "metadata",
        "dispatched": "na",
        "verified": "na",
        "evidence": "",
        "error": "",
    }
    row.update(payload)
    return row


def _bootstrap_metadata_rows(ctx: BootstrapContext | None) -> list[dict[str, Any]]:
    if ctx is None:
        return []
    rows: list[dict[str, Any]] = []
    if ctx.bootstrap_readiness:
        rows.append(
            _metadata_row(
                "__bootstrap_readiness__",
                **ctx.bootstrap_readiness,
            )
        )
    if ctx.runtime_capability_profile:
        rows.append(
            _metadata_row(
                "__runtime_capability_profile__",
                **ctx.runtime_capability_profile,
            )
        )
    for item in ctx.callback_diagnostics:
        rows.append(_metadata_row("__callback_diagnostic__", **item))
    for item in ctx.prerequisite_resolution_records:
        rows.append(_metadata_row("__prerequisite_resolution__", **item))
    for item in ctx.map_source_decisions:
        rows.append(_metadata_row("__map_source_decision__", **item))
    return rows


# ---- dry-run (no live engine) -------------------------------------------


def run_dry(threshold: float, output_dir: Path) -> int:
    """Emit a CSV with all rows marked (dispatched=false, verified=na,
    error=precondition_unmet). Used when --skip-live is set OR when
    the orchestrator cannot connect to the gateway. This is legit per
    contracts/bootstrap-plan.md §Execution §Wait timeout fallback.
    """
    rows = _collect_dry_rows()
    csv_path = output_dir / "aicommand-behavioral-coverage.csv"
    digest_path = output_dir / "aicommand-behavioral-coverage.digest"
    write_csv(csv_path, rows)
    tuples = [(r["arm_name"], r["dispatched"], r["verified"], r["error"])
              for r in rows]
    digest = canonical_digest(tuples)
    write_digest(digest_path, digest)
    ok, line = summarize(rows, threshold)
    print(line)
    return 0 if ok else 1


# ---- live-run orchestrator ----------------------------------------------


def _open_channel(endpoint: str):
    import grpc
    return grpc.insecure_channel(endpoint)


def _candidate_token_paths() -> tuple[str, ...]:
    candidates: list[str] = []
    configured = os.environ.get("HIGHBAR_TOKEN_PATH", "").strip()
    if configured:
        candidates.append(configured)
    write_dir = os.environ.get("HIGHBAR_WRITE_DIR", "").strip()
    if write_dir:
        engine_release = os.environ.get("HIGHBAR_ENGINE_RELEASE", "recoil_2025.06.19").strip()
        candidates.extend(
            [
                os.path.join(write_dir, "engine", engine_release, "highbar.token"),
                os.path.join(write_dir, "highbar.token"),
            ]
        )
    runtime_dir = os.environ.get("XDG_RUNTIME_DIR", "").strip()
    if runtime_dir:
        candidates.append(os.path.join(runtime_dir, "highbar.token"))
    candidates.append("/tmp/highbar.token")
    deduped: list[str] = []
    for path in candidates:
        if path and path not in deduped:
            deduped.append(path)
    return tuple(deduped)


def _load_ai_token() -> str:
    candidates = _candidate_token_paths()
    if not candidates:
        raise RuntimeError(
            "HIGHBAR_TOKEN_PATH or HIGHBAR_WRITE_DIR must be set for AI-role RPC auth"
        )
    last_error: Exception | None = None
    for path in candidates:
        try:
            return read_token_with_backoff(path, max_delay_ms=5000)
        except Exception as exc:  # noqa: BLE001
            last_error = exc
    assert last_error is not None
    raise RuntimeError(f"unable to load AI token from {candidates}: {last_error}")


def _hello_ai(channel, client_id: str, token: str | None = None):
    from ..highbar import service_pb2, service_pb2_grpc
    stub = service_pb2_grpc.HighBarProxyStub(channel)
    req = service_pb2.HelloRequest(
        schema_version="1.0.0",
        client_id=client_id,
        role=service_pb2.Role.ROLE_AI,
    )
    metadata = [(TOKEN_HEADER, token)] if token else None
    return stub, stub.Hello(req, metadata=metadata, timeout=5.0)


def _start_state_stream(stub):
    """Start a thread that continuously drains StateState into a
    bounded rolling buffer. Returns (shared, thread).
    """
    import threading
    from ..highbar import service_pb2

    shared = {"snapshots": [], "deltas": [], "stop": False, "err": None}

    def worker():
        try:
            for upd in stub.StreamState(
                    service_pb2.StreamStateRequest(resume_from_seq=0),
                    timeout=600.0):
                if shared["stop"]:
                    return
                kind = upd.WhichOneof("payload")
                if kind == "snapshot":
                    shared["snapshots"].append(upd.snapshot)
                    # Bounded buffer — keep last 200 snapshots.
                    if len(shared["snapshots"]) > 200:
                        del shared["snapshots"][:100]
                elif kind == "delta":
                    for ev in upd.delta.events:
                        shared["deltas"].append(ev)
                    if len(shared["deltas"]) > 5000:
                        del shared["deltas"][:2500]
        except Exception as e:  # noqa: BLE001 — diagnostic capture
            shared["err"] = repr(e)

    t = threading.Thread(target=worker, daemon=True)
    t.start()
    return shared, t


def _wait_for_snapshot(shared: dict, min_frame: int,
                        timeout_s: float) -> Optional[Any]:
    end = time.monotonic() + timeout_s
    while time.monotonic() < end:
        for s in reversed(shared["snapshots"]):
            if s.frame_number >= min_frame:
                return s
        time.sleep(0.1)
    return None


def _request_snapshot(stub, token: str | None = None) -> int:
    """Force a snapshot. Returns scheduled_frame (0 on not-healthy)."""
    from ..highbar import service_pb2
    try:
        resp = stub.RequestSnapshot(
            service_pb2.RequestSnapshotRequest(),
            metadata=[(TOKEN_HEADER, token)] if token else None,
            timeout=2.0,
        )
        return resp.scheduled_frame
    except Exception:  # noqa: BLE001 — coordinator may not implement it
        return 0


def _dispatch(stub, batch, token: Optional[str] = None):
    """One-shot SubmitCommands with a single batch."""
    from ..highbar import service_pb2, service_pb2_grpc  # noqa
    import grpc
    md = []
    if token is not None:
        md.append(("x-highbar-ai-token", token))

    def gen():
        yield batch

    return stub.SubmitCommands(gen(), metadata=md, timeout=10.0)


def _row_for_outcome(case: BehavioralTestCase,
                      dispatched: bool,
                      outcome: VerificationOutcome) -> dict:
    return {
        "arm_name": case.arm_name,
        "category": case.category,
        "dispatched": "true" if dispatched else "false",
        "verified": outcome.verified,
        "evidence": outcome.evidence,
        "error": outcome.error,
    }


_FIXTURE_HEALTH_HINTS = {
    "builder": 690.0,
    "cloakable": 89.0,
    "factory_air": 2050.0,
    "transport_unit": 265.0,
}

_DERIVED_CAPABILITY_UNITS = frozenset({"builder", "cloakable", "factory_air"})
_DERIVED_FIXTURE_UNITS = frozenset(
    {
        "builder",
        "cloakable",
        "transport_unit",
        "payload_unit",
        "damaged_friendly",
        "hostile_target",
        "capturable_target",
        "custom_target",
    }
)
_DERIVED_FIXTURE_FEATURES = frozenset({"reclaim_target", "wreck_target"})
_DERIVED_FIXTURE_POSITIONS = frozenset(
    {
        "builder",
        "cloakable",
        "factory_air",
        "transport_unit",
        "payload_unit",
        "damaged_friendly",
        "hostile_target",
        "capturable_target",
        "custom_target",
        "reclaim_target",
        "wreck_target",
        "restore_target",
    }
)


def _vector3_from_position(position: Any) -> Vector3:
    return Vector3(
        x=float(getattr(position, "x", 0.0)),
        y=float(getattr(position, "y", 0.0)),
        z=float(getattr(position, "z", 0.0)),
    )


def _format_vector3(position: Vector3) -> str:
    return f"({position.x:.1f},{position.y:.1f},{position.z:.1f})"


def _distance_sq(a: Vector3, b: Vector3) -> float:
    dx = a.x - b.x
    dy = a.y - b.y
    dz = a.z - b.z
    return dx * dx + dy * dy + dz * dz


def _position_is_clear(
    candidate: Vector3,
    *,
    snapshot: Any | None = None,
    ignore_unit_ids: set[int] | None = None,
    clearance_radius: float = 96.0,
) -> bool:
    if snapshot is None:
        return True
    ignore_unit_ids = ignore_unit_ids or set()
    clearance_sq = clearance_radius * clearance_radius
    for unit in getattr(snapshot, "own_units", ()):
        if getattr(unit, "unit_id", 0) in ignore_unit_ids:
            continue
        if _distance_sq(candidate, _vector3_from_position(unit.position)) < clearance_sq:
            return False
    for feature in getattr(snapshot, "map_features", ()):
        if _distance_sq(candidate, _vector3_from_position(feature.position)) < clearance_sq:
            return False
    return True


def _find_clear_build_position(
    desired: Vector3,
    *,
    snapshot: Any | None = None,
    ignore_unit_ids: set[int] | None = None,
    clearance_radius: float,
    search_step: float = 128.0,
    max_ring: int = 4,
) -> Vector3:
    if _position_is_clear(
        desired,
        snapshot=snapshot,
        ignore_unit_ids=ignore_unit_ids,
        clearance_radius=clearance_radius,
    ):
        return desired
    for ring in range(1, max_ring + 1):
        offsets: list[tuple[float, float]] = []
        extent = ring * search_step
        for dx in range(-ring, ring + 1):
            offsets.append((dx * search_step, -extent))
            offsets.append((dx * search_step, extent))
        for dz in range(-ring + 1, ring):
            offsets.append((-extent, dz * search_step))
            offsets.append((extent, dz * search_step))
        for dx, dz in offsets:
            candidate = Vector3(x=desired.x + dx, y=desired.y, z=desired.z + dz)
            if _position_is_clear(
                candidate,
                snapshot=snapshot,
                ignore_unit_ids=ignore_unit_ids,
                clearance_radius=clearance_radius,
            ):
                return candidate
    return desired


def _position_for_bootstrap_step(
    step: Any,
    commander_position: Vector3,
    *,
    static_map: Any | None = None,
    snapshot: Any | None = None,
    ignore_unit_ids: set[int] | None = None,
) -> Vector3:
    if step.def_id == "armmex" and static_map is not None:
        metal_spots = tuple(getattr(static_map, "metal_spots", ()) or ())
        if metal_spots:
            ordered_spots = sorted(
                metal_spots,
                key=lambda spot: _distance_sq(
                    _vector3_from_position(spot),
                    commander_position,
                ),
            )
            for spot in ordered_spots:
                spot_position = _vector3_from_position(spot)
                if _position_is_clear(
                    spot_position,
                    snapshot=snapshot,
                    ignore_unit_ids=ignore_unit_ids,
                ):
                    return spot_position
            return _vector3_from_position(ordered_spots[0])
    desired = Vector3(
        x=commander_position.x + step.relative_position.x,
        y=commander_position.y + step.relative_position.y,
        z=commander_position.z + step.relative_position.z,
    )
    clearance_radius = 96.0
    if getattr(step, "capability", "") in {"factory_ground", "factory_air"}:
        clearance_radius = 192.0
    elif getattr(step, "capability", "") in {"solar", "radar"}:
        clearance_radius = 128.0
    return _find_clear_build_position(
        desired,
        snapshot=snapshot,
        ignore_unit_ids=ignore_unit_ids,
        clearance_radius=clearance_radius,
    )


def _find_commander(snapshot: Any) -> Any | None:
    commander = None
    for unit in getattr(snapshot, "own_units", ()):
        if unit.max_health > 3000.0 and (
            commander is None or unit.max_health > commander.max_health
        ):
            commander = unit
    return commander


def _matches_health(unit: Any, expected: float) -> bool:
    return abs(float(getattr(unit, "max_health", 0.0)) - expected) <= 1.0


def _unit_is_alive(unit: Any) -> bool:
    return float(getattr(unit, "health", 0.0)) > 0.0


def _unit_is_under_construction(unit: Any) -> bool:
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


def _unit_is_ready_fixture_unit(unit: Any) -> bool:
    return _unit_is_alive(unit) and not _unit_is_under_construction(unit)


def _transport_variant_identity(unit: Any, ctx: BootstrapContext) -> str | None:
    resolved_by_name = {
        variant.def_name: ctx.def_id_by_name.get(variant.def_name, 0)
        for variant in supported_transport_variants()
    }
    for variant in sorted(supported_transport_variants(), key=lambda item: item.priority):
        resolved_def_id = resolved_by_name.get(variant.def_name, 0)
        if resolved_def_id and getattr(unit, "def_id", 0) == resolved_def_id:
            return variant.variant_id
    if _matches_health(unit, _FIXTURE_HEALTH_HINTS["transport_unit"]):
        return "armatlas"
    return None


def _transport_variant_unit(unit: Any, ctx: BootstrapContext) -> tuple[str, Any] | None:
    variant_id = _transport_variant_identity(unit, ctx)
    if variant_id is None or not _unit_is_ready_fixture_unit(unit):
        return None
    return variant_id, unit


def _matches_factory_air(unit: Any, ctx: BootstrapContext) -> bool:
    factory_air_def_id = ctx.def_id_by_name.get("armap", 0)
    if factory_air_def_id:
        return getattr(unit, "def_id", 0) == factory_air_def_id
    return _matches_health(unit, _FIXTURE_HEALTH_HINTS["factory_air"])


def _clear_derived_live_context(ctx: BootstrapContext) -> None:
    for key in _DERIVED_CAPABILITY_UNITS:
        ctx.capability_units.pop(key, None)
    for key in _DERIVED_FIXTURE_UNITS:
        ctx.fixture_unit_ids.pop(key, None)
    for key in _DERIVED_FIXTURE_FEATURES:
        ctx.fixture_feature_ids.pop(key, None)
    for key in _DERIVED_FIXTURE_POSITIONS:
        ctx.fixture_positions.pop(key, None)
    ctx.enemy_seed_id = None
    ctx.observed_own_units = {}


def _select_payload_candidate(
    own_units: list[Any],
    ctx: BootstrapContext,
) -> Any | None:
    transport_id = ctx.fixture_unit_ids.get("transport_unit")
    ready_units = [
        unit
        for unit in own_units
        if _unit_is_ready_fixture_unit(unit) and unit.unit_id != transport_id
    ]
    if not ready_units:
        return None

    builder_id = ctx.capability_units.get("builder") or ctx.fixture_unit_ids.get("builder")
    if builder_id:
        for unit in ready_units:
            if unit.unit_id == builder_id:
                return unit

    non_cloakable = [
        unit
        for unit in ready_units
        if not _matches_health(unit, _FIXTURE_HEALTH_HINTS["cloakable"])
    ]
    candidates = non_cloakable or ready_units
    return min(
        candidates,
        key=lambda item: (
            float(getattr(item, "max_health", 0.0)) <= 0.0,
            float(getattr(item, "max_health", 0.0)),
            item.unit_id,
        ),
    )


def _build_unit_batch(builder_unit_id: int, build_def_id: int, position: Vector3):
    from ..highbar import commands_pb2

    batch = commands_pb2.CommandBatch()
    batch.batch_seq = 1
    batch.target_unit_id = builder_unit_id
    cmd = batch.commands.add()
    cmd.build_unit.unit_id = builder_unit_id
    cmd.build_unit.to_build_unit_def_id = build_def_id
    cmd.build_unit.build_position.x = position.x
    cmd.build_unit.build_position.y = position.y
    cmd.build_unit.build_position.z = position.z
    return batch


def _transport_build_batch(factory_unit_id: int, transport_def_id: int, position: Vector3):
    return _build_unit_batch(
        factory_unit_id,
        transport_def_id,
        Vector3(
            x=position.x + 96.0,
            y=position.y,
            z=position.z + 96.0,
        ),
    )


def _latest_snapshot(shared: dict) -> Any | None:
    snapshots = shared.get("snapshots") or ()
    if not snapshots:
        return None
    return snapshots[-1]


def _refreshing_snapshot(
    stub: Any,
    shared: dict,
    *,
    token: str | None = None,
    timeout_s: float = 5.0,
) -> Any | None:
    latest = _latest_snapshot(shared)
    min_frame = (getattr(latest, "frame_number", 0) if latest is not None else 0) + 1
    scheduled_frame = _request_snapshot(stub, token=token)
    if scheduled_frame > 0:
        min_frame = max(min_frame, scheduled_frame)
    snapshot = _wait_for_snapshot(shared, min_frame=min_frame, timeout_s=timeout_s)
    if snapshot is not None:
        return snapshot
    return _latest_snapshot(shared)


def _new_units_for_def(snapshot: Any, def_id: int, baseline_ids: set[int]) -> list[Any]:
    return [
        unit
        for unit in getattr(snapshot, "own_units", ())
        if getattr(unit, "def_id", 0) == def_id and unit.unit_id not in baseline_ids
    ]


def _ready_units_for_def(snapshot: Any, def_id: int) -> list[Any]:
    return [
        unit
        for unit in getattr(snapshot, "own_units", ())
        if getattr(unit, "def_id", 0) == def_id and _unit_is_ready_fixture_unit(unit)
    ]


def _wait_for_new_ready_unit(
    shared: dict,
    *,
    def_id: int,
    baseline_ids: set[int],
    timeout_s: float,
    stub: Any | None = None,
    token: str | None = None,
) -> Any:
    deadline = time.monotonic() + timeout_s
    saw_new_candidate = False
    latest = _latest_snapshot(shared)
    min_frame = (getattr(latest, "frame_number", 0) if latest is not None else 0) + 1
    refresh_due = 0.0
    while time.monotonic() < deadline:
        now = time.monotonic()
        if stub is not None and now >= refresh_due:
            _request_snapshot(stub, token=token)
            refresh_due = now + 0.5
        snapshot = _wait_for_snapshot(
            shared,
            min_frame=min_frame,
            timeout_s=min(1.0, max(0.1, deadline - time.monotonic())),
        )
        if snapshot is None:
            snapshot = _latest_snapshot(shared)
        if snapshot is None:
            continue
        min_frame = getattr(snapshot, "frame_number", 0) + 1
        new_units = _new_units_for_def(snapshot, def_id, baseline_ids)
        if new_units:
            saw_new_candidate = True
        ready_units = [
            unit
            for unit in new_units
            if _unit_is_ready_fixture_unit(unit)
        ]
        if ready_units:
            return min(ready_units, key=lambda item: item.unit_id)
    state = "saw_new_candidate=1" if saw_new_candidate else "saw_new_candidate=0"
    raise RuntimeError(f"timeout waiting for new ready unit def_id={def_id} {state}")


def _issue_bootstrap_build_step(
    stub: Any,
    shared: dict,
    ctx: BootstrapContext,
    step: Any,
    *,
    builder_unit_id: int,
    target_position: Vector3,
    baseline_ids: set[int],
    token: str | None = None,
    static_map: Any | None = None,
    failure_snapshot: Any | None = None,
) -> Any:
    resolved_def_id = ctx.def_id_by_name.get(step.def_id, 0)
    if not resolved_def_id:
        raise RuntimeError(f"runtime def id for {step.def_id} was not resolved")
    _dispatch(
        stub,
        _build_unit_batch(builder_unit_id, resolved_def_id, target_position),
        token=token,
    )
    try:
        return _wait_for_new_ready_unit(
            shared,
            def_id=resolved_def_id,
            baseline_ids=baseline_ids,
            timeout_s=step.timeout_seconds,
            stub=stub,
            token=token,
        )
    except RuntimeError as exc:
        metal_spots = tuple(getattr(static_map, "metal_spots", ()) or ())
        metal_detail = (
            f" metal_spots={len(metal_spots)}"
            if step.def_id == "armmex"
            else ""
        )
        commander_detail = ""
        if getattr(step, "builder_capability", "") == "commander":
            commander_detail = " " + _commander_build_context_debug(
                stub,
                ctx,
                snapshot=failure_snapshot or _latest_snapshot(shared),
                token=token,
            )
        raise RuntimeError(
            f"{step.capability}/{step.def_id} "
            f"builder={step.builder_capability} "
            f"builder_unit_id={builder_unit_id} "
            f"build_pos={_format_vector3(target_position)}"
            f"{metal_detail} "
            f"{commander_detail}"
            f"{exc}"
        ) from exc


def _can_skip_bootstrap_step_failure(
    step: Any,
    exc: RuntimeError,
    ctx: BootstrapContext | None = None,
) -> bool:
    capability = getattr(step, "capability", "")
    if capability in {"mex", "solar", "radar"}:
        return "saw_new_candidate=0" in str(exc)

    # Prepared live closeout can already contain the downstream units we
    # historically built these factories for. In that state, rebuilding a
    # missing factory is diagnostic detail, not a prerequisite for
    # commander-centric command coverage.
    if ctx is None:
        return False
    if capability == "factory_ground":
        return bool(
            ctx.capability_units.get("builder")
            or ctx.fixture_unit_ids.get("builder")
        )
    if capability == "factory_air":
        return bool(
            ctx.capability_units.get("cloakable")
            or ctx.fixture_unit_ids.get("cloakable")
        )
    return False


def _wait_for_manifest_match(
    shared: dict,
    ctx: BootstrapContext,
    *,
    timeout_s: float,
) -> Any:
    deadline = time.monotonic() + timeout_s
    latest = _latest_snapshot(shared)
    min_frame = (getattr(latest, "frame_number", 0) if latest is not None else 0) + 1
    while time.monotonic() < deadline:
        snapshot = _wait_for_snapshot(
            shared,
            min_frame=min_frame,
            timeout_s=min(1.0, max(0.1, deadline - time.monotonic())),
        )
        if snapshot is None:
            snapshot = _latest_snapshot(shared)
        if snapshot is None:
            continue
        min_frame = getattr(snapshot, "frame_number", 0) + 1
        current = compute_manifest(getattr(snapshot, "own_units", ()), ctx.def_id_by_name)
        if not manifest_shortages(current, ctx.manifest):
            return snapshot
    raise RuntimeError("timeout waiting for bootstrap manifest to be restored")


def _invoke_callback(
    stub: Any,
    callback_id: int,
    *,
    request_id: int = 1,
    params: tuple[Any, ...] = (),
    token: str | None = None,
) -> Any:
    from ..highbar import callbacks_pb2

    return stub.InvokeCallback(
        callbacks_pb2.CallbackRequest(
            request_id=request_id,
            callback_id=callback_id,
            params=params,
        ),
        metadata=[(TOKEN_HEADER, token)] if token else None,
        timeout=5.0,
    )


def _callback_int_value(response: Any) -> int | None:
    if not getattr(response, "success", False):
        return None
    result = getattr(response, "result", None)
    if result is None or not result.HasField("int_value"):
        return None
    return int(result.int_value)


def _callback_string_value(response: Any) -> str | None:
    if not getattr(response, "success", False):
        return None
    result = getattr(response, "result", None)
    if result is None or not result.HasField("string_value"):
        return None
    return str(result.string_value)


def _callback_int_array(response: Any) -> tuple[int, ...] | None:
    if not getattr(response, "success", False):
        return None
    result = getattr(response, "result", None)
    if result is None or not result.HasField("int_array_value"):
        return None
    return tuple(int(value) for value in result.int_array_value.values)


def _economy_debug_string(snapshot: Any | None) -> str:
    economy = getattr(snapshot, "economy", None)
    if economy is None:
        return "economy=unknown"
    return (
        "economy="
        f"metal:{float(getattr(economy, 'metal', 0.0)):.1f}/"
        f"{float(getattr(economy, 'metal_income', 0.0)):.1f}/"
        f"{float(getattr(economy, 'metal_storage', 0.0)):.1f} "
        f"energy:{float(getattr(economy, 'energy', 0.0)):.1f}/"
        f"{float(getattr(economy, 'energy_income', 0.0)):.1f}/"
        f"{float(getattr(economy, 'energy_storage', 0.0)):.1f}"
    )


def _economy_obviously_starved(snapshot: Any | None) -> bool:
    economy = getattr(snapshot, "economy", None)
    if economy is None:
        return False
    metal = float(getattr(economy, "metal", 0.0))
    metal_income = float(getattr(economy, "metal_income", 0.0))
    return metal < 1.0 and metal_income <= 0.0


def _record_bootstrap_readiness(
    ctx: BootstrapContext,
    *,
    readiness_status: str,
    readiness_path: str,
    first_required_step: str,
    economy_summary: str,
    reason: str,
) -> None:
    ctx.bootstrap_readiness = {
        "run_id": "live-closeout",
        "readiness_status": readiness_status,
        "readiness_path": readiness_path,
        "first_required_step": first_required_step,
        "economy_summary": economy_summary,
        "reason": reason,
        "recorded_at": _utc_now_iso(),
    }


def _record_callback_diagnostic(
    ctx: BootstrapContext,
    *,
    capture_stage: str,
    availability_status: str,
    source: str,
    diagnostic_scope: tuple[str, ...],
    summary: str,
) -> None:
    ctx.callback_diagnostics.append(
        {
            "snapshot_id": f"callback-{len(ctx.callback_diagnostics) + 1:02d}",
            "capture_stage": capture_stage,
            "availability_status": availability_status,
            "source": source,
            "diagnostic_scope": diagnostic_scope,
            "summary": summary,
            "captured_at": _utc_now_iso(),
        }
    )


def _runtime_capability_notes(payload: dict[str, Any]) -> str:
    scopes = ", ".join(payload.get("supported_scopes", ())) or "none"
    unsupported = ", ".join(payload.get("unsupported_callback_groups", ())) or "none"
    map_status = payload.get("map_data_source_status", "missing")
    return (
        f"supported scopes: {scopes}; "
        f"unsupported groups: {unsupported}; "
        f"map source: {map_status}"
    )


def _update_runtime_capability_profile(
    ctx: BootstrapContext,
    *,
    supported_callbacks: tuple[int, ...] = (),
    supported_scopes: tuple[str, ...] = (),
    unsupported_callback_groups: tuple[str, ...] = (),
    map_data_source_status: str | None = None,
    notes: str | None = None,
) -> None:
    payload = dict(ctx.runtime_capability_profile or {})
    payload.setdefault("profile_id", "runtime-capability-profile")
    payload["supported_callbacks"] = sorted(
        {
            *(payload.get("supported_callbacks", ())),
            *supported_callbacks,
        }
    )
    payload["supported_scopes"] = sorted(
        {
            *(payload.get("supported_scopes", ())),
            *supported_scopes,
        }
    )
    payload["unsupported_callback_groups"] = sorted(
        {
            *(payload.get("unsupported_callback_groups", ())),
            *unsupported_callback_groups,
        }
    )
    if map_data_source_status is not None:
        payload["map_data_source_status"] = map_data_source_status
    else:
        payload.setdefault("map_data_source_status", "missing")
    payload["notes"] = notes or _runtime_capability_notes(payload)
    payload["recorded_at"] = _utc_now_iso()
    callbacks = "-".join(str(item) for item in payload["supported_callbacks"]) or "none"
    payload["profile_id"] = (
        f"runtime-capability-{callbacks}-{payload['map_data_source_status']}"
    )
    ctx.runtime_capability_profile = payload


def _record_prerequisite_resolution(
    ctx: BootstrapContext,
    *,
    prerequisite_name: str,
    consumer: str,
    callback_path: str,
    resolved_def_id: int | None,
    resolution_status: str,
    reason: str,
) -> None:
    ctx.prerequisite_resolution_records.append(
        {
            "prerequisite_name": prerequisite_name,
            "consumer": consumer,
            "callback_path": callback_path,
            "resolved_def_id": resolved_def_id,
            "resolution_status": resolution_status,
            "reason": reason,
            "recorded_at": _utc_now_iso(),
        }
    )


def _record_map_source_decision(
    ctx: BootstrapContext,
    *,
    consumer: str,
    selected_source: str,
    metal_spot_count: int,
    reason: str,
) -> None:
    ctx.map_source_decisions.append(
        {
            "consumer": consumer,
            "selected_source": selected_source,
            "metal_spot_count": metal_spot_count,
            "reason": reason,
            "recorded_at": _utc_now_iso(),
        }
    )


def _record_live_closeout_map_source(
    ctx: BootstrapContext,
    *,
    static_map: Any | None,
) -> None:
    metal_spots = tuple(getattr(static_map, "metal_spots", ()) or ())
    if metal_spots:
        _record_map_source_decision(
            ctx,
            consumer="live_closeout",
            selected_source="hello_static_map",
            metal_spot_count=len(metal_spots),
            reason=(
                "used HelloResponse.static_map because callback map inspection is "
                "unsupported or unnecessary on this host"
            ),
        )
        _update_runtime_capability_profile(
            ctx,
            supported_scopes=("session_start_map",),
            map_data_source_status="hello_static_map",
        )
        return
    _record_map_source_decision(
        ctx,
        consumer="live_closeout",
        selected_source="missing",
        metal_spot_count=0,
        reason="session-start map payload unavailable for live bootstrap targeting",
    )
    _update_runtime_capability_profile(
        ctx,
        map_data_source_status="missing",
    )


def _capture_callback_diagnostic(
    stub: Any,
    shared: dict,
    ctx: BootstrapContext,
    *,
    capture_stage: str,
    token: str | None = None,
) -> None:
    summary = _commander_build_context_debug(
        stub,
        ctx,
        snapshot=_latest_snapshot(shared),
        token=token,
    )
    if summary.startswith("commander_diag_error="):
        _update_runtime_capability_profile(
            ctx,
            unsupported_callback_groups=("unit", "unitdef_except_name"),
            notes=(
                "callback-limited host preserved unit-def lookup while commander "
                "and build-option diagnostics were unavailable"
            ),
        )
        if ctx.callback_diagnostics:
            _record_callback_diagnostic(
                ctx,
                capture_stage=capture_stage,
                availability_status="cached",
                source="preserved_earlier_capture",
                diagnostic_scope=("commander_def", "build_options", "economy"),
                summary=f"late callback refresh unavailable; preserved earlier capture after: {summary}",
            )
            return
        _record_callback_diagnostic(
            ctx,
            capture_stage=capture_stage,
            availability_status="missing",
            source="not_available",
            diagnostic_scope=("commander_def", "build_options", "economy"),
            summary=summary,
        )
        return
    _update_runtime_capability_profile(
        ctx,
        supported_callbacks=(23, 42),
        supported_scopes=("unit", "unitdef_build_options"),
    )
    _record_callback_diagnostic(
        ctx,
        capture_stage=capture_stage,
        availability_status="live",
        source="invoke_callback_live",
        diagnostic_scope=("commander_def", "build_options", "economy"),
        summary=summary,
    )


def _assess_bootstrap_readiness(
    starting_snapshot: Any,
    ctx: BootstrapContext,
) -> tuple[str, str, str, str]:
    commander_steps = tuple(
        step for step in DEFAULT_BOOTSTRAP_PLAN if step.builder_capability == "commander"
    )
    preexisting_steps = [
        step.def_id
        for step in commander_steps
        if _ready_units_for_def(starting_snapshot, ctx.def_id_by_name.get(step.def_id, 0))
    ]
    missing_steps = [
        step
        for step in commander_steps
        if not _ready_units_for_def(starting_snapshot, ctx.def_id_by_name.get(step.def_id, 0))
    ]
    first_missing_step = next(
        iter(missing_steps),
        None,
    )
    first_required_step = next(
        (
            step
            for step in missing_steps
            if not _can_skip_bootstrap_step_failure(
                step,
                RuntimeError("timeout waiting for new ready unit def_id=0 saw_new_candidate=0"),
                ctx,
            )
        ),
        None,
    )
    economy_summary = _economy_debug_string(starting_snapshot)
    if first_missing_step is None:
        return (
            "seeded_ready" if preexisting_steps else "natural_ready",
            "explicit_seed" if preexisting_steps else "prepared_state",
            commander_steps[0].def_id if commander_steps else "armmex",
            (
                "prepared live start already contained commander-built bootstrap fixtures: "
                + ", ".join(preexisting_steps)
                if preexisting_steps
                else "prepared live start already satisfied commander-built bootstrap requirements"
            ),
        )
    if first_required_step is None:
        optional_missing = ", ".join(step.def_id for step in missing_steps)
        return (
            "natural_ready",
            "prepared_state",
            first_missing_step.def_id,
            (
                "prepared live state can continue despite optional commander-built gaps: "
                f"{optional_missing}"
            ),
        )
    if _economy_obviously_starved(starting_snapshot):
        return (
            "resource_starved",
            "unavailable",
            first_required_step.def_id,
            f"first commander-built bootstrap step {first_required_step.def_id} would start from a resource-starved state",
        )
    return (
        "natural_ready",
        "prepared_state",
        first_required_step.def_id,
        f"prepared live state can start commander bootstrap at {first_required_step.def_id}",
    )


def _commander_build_context_debug(
    stub: Any,
    ctx: BootstrapContext,
    *,
    snapshot: Any | None = None,
    token: str | None = None,
) -> str:
    from ..highbar import callbacks_pb2

    try:
        commander_def_resp = _invoke_callback(
            stub,
            callbacks_pb2.CALLBACK_UNIT_GET_DEF,
            request_id=200,
            params=(callbacks_pb2.CallbackParam(int_value=int(ctx.commander_unit_id)),),
            token=token,
        )
        commander_def_id = _callback_int_value(commander_def_resp)
        if not commander_def_id:
            return f"commander_def=unresolved {_economy_debug_string(snapshot)}"
        commander_name_resp = _invoke_callback(
            stub,
            callbacks_pb2.CALLBACK_UNITDEF_GET_NAME,
            request_id=201,
            params=(callbacks_pb2.CallbackParam(int_value=commander_def_id),),
            token=token,
        )
        commander_name = _callback_string_value(commander_name_resp) or f"def#{commander_def_id}"
        build_options_resp = _invoke_callback(
            stub,
            callbacks_pb2.CALLBACK_UNITDEF_GET_BUILD_OPTIONS,
            request_id=202,
            params=(callbacks_pb2.CallbackParam(int_value=commander_def_id),),
            token=token,
        )
        build_options = set(_callback_int_array(build_options_resp) or ())
        bootstrap_option_state = ",".join(
            f"{name}:{1 if ctx.def_id_by_name.get(name, 0) in build_options else 0}"
            for name in ("armmex", "armsolar", "armvp", "armap", "armrad")
            if ctx.def_id_by_name.get(name, 0)
        ) or "none"
        return (
            f"commander_def={commander_name} "
            f"commander_builds={bootstrap_option_state} "
            f"{_economy_debug_string(snapshot)}"
        )
    except Exception as exc:  # noqa: BLE001
        return f"commander_diag_error={exc} {_economy_debug_string(snapshot)}"


def _transport_debug_snapshot(ctx: BootstrapContext) -> str:
    factory_air_id = ctx.capability_units.get("factory_air")
    ready_transport_id = ctx.fixture_unit_ids.get("transport_unit")
    ready_transport_variant = None
    if ready_transport_id:
        observed = ctx.observed_own_units.get(ready_transport_id)
        if observed is not None:
            ready_transport_variant = _transport_variant_identity(observed, ctx)
    resolved_variants = ",".join(
        f"{variant.variant_id}:{'1' if ctx.def_id_by_name.get(variant.def_name, 0) else '0'}"
        for variant in supported_transport_variants()
    )
    attempts = ",".join(
        f"{variant_id}:{state}"
        for variant_id, state in sorted(ctx.transport_build_requests.items())
    ) or "none"
    pending_variants = ",".join(
        sorted(
            variant_id
            for unit in ctx.observed_own_units.values()
            for variant_id in (_transport_variant_identity(unit, ctx),)
            if variant_id is not None and _unit_is_under_construction(unit)
        )
    ) or "none"
    ready = (
        f"{ready_transport_variant or 'unknown'}#{ready_transport_id}"
        if ready_transport_id
        else "none"
    )
    return (
        "transport_debug "
        f"factory_air={'present' if factory_air_id else 'absent'} "
        f"resolved_defs={resolved_variants} "
        f"build_attempts={attempts} "
        f"pending={pending_variants} "
        f"ready={ready}"
    )


def _set_transport_debug(ctx: BootstrapContext, *details: str) -> None:
    snapshot = _transport_debug_snapshot(ctx)
    detail_suffix = " ".join(part for part in details if part)
    ctx.transport_diagnostics = [snapshot if not detail_suffix else f"{snapshot} {detail_suffix}"]


def _wait_for_transport_fixture(
    shared: dict,
    ctx: BootstrapContext,
    timeout_s: float,
) -> BootstrapContext:
    end = time.monotonic() + timeout_s
    while time.monotonic() < end:
        refreshed = _refresh_bootstrap_context(shared, ctx)
        if refreshed.fixture_unit_ids.get("transport_unit"):
            _set_transport_debug(refreshed, "transport_ready_after_wait=1")
            return refreshed
        time.sleep(0.5)
    refreshed = _refresh_bootstrap_context(shared, ctx)
    _set_transport_debug(refreshed, "transport_ready_after_wait=0")
    return refreshed


def _attempt_transport_provisioning(
    stub: Any,
    shared: dict,
    ctx: BootstrapContext,
    *,
    wait_timeout_s: float = 0.0,
    token: str | None = None,
) -> BootstrapContext:
    ctx = _refresh_bootstrap_context(shared, ctx)
    if ctx.fixture_unit_ids.get("transport_unit"):
        _set_transport_debug(ctx, "provisioning_action=reuse_ready_candidate")
        return ctx

    snapshot = shared["snapshots"][-1] if shared.get("snapshots") else None
    if snapshot is None:
        _set_transport_debug(ctx, "provisioning_action=no_snapshot")
        return ctx

    own_units = [
        unit
        for unit in getattr(snapshot, "own_units", ())
        if unit.unit_id != ctx.commander_unit_id
    ]
    pending_variants = {
        variant_id
        for unit in own_units
        for variant_id in (_transport_variant_identity(unit, ctx),)
        if variant_id is not None and _unit_is_under_construction(unit)
    }
    if pending_variants:
        for variant_id in pending_variants:
            ctx.transport_build_requests[variant_id] = "pending"
        if wait_timeout_s > 0.0:
            _set_transport_debug(
                ctx,
                "provisioning_action=wait_pending_candidate",
                f"pending_candidates={','.join(sorted(pending_variants))}",
            )
            return _wait_for_transport_fixture(shared, ctx, wait_timeout_s)
        _set_transport_debug(
            ctx,
            "provisioning_action=pending_candidate_present",
            f"pending_candidates={','.join(sorted(pending_variants))}",
        )
        return ctx

    factory_air_id = ctx.capability_units.get("factory_air")
    factory_air_unit = ctx.observed_own_units.get(factory_air_id or 0)
    if factory_air_unit is None or not _unit_is_ready_fixture_unit(factory_air_unit):
        _set_transport_debug(ctx, "provisioning_action=no_ready_factory_air")
        return ctx

    attempted_variant = None
    for variant in sorted(supported_transport_variants(), key=lambda item: item.priority):
        transport_def_id = ctx.def_id_by_name.get(variant.def_name, 0)
        if not transport_def_id:
            continue
        if ctx.transport_build_requests.get(variant.variant_id) in {
            "dispatched",
            "pending",
            "ready",
            "dispatch_failed",
            "dispatched_waited_no_ready_transport",
        }:
            continue
        try:
            _dispatch(
                stub,
                _transport_build_batch(
                    factory_air_id,
                    transport_def_id,
                    _vector3_from_position(factory_air_unit.position),
                ),
                token=token,
            )
        except Exception:  # noqa: BLE001
            ctx.transport_build_requests[variant.variant_id] = "dispatch_failed"
            _set_transport_debug(
                ctx,
                "provisioning_action=dispatch_failed",
                f"attempted_variant={variant.variant_id}",
            )
            continue
        attempted_variant = variant.variant_id
        ctx.transport_build_requests[variant.variant_id] = "dispatched"
        if wait_timeout_s > 0.0:
            _set_transport_debug(
                ctx,
                "provisioning_action=dispatch_and_wait",
                f"attempted_variant={variant.variant_id}",
            )
            waited = _wait_for_transport_fixture(shared, ctx, wait_timeout_s)
            if waited.fixture_unit_ids.get("transport_unit"):
                waited.transport_build_requests[variant.variant_id] = "ready"
            else:
                waited.transport_build_requests[variant.variant_id] = "dispatched_waited_no_ready_transport"
                _set_transport_debug(
                    waited,
                    "provisioning_action=dispatch_wait_completed",
                    f"attempted_variant={variant.variant_id}",
                )
            return waited
        break
    refreshed = _refresh_bootstrap_context(shared, ctx)
    if attempted_variant is None:
        _set_transport_debug(refreshed, "provisioning_action=no_resolved_transport_defs")
    else:
        _set_transport_debug(
            refreshed,
            "provisioning_action=dispatch_submitted",
            f"attempted_variant={attempted_variant}",
        )
    return refreshed


def _resolve_live_def_ids(
    stub: Any,
    ctx: BootstrapContext,
    *,
    wanted_names: tuple[str, ...],
    token: str | None = None,
) -> None:
    from ..highbar import callbacks_pb2

    bulk = stub.InvokeCallback(
        callbacks_pb2.CallbackRequest(
            request_id=1,
            callback_id=callbacks_pb2.CALLBACK_GET_UNIT_DEFS,
        ),
        metadata=[(TOKEN_HEADER, token)] if token else None,
        timeout=5.0,
    )
    if not bulk.success or not bulk.result.HasField("int_array_value"):
        raise RuntimeError(bulk.error_message or "bulk unit-def callback returned no ids")
    for index, def_id in enumerate(bulk.result.int_array_value.values, start=2):
        name_resp = stub.InvokeCallback(
            callbacks_pb2.CallbackRequest(
                request_id=index,
                callback_id=callbacks_pb2.CALLBACK_UNITDEF_GET_NAME,
                params=(callbacks_pb2.CallbackParam(int_value=int(def_id)),),
            ),
            metadata=[(TOKEN_HEADER, token)] if token else None,
            timeout=5.0,
        )
        if not name_resp.success or not name_resp.result.HasField("string_value"):
            continue
        def_name = name_resp.result.string_value
        if def_name in wanted_names:
            ctx.def_id_by_name[def_name] = int(def_id)


def _resolve_supported_transport_defs(stub, ctx: BootstrapContext, *, token: str | None = None) -> None:
    wanted = (
        *(variant.def_name for variant in supported_transport_variants()),
        "armap",
    )
    traces = []
    try:
        _resolve_live_def_ids(stub, ctx, wanted_names=tuple(wanted), token=token)
        for variant in supported_transport_variants():
            resolved = ctx.def_id_by_name.get(variant.def_name)
            traces.append(
                {
                    "variant_id": variant.variant_id,
                    "callback_path": f"InvokeCallback/{variant.def_name}",
                    "resolved_def_id": resolved,
                    "resolution_status": "resolved" if resolved else "missing",
                    "reason": (
                        f"resolved runtime def id for {variant.def_name}"
                        if resolved
                        else f"runtime callback results did not include {variant.def_name}"
                    ),
                }
            )
    except Exception as exc:  # noqa: BLE001
        traces = [
            {
                "variant_id": variant.variant_id,
                "callback_path": f"InvokeCallback/{variant.def_name}",
                "resolved_def_id": None,
                "resolution_status": "relay_unavailable",
                "reason": str(exc),
            }
            for variant in supported_transport_variants()
        ]
    ctx.transport_resolution_trace = tuple(traces)


def _resolve_bootstrap_defs(stub: Any, ctx: BootstrapContext, *, token: str | None = None) -> None:
    wanted_names = tuple(
        dict.fromkeys(
            [
                *(step.def_id for step in DEFAULT_BOOTSTRAP_PLAN),
                *(variant.def_name for variant in supported_transport_variants()),
            ]
        )
    )
    _resolve_live_def_ids(stub, ctx, wanted_names=wanted_names, token=token)


def _refresh_bootstrap_context(shared: dict, ctx: BootstrapContext) -> BootstrapContext:
    snapshot = shared["snapshots"][-1] if shared.get("snapshots") else None
    if snapshot is None:
        return ctx

    _clear_derived_live_context(ctx)
    commander = _find_commander(snapshot)
    if commander is not None:
        ctx.commander_unit_id = commander.unit_id
        ctx.commander_position = _vector3_from_position(commander.position)
        ctx.capability_units["commander"] = commander.unit_id

    own_units = [
        unit
        for unit in getattr(snapshot, "own_units", ())
        if unit.unit_id != ctx.commander_unit_id
    ]
    ctx.observed_own_units = {
        unit.unit_id: unit for unit in getattr(snapshot, "own_units", ())
    }

    for unit in own_units:
        if _matches_factory_air(unit, ctx) and _unit_is_ready_fixture_unit(unit):
            ctx.capability_units["factory_air"] = unit.unit_id
            ctx.fixture_positions["factory_air"] = _vector3_from_position(unit.position)
            break

    for fixture_class, expected_health in _FIXTURE_HEALTH_HINTS.items():
        if fixture_class == "factory_air":
            continue
        for unit in own_units:
            if fixture_class == "transport_unit":
                matched = _transport_variant_unit(unit, ctx)
                if matched is None:
                    continue
            elif not _matches_health(unit, expected_health) or not _unit_is_ready_fixture_unit(unit):
                continue
            ctx.fixture_unit_ids[fixture_class] = unit.unit_id
            if fixture_class in {"builder", "cloakable"}:
                ctx.capability_units[fixture_class] = unit.unit_id
            ctx.fixture_positions[fixture_class] = _vector3_from_position(unit.position)
            break

    payload_candidate = _select_payload_candidate(own_units, ctx)
    if payload_candidate is not None:
        ctx.fixture_unit_ids.setdefault("payload_unit", payload_candidate.unit_id)
        ctx.fixture_positions.setdefault(
            "payload_unit",
            _vector3_from_position(payload_candidate.position),
        )

    damaged_friendly = next(
        (
            unit
            for unit in own_units
            if _unit_is_ready_fixture_unit(unit) and unit.health < unit.max_health
        ),
        None,
    )
    if damaged_friendly is not None:
        ctx.fixture_unit_ids["damaged_friendly"] = damaged_friendly.unit_id
        ctx.fixture_positions["damaged_friendly"] = _vector3_from_position(
            damaged_friendly.position
        )

    enemy = next(iter(getattr(snapshot, "visible_enemies", ())), None)
    if enemy is not None:
        ctx.enemy_seed_id = enemy.unit_id
        enemy_position = _vector3_from_position(enemy.position)
        for fixture_class in (
            "hostile_target",
            "capturable_target",
            "custom_target",
        ):
            ctx.fixture_unit_ids[fixture_class] = enemy.unit_id
            ctx.fixture_positions[fixture_class] = enemy_position

    reclaimable_features = [
        feature
        for feature in getattr(snapshot, "map_features", ())
        if feature.reclaim_value_metal > 0.0 or feature.reclaim_value_energy > 0.0
    ]
    if reclaimable_features:
        feature = reclaimable_features[0]
        ctx.fixture_feature_ids["reclaim_target"] = feature.feature_id
        ctx.fixture_positions["reclaim_target"] = _vector3_from_position(feature.position)

    current_feature_ids = {feature.feature_id for feature in getattr(snapshot, "map_features", ())}
    for event in reversed(shared.get("deltas", ())):
        if event.WhichOneof("kind") != "feature_created":
            continue
        feature_id = event.feature_created.feature_id
        if feature_id not in current_feature_ids:
            continue
        ctx.fixture_feature_ids["wreck_target"] = feature_id
        ctx.fixture_positions["wreck_target"] = _vector3_from_position(
            event.feature_created.position
        )
        break
    else:
        reclaim_target_id = ctx.fixture_feature_ids.get("reclaim_target")
        wreck_candidate = next(
            (
                feature
                for feature in sorted(
                    reclaimable_features,
                    key=lambda item: item.feature_id,
                    reverse=True,
                )
                if feature.feature_id != reclaim_target_id
            ),
            None,
        )
        if wreck_candidate is not None:
            ctx.fixture_feature_ids["wreck_target"] = wreck_candidate.feature_id
            ctx.fixture_positions["wreck_target"] = _vector3_from_position(
                wreck_candidate.position
            )

    ctx.fixture_positions.setdefault(
        "restore_target",
        Vector3(
            x=ctx.commander_position.x + 96.0,
            y=ctx.commander_position.y,
            z=ctx.commander_position.z,
        ),
    )
    ctx.fixture_positions.setdefault(
        "movement_lane",
        Vector3(
            x=ctx.commander_position.x + 500.0,
            y=ctx.commander_position.y,
            z=ctx.commander_position.z,
        ),
    )
    ctx.fixture_positions.setdefault("resource_baseline", ctx.commander_position)
    return ctx


def _execute_live_bootstrap(
    stub: Any,
    shared: dict,
    *,
    token: str | None = None,
    static_map: Any | None = None,
) -> BootstrapContext:
    commander = None
    deadline = time.monotonic() + 30.0
    while time.monotonic() < deadline:
        snapshot = _latest_snapshot(shared)
        if snapshot is not None:
            commander = _find_commander(snapshot)
            if commander is not None:
                break
        time.sleep(0.2)
    if commander is None:
        raise RuntimeError("no commander within 30s")

    ctx = BootstrapContext(
        commander_unit_id=commander.unit_id,
        commander_position=_vector3_from_position(commander.position),
        capability_units={"commander": commander.unit_id},
        fixture_unit_ids={},
        fixture_feature_ids={},
        fixture_positions={},
        enemy_seed_id=None,
        manifest=(),
        cheats_enabled=False,
        def_id_by_name={},
    )
    try:
        _resolve_bootstrap_defs(stub, ctx, token=token)
        _update_runtime_capability_profile(
            ctx,
            supported_callbacks=(47, 40),
            supported_scopes=("unit_def_lookup", "unit_def_name"),
        )
    except Exception as exc:  # noqa: BLE001
        _record_prerequisite_resolution(
            ctx,
            prerequisite_name="armmex",
            consumer="live_closeout",
            callback_path="InvokeCallback/armmex",
            resolved_def_id=None,
            resolution_status="relay_unavailable",
            reason=str(exc),
        )
        raise BootstrapExecutionError(
            f"bootstrap def resolution failed: {exc}",
            ctx=ctx,
        ) from exc
    _resolve_supported_transport_defs(stub, ctx, token=token)
    _record_prerequisite_resolution(
        ctx,
        prerequisite_name="armmex",
        consumer="live_closeout",
        callback_path="InvokeCallback/armmex",
        resolved_def_id=ctx.def_id_by_name.get("armmex"),
        resolution_status="resolved" if ctx.def_id_by_name.get("armmex") else "missing",
        reason=(
            "resolved runtime def id for armmex during live bootstrap"
            if ctx.def_id_by_name.get("armmex")
            else "runtime callback results did not include armmex"
        ),
    )

    starting_snapshot = _refreshing_snapshot(stub, shared, token=token, timeout_s=5.0) or _latest_snapshot(shared)
    if starting_snapshot is None:
        raise BootstrapExecutionError("no live snapshot available for bootstrap", ctx=ctx)
    commander = _find_commander(starting_snapshot)
    if commander is None:
        raise BootstrapExecutionError("commander missing from bootstrap snapshot", ctx=ctx)
    ctx.commander_unit_id = commander.unit_id
    ctx.commander_position = _vector3_from_position(commander.position)
    ctx.capability_units["commander"] = commander.unit_id
    ctx = _refresh_bootstrap_context(shared, ctx)
    _record_live_closeout_map_source(ctx, static_map=static_map)
    readiness_status, readiness_path, first_required_step, readiness_reason = _assess_bootstrap_readiness(
        starting_snapshot,
        ctx,
    )
    _record_bootstrap_readiness(
        ctx,
        readiness_status=readiness_status,
        readiness_path=readiness_path,
        first_required_step=first_required_step,
        economy_summary=_economy_debug_string(starting_snapshot),
        reason=readiness_reason,
    )
    _capture_callback_diagnostic(
        stub,
        shared,
        ctx,
        capture_stage="bootstrap_start",
        token=token,
    )
    if readiness_status == "resource_starved":
        raise BootstrapExecutionError(
            (
                f"bootstrap_readiness=resource_starved "
                f"first_required_step={first_required_step} "
                f"{readiness_reason} {_economy_debug_string(starting_snapshot)}"
            ),
            ctx=ctx,
        )

    commander_steps = tuple(
        step for step in DEFAULT_BOOTSTRAP_PLAN if step.builder_capability == "commander"
    )
    baseline_ids_by_step: dict[str, set[int]] = {
        step.capability: {
            unit.unit_id
            for unit in getattr(starting_snapshot, "own_units", ())
            if getattr(unit, "def_id", 0) == ctx.def_id_by_name.get(step.def_id, 0)
        }
        for step in commander_steps
    }
    for step in commander_steps:
        existing_units = _ready_units_for_def(
            starting_snapshot,
            ctx.def_id_by_name.get(step.def_id, 0),
        )
        if existing_units:
            completed = min(existing_units, key=lambda item: item.unit_id)
            ctx.capability_units[step.capability] = completed.unit_id
            ctx.fixture_positions[step.capability] = _vector3_from_position(completed.position)
            continue
        try:
            completed = _issue_bootstrap_build_step(
                stub,
                shared,
                ctx,
                step,
                builder_unit_id=ctx.commander_unit_id,
                target_position=_position_for_bootstrap_step(
                    step,
                    ctx.commander_position,
                    static_map=static_map,
                    snapshot=starting_snapshot,
                    ignore_unit_ids={ctx.commander_unit_id},
                ),
                baseline_ids=baseline_ids_by_step[step.capability],
                token=token,
                static_map=static_map,
            )
        except RuntimeError as exc:
            if _can_skip_bootstrap_step_failure(step, exc, ctx):
                print(f"bootstrap-optional-skip: {exc}", file=sys.stderr, flush=True)
                continue
            _capture_callback_diagnostic(
                stub,
                shared,
                ctx,
                capture_stage="bootstrap_failure",
                token=token,
            )
            raise BootstrapExecutionError(str(exc), ctx=ctx) from exc
        ctx.capability_units[step.capability] = completed.unit_id
        ctx.fixture_positions[step.capability] = _vector3_from_position(completed.position)

    ctx = _refresh_bootstrap_context(shared, ctx)
    factory_steps = tuple(
        step for step in DEFAULT_BOOTSTRAP_PLAN if step.builder_capability != "commander"
    )
    factory_snapshot = _refreshing_snapshot(stub, shared, token=token, timeout_s=5.0) or _latest_snapshot(shared)
    if factory_snapshot is None:
        raise BootstrapExecutionError("no live snapshot available after commander bootstrap", ctx=ctx)
    baseline_ids_by_step = {
        step.capability: {
            unit.unit_id
            for unit in getattr(factory_snapshot, "own_units", ())
            if getattr(unit, "def_id", 0) == ctx.def_id_by_name.get(step.def_id, 0)
        }
        for step in factory_steps
    }
    for step in factory_steps:
        existing_units = _ready_units_for_def(
            factory_snapshot,
            ctx.def_id_by_name.get(step.def_id, 0),
        )
        if existing_units:
            completed = min(existing_units, key=lambda item: item.unit_id)
            ctx.capability_units[step.capability] = completed.unit_id
            ctx.fixture_positions[step.capability] = _vector3_from_position(completed.position)
            ctx = _refresh_bootstrap_context(shared, ctx)
            continue
        builder_unit_id = ctx.capability_units.get(step.builder_capability)
        if not builder_unit_id:
            raise BootstrapExecutionError(f"builder capability {step.builder_capability} is not available", ctx=ctx)
        builder_unit = ctx.observed_own_units.get(builder_unit_id)
        if builder_unit is None or not _unit_is_ready_fixture_unit(builder_unit):
            raise BootstrapExecutionError(f"builder capability {step.builder_capability} is not ready", ctx=ctx)
        try:
            completed = _issue_bootstrap_build_step(
                stub,
                shared,
                ctx,
                step,
                builder_unit_id=builder_unit_id,
                target_position=_vector3_from_position(builder_unit.position),
                baseline_ids=baseline_ids_by_step[step.capability],
                token=token,
            )
        except RuntimeError as exc:
            if _can_skip_bootstrap_step_failure(step, exc, ctx):
                print(f"bootstrap-optional-skip: {exc}", file=sys.stderr, flush=True)
                ctx = _refresh_bootstrap_context(shared, ctx)
                continue
            _capture_callback_diagnostic(
                stub,
                shared,
                ctx,
                capture_stage="bootstrap_failure",
                token=token,
            )
            raise BootstrapExecutionError(str(exc), ctx=ctx) from exc
        ctx.capability_units[step.capability] = completed.unit_id
        ctx.fixture_positions[step.capability] = _vector3_from_position(completed.position)
        ctx = _refresh_bootstrap_context(shared, ctx)

    final_snapshot = _refreshing_snapshot(stub, shared, token=token, timeout_s=5.0) or _latest_snapshot(shared)
    if final_snapshot is None:
        raise BootstrapExecutionError("bootstrap completed without a final snapshot", ctx=ctx)
    ctx.manifest = compute_manifest(getattr(final_snapshot, "own_units", ()), ctx.def_id_by_name)
    print(f"bootstrap-manifest: {list(ctx.manifest)}", file=sys.stderr, flush=True)
    ctx = _refresh_bootstrap_context(shared, ctx)
    _capture_callback_diagnostic(
        stub,
        shared,
        ctx,
        capture_stage="late_refresh",
        token=token,
    )
    return _attempt_transport_provisioning(stub, shared, ctx, token=token)


def _reissue_manifest_shortages(
    stub: Any,
    shared: dict,
    ctx: BootstrapContext,
    shortages: dict[str, int],
    *,
    token: str | None = None,
) -> BootstrapContext:
    step_by_def_name = {step.def_id: step for step in DEFAULT_BOOTSTRAP_PLAN}
    for def_name in sorted(shortages):
        step = step_by_def_name.get(def_name)
        if step is None:
            continue
        resolved_def_id = ctx.def_id_by_name.get(def_name, 0)
        if not resolved_def_id:
            raise RuntimeError(f"runtime def id for {def_name} was not resolved")
        for _ in range(shortages[def_name]):
            if step.builder_capability == "commander":
                if ctx.commander_unit_id <= 0:
                    raise RuntimeError("commander_lost")
                target_position = Vector3(
                    x=ctx.commander_position.x + step.relative_position.x,
                    y=ctx.commander_position.y + step.relative_position.y,
                    z=ctx.commander_position.z + step.relative_position.z,
                )
                builder_unit_id = ctx.commander_unit_id
            else:
                ctx = _refresh_bootstrap_context(shared, ctx)
                builder_unit_id = ctx.capability_units.get(step.builder_capability, 0)
                if not builder_unit_id:
                    prerequisite_step = next(
                        (
                            candidate
                            for candidate in DEFAULT_BOOTSTRAP_PLAN
                            if candidate.capability == step.builder_capability
                        ),
                        None,
                    )
                    if prerequisite_step is None:
                        raise RuntimeError(f"builder capability {step.builder_capability} is not available")
                    ctx = _reissue_manifest_shortages(
                        stub,
                        shared,
                        ctx,
                        {prerequisite_step.def_id: 1},
                        token=token,
                    )
                    _wait_for_manifest_match(shared, ctx, timeout_s=10.0)
                    ctx = _refresh_bootstrap_context(shared, ctx)
                    builder_unit_id = ctx.capability_units.get(step.builder_capability, 0)
                builder_unit = ctx.observed_own_units.get(builder_unit_id)
                if builder_unit is None:
                    raise RuntimeError(f"builder capability {step.builder_capability} is not observable")
                target_position = _vector3_from_position(builder_unit.position)
            _dispatch(
                stub,
                _build_unit_batch(builder_unit_id, resolved_def_id, target_position),
                token=token,
            )
    return ctx


def _reset_live_context_to_manifest(
    stub: Any,
    shared: dict,
    ctx: BootstrapContext,
    *,
    timeout_s: float = 10.0,
    token: str | None = None,
) -> BootstrapContext:
    if not ctx.manifest:
        return _refresh_bootstrap_context(shared, ctx)
    snapshot = _refreshing_snapshot(stub, shared, token=token, timeout_s=min(5.0, timeout_s)) or _latest_snapshot(shared)
    if snapshot is None:
        raise RuntimeError("no live snapshot available for bootstrap reset")
    current = compute_manifest(getattr(snapshot, "own_units", ()), ctx.def_id_by_name)
    shortages = manifest_shortages(current, ctx.manifest)
    if not shortages:
        return _refresh_bootstrap_context(shared, ctx)
    ctx = _reissue_manifest_shortages(stub, shared, ctx, shortages, token=token)
    _wait_for_manifest_match(shared, ctx, timeout_s=timeout_s)
    refreshed = _refresh_bootstrap_context(shared, ctx)
    return _attempt_transport_provisioning(stub, shared, refreshed, token=token)


def _has_fixture_unit(ctx: BootstrapContext, fixture_class: str) -> bool:
    return bool(
        ctx.fixture_unit_ids.get(fixture_class)
        or ctx.capability_units.get(fixture_class)
    )


def _has_fixture_feature(ctx: BootstrapContext, fixture_class: str) -> bool:
    return bool(ctx.fixture_feature_ids.get(fixture_class))


def _has_fixture_position(ctx: BootstrapContext, fixture_class: str) -> bool:
    return fixture_class in ctx.fixture_positions


def _custom_command_ready(ctx: BootstrapContext) -> bool:
    return any(
        (
            _has_fixture_unit(ctx, "cloakable"),
            _has_fixture_unit(ctx, "builder"),
            _has_fixture_unit(ctx, "custom_target"),
            ctx.enemy_seed_id is not None,
        )
    )


def _missing_fixture_classes(
    ctx: BootstrapContext,
    fixture_classes: tuple[str, ...],
) -> tuple[str, ...]:
    missing: list[str] = []
    for fixture_class in fixture_classes:
        if fixture_class in {"restore_target", "movement_lane", "resource_baseline"}:
            if not _has_fixture_position(ctx, fixture_class):
                missing.append(fixture_class)
        elif fixture_class in {"reclaim_target", "wreck_target"}:
            if not (
                _has_fixture_feature(ctx, fixture_class)
                or _has_fixture_position(ctx, fixture_class)
            ):
                missing.append(fixture_class)
        else:
            if not _has_fixture_unit(ctx, fixture_class):
                missing.append(fixture_class)
    return tuple(missing)


def _missing_fixture_classes_for_context(
    arm_name: str,
    ctx: BootstrapContext,
) -> tuple[str, ...]:
    command_id = f"cmd-{arm_name.replace('_', '-')}"
    command_specific: dict[str, tuple[str, ...]] = {
        "attack": () if _has_fixture_unit(ctx, "hostile_target") else ("hostile_target",),
        "attack_area": () if _has_fixture_position(ctx, "hostile_target") else ("hostile_target",),
        "capture": () if _has_fixture_unit(ctx, "capturable_target") else ("capturable_target",),
        "capture_area": () if _has_fixture_position(ctx, "capturable_target") else ("capturable_target",),
        "custom": () if _custom_command_ready(ctx) else ("custom_target",),
        "dgun": () if _has_fixture_unit(ctx, "hostile_target") else ("hostile_target",),
        "guard": () if _has_fixture_unit(ctx, "damaged_friendly") else ("damaged_friendly",),
        "repair": () if _has_fixture_unit(ctx, "damaged_friendly") else ("damaged_friendly",),
        "load_onto": _missing_fixture_classes(ctx, ("transport_unit", "payload_unit")),
        "load_units": _missing_fixture_classes(ctx, ("transport_unit", "payload_unit")),
        "load_units_area": _missing_fixture_classes(ctx, ("transport_unit", "payload_unit")),
        "reclaim_unit": (
            ()
            if _has_fixture_unit(ctx, "reclaim_target") or _has_fixture_unit(ctx, "hostile_target")
            else ("reclaim_target",)
        ),
        "reclaim_feature": () if _has_fixture_feature(ctx, "reclaim_target") else ("reclaim_target",),
        "reclaim_area": () if _has_fixture_position(ctx, "reclaim_target") else ("reclaim_target",),
        "reclaim_in_area": () if _has_fixture_position(ctx, "reclaim_target") else ("reclaim_target",),
        "restore_area": () if _has_fixture_position(ctx, "restore_target") else ("restore_target",),
        "resurrect": () if _has_fixture_feature(ctx, "wreck_target") else ("wreck_target",),
        "resurrect_in_area": () if _has_fixture_position(ctx, "wreck_target") else ("wreck_target",),
        "self_destruct": (
            ()
            if (
                _has_fixture_unit(ctx, "cloakable")
                or _has_fixture_unit(ctx, "builder")
                or _has_fixture_unit(ctx, "payload_unit")
                or _has_fixture_unit(ctx, "damaged_friendly")
            )
            else ("builder", "cloakable")
        ),
        "set_base": () if _has_fixture_position(ctx, "restore_target") else ("restore_target",),
        "unload_unit": _missing_fixture_classes(ctx, ("transport_unit", "payload_unit")),
        "unload_units_area": _missing_fixture_classes(ctx, ("transport_unit", "payload_unit")),
    }
    if arm_name in command_specific:
        return command_specific[arm_name]

    available_fixture_classes = {"commander", "movement_lane", "resource_baseline"}
    for fixture_class in (
        "builder",
        "cloakable",
        "hostile_target",
        "capturable_target",
        "custom_target",
        "damaged_friendly",
        "transport_unit",
        "payload_unit",
    ):
        if _has_fixture_unit(ctx, fixture_class):
            available_fixture_classes.add(fixture_class)
    for fixture_class in ("reclaim_target", "wreck_target"):
        if _has_fixture_feature(ctx, fixture_class) or _has_fixture_position(ctx, fixture_class):
            available_fixture_classes.add(fixture_class)
    if _has_fixture_position(ctx, "restore_target"):
        available_fixture_classes.add("restore_target")
    return tuple(
        fixture_class
        for fixture_class in fixture_classes_for_command(command_id)
        if fixture_class not in available_fixture_classes
    )


def _simplified_bootstrap_precondition_message(
    arm_name: str,
    case: BehavioralTestCase,
    ctx: BootstrapContext,
) -> str | None:
    command_id = f"cmd-{arm_name.replace('_', '-')}"
    if case.required_capability not in ("none", "commander"):
        if case.required_capability not in ctx.capability_units:
            return (
                f"required_capability={case.required_capability} "
                f"not provisioned by the live bootstrap context"
            )
    missing_fixture_classes = _missing_fixture_classes_for_context(arm_name, ctx)
    if missing_fixture_classes:
        return (
            "live fixture dependency unavailable for this arm "
            f"({', '.join(missing_fixture_classes)})"
        )
    compatibility_result, compatibility_detail = transport_compatibility_for_command(
        command_id,
        ctx,
    )
    if compatibility_result in {"candidate_unusable", "payload_incompatible"} and compatibility_detail:
        return compatibility_detail
    return None


def _fixture_status_detail(
    arm_name: str,
    ctx: BootstrapContext,
) -> str:
    command_id = f"cmd-{arm_name.replace('_', '-')}"
    if not is_transport_dependent_command(command_id):
        return ""
    return " ".join(ctx.transport_diagnostics or ()).strip()


def collect_live_rows(args: argparse.Namespace) -> list[dict]:
    """Collect live behavioral rows without emitting artifacts."""
    try:
        channel = _open_channel(args.endpoint)
        ai_token = _load_ai_token()
        stub, hello_resp = _hello_ai(channel, client_id="bcov", token=ai_token)
    except Exception as e:  # noqa: BLE001
        print(f"behavioral-coverage: connection failed: {e}", file=sys.stderr)
        return _collect_dry_rows()

    print(f"behavioral-coverage: connected schema={hello_resp.schema_version} "
          f"session={hello_resp.session_id}", flush=True)

    shared, _worker = _start_state_stream(stub)

    time.sleep(3.0)
    try:
        ctx = _execute_live_bootstrap(
            stub,
            shared,
            token=ai_token,
            static_map=getattr(hello_resp, "static_map", None),
        )
    except Exception as exc:  # noqa: BLE001
        detail = f"bootstrap_failed: {exc}"
        print(f"behavioral-coverage: {detail}", file=sys.stderr, flush=True)
        rows = _collect_bootstrap_blocked_rows(detail)
        rows.extend(_bootstrap_metadata_rows(getattr(exc, "ctx", None)))
        return rows

    # ---- Phase 2: per-arm dispatch + verify --------------------------

    rows: list[dict] = []
    ordered_arm_names = sorted(REGISTRY.keys())
    for index, arm_name in enumerate(ordered_arm_names):
        case = REGISTRY[arm_name]
        try:
            ctx = _reset_live_context_to_manifest(stub, shared, ctx, token=ai_token)
        except Exception as exc:  # noqa: BLE001
            detail = f"bootstrap_reset_failed: {exc}"
            print(f"behavioral-coverage: {detail}", file=sys.stderr, flush=True)
            rows.append(
                {
                    "arm_name": case.arm_name,
                    "category": case.category,
                    "dispatched": "false",
                    "verified": "na",
                    "evidence": detail,
                    "error": "bootstrap_reset_failed",
                }
            )
            for remaining_arm_name in ordered_arm_names[index + 1:]:
                remaining_case = REGISTRY[remaining_arm_name]
                rows.append(
                    {
                        "arm_name": remaining_case.arm_name,
                        "category": remaining_case.category,
                        "dispatched": "false",
                        "verified": "na",
                        "evidence": detail,
                        "error": "bootstrap_reset_failed",
                    }
                )
            if shared.get("err"):
                _capture_callback_diagnostic(
                    stub,
                    shared,
                    ctx,
                    capture_stage="late_refresh",
                    token=ai_token,
                )
            rows.extend(_bootstrap_metadata_rows(ctx))
            shared["stop"] = True
            return rows
        command_id = f"cmd-{arm_name.replace('_', '-')}"
        if is_transport_dependent_command(command_id):
            ctx = _attempt_transport_provisioning(
                stub,
                shared,
                ctx,
                wait_timeout_s=6.0,
                token=ai_token,
            )

        # NotWireObservable sentinel: dispatch, record na/not_wire_observable.
        if isinstance(case.verify_predicate, NotWireObservable):
            dispatched = False
            try:
                batch = case.input_builder(ctx)
                _dispatch(stub, batch, token=ai_token)
                dispatched = True
            except Exception:  # noqa: BLE001
                dispatched = False
            outcome = VerificationOutcome(
                verified="na",
                evidence=case.verify_predicate.rationale,
                error="not_wire_observable",
            )
            rows.append(_row_for_outcome(case, dispatched, outcome))
            continue

        precondition_message = _simplified_bootstrap_precondition_message(
            arm_name, case, ctx
        )
        if precondition_message is not None:
            outcome = VerificationOutcome(
                verified="na",
                evidence=precondition_message,
                error="precondition_unmet",
            )
            row = _row_for_outcome(case, False, outcome)
            fixture_status = _fixture_status_detail(arm_name, ctx)
            if fixture_status:
                row["fixture_status"] = fixture_status
            rows.append(row)
            continue

        # Capture pre-dispatch snapshot.
        pre = shared["snapshots"][-1] if shared["snapshots"] else None
        if pre is None:
            outcome = VerificationOutcome(
                verified="na", evidence="no pre-dispatch snapshot",
                error="precondition_unmet",
            )
            rows.append(_row_for_outcome(case, False, outcome))
            continue

        # Dispatch.
        dispatched = False
        try:
            batch = case.input_builder(ctx)
            _dispatch(stub, batch, token=ai_token)
            dispatched = True
        except Exception as e:  # noqa: BLE001
            detail = str(e)
            if is_channel_failure_signal(detail):
                outcome = VerificationOutcome(
                    verified="na",
                    evidence="plugin command channel is not connected",
                    error="dispatcher_rejected",
                )
                rows.append(_row_for_outcome(case, False, outcome))
                continue
            outcome = VerificationOutcome(
                verified="na",
                evidence=f"dispatch failed: {e}",
                error="dispatcher_rejected",
            )
            rows.append(_row_for_outcome(case, False, outcome))
            continue

        # Wait verify_window_frames (≈ verify_window_frames / 30 seconds).
        target_frame = pre.frame_number + case.verify_window_frames
        post = _wait_for_snapshot(
            shared, target_frame,
            timeout_s=max(5.0, case.verify_window_frames / 30.0 + 2.0))
        if post is None:
            if shared["deltas"] and is_channel_failure_signal(str(shared["deltas"][-1])):
                outcome = VerificationOutcome(
                    verified="na",
                    evidence="plugin command channel is not connected",
                    error="dispatcher_rejected",
                )
                rows.append(_row_for_outcome(case, dispatched, outcome))
                continue
            outcome = VerificationOutcome(
                verified="false",
                evidence=f"timeout waiting for frame {target_frame}",
                error="timeout",
            )
            rows.append(_row_for_outcome(case, dispatched, outcome))
            continue

        pair = SnapshotPair(
            before=pre, after=post,
            dispatched_at_frame=pre.frame_number,
            delta_log=list(shared["deltas"]))

        try:
            outcome = case.verify_predicate(pair, pair.delta_log)
        except Exception as e:  # noqa: BLE001 — predicate bug
            outcome = VerificationOutcome(
                verified="false",
                evidence=f"predicate threw: {e}",
                error="internal_error",
            )
        rows.append(_row_for_outcome(case, dispatched, outcome))

    if any(
        row.get("error") in {"dispatcher_rejected", "timeout", "bootstrap_reset_failed"}
        for row in rows
    ) or shared.get("err"):
        _capture_callback_diagnostic(
            stub,
            shared,
            ctx,
            capture_stage="late_refresh",
            token=ai_token,
        )

    rows.extend(_bootstrap_metadata_rows(ctx))
    shared["stop"] = True
    return rows


def run_live(args: argparse.Namespace) -> int:
    """Full live-topology run. Returns process exit code.

    Implementation is intentionally simple: we rely on the periodic
    snapshot tick (contract: ≈ 1s cadence) to capture before/after
    snapshots for each arm. If `RequestSnapshot` is plumbed we use it
    to tighten the pre-dispatch capture.
    """
    output_dir = Path(args.output_dir)
    if args.run_index > 0:
        output_dir = output_dir / f"run-{args.run_index}"
    output_dir.mkdir(parents=True, exist_ok=True)

    start = time.monotonic()
    rows = collect_live_rows(args)

    # ---- Emit CSV + digest ------------------------------------------
    csv_path = output_dir / "aicommand-behavioral-coverage.csv"
    digest_path = output_dir / "aicommand-behavioral-coverage.digest"
    try:
        write_csv(csv_path, rows)
    except CoverageReportError as e:
        print(f"behavioral-coverage: CSV emission failed: {e}",
              file=sys.stderr)
        return 2

    tuples = [(r["arm_name"], r["dispatched"], r["verified"], r["error"])
              for r in rows]
    digest = canonical_digest(tuples)
    write_digest(digest_path, digest)

    wall = time.monotonic() - start
    if wall > 300.0:
        print(f"behavioral-coverage: wall_clock={wall:.1f}s exceeds "
              f"SC-003 budget 300s", file=sys.stderr)
        return 1

    ok, line = summarize(rows, args.threshold)
    print(line)
    print(f"behavioral-coverage: wall_clock={wall:.1f}s digest={digest}")
    return 0 if ok else 1


def main(argv: Optional[list[str]] = None) -> int:
    if argv and argv[:1] == ["itertesting"]:
        from .itertesting_runner import itertesting_main

        return itertesting_main(argv[1:])
    if argv and argv[:1] == ["audit"]:
        return _audit_main(argv[1:])
    args = _parse_args(argv)
    output_dir = Path(args.output_dir)
    if args.run_index > 0:
        output_dir = output_dir / f"run-{args.run_index}"
    output_dir.mkdir(parents=True, exist_ok=True)

    if args.skip_live:
        return run_dry(args.threshold, output_dir)

    try:
        return run_live(args)
    except KeyboardInterrupt:
        return 130
    except Exception as e:  # noqa: BLE001 — top-level guard
        print(f"behavioral-coverage: internal error: {e}", file=sys.stderr)
        return 2


__all__ = ["main", "run_dry", "run_live", "REGISTRY", "validate_registry"]
def _audit_main(argv: list[str]) -> int:
    from .audit_report import generate
    from .audit_runner import (
        collect_live_audit_run,
        execute_hypothesis,
        latest_completed_run,
        refresh_summary_text,
        render_repro_report,
        serialize_manifest,
        write_drift_report,
        write_phase2_report,
    )

    audit = argparse.ArgumentParser(prog="highbar_client.behavioral_coverage audit")
    sub = audit.add_subparsers(dest="command", required=True)

    refresh = sub.add_parser("refresh")
    refresh.add_argument("--audit-dir", default="audit")
    refresh.add_argument("--summary-only", action="store_true")
    refresh.add_argument("--fail-rows", default="")
    refresh.add_argument("--fail-rpcs", default="")
    refresh.add_argument("--topology-failure", default="")
    refresh.add_argument("--session-failure", default="")

    repro = sub.add_parser("repro")
    repro.add_argument("row_id")
    repro.add_argument("--phase", default="phase1")
    repro.add_argument("--report-path")

    hypothesis = sub.add_parser("hypothesis")
    hypothesis.add_argument("row_id")
    hypothesis.add_argument("hypothesis_class")
    hypothesis.add_argument("--report-path")

    drift = sub.add_parser("drift")

    phase2 = sub.add_parser("phase2")

    args = audit.parse_args(argv)

    if args.command == "refresh":
        if args.fail_rows:
            os.environ["HIGHBAR_AUDIT_FAIL_ROWS"] = args.fail_rows
        if args.fail_rpcs:
            os.environ["HIGHBAR_AUDIT_FAIL_RPCS"] = args.fail_rpcs
        if args.topology_failure:
            os.environ["HIGHBAR_AUDIT_TOPOLOGY_FAILURE"] = args.topology_failure
        if args.session_failure:
            os.environ["HIGHBAR_AUDIT_SESSION_FAILURE"] = args.session_failure
        previous = latest_completed_run()
        run = collect_live_audit_run(previous)
        manifest_path = serialize_manifest(run)
        write_phase2_report()
        if not args.summary_only:
            generate(run, Path(args.audit_dir))
        print(refresh_summary_text(run.summary))
        print(f"Manifest: {manifest_path}")
        return 0

    if args.command == "repro":
        result = render_repro_report(args.row_id, args.phase)
        if args.report_path:
            Path(args.report_path).write_text(result.body, encoding="utf-8")
        print(result.summary)
        return 0

    if args.command == "hypothesis":
        result = execute_hypothesis(args.row_id, args.hypothesis_class)
        if args.report_path:
            Path(args.report_path).write_text(result.body, encoding="utf-8")
        print(f"{result.verdict}: {result.hypothesis_class}")
        return 0

    if args.command == "drift":
        run = latest_completed_run()
        if run is None:
            print("No completed manifest found.")
            return 1
        report = write_drift_report(run)
        print(f"PASS: drift report written to {report}")
        return 0

    if args.command == "phase2":
        report = write_phase2_report()
        print(f"PASS: phase2 macro-chain report generated at {report}")
        return 0

    return 2

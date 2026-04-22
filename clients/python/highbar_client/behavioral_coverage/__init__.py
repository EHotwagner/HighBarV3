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
from pathlib import Path
from typing import Any, Optional

from .bootstrap import (
    BootstrapContext,
    DEFAULT_BOOTSTRAP_PLAN,
    Vector3,
    compute_manifest,
    fixture_classes_for_command,
    manifest_shortages,
)
from .live_failure_classification import is_channel_failure_signal
from .capabilities import CAPABILITY_TAGS
from .registry import REGISTRY, validate_registry
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


def _hello_ai(channel, client_id: str):
    from ..highbar import service_pb2, service_pb2_grpc
    stub = service_pb2_grpc.HighBarProxyStub(channel)
    req = service_pb2.HelloRequest(
        schema_version="1.0.0",
        client_id=client_id,
        role=service_pb2.Role.ROLE_AI,
    )
    return stub, stub.Hello(req, timeout=5.0)


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


def _request_snapshot(stub) -> int:
    """Force a snapshot. Returns scheduled_frame (0 on not-healthy)."""
    from ..highbar import service_pb2
    try:
        resp = stub.RequestSnapshot(
            service_pb2.RequestSnapshotRequest(), timeout=2.0)
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
    "transport_unit": 265.0,
}


def _vector3_from_position(position: Any) -> Vector3:
    return Vector3(
        x=float(getattr(position, "x", 0.0)),
        y=float(getattr(position, "y", 0.0)),
        z=float(getattr(position, "z", 0.0)),
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


def _refresh_bootstrap_context(shared: dict, ctx: BootstrapContext) -> BootstrapContext:
    snapshot = shared["snapshots"][-1] if shared.get("snapshots") else None
    if snapshot is None:
        return ctx

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

    for fixture_class, expected_health in _FIXTURE_HEALTH_HINTS.items():
        for unit in own_units:
            if _matches_health(unit, expected_health):
                ctx.fixture_unit_ids[fixture_class] = unit.unit_id
                if fixture_class in {"builder", "cloakable"}:
                    ctx.capability_units[fixture_class] = unit.unit_id
                ctx.fixture_positions[fixture_class] = _vector3_from_position(unit.position)
                break

    payload_candidate = next(
        (
            unit
            for unit in own_units
            if unit.unit_id != ctx.fixture_unit_ids.get("transport_unit")
        ),
        None,
    )
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
            if unit.health > 0.0 and unit.health < unit.max_health
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
    return None


def collect_live_rows(args: argparse.Namespace) -> list[dict]:
    """Collect live behavioral rows without emitting artifacts."""
    try:
        channel = _open_channel(args.endpoint)
        stub, hello_resp = _hello_ai(channel, client_id="bcov")
    except Exception as e:  # noqa: BLE001
        print(f"behavioral-coverage: connection failed: {e}", file=sys.stderr)
        return _collect_dry_rows()

    print(f"behavioral-coverage: connected schema={hello_resp.schema_version} "
          f"session={hello_resp.session_id}", flush=True)

    shared, _worker = _start_state_stream(stub)

    # Let a few snapshots accumulate so we can find the commander.
    time.sleep(3.0)

    # ---- Phase 1: bootstrap ------------------------------------------
    # Simplified bootstrap: wait for a snapshot with a commander. Full
    # plan execution (mex / solar / factories) is still deferred until
    # the coordinator/build-order path is wired into the engine. The
    # minimal InvokeCallback def-id resolver no longer blocks that
    # specific piece, but the actual build orchestration remains
    # outside this feature. Phase-2 arm dispatch still runs; each arm
    # that requires a non-commander capability will report
    # precondition_unmet.

    commander = None
    deadline = time.monotonic() + 30.0
    while time.monotonic() < deadline:
        for s in reversed(shared["snapshots"]):
            commander = _find_commander(s)
            if commander:
                break
        if commander:
            break
        time.sleep(0.5)

    if commander is None:
        print("behavioral-coverage: no commander within 30s — falling back "
              "to dry output", file=sys.stderr)
        return _collect_dry_rows()

    ctx = BootstrapContext(
        commander_unit_id=commander.unit_id,
        commander_position=type("V3", (), {
            "x": commander.position.x,
            "y": commander.position.y,
            "z": commander.position.z})(),
        capability_units={"commander": commander.unit_id},
        fixture_unit_ids={},
        fixture_feature_ids={},
        fixture_positions={},
        enemy_seed_id=None,
        manifest=(),
        cheats_enabled=False,
        def_id_by_name={},
    )
    ctx = _refresh_bootstrap_context(shared, ctx)

    # ---- Phase 2: per-arm dispatch + verify --------------------------

    rows: list[dict] = []
    for arm_name in sorted(REGISTRY.keys()):
        case = REGISTRY[arm_name]
        ctx = _refresh_bootstrap_context(shared, ctx)

        # NotWireObservable sentinel: dispatch, record na/not_wire_observable.
        if isinstance(case.verify_predicate, NotWireObservable):
            dispatched = False
            try:
                batch = case.input_builder(ctx)
                _dispatch(stub, batch)
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
            rows.append(_row_for_outcome(case, False, outcome))
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
            _dispatch(stub, batch)
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

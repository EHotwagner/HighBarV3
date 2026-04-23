# SPDX-License-Identifier: GPL-2.0-only
"""BootstrapPlan + manifest + reset for the macro driver.

Contract: contracts/bootstrap-plan.md §Static plan definition and
§Plan execution protocol.

The bootstrap plan is the Phase-1 topology the Phase-2 arm registry
assumes: commander + mex + solar + factory_ground + factory_air +
radar + builder (factory output) + cloakable (factory output).
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Iterable, Optional

from .itertesting_types import (
    CommandFixtureDependency,
    FixtureClassStatus,
    SharedFixtureInstance,
    SupportedTransportVariant,
)
from .types import RegistryError


@dataclass(frozen=True)
class Vector3:
    """Local copy to avoid depending on the proto type for the module-
    level DEFAULT_BOOTSTRAP_PLAN literal. Converted to common_pb2.Vector3
    inside the dispatcher at build-order issue time.
    """

    x: float = 0.0
    y: float = 0.0
    z: float = 0.0


@dataclass(frozen=True)
class BuildStep:
    step_index: int
    capability: str
    def_id: str
    builder_capability: str
    relative_position: Vector3
    timeout_seconds: float


# Default plan per contracts/bootstrap-plan.md §Default plan.
# Critical path = max(commander-built timeouts) + max(factory-produced
# timeouts) = 45 + 30 = 75s ≤ 90s (SC-003 bootstrap budget).
DEFAULT_BOOTSTRAP_PLAN: tuple[BuildStep, ...] = (
    BuildStep(1, "mex",            "armmex",   "commander",      Vector3(+96.0, 0.0, 0.0),   10.0),
    BuildStep(2, "solar",          "armsolar", "commander",      Vector3(-96.0, 0.0, 0.0),   10.0),
    BuildStep(3, "factory_ground", "armvp",    "commander",      Vector3(+160.0, 0.0, 96.0), 45.0),
    BuildStep(4, "factory_air",    "armap",    "commander",      Vector3(-160.0, 0.0, 96.0), 45.0),
    BuildStep(5, "radar",          "armrad",   "commander",      Vector3(+96.0, 0.0, -96.0), 10.0),
    BuildStep(6, "builder",        "armck",    "factory_ground", Vector3(0.0, 0.0, 0.0),     30.0),
    BuildStep(7, "cloakable",      "armpeep",  "factory_air",    Vector3(0.0, 0.0, 0.0),     30.0),
)


@dataclass
class BootstrapContext:
    """Container the driver threads through input-builder calls.

    Populated once Phase 1 completes. `capability_units` is refreshed
    after each reset; `commander_unit_id` is stable for the run (the
    commander dying is a fatal run-abort).
    """

    commander_unit_id: int = 0
    commander_position: Vector3 = Vector3()
    capability_units: dict[str, int] = None                   # type: ignore[assignment]
    fixture_unit_ids: dict[str, int] = None                   # type: ignore[assignment]
    fixture_feature_ids: dict[str, int] = None                # type: ignore[assignment]
    fixture_positions: dict[str, Vector3] = None              # type: ignore[assignment]
    bootstrap_positions: dict[str, Vector3] = None            # type: ignore[assignment]
    enemy_seed_id: Optional[int] = None
    manifest: tuple[tuple[str, int], ...] = ()
    cheats_enabled: bool = False
    def_id_by_name: dict[str, int] = None                     # type: ignore[assignment]
    observed_own_units: dict[int, Any] = None                 # type: ignore[assignment]
    transport_build_requests: dict[str, str] = None           # type: ignore[assignment]
    transport_diagnostics: list[str] = None                   # type: ignore[assignment]
    bootstrap_readiness: dict[str, Any] | None = None
    runtime_capability_profile: dict[str, Any] | None = None
    callback_diagnostics: list[dict[str, Any]] = None         # type: ignore[assignment]
    prerequisite_resolution_records: list[dict[str, Any]] = None  # type: ignore[assignment]
    map_source_decisions: list[dict[str, Any]] = None        # type: ignore[assignment]

    def __post_init__(self):
        if self.capability_units is None:
            self.capability_units = {}
        if self.fixture_unit_ids is None:
            self.fixture_unit_ids = {}
        if self.fixture_feature_ids is None:
            self.fixture_feature_ids = {}
        if self.fixture_positions is None:
            self.fixture_positions = {}
        if self.bootstrap_positions is None:
            self.bootstrap_positions = {}
        if self.def_id_by_name is None:
            self.def_id_by_name = {}
        if self.observed_own_units is None:
            self.observed_own_units = {}
        if self.transport_build_requests is None:
            self.transport_build_requests = {}
        if self.transport_diagnostics is None:
            self.transport_diagnostics = []
        if self.callback_diagnostics is None:
            self.callback_diagnostics = []
        if self.prerequisite_resolution_records is None:
            self.prerequisite_resolution_records = []
        if self.map_source_decisions is None:
            self.map_source_decisions = []


def _utc_now_iso() -> str:
    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def append_prerequisite_resolution_record(
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


def append_map_source_decision(
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


# ---- manifest computation -----------------------------------------------


def compute_manifest(own_units: Iterable[Any],
                      def_id_by_name: dict[str, int]) -> tuple[tuple[str, int], ...]:
    """From a collection of own_units protos, produce the sorted
    `(def_name, count)` pairs that comprise the BootstrapManifest.

    The def_id→name resolution is approximate here — we map through
    def_id_by_name in reverse. Unknown def_ids are labeled as
    `def#<num>` so the manifest is still deterministic.
    """
    name_by_id = {v: k for k, v in def_id_by_name.items()}
    counts: dict[str, int] = {}
    for u in own_units:
        name = name_by_id.get(u.def_id, f"def#{u.def_id}")
        counts[name] = counts.get(name, 0) + 1
    return tuple(sorted(counts.items(), key=lambda kv: kv[0]))


def compute_bootstrap_manifest(
    own_units: Iterable[Any],
    def_id_by_name: dict[str, int],
) -> tuple[tuple[str, int], ...]:
    """Return only the bootstrap-plan unit counts needed for reset.

    Seeded live runs can include many incidental or preexisting units.
    Reset only knows how to reissue the explicit bootstrap plan, so the
    stored manifest must be limited to those def names.
    """
    allowed = {step.def_id for step in DEFAULT_BOOTSTRAP_PLAN}
    return tuple(
        (name, count)
        for name, count in compute_manifest(own_units, def_id_by_name)
        if name in allowed
    )


def manifest_shortages(current: tuple[tuple[str, int], ...],
                        target: tuple[tuple[str, int], ...]) -> dict[str, int]:
    """Diff `current` against `target` manifest. Returns {def_name:
    missing_count} in deterministic ascending-def_name iteration order
    (dict preserves insertion order in CPython 3.7+; we insert sorted).
    """
    cur = dict(current)
    out: dict[str, int] = {}
    for name, want in sorted(target, key=lambda kv: kv[0]):
        have = cur.get(name, 0)
        if have < want:
            out[name] = want - have
    return out


# ---- plan validation ----------------------------------------------------


def critical_path_seconds(plan: tuple[BuildStep, ...]) -> float:
    """Sum of (max commander-step timeout) + (max factory-step
    timeout). Must be ≤ 90.0 seconds per SC-003.
    """
    commander_max = max(
        (s.timeout_seconds for s in plan if s.builder_capability == "commander"),
        default=0.0,
    )
    factory_max = max(
        (s.timeout_seconds for s in plan if s.builder_capability
         in ("factory_ground", "factory_air")),
        default=0.0,
    )
    return commander_max + factory_max


def validate_plan(plan: tuple[BuildStep, ...]) -> None:
    """Raises RegistryError on violation of contract rules:
       * per-step timeout bounds
       * critical path ≤ 90s
       * each capability appears exactly once.
    """
    if critical_path_seconds(plan) > 90.0:
        raise RegistryError(
            f"bootstrap plan critical path "
            f"{critical_path_seconds(plan):.1f}s > 90s (SC-003)"
        )
    seen: set[str] = set()
    for s in plan:
        if s.builder_capability == "commander" and s.timeout_seconds > 45.0:
            raise RegistryError(
                f"commander-built step {s.capability} timeout "
                f"{s.timeout_seconds}s > 45s"
            )
        if s.builder_capability in ("factory_ground", "factory_air") \
                and s.timeout_seconds > 30.0:
            raise RegistryError(
                f"factory-produced step {s.capability} timeout "
                f"{s.timeout_seconds}s > 30s"
            )
        if s.capability in seen:
            raise RegistryError(
                f"duplicate capability in bootstrap plan: {s.capability}"
            )
        seen.add(s.capability)


# Validate the default plan at import time so typos can't ship.
validate_plan(DEFAULT_BOOTSTRAP_PLAN)


DEFAULT_LIVE_FIXTURE_CLASS_BY_COMMAND: dict[str, tuple[str, ...]] = {
    "cmd-attack": ("commander", "hostile_target"),
    "cmd-attack-area": ("commander", "hostile_target"),
    "cmd-build-unit": ("commander", "resource_baseline"),
    "cmd-capture": ("commander", "capturable_target"),
    "cmd-capture-area": ("commander", "capturable_target"),
    "cmd-custom": ("commander", "custom_target"),
    "cmd-dgun": ("commander", "hostile_target"),
    "cmd-fight": ("commander", "hostile_target", "movement_lane"),
    "cmd-guard": ("commander", "damaged_friendly"),
    "cmd-load-onto": ("commander", "transport_unit", "payload_unit"),
    "cmd-load-units": ("commander", "transport_unit", "payload_unit"),
    "cmd-load-units-area": ("commander", "transport_unit", "payload_unit"),
    "cmd-move-unit": ("commander", "movement_lane"),
    "cmd-patrol": ("commander", "movement_lane"),
    "cmd-reclaim-area": ("commander", "reclaim_target"),
    "cmd-reclaim-feature": ("commander", "reclaim_target"),
    "cmd-reclaim-in-area": ("commander", "reclaim_target"),
    "cmd-reclaim-unit": ("commander", "reclaim_target"),
    "cmd-repair": ("commander", "damaged_friendly"),
    "cmd-restore-area": ("commander", "restore_target"),
    "cmd-resurrect": ("commander", "wreck_target"),
    "cmd-resurrect-in-area": ("commander", "wreck_target"),
    "cmd-self-destruct": ("cloakable", "builder"),
    "cmd-unload-unit": ("commander", "transport_unit", "payload_unit"),
    "cmd-unload-units-area": ("commander", "transport_unit", "payload_unit"),
}

DEFAULT_LIVE_FIXTURE_CLASSES: tuple[str, ...] = (
    "commander",
    "builder",
    "hostile_target",
    "movement_lane",
    "resource_baseline",
    "cloakable",
)

OPTIONAL_LIVE_FIXTURE_CLASSES: tuple[str, ...] = (
    "damaged_friendly",
    "reclaim_target",
    "transport_unit",
    "payload_unit",
    "capturable_target",
    "restore_target",
    "wreck_target",
    "custom_target",
)

_REFRESHABLE_SHARED_FIXTURE_CLASSES = frozenset(
    {
        "transport_unit",
        "payload_unit",
        "capturable_target",
        "restore_target",
        "wreck_target",
        "custom_target",
    }
)

_SHARED_FIXTURE_BACKING_KIND_BY_CLASS: dict[str, str] = {
    "builder": "unit",
    "capturable_target": "target-handle",
    "cloakable": "unit",
    "commander": "unit",
    "custom_target": "target-handle",
    "damaged_friendly": "unit",
    "hostile_target": "unit",
    "movement_lane": "area",
    "payload_unit": "unit",
    "reclaim_target": "feature",
    "resource_baseline": "area",
    "restore_target": "target-handle",
    "transport_unit": "unit",
    "wreck_target": "feature",
}

_FIXTURE_CLASSES_BY_CUSTOM_COMMAND_ID: dict[int, tuple[str, ...]] = {
    32102: ("hostile_target",),
    34571: ("builder",),
    34922: ("hostile_target",),
    34923: ("hostile_target",),
    34924: ("hostile_target",),
    34925: ("hostile_target",),
    37382: ("cloakable",),
}

TRANSPORT_DEPENDENT_COMMAND_IDS: tuple[str, ...] = (
    "cmd-load-onto",
    "cmd-load-units",
    "cmd-load-units-area",
    "cmd-unload-unit",
    "cmd-unload-units-area",
)

_SUPPORTED_TRANSPORT_VARIANTS: tuple[SupportedTransportVariant, ...] = (
    SupportedTransportVariant(
        variant_id="armatlas",
        def_name="armatlas",
        resolution_source="invoke_callback",
        provisioning_mode="natural-build",
        payload_rules=(
            "Preferred baseline ARM air transport variant.",
            "Must be alive and distinct from the pending payload unit.",
        ),
        priority=10,
    ),
    SupportedTransportVariant(
        variant_id="armhvytrans",
        def_name="armhvytrans",
        resolution_source="invoke_callback",
        provisioning_mode="natural-build",
        payload_rules=(
            "Acceptable heavy transport variant for transport_unit coverage.",
            "Must be alive and distinct from the pending payload unit.",
        ),
        priority=20,
    ),
)


def fixture_classes_for_command(command_id: str) -> tuple[str, ...]:
    return DEFAULT_LIVE_FIXTURE_CLASS_BY_COMMAND.get(command_id, ("commander",))


def transport_dependent_command_ids() -> tuple[str, ...]:
    return TRANSPORT_DEPENDENT_COMMAND_IDS


def is_transport_dependent_command(command_id: str) -> bool:
    return command_id in TRANSPORT_DEPENDENT_COMMAND_IDS


def supported_transport_variants() -> tuple[SupportedTransportVariant, ...]:
    return _SUPPORTED_TRANSPORT_VARIANTS


def supported_transport_variant_by_name(
    def_name: str,
) -> SupportedTransportVariant | None:
    for variant in _SUPPORTED_TRANSPORT_VARIANTS:
        if variant.def_name == def_name:
            return variant
    return None


def all_live_fixture_classes() -> tuple[str, ...]:
    return tuple(
        sorted(
            {
                *DEFAULT_LIVE_FIXTURE_CLASSES,
                *OPTIONAL_LIVE_FIXTURE_CLASSES,
            }
        )
    )


def provisioning_strategy_for_command(command_id: str) -> str:
    fixture_classes = set(fixture_classes_for_command(command_id))
    if fixture_classes.intersection(_REFRESHABLE_SHARED_FIXTURE_CLASSES):
        return "refreshable-shared-instance"
    if fixture_classes.difference(DEFAULT_LIVE_FIXTURE_CLASSES):
        return "shared-instance"
    return "baseline"


def command_fixture_dependency(command_id: str) -> CommandFixtureDependency:
    required_fixture_classes = fixture_classes_for_command(command_id)
    strategy = provisioning_strategy_for_command(command_id)
    blocking_fallback = (
        "missing_fixture"
        if strategy != "baseline"
        else "transport_interruption_only_if_session_unhealthy"
    )
    return CommandFixtureDependency(
        command_id=command_id,
        required_fixture_classes=required_fixture_classes,
        provisioning_strategy=strategy,  # type: ignore[arg-type]
        blocking_fallback=blocking_fallback,  # type: ignore[arg-type]
    )


def planned_command_ids_for_fixture_class(
    fixture_class: str,
    supported_command_ids: Iterable[str] | None = None,
) -> tuple[str, ...]:
    command_ids = supported_command_ids or DEFAULT_LIVE_FIXTURE_CLASS_BY_COMMAND.keys()
    return tuple(
        sorted(
            command_id
            for command_id in command_ids
            if fixture_class in fixture_classes_for_command(command_id)
        )
    )


def affected_commands_for_fixture_classes(
    fixture_classes: Iterable[str],
    supported_command_ids: Iterable[str] | None = None,
) -> tuple[str, ...]:
    classes = frozenset(fixture_classes)
    if not classes:
        return ()
    command_ids = supported_command_ids or DEFAULT_LIVE_FIXTURE_CLASS_BY_COMMAND.keys()
    return tuple(
        sorted(
            command_id
            for command_id in command_ids
            if classes.intersection(fixture_classes_for_command(command_id))
        )
    )


def known_custom_command_ids() -> tuple[int, ...]:
    return tuple(sorted(_FIXTURE_CLASSES_BY_CUSTOM_COMMAND_ID))


def fixture_classes_for_custom_command_id(command_id: int) -> tuple[str, ...]:
    return _FIXTURE_CLASSES_BY_CUSTOM_COMMAND_ID.get(command_id, ("custom_target",))


def shared_fixture_backing_kind(fixture_class: str) -> str:
    return _SHARED_FIXTURE_BACKING_KIND_BY_CLASS.get(fixture_class, "target-handle")


def build_fixture_class_statuses(
    *,
    updated_at: str,
    provisioned_fixture_classes: Iterable[str],
    missing_fixture_classes: Iterable[str],
    refreshed_fixture_classes: Iterable[str] = (),
    unusable_fixture_classes: Iterable[str] = (),
    ready_instance_ids_by_class: dict[str, tuple[str, ...]] | None = None,
    transition_reason_by_class: dict[str, str] | None = None,
    supported_command_ids: Iterable[str] | None = None,
) -> tuple[FixtureClassStatus, ...]:
    provisioned = frozenset(provisioned_fixture_classes)
    missing = frozenset(missing_fixture_classes)
    refreshed = frozenset(refreshed_fixture_classes)
    unusable = frozenset(unusable_fixture_classes)
    ready_ids = ready_instance_ids_by_class or {}
    reasons = transition_reason_by_class or {}
    classes = supported_command_ids or all_live_fixture_classes()
    statuses: list[FixtureClassStatus] = []
    for fixture_class in all_live_fixture_classes():
        planned_command_ids = planned_command_ids_for_fixture_class(
            fixture_class,
            supported_command_ids=supported_command_ids,
        )
        if fixture_class in unusable:
            status = "unusable"
            affected = planned_command_ids
            default_reason = "fixture became unusable before dependent commands ran"
        elif fixture_class in refreshed:
            status = "refreshed"
            affected = ()
            default_reason = "fixture was refreshed or replaced after going stale"
        elif fixture_class in provisioned:
            status = "provisioned"
            affected = ()
            default_reason = "fixture was provisioned and remained usable"
        elif fixture_class in missing:
            status = "missing"
            affected = planned_command_ids
            default_reason = "fixture could not be provisioned for this run"
        else:
            status = "planned"
            affected = ()
            default_reason = "fixture is planned but was not exercised in this run"
        statuses.append(
            FixtureClassStatus(
                fixture_class=fixture_class,
                status=status,  # type: ignore[arg-type]
                planned_command_ids=planned_command_ids,
                ready_instance_ids=ready_ids.get(fixture_class, ()),
                last_transition_reason=reasons.get(fixture_class, default_reason),
                affected_command_ids=affected,
                updated_at=updated_at,
            )
        )
    return tuple(statuses)


def build_shared_fixture_instance(
    *,
    fixture_class: str,
    instance_id: str,
    backing_id: str,
    usability_state: str = "ready",
    refresh_count: int = 0,
    last_ready_at: str | None = None,
    replacement_of: str | None = None,
) -> SharedFixtureInstance:
    return SharedFixtureInstance(
        instance_id=instance_id,
        fixture_class=fixture_class,
        backing_kind=shared_fixture_backing_kind(fixture_class),  # type: ignore[arg-type]
        backing_id=backing_id,
        usability_state=usability_state,  # type: ignore[arg-type]
        refresh_count=refresh_count,
        last_ready_at=last_ready_at,
        replacement_of=replacement_of,
    )


# ---- execution + reset (engine-dependent, kept thin) --------------------


def execute_bootstrap(session: Any, stream: Any,
                       plan: tuple[BuildStep, ...] = DEFAULT_BOOTSTRAP_PLAN
                       ) -> BootstrapContext:
    """Phase-1 orchestration per contracts/bootstrap-plan.md §Plan
    execution protocol.

    This is a thin coordinator. The heavy lifting — `SubmitCommands`,
    snapshot sampling, def-id resolution — is done via the session and
    stream helpers the orchestrator provides. The function returns a
    BootstrapContext or raises RuntimeError on per-step timeout.

    This function DOES touch wall-clock time (for step timeouts) —
    that's acceptable because it is not part of the verify-predicate
    decision path (FR-012) and the timeout is fail-closed: a timeout
    aborts the entire run with all-precondition_unmet rows.
    """
    # The actual implementation is host-dependent (needs real session /
    # stream helpers and the InvokeCallback def-id resolver). We expose
    # a stub that fails loudly: real callers wire it at the orchestrator.
    raise NotImplementedError(
        "execute_bootstrap is wired in the orchestrator (__init__.py) "
        "— this module-level stub is a contract marker."
    )


def reset_to_manifest(context: BootstrapContext, session: Any, stream: Any,
                       timeout_seconds: float = 10.0) -> BootstrapContext:
    """Between-arm reset per contracts/bootstrap-plan.md §3.

    Same pattern as execute_bootstrap: the actual snapshot-sampling +
    dispatch loop is wired in the orchestrator where it has live
    session/stream handles.
    """
    raise NotImplementedError(
        "reset_to_manifest is wired in the orchestrator (__init__.py) "
        "— this module-level stub is a contract marker."
    )


__all__ = [
    "Vector3",
    "BuildStep",
    "DEFAULT_BOOTSTRAP_PLAN",
    "BootstrapContext",
    "compute_manifest",
    "compute_bootstrap_manifest",
    "manifest_shortages",
    "critical_path_seconds",
    "validate_plan",
    "DEFAULT_LIVE_FIXTURE_CLASS_BY_COMMAND",
    "DEFAULT_LIVE_FIXTURE_CLASSES",
    "OPTIONAL_LIVE_FIXTURE_CLASSES",
    "TRANSPORT_DEPENDENT_COMMAND_IDS",
    "all_live_fixture_classes",
    "command_fixture_dependency",
    "planned_command_ids_for_fixture_class",
    "affected_commands_for_fixture_classes",
    "known_custom_command_ids",
    "is_transport_dependent_command",
    "fixture_classes_for_custom_command_id",
    "supported_transport_variant_by_name",
    "supported_transport_variants",
    "transport_dependent_command_ids",
    "build_fixture_class_statuses",
    "build_shared_fixture_instance",
    "fixture_classes_for_command",
    "execute_bootstrap",
    "reset_to_manifest",
]

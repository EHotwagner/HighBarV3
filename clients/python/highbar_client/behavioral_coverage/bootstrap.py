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
from typing import Any, Iterable, Optional

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
    enemy_seed_id: Optional[int] = None
    manifest: tuple[tuple[str, int], ...] = ()
    cheats_enabled: bool = False
    def_id_by_name: dict[str, int] = None                     # type: ignore[assignment]

    def __post_init__(self):
        if self.capability_units is None:
            self.capability_units = {}
        if self.def_id_by_name is None:
            self.def_id_by_name = {}


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
    "cmd-build-unit": ("commander", "builder", "resource_baseline"),
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
    "cmd-self-destruct": ("cloakable",),
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


def fixture_classes_for_command(command_id: str) -> tuple[str, ...]:
    return DEFAULT_LIVE_FIXTURE_CLASS_BY_COMMAND.get(command_id, ("commander",))


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
    "manifest_shortages",
    "critical_path_seconds",
    "validate_plan",
    "DEFAULT_LIVE_FIXTURE_CLASS_BY_COMMAND",
    "DEFAULT_LIVE_FIXTURE_CLASSES",
    "OPTIONAL_LIVE_FIXTURE_CLASSES",
    "fixture_classes_for_command",
    "execute_bootstrap",
    "reset_to_manifest",
]

# SPDX-License-Identifier: GPL-2.0-only
"""Shared verify-predicate building blocks for the behavioral-coverage
macro driver.

All predicates are **pure** (contracts/arm-registry.md §Pure-function
discipline): no clock reads, no rng, no I/O, no mutation of captured
state. Same inputs → same outputs.

Per spec §Edge Cases:
  - Predicates that target a specific unit re-resolve the target's
    `unit_id` from the post-dispatch snapshot rather than caching.
  - Predicates tolerate ≥ 2 snapshots of slack before declaring
    `effect_not_observed`.
"""

from __future__ import annotations

import math
import re
from typing import Any, Callable, Optional

from .types import (
    NotWireObservable,
    SnapshotPair,
    VerificationOutcome,
)


# ---- helpers -------------------------------------------------------------


def _find_unit(snap: Any, unit_id: int) -> Optional[Any]:
    """Find ``unit_id`` in snap.own_units or visible_enemies. Returns
    None if absent (e.g., destroyed).
    """
    for u in snap.own_units:
        if u.unit_id == unit_id:
            return u
    for e in snap.visible_enemies:
        if e.unit_id == unit_id:
            return e
    return None


def _find_feature(snap: Any, feature_id: int) -> Optional[Any]:
    for feature in getattr(snap, "map_features", ()):
        if getattr(feature, "feature_id", 0) == feature_id:
            return feature
    return None


def _delta_kind(delta: Any) -> str:
    which_oneof = getattr(delta, "WhichOneof", None)
    if which_oneof is None:
        return ""
    try:
        return which_oneof("kind") or ""
    except Exception:  # noqa: BLE001
        return ""


def _distance(p1: Any, p2: Any) -> float:
    return math.sqrt(
        (p1.x - p2.x) ** 2 + (p1.y - p2.y) ** 2 + (p1.z - p2.z) ** 2
    )


_HELPER_PARITY_TOKENS = (
    "helper parity",
    "local helper",
    "stubbed",
    "commented out",
    "cmdwantedspeed",
    "cmdpriority",
    "cmdmiscpriority",
    "cmdmanualfire",
    "cmdfireatradar",
    "cmdairstrafe",
)
_LUA_REWRITE_TOKENS = (
    "place_target_on_ground",
    "lua rewrite",
    "rewritten to map",
    "set-target rewrite",
    "target contract rewrote",
)
_UNIT_SHAPE_TOKENS = (
    "fixed-wing",
    "fixed wing",
    "non-commander",
    "non commander",
    "manual launch substitution",
    "does not receive the relevant bar command shape",
    "does not receive the command descriptor",
    "unit-shape",
)
_MOD_OPTION_TOKENS = (
    "emprework",
    "mod option",
    "mod-option",
    "modoption",
)
_CUSTOM_COMMAND_ID_PATTERN = re.compile(r"\b(32102|34571|34922|34923|34924|34925|37382)\b")


def semantic_gate_metadata(
    command_id: str,
    detail: str | None,
) -> tuple[str, str, int | None] | None:
    lowered = (detail or "").lower()
    if not lowered:
        return None
    custom_command_id = _extract_custom_command_id(lowered)
    if any(token in lowered for token in _MOD_OPTION_TOKENS):
        return (
            "mod-option",
            detail or f"{command_id} is blocked by a required BAR mod option",
            custom_command_id,
        )
    if any(token in lowered for token in _LUA_REWRITE_TOKENS):
        return (
            "lua-rewrite",
            detail or f"{command_id} is blocked by BAR Lua command-shape rewriting",
            custom_command_id,
        )
    if any(token in lowered for token in _UNIT_SHAPE_TOKENS):
        return (
            "unit-shape",
            detail or f"{command_id} is blocked by unit eligibility or command-shape constraints",
            custom_command_id,
        )
    if any(token in lowered for token in _HELPER_PARITY_TOKENS):
        return (
            "helper-parity",
            detail or f"{command_id} is blocked by a local helper parity gap",
            custom_command_id,
        )
    return None


def _extract_custom_command_id(detail: str) -> int | None:
    match = _CUSTOM_COMMAND_ID_PATTERN.search(detail)
    if match is None:
        return None
    return int(match.group(1))


# ---- factory functions ---------------------------------------------------


def position_delta_predicate(
    unit_id_selector: Callable[[Any], Optional[int]],
    min_delta: float = 100.0,
) -> Callable[[SnapshotPair, list], VerificationOutcome]:
    """Verify that a unit's position changed by ≥ min_delta elmos between
    before and after snapshots.

    ``unit_id_selector``: pure function `(before_snap) -> unit_id | None`.
    The predicate re-resolves the target in both snapshots by id, so a
    mid-test commander-destroyed race shows up as target_unit_destroyed.
    """

    def predicate(pair: SnapshotPair, _deltas: list) -> VerificationOutcome:
        uid = unit_id_selector(pair.before)
        if uid is None:
            return VerificationOutcome(
                verified="na", evidence="target unit not in pre-snapshot",
                error="precondition_unmet",
            )
        pre = _find_unit(pair.before, uid)
        post = _find_unit(pair.after, uid)
        if pre is None:
            return VerificationOutcome(
                verified="na", evidence=f"unit_id={uid} not in pre-snapshot",
                error="precondition_unmet",
            )
        if post is None:
            return VerificationOutcome(
                verified="false",
                evidence=f"unit_id={uid} absent from post-snapshot",
                error="target_unit_destroyed",
            )
        delta = _distance(pre.position, post.position)
        if delta >= min_delta:
            return VerificationOutcome(
                verified="true",
                evidence=(
                    f"position dx={post.position.x - pre.position.x:.3f} "
                    f"dz={post.position.z - pre.position.z:.3f} "
                    f"|d|={delta:.3f} (threshold {min_delta:.3f})"
                ),
            )
        return VerificationOutcome(
            verified="false",
            evidence=(
                f"position delta={delta:.3f} < threshold {min_delta:.3f}"
            ),
            error="effect_not_observed",
        )

    return predicate


def movement_progress_predicate(
    unit_id_selector: Callable[[Any], Optional[int]],
    *,
    min_delta: float = 48.0,
) -> Callable[[SnapshotPair, list], VerificationOutcome]:
    return position_delta_predicate(unit_id_selector=unit_id_selector, min_delta=min_delta)


def unit_count_delta_predicate(
    expected_delta: int,
    new_unit_filter: Optional[Callable[[Any], bool]] = None,
) -> Callable[[SnapshotPair, list], VerificationOutcome]:
    """Verify own_units changed by exactly ``expected_delta`` entries
    between before and after snapshots, optionally requiring the newly
    appeared unit to satisfy ``new_unit_filter`` (e.g., `lambda u:
    u.under_construction`).
    """

    def predicate(pair: SnapshotPair, _deltas: list) -> VerificationOutcome:
        pre_ids = {u.unit_id for u in pair.before.own_units}
        post_ids = {u.unit_id for u in pair.after.own_units}
        new = post_ids - pre_ids
        removed = pre_ids - post_ids
        net = len(post_ids) - len(pre_ids)
        if net != expected_delta:
            return VerificationOutcome(
                verified="false",
                evidence=(
                    f"unit_count_delta={net} expected={expected_delta} "
                    f"(new={len(new)} removed={len(removed)})"
                ),
                error="effect_not_observed",
            )
        if new_unit_filter is not None and len(new) >= 1:
            for u in pair.after.own_units:
                if u.unit_id in new and not new_unit_filter(u):
                    return VerificationOutcome(
                        verified="false",
                        evidence=(
                            f"new unit_id={u.unit_id} def={u.def_id} "
                            f"failed filter (under_construction="
                            f"{u.under_construction})"
                        ),
                        error="effect_not_observed",
                    )
        new_details = []
        for u in pair.after.own_units:
            if u.unit_id in new:
                new_details.append(
                    f"unit_id={u.unit_id} def={u.def_id} "
                    f"under_construction={u.under_construction}"
                )
        return VerificationOutcome(
            verified="true",
            evidence=f"unit_count_delta=+{net} " + "; ".join(new_details),
        )

    return predicate


def health_delta_predicate(
    target_selector: Callable[[Any], Optional[int]],
    min_drop: float = 1.0,
    target_is_enemy: bool = True,
) -> Callable[[SnapshotPair, list], VerificationOutcome]:
    """Verify that a target's health dropped by ≥ ``min_drop`` between
    snapshots, OR that the target disappeared (destroyed).
    """

    def predicate(pair: SnapshotPair, deltas: list) -> VerificationOutcome:
        tid = target_selector(pair.before)
        if tid is None:
            return VerificationOutcome(
                verified="na", evidence="no target unit in pre-snapshot",
                error="precondition_unmet",
            )
        pre = _find_unit(pair.before, tid)
        post = _find_unit(pair.after, tid)
        if pre is None:
            return VerificationOutcome(
                verified="na", evidence=f"target {tid} missing pre-snapshot",
                error="precondition_unmet",
            )
        if post is None:
            # Target destroyed — sufficient signal for attack arms.
            destroyed_event = any(
                getattr(d, "WhichOneof", lambda _: "")("kind")
                in ("enemy_destroyed" if target_is_enemy else "unit_destroyed")
                for d in deltas
            )
            return VerificationOutcome(
                verified="true",
                evidence=f"target {tid} destroyed (delta_event={destroyed_event})",
            )
        drop = pre.health - post.health
        if drop >= min_drop:
            return VerificationOutcome(
                verified="true",
                evidence=(
                    f"target_health before={pre.health:.3f} "
                    f"after={post.health:.3f} delta=-{drop:.3f}"
                ),
            )
        return VerificationOutcome(
            verified="false",
            evidence=(
                f"target_health before={pre.health:.3f} "
                f"after={post.health:.3f} delta=-{drop:.3f} "
                f"(threshold {min_drop:.3f})"
            ),
            error="effect_not_observed",
        )

    return predicate


def combat_engagement_predicate(
    unit_id_selector: Callable[[Any], Optional[int]],
    target_selector: Callable[[Any], Optional[int]],
    *,
    min_drop: float = 1.0,
    min_distance_delta: float = 48.0,
) -> Callable[[SnapshotPair, list], VerificationOutcome]:
    def predicate(pair: SnapshotPair, deltas: list) -> VerificationOutcome:
        health_outcome = health_delta_predicate(
            target_selector=target_selector,
            min_drop=min_drop,
            target_is_enemy=True,
        )(pair, deltas)
        if health_outcome.verified == "true":
            return health_outcome

        uid = unit_id_selector(pair.before)
        tid = target_selector(pair.before)
        if uid is None or tid is None:
            return VerificationOutcome(
                verified="na",
                evidence="combat target or acting unit missing pre-snapshot",
                error="precondition_unmet",
            )
        pre_unit = _find_unit(pair.before, uid)
        post_unit = _find_unit(pair.after, uid)
        pre_target = _find_unit(pair.before, tid)
        post_target = _find_unit(pair.after, tid)
        if any(item is None for item in (pre_unit, post_unit, pre_target, post_target)):
            return health_outcome
        pre_distance = _distance(pre_unit.position, pre_target.position)
        post_distance = _distance(post_unit.position, post_target.position)
        distance_delta = pre_distance - post_distance
        if distance_delta >= min_distance_delta:
            return VerificationOutcome(
                verified="true",
                evidence=(
                    f"distance_to_target shrank by {distance_delta:.3f} "
                    f"(threshold {min_distance_delta:.3f}) before direct damage landed"
                ),
            )
        return VerificationOutcome(
            verified="false",
            evidence=(
                f"target health unchanged and distance delta={distance_delta:.3f} "
                f"< threshold {min_distance_delta:.3f}"
            ),
            error="effect_not_observed",
        )

    return predicate


def build_progress_monotonic_predicate(
    builder_id_selector: Callable[[Any], Optional[int]],
) -> Callable[[SnapshotPair, list], VerificationOutcome]:
    """Verify a new construction site's build_progress strictly
    increased between two post-dispatch snapshots.

    Expects the SnapshotPair to have ``before`` = pre-dispatch and
    ``after`` = snapshot sampled ≥ verify_window_frames after dispatch.
    ``builder_id_selector`` identifies which commander/factory issued
    the build order; the new unit is any unit in after.own_units not
    in before.own_units.
    """

    def predicate(pair: SnapshotPair, _deltas: list) -> VerificationOutcome:
        builder_id = builder_id_selector(pair.before)
        pre_ids = {u.unit_id for u in pair.before.own_units}
        if builder_id is not None:
            created_by_builder = [
                getattr(delta, "unit_created")
                for delta in pair.delta_log
                if _delta_kind(delta) == "unit_created"
                and getattr(getattr(delta, "unit_created"), "builder_id", 0) == builder_id
                and getattr(getattr(delta, "unit_created"), "unit_id", 0) not in pre_ids
            ]
            if created_by_builder:
                created = max(created_by_builder, key=lambda item: getattr(item, "unit_id", 0))
                return VerificationOutcome(
                    verified="true",
                    evidence=(
                        f"unit_created unit_id={created.unit_id} "
                        f"builder_id={created.builder_id}"
                    ),
                )

        pre_ids = {u.unit_id for u in pair.before.own_units}
        new_units = [u for u in pair.after.own_units
                     if u.unit_id not in pre_ids]
        if not new_units:
            return VerificationOutcome(
                verified="false",
                evidence="no new own_units between before and after",
                error="effect_not_observed",
            )
        # Pick the newest (highest unit_id) as the freshly built one.
        new_unit = max(new_units, key=lambda u: u.unit_id)
        if not new_unit.under_construction:
            return VerificationOutcome(
                verified="false",
                evidence=(
                    f"new unit_id={new_unit.unit_id} not under_construction"
                ),
                error="effect_not_observed",
            )
        if new_unit.build_progress <= 0.0:
            return VerificationOutcome(
                verified="false",
                evidence=(
                    f"new unit_id={new_unit.unit_id} build_progress=0 "
                    f"(construction site not started)"
                ),
                error="effect_not_observed",
            )
        return VerificationOutcome(
            verified="true",
            evidence=(
                f"new unit_id={new_unit.unit_id} def={new_unit.def_id} "
                f"under_construction=true "
                f"build_progress={new_unit.build_progress:.3f}"
            ),
        )

    return predicate


def construction_started_predicate(
    builder_id_selector: Callable[[Any], Optional[int]],
) -> Callable[[SnapshotPair, list], VerificationOutcome]:
    return build_progress_monotonic_predicate(builder_id_selector=builder_id_selector)


def unit_destroyed_predicate(
    target_selector: Callable[[Any], Optional[int]],
) -> Callable[[SnapshotPair, list], VerificationOutcome]:
    def predicate(pair: SnapshotPair, deltas: list) -> VerificationOutcome:
        target_id = target_selector(pair.before)
        if target_id is None:
            return VerificationOutcome(
                verified="na",
                evidence="target unit not in pre-snapshot",
                error="precondition_unmet",
            )
        pre = _find_unit(pair.before, target_id)
        if pre is None:
            return VerificationOutcome(
                verified="na",
                evidence=f"unit_id={target_id} not in pre-snapshot",
                error="precondition_unmet",
            )
        if _find_unit(pair.after, target_id) is None:
            return VerificationOutcome(
                verified="true",
                evidence=f"unit_id={target_id} absent from post-snapshot",
            )
        if any(
            _delta_kind(delta) == "unit_destroyed"
            and getattr(getattr(delta, "unit_destroyed"), "unit_id", 0) == target_id
            for delta in deltas
        ):
            return VerificationOutcome(
                verified="true",
                evidence=f"unit_destroyed delta observed for unit_id={target_id}",
            )
        return VerificationOutcome(
            verified="false",
            evidence=f"unit_id={target_id} still present after self_destruct window",
            error="effect_not_observed",
        )

    return predicate


def feature_consumed_predicate(
    feature_id_selector: Callable[[Any], Optional[int]],
) -> Callable[[SnapshotPair, list], VerificationOutcome]:
    def predicate(pair: SnapshotPair, deltas: list) -> VerificationOutcome:
        feature_id = feature_id_selector(pair.before)
        if feature_id is None:
            return VerificationOutcome(
                verified="na",
                evidence="target feature not in pre-snapshot",
                error="precondition_unmet",
            )
        pre = _find_feature(pair.before, feature_id)
        if pre is None:
            return VerificationOutcome(
                verified="na",
                evidence=f"feature_id={feature_id} not in pre-snapshot",
                error="precondition_unmet",
            )
        if _find_feature(pair.after, feature_id) is None:
            return VerificationOutcome(
                verified="true",
                evidence=f"feature_id={feature_id} absent from post-snapshot",
            )
        if any(
            _delta_kind(delta) == "feature_destroyed"
            and getattr(getattr(delta, "feature_destroyed"), "feature_id", 0) == feature_id
            for delta in deltas
        ):
            return VerificationOutcome(
                verified="true",
                evidence=f"feature_destroyed delta observed for feature_id={feature_id}",
            )
        return VerificationOutcome(
            verified="false",
            evidence=f"feature_id={feature_id} still present after reclaim/resurrect window",
            error="effect_not_observed",
        )

    return predicate


def repair_health_gain_predicate(
    target_selector: Callable[[Any], Optional[int]],
    *,
    min_gain: float = 1.0,
) -> Callable[[SnapshotPair, list], VerificationOutcome]:
    def predicate(pair: SnapshotPair, _deltas: list) -> VerificationOutcome:
        target_id = target_selector(pair.before)
        if target_id is None:
            return VerificationOutcome(
                verified="na",
                evidence="repair target not in pre-snapshot",
                error="precondition_unmet",
            )
        pre = _find_unit(pair.before, target_id)
        post = _find_unit(pair.after, target_id)
        if pre is None or post is None:
            return VerificationOutcome(
                verified="false",
                evidence=f"repair target unit_id={target_id} was not observable across the window",
                error="target_unit_destroyed",
            )
        gain = post.health - pre.health
        if gain >= min_gain:
            return VerificationOutcome(
                verified="true",
                evidence=(
                    f"repair target health before={pre.health:.3f} "
                    f"after={post.health:.3f} delta=+{gain:.3f}"
                ),
            )
        return VerificationOutcome(
            verified="false",
            evidence=(
                f"repair target health before={pre.health:.3f} "
                f"after={post.health:.3f} delta=+{gain:.3f} "
                f"(threshold {min_gain:.3f})"
            ),
            error="effect_not_observed",
        )

    return predicate


def guard_proximity_predicate(
    unit_id_selector: Callable[[Any], Optional[int]],
    target_selector: Callable[[Any], Optional[int]],
    *,
    min_distance_delta: float = 24.0,
    max_post_distance: float = 160.0,
) -> Callable[[SnapshotPair, list], VerificationOutcome]:
    def predicate(pair: SnapshotPair, _deltas: list) -> VerificationOutcome:
        unit_id = unit_id_selector(pair.before)
        target_id = target_selector(pair.before)
        if unit_id is None or target_id is None:
            return VerificationOutcome(
                verified="na",
                evidence="guard actor or target missing pre-snapshot",
                error="precondition_unmet",
            )
        pre_unit = _find_unit(pair.before, unit_id)
        post_unit = _find_unit(pair.after, unit_id)
        pre_target = _find_unit(pair.before, target_id)
        post_target = _find_unit(pair.after, target_id)
        if any(item is None for item in (pre_unit, post_unit, pre_target, post_target)):
            return VerificationOutcome(
                verified="false",
                evidence="guard actor or target was not observable across the window",
                error="target_unit_destroyed",
            )
        pre_distance = _distance(pre_unit.position, pre_target.position)
        post_distance = _distance(post_unit.position, post_target.position)
        distance_delta = pre_distance - post_distance
        if distance_delta >= min_distance_delta or (
            post_distance <= max_post_distance and post_distance < pre_distance
        ):
            return VerificationOutcome(
                verified="true",
                evidence=(
                    f"distance_to_guard_target before={pre_distance:.3f} "
                    f"after={post_distance:.3f} delta=-{distance_delta:.3f}"
                ),
            )
        return VerificationOutcome(
            verified="false",
            evidence=(
                f"distance_to_guard_target before={pre_distance:.3f} "
                f"after={post_distance:.3f} delta=-{distance_delta:.3f}"
            ),
            error="effect_not_observed",
        )

    return predicate


def capture_ownership_predicate(
    target_selector: Callable[[Any], Optional[int]],
) -> Callable[[SnapshotPair, list], VerificationOutcome]:
    def predicate(pair: SnapshotPair, deltas: list) -> VerificationOutcome:
        target_id = target_selector(pair.before)
        if target_id is None:
            return VerificationOutcome(
                verified="na",
                evidence="capture target missing pre-snapshot",
                error="precondition_unmet",
            )
        pre_target = _find_unit(pair.before, target_id)
        if pre_target is None:
            return VerificationOutcome(
                verified="na",
                evidence=f"capture target unit_id={target_id} not in pre-snapshot",
                error="precondition_unmet",
            )
        if any(getattr(unit, "unit_id", 0) == target_id for unit in pair.after.own_units):
            return VerificationOutcome(
                verified="true",
                evidence=f"captured unit_id={target_id} now appears in own_units",
            )
        if any(
            _delta_kind(delta) in {"unit_captured", "unit_given"}
            and getattr(getattr(delta, _delta_kind(delta)), "unit_id", 0) == target_id
            for delta in deltas
        ):
            return VerificationOutcome(
                verified="true",
                evidence=f"capture delta observed for unit_id={target_id}",
            )
        return VerificationOutcome(
            verified="false",
            evidence=f"capture target unit_id={target_id} remained hostile or unobserved",
            error="effect_not_observed",
        )

    return predicate


# ---- selector helpers ---------------------------------------------------


def commander_selector(bootstrap_ctx: Any) -> Optional[int]:
    """Return the commander's unit_id from the BootstrapContext, or
    None if not yet provisioned.
    """
    return getattr(bootstrap_ctx, "commander_unit_id", None)


def capability_selector(capability: str) -> Callable[[Any], Optional[int]]:
    """Return a selector that pulls the capability's unit_id from the
    BootstrapContext's capability_units dict.
    """

    def _sel(bootstrap_ctx: Any) -> Optional[int]:
        units = getattr(bootstrap_ctx, "capability_units", None)
        if units is None:
            return None
        return units.get(capability)

    return _sel


__all__ = [
    "capture_ownership_predicate",
    "position_delta_predicate",
    "unit_count_delta_predicate",
    "health_delta_predicate",
    "build_progress_monotonic_predicate",
    "feature_consumed_predicate",
    "guard_proximity_predicate",
    "repair_health_gain_predicate",
    "semantic_gate_metadata",
    "commander_selector",
    "capability_selector",
    "unit_destroyed_predicate",
    "NotWireObservable",
]

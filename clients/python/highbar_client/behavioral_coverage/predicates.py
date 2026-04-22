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


def _distance(p1: Any, p2: Any) -> float:
    return math.sqrt(
        (p1.x - p2.x) ** 2 + (p1.y - p2.y) ** 2 + (p1.z - p2.z) ** 2
    )


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
    "position_delta_predicate",
    "unit_count_delta_predicate",
    "health_delta_predicate",
    "build_progress_monotonic_predicate",
    "commander_selector",
    "capability_selector",
    "NotWireObservable",
]

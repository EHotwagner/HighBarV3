# SPDX-License-Identifier: GPL-2.0-only
"""Observation predicates for admin behavioral evidence."""

from __future__ import annotations

from dataclasses import dataclass, field
from math import hypot
from typing import Any

from .admin_actions import AdminObservation


@dataclass(frozen=True)
class ObservedMatchState:
    frame: int = 0
    speed: float = 1.0
    resources: dict[tuple[int, int], float] = field(default_factory=dict)
    units: dict[int, dict[str, Any]] = field(default_factory=dict)
    leases: dict[str, str] = field(default_factory=dict)


def frame_stopped(before: ObservedMatchState, after: ObservedMatchState, *, tolerance_frames: int = 1) -> AdminObservation:
    delta = after.frame - before.frame
    observed = delta <= tolerance_frames
    return AdminObservation("pause", "frame_stopped", True, delta,
                            tolerance=float(tolerance_frames), observed=observed,
                            failure_reason="" if observed else f"frame advanced by {delta}")


def frame_advanced(before: ObservedMatchState, after: ObservedMatchState) -> AdminObservation:
    observed = after.frame > before.frame
    return AdminObservation("pause", "frame_advanced", True, after.frame - before.frame,
                            observed=observed,
                            failure_reason="" if observed else "frame did not advance")


def speed_matches(after: ObservedMatchState, expected: float, *, tolerance: float = 0.35) -> AdminObservation:
    observed = abs(after.speed - expected) <= tolerance
    return AdminObservation("global_speed", "speed_multiplier", expected, after.speed,
                            tolerance=tolerance, observed=observed,
                            failure_reason="" if observed else f"speed {after.speed} not within {tolerance} of {expected}")


def resource_increased(
    before: ObservedMatchState,
    after: ObservedMatchState,
    *,
    team_id: int,
    resource_id: int,
    amount: float,
    tolerance: float = 0.01,
) -> AdminObservation:
    key = (team_id, resource_id)
    delta = after.resources.get(key, 0.0) - before.resources.get(key, 0.0)
    observed = delta + tolerance >= amount
    return AdminObservation("resource_grant", "resource_delta", amount, delta,
                            tolerance=tolerance, observed=observed,
                            failure_reason="" if observed else f"resource delta {delta} below {amount}")


def unit_spawned(
    before: ObservedMatchState,
    after: ObservedMatchState,
    *,
    team_id: int,
    unit_def_id: int,
    position: tuple[float, float, float],
    tolerance: float = 128.0,
) -> AdminObservation:
    before_ids = set(before.units)
    for unit_id, unit in after.units.items():
        if unit_id in before_ids:
            continue
        if unit.get("team_id") != team_id or unit.get("unit_def_id") != unit_def_id:
            continue
        actual = unit.get("position", (0.0, 0.0, 0.0))
        distance = hypot(actual[0] - position[0], actual[2] - position[2])
        if distance <= tolerance:
            return AdminObservation("unit_spawn", "unit_spawned", unit_def_id, unit_id,
                                    tolerance=tolerance, observed=True)
    return AdminObservation("unit_spawn", "unit_spawned", unit_def_id, None,
                            tolerance=tolerance, observed=False,
                            failure_reason="matching spawned unit not observed")


def owner_changed(before: ObservedMatchState, after: ObservedMatchState, *, unit_id: int, to_team_id: int) -> AdminObservation:
    before_owner = before.units.get(unit_id, {}).get("team_id")
    after_owner = after.units.get(unit_id, {}).get("team_id")
    observed = before_owner != to_team_id and after_owner in {to_team_id, -1}
    return AdminObservation("unit_transfer", "owner_changed", to_team_id, after_owner,
                            observed=observed,
                            failure_reason="" if observed else f"owner changed from {before_owner} to {after_owner}")


def rejected_effect_absent(before: ObservedMatchState, after: ObservedMatchState, *, action: Any) -> AdminObservation:
    action_case = action.WhichOneof("action")
    if action_case == "pause":
        observed = after.frame >= before.frame
        actual = after.frame - before.frame
        reason = "" if observed else "frame regressed after rejected pause request"
    elif action_case == "global_speed":
        actual = after.speed
        observed = after.speed == before.speed
        reason = "" if observed else f"speed changed from {before.speed} to {after.speed}"
    elif action_case == "resource_grant":
        key = (int(action.resource_grant.team_id), int(action.resource_grant.resource_id))
        actual = after.resources.get(key)
        observed = before.resources.get(key) == after.resources.get(key)
        reason = "" if observed else f"resource {key} changed after rejected grant"
    elif action_case == "unit_spawn":
        spawn = action.unit_spawn
        actual = len(after.units) - len(before.units)
        observed = not any(
            int(unit.get("team_id", -1)) == int(spawn.team_id)
            and int(unit.get("unit_def_id", -1)) == int(spawn.unit_def_id)
            and unit_id not in before.units
            for unit_id, unit in after.units.items()
        )
        reason = "" if observed else "matching unit appeared after rejected spawn"
    elif action_case == "unit_transfer":
        unit_id = int(action.unit_transfer.unit_id)
        actual = after.units.get(unit_id, {}).get("team_id")
        observed = before.units.get(unit_id, {}).get("team_id") == actual
        reason = "" if observed else f"unit {unit_id} owner changed after rejected transfer"
    else:
        actual = None
        observed = unchanged_state(before, after).observed
        reason = "" if observed else "state changed after rejected request"
    return AdminObservation(str(action_case), "unchanged_state", True, actual,
                            observed=observed, failure_reason=reason)


def unchanged_state(before: ObservedMatchState, after: ObservedMatchState, *, scope: str = "state") -> AdminObservation:
    observed = (
        before.speed == after.speed
        and before.resources == after.resources
        and before.units == after.units
        and before.leases == after.leases
    )
    return AdminObservation(scope, "unchanged_state", True, observed,
                            observed=observed,
                            failure_reason="" if observed else "non-frame state mutated after rejected request")

# SPDX-License-Identifier: GPL-2.0-only
"""Strict admin behavioral evidence evaluation."""

from __future__ import annotations

from typing import Any

from .admin_actions import AdminBehaviorScenario, AdminEvidenceRecord
from .admin_observations import (
    ObservedMatchState,
    frame_advanced,
    frame_stopped,
    owner_changed,
    rejected_effect_absent,
    resource_increased,
    speed_matches,
    unchanged_state,
    unit_spawned,
)
from ..highbar import service_pb2

BEHAVIORAL_EVIDENCE_SOURCES = {
    "state_stream",
    "snapshot",
    "delta_window",
    "snapshot_delta",
    "engine_log",
}


def status_name(status: int) -> str:
    return service_pb2.AdminActionStatus.Name(status)


def status_value(name_or_value: str | int) -> int:
    if isinstance(name_or_value, int):
        return name_or_value
    return service_pb2.AdminActionStatus.Value(name_or_value)


def state_from_mapping(payload: dict[str, Any]) -> ObservedMatchState:
    resources: dict[tuple[int, int], float] = {}
    for item in payload.get("resources", []):
        resources[(int(item["team_id"]), int(item["resource_id"]))] = float(item["amount"])

    units: dict[int, dict[str, Any]] = {}
    for item in payload.get("units", []):
        position = item.get("position", (0.0, 0.0, 0.0))
        units[int(item["unit_id"])] = {
            "team_id": int(item["team_id"]),
            "unit_def_id": int(item["unit_def_id"]),
            "position": tuple(float(v) for v in position),
        }

    return ObservedMatchState(
        frame=int(payload.get("frame", 0)),
        speed=float(payload.get("speed", 1.0)),
        resources=resources,
        units=units,
        leases={str(k): str(v) for k, v in payload.get("leases", {}).items()},
    )


def evaluate_observation(
    scenario: AdminBehaviorScenario,
    before: ObservedMatchState,
    after: ObservedMatchState,
):
    action = scenario.action
    if scenario.category == "rejection":
        return rejected_effect_absent(before, after, action=action)

    if scenario.scenario_id == "pause_match":
        return frame_stopped(before, after)
    if scenario.scenario_id == "resume_match":
        return frame_advanced(before, after)
    if scenario.scenario_id == "set_speed_fast":
        return speed_matches(after, action.global_speed.speed, tolerance=scenario.expected_observation.tolerance)
    if scenario.scenario_id == "grant_resource":
        grant = action.resource_grant
        expected_amount = scenario.expected_observation.expected_value
        return resource_increased(
            before,
            after,
            team_id=grant.team_id,
            resource_id=grant.resource_id,
            amount=float(expected_amount) if isinstance(expected_amount, int | float) else grant.amount,
            tolerance=scenario.expected_observation.tolerance,
        )
    if scenario.scenario_id == "spawn_enemy_unit":
        spawn = action.unit_spawn
        return unit_spawned(
            before,
            after,
            team_id=spawn.team_id,
            unit_def_id=spawn.unit_def_id,
            position=(spawn.position.x, spawn.position.y, spawn.position.z),
        )
    if scenario.scenario_id == "transfer_unit":
        transfer = action.unit_transfer
        return owner_changed(before, after, unit_id=transfer.unit_id, to_team_id=transfer.to_team_id)

    return scenario.expected_observation


def evidence_record(
    scenario: AdminBehaviorScenario,
    *,
    result_status: int,
    before: ObservedMatchState,
    after: ObservedMatchState,
    evidence_source: str,
    log_location: str = "",
) -> AdminEvidenceRecord:
    observation = evaluate_observation(scenario, before, after)
    status_ok = result_status == scenario.expected_status
    source_ok = evidence_source in BEHAVIORAL_EVIDENCE_SOURCES
    passed = status_ok and observation.observed and source_ok
    diagnostics: list[str] = []
    failure_class = ""
    if not status_ok:
        diagnostics.append(
            f"expected {status_name(scenario.expected_status)} got {status_name(result_status)}"
        )
        failure_class = "unexpected_mutation" if scenario.category == "rejection" else "effect_not_observed"
    if not observation.observed:
        diagnostics.append(observation.failure_reason or "required behavioral observation was not seen")
        failure_class = "unexpected_mutation" if scenario.category == "rejection" else "effect_not_observed"
    if not source_ok:
        diagnostics.append(f"non-behavioral evidence source: {evidence_source or 'none'}")
        failure_class = "internal_error" if scenario.category not in {"success", "rejection"} else "effect_not_observed"

    return AdminEvidenceRecord(
        scenario_id=scenario.scenario_id,
        action_name=scenario.action_name,
        category=scenario.category,
        caller=scenario.caller,
        request={
            "action_seq": scenario.action.action_seq,
            "client_action_id": scenario.action.client_action_id,
            "action": scenario.action.WhichOneof("action"),
        },
        result={"status": status_name(result_status), "issues": []},
        expected_observation=scenario.expected_observation.expected_kind,
        actual_observation=str(observation.actual_value),
        observed=observation.observed,
        evidence_source=evidence_source,
        passed=passed,
        diagnostics=diagnostics,
        log_location=log_location,
        failure_class=failure_class,
    )


def missing_evidence_record(
    scenario: AdminBehaviorScenario,
    *,
    result_status: int | None = None,
    log_location: str = "",
) -> AdminEvidenceRecord:
    status = scenario.expected_status if result_status is None else result_status
    return AdminEvidenceRecord(
        scenario_id=scenario.scenario_id,
        action_name=scenario.action_name,
        category=scenario.category,
        caller=scenario.caller,
        request={
            "action_seq": scenario.action.action_seq,
            "client_action_id": scenario.action.client_action_id,
            "action": scenario.action.WhichOneof("action"),
        },
        result={"status": status_name(status), "issues": []},
        expected_observation=scenario.expected_observation.expected_kind,
        actual_observation="missing before/after state-stream evidence",
        observed=False,
        evidence_source="none",
        passed=False,
        diagnostics=["admin result status is not sufficient without behavioral evidence"],
        log_location=log_location,
        failure_class="effect_not_observed" if scenario.category == "success" else "unexpected_mutation",
    )


def records_from_replay(
    scenarios: list[AdminBehaviorScenario],
    replay: dict[str, Any],
    *,
    log_location: str = "",
) -> list[AdminEvidenceRecord]:
    by_id = {scenario.scenario_id: scenario for scenario in scenarios}
    records: list[AdminEvidenceRecord] = []
    for scenario_id, scenario in by_id.items():
        entry = replay.get(scenario_id)
        if entry is None:
            records.append(missing_evidence_record(scenario, log_location=log_location))
            continue
        records.append(
            evidence_record(
                scenario,
                result_status=status_value(entry["result_status"]),
                before=state_from_mapping(entry.get("before", {})),
                after=state_from_mapping(entry.get("after", {})),
                evidence_source=str(entry.get("evidence_source", "snapshot_delta")),
                log_location=log_location,
            )
        )
    return records

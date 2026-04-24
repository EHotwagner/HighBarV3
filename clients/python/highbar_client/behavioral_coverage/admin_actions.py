# SPDX-License-Identifier: GPL-2.0-only
"""Admin behavioral scenario builders."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Iterable

from ..highbar import service_pb2


class AdminRole(str, Enum):
    OPERATOR = "operator"
    ADMIN = "admin"
    TEST_HARNESS = "test-harness"
    AI = "ai"
    OBSERVER = "observer"


@dataclass(frozen=True)
class AdminCaller:
    client_id: str
    role: AdminRole | str
    token_identity: str = "local-token"
    metadata_source: str = "grpc-metadata"

    @property
    def role_name(self) -> str:
        return self.role.value if isinstance(self.role, AdminRole) else str(self.role)


@dataclass(frozen=True)
class AdminObservation:
    action_name: str
    expected_kind: str
    expected_value: object
    actual_value: object | None = None
    tolerance: float = 0.0
    deadline_seconds: float = 10.0
    observed: bool = False
    failure_reason: str = ""


@dataclass(frozen=True)
class AdminBehaviorScenario:
    scenario_id: str
    priority: str
    category: str
    action_name: str
    caller: AdminCaller
    action: service_pb2.AdminAction
    expected_status: int
    expected_observation: AdminObservation
    cleanup_actions: tuple[service_pb2.AdminAction, ...] = ()
    capability_requirement: str = ""


@dataclass(frozen=True)
class AdminEvidenceRecord:
    scenario_id: str
    action_name: str
    category: str
    caller: AdminCaller
    request: dict
    result: dict
    expected_observation: str
    actual_observation: str
    observed: bool
    evidence_source: str
    passed: bool
    diagnostics: list[str] = field(default_factory=list)
    log_location: str = ""
    failure_class: str = ""


@dataclass(frozen=True)
class AdminBehaviorRun:
    run_id: str
    fixture_id: str
    repeat_index: int
    started_at: str
    completed_at: str
    prerequisite_status: str
    capabilities: dict
    records: list[AdminEvidenceRecord]
    cleanup_status: str
    exit_code: int
    report_path: str


def _action(seq: int, action_name: str) -> service_pb2.AdminAction:
    action = service_pb2.AdminAction(
        action_seq=seq,
        client_action_id=1000 + seq,
        conflict_policy=service_pb2.ADMIN_CONFLICT_REJECT_IF_CONTROLLED,
        reason=f"admin behavioral suite: {action_name}",
    )
    return action


def pause_action(seq: int, paused: bool) -> service_pb2.AdminAction:
    action = _action(seq, "pause")
    action.pause.paused = paused
    return action


def speed_action(seq: int, speed: float) -> service_pb2.AdminAction:
    action = _action(seq, "global_speed")
    action.global_speed.speed = speed
    return action


def resource_grant_action(seq: int, team_id: int, resource_id: int, amount: float) -> service_pb2.AdminAction:
    action = _action(seq, "resource_grant")
    action.resource_grant.team_id = team_id
    action.resource_grant.resource_id = resource_id
    action.resource_grant.amount = amount
    return action


def unit_spawn_action(seq: int, team_id: int, unit_def_id: int, position: tuple[float, float, float]) -> service_pb2.AdminAction:
    action = _action(seq, "unit_spawn")
    action.unit_spawn.team_id = team_id
    action.unit_spawn.unit_def_id = unit_def_id
    action.unit_spawn.position.x = position[0]
    action.unit_spawn.position.y = position[1]
    action.unit_spawn.position.z = position[2]
    return action


def unit_transfer_action(seq: int, unit_id: int, from_team_id: int, to_team_id: int) -> service_pb2.AdminAction:
    action = _action(seq, "unit_transfer")
    action.unit_transfer.unit_id = unit_id
    action.unit_transfer.from_team_id = from_team_id
    action.unit_transfer.to_team_id = to_team_id
    action.unit_transfer.preserve_orders = True
    return action


def cleanup_actions() -> tuple[service_pb2.AdminAction, ...]:
    return (
        pause_action(9001, False),
        speed_action(9002, 1.0),
    )


def success_scenarios() -> list[AdminBehaviorScenario]:
    caller = AdminCaller(client_id="admin-suite", role=AdminRole.OPERATOR)
    cleanup = cleanup_actions()
    return [
        AdminBehaviorScenario("pause_match", "P1", "success", "pause", caller, pause_action(1, True),
                              service_pb2.ADMIN_ACTION_EXECUTED,
                              AdminObservation("pause", "frame_stopped", True), cleanup, "pause"),
        AdminBehaviorScenario("resume_match", "P1", "success", "pause", caller, pause_action(2, False),
                              service_pb2.ADMIN_ACTION_EXECUTED,
                              AdminObservation("pause", "frame_advanced", True), cleanup, "pause"),
        AdminBehaviorScenario("set_speed_fast", "P1", "success", "global_speed", caller, speed_action(3, 2.0),
                              service_pb2.ADMIN_ACTION_EXECUTED,
                              AdminObservation("global_speed", "speed_multiplier", 2.0, tolerance=0.35), cleanup, "global_speed"),
        AdminBehaviorScenario("grant_resource", "P1", "success", "resource_grant", caller, resource_grant_action(4, 0, 0, 100.0),
                              service_pb2.ADMIN_ACTION_EXECUTED,
                              AdminObservation("resource_grant", "resource_delta", 100.0, tolerance=0.01), cleanup, "resource_grant"),
        AdminBehaviorScenario("spawn_enemy_unit", "P1", "success", "unit_spawn", caller, unit_spawn_action(5, 1, 1, (1024.0, 0.0, 1024.0)),
                              service_pb2.ADMIN_ACTION_EXECUTED,
                              AdminObservation("unit_spawn", "unit_spawned", {"team_id": 1, "unit_def_id": 1}), cleanup, "unit_spawn"),
        AdminBehaviorScenario("transfer_unit", "P1", "success", "unit_transfer", caller, unit_transfer_action(6, 1, 0, 1),
                              service_pb2.ADMIN_ACTION_EXECUTED,
                              AdminObservation("unit_transfer", "owner_changed", {"unit_id": 1, "to_team_id": 1}), cleanup, "unit_transfer"),
    ]


def rejection_scenarios() -> list[AdminBehaviorScenario]:
    operator = AdminCaller(client_id="admin-suite", role=AdminRole.OPERATOR)
    observer = AdminCaller(client_id="observer-suite", role=AdminRole.OBSERVER)
    return [
        AdminBehaviorScenario("reject_unauthorized", "P1", "rejection", "pause", observer, pause_action(101, True),
                              service_pb2.ADMIN_ACTION_REJECTED_PERMISSION_DENIED,
                              AdminObservation("pause", "unchanged_state", True), (), "pause"),
        AdminBehaviorScenario("reject_invalid_speed", "P1", "rejection", "global_speed", operator, speed_action(102, 0.0),
                              service_pb2.ADMIN_ACTION_REJECTED_INVALID_VALUE,
                              AdminObservation("global_speed", "unchanged_state", True), (), "global_speed"),
        AdminBehaviorScenario("reject_invalid_resource", "P1", "rejection", "resource_grant", operator, resource_grant_action(103, -1, 99, -10.0),
                              service_pb2.ADMIN_ACTION_REJECTED_INVALID_TARGET,
                              AdminObservation("resource_grant", "unchanged_state", True), (), "resource_grant"),
        AdminBehaviorScenario("reject_invalid_spawn", "P1", "rejection", "unit_spawn", operator, unit_spawn_action(104, -1, -1, (-1.0, 0.0, -1.0)),
                              service_pb2.ADMIN_ACTION_REJECTED_INVALID_TARGET,
                              AdminObservation("unit_spawn", "unchanged_state", True), (), "unit_spawn"),
        AdminBehaviorScenario("reject_invalid_transfer", "P1", "rejection", "unit_transfer", operator, unit_transfer_action(105, -1, 0, 1),
                              service_pb2.ADMIN_ACTION_REJECTED_INVALID_TARGET,
                              AdminObservation("unit_transfer", "unchanged_state", True), (), "unit_transfer"),
        AdminBehaviorScenario("reject_lease_conflict", "P1", "rejection", "pause", AdminCaller("other-admin", AdminRole.ADMIN), pause_action(106, True),
                              service_pb2.ADMIN_ACTION_REJECTED_CONFLICT,
                              AdminObservation("pause", "unchanged_state", True), (), "pause"),
    ]


def all_scenarios() -> list[AdminBehaviorScenario]:
    return success_scenarios() + rejection_scenarios()


def supported_action_names(capabilities: service_pb2.AdminCapabilitiesResponse | None) -> set[str]:
    if capabilities is None:
        return {scenario.capability_requirement for scenario in all_scenarios()}
    return set(capabilities.supported_actions)


def executable_scenarios(
    scenarios: Iterable[AdminBehaviorScenario],
    capabilities: service_pb2.AdminCapabilitiesResponse | None,
) -> list[AdminBehaviorScenario]:
    supported = supported_action_names(capabilities)
    return [
        scenario for scenario in scenarios
        if not scenario.capability_requirement or scenario.capability_requirement in supported
    ]


def advertised_but_missing_required(
    capabilities: service_pb2.AdminCapabilitiesResponse,
    required: Iterable[str] = ("pause", "global_speed", "resource_grant", "unit_spawn", "unit_transfer"),
) -> list[str]:
    supported = set(capabilities.supported_actions)
    return [name for name in required if name not in supported]

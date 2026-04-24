# SPDX-License-Identifier: GPL-2.0-only
from __future__ import annotations

from highbar_client.behavioral_coverage.admin_actions import (
    advertised_but_missing_required,
    executable_scenarios,
    rejection_scenarios,
    success_scenarios,
)
from highbar_client.highbar import service_pb2


def test_success_scenario_builders_cover_required_admin_actions():
    scenarios = {scenario.scenario_id: scenario for scenario in success_scenarios()}

    assert scenarios["pause_match"].action.WhichOneof("action") == "pause"
    assert scenarios["resume_match"].action.pause.paused is False
    assert scenarios["set_speed_fast"].action.global_speed.speed > 1.0
    assert scenarios["grant_resource"].action.resource_grant.amount > 0.0
    assert scenarios["spawn_enemy_unit"].action.unit_spawn.unit_def_id > 0
    assert scenarios["transfer_unit"].action.unit_transfer.to_team_id == 1


def test_rejection_scenarios_include_expected_statuses():
    scenarios = {scenario.scenario_id: scenario for scenario in rejection_scenarios()}

    assert scenarios["reject_unauthorized"].expected_status == service_pb2.ADMIN_ACTION_REJECTED_PERMISSION_DENIED
    assert scenarios["reject_invalid_speed"].expected_status == service_pb2.ADMIN_ACTION_REJECTED_INVALID_VALUE
    assert scenarios["reject_invalid_resource"].expected_status == service_pb2.ADMIN_ACTION_REJECTED_INVALID_TARGET
    assert scenarios["reject_invalid_spawn"].expected_status == service_pb2.ADMIN_ACTION_REJECTED_INVALID_TARGET
    assert scenarios["reject_invalid_transfer"].expected_status == service_pb2.ADMIN_ACTION_REJECTED_INVALID_TARGET
    assert scenarios["reject_lease_conflict"].expected_status == service_pb2.ADMIN_ACTION_REJECTED_CONFLICT


def test_capability_filter_skips_disabled_controls_and_reports_missing_required():
    capabilities = service_pb2.AdminCapabilitiesResponse(
        enabled=True,
        supported_actions=["pause", "global_speed", "resource_grant"],
    )

    selected = executable_scenarios(success_scenarios(), capabilities)
    assert {scenario.capability_requirement for scenario in selected} == {
        "pause",
        "global_speed",
        "resource_grant",
    }
    assert advertised_but_missing_required(capabilities) == ["unit_spawn", "unit_transfer"]

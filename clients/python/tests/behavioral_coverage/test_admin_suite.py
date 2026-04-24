# SPDX-License-Identifier: GPL-2.0-only
from __future__ import annotations

from highbar_client.behavioral_coverage.admin_actions import (
    rejection_scenarios,
    success_scenarios,
)
from highbar_client.behavioral_coverage.admin_observations import ObservedMatchState
from highbar_client.behavioral_coverage.admin_suite import (
    evidence_record,
    missing_evidence_record,
    records_from_replay,
)
from highbar_client.behavioral_coverage import _admin_main
from highbar_client.highbar import service_pb2


def _success_states(scenario_id: str) -> tuple[ObservedMatchState, ObservedMatchState]:
    if scenario_id == "pause_match":
        return ObservedMatchState(frame=10), ObservedMatchState(frame=10)
    if scenario_id == "resume_match":
        return ObservedMatchState(frame=10), ObservedMatchState(frame=20)
    if scenario_id == "set_speed_fast":
        return ObservedMatchState(speed=1.0), ObservedMatchState(speed=2.0)
    if scenario_id == "grant_resource":
        return ObservedMatchState(resources={(0, 0): 10.0}), ObservedMatchState(resources={(0, 0): 110.0})
    if scenario_id == "spawn_enemy_unit":
        return (
            ObservedMatchState(units={1: {"team_id": 0, "unit_def_id": 1, "position": (0.0, 0.0, 0.0)}}),
            ObservedMatchState(
                units={
                    1: {"team_id": 0, "unit_def_id": 1, "position": (0.0, 0.0, 0.0)},
                    2: {"team_id": 1, "unit_def_id": 1, "position": (1024.0, 0.0, 1024.0)},
                }
            ),
        )
    if scenario_id == "transfer_unit":
        return (
            ObservedMatchState(units={1: {"team_id": 0, "unit_def_id": 1, "position": (0.0, 0.0, 0.0)}}),
            ObservedMatchState(units={1: {"team_id": 1, "unit_def_id": 1, "position": (0.0, 0.0, 0.0)}}),
        )
    raise AssertionError(scenario_id)


def test_all_success_scenarios_require_and_accept_behavioral_evidence():
    for scenario in success_scenarios():
        before, after = _success_states(scenario.scenario_id)

        record = evidence_record(
            scenario,
            result_status=service_pb2.ADMIN_ACTION_EXECUTED,
            before=before,
            after=after,
            evidence_source="state_stream",
        )

        assert record.passed is True, scenario.scenario_id
        assert record.observed is True
        assert record.evidence_source == "state_stream"


def test_speed_scenario_accepts_live_engine_log_evidence():
    scenario = next(s for s in success_scenarios() if s.scenario_id == "set_speed_fast")

    record = evidence_record(
        scenario,
        result_status=service_pb2.ADMIN_ACTION_EXECUTED,
        before=ObservedMatchState(speed=1.0),
        after=ObservedMatchState(speed=2.0),
        evidence_source="engine_log",
    )

    assert record.passed is True
    assert record.observed is True
    assert record.actual_observation == "2.0"


def test_speed_engine_log_source_without_speed_change_still_fails():
    scenario = next(s for s in success_scenarios() if s.scenario_id == "set_speed_fast")

    record = evidence_record(
        scenario,
        result_status=service_pb2.ADMIN_ACTION_EXECUTED,
        before=ObservedMatchState(speed=1.0),
        after=ObservedMatchState(speed=1.0),
        evidence_source="engine_log",
    )

    assert record.passed is False
    assert record.observed is False
    assert record.failure_class == "effect_not_observed"


def test_status_only_success_is_rejected_for_every_scenario():
    for scenario in success_scenarios() + rejection_scenarios():
        record = missing_evidence_record(scenario)

        assert record.passed is False, scenario.scenario_id
        assert record.observed is False
        assert "not sufficient" in record.diagnostics[0]


def test_rejection_scenarios_require_unchanged_behavioral_state():
    same = ObservedMatchState(frame=10, speed=1.0, resources={(0, 0): 10.0})
    for scenario in rejection_scenarios():
        record = evidence_record(
            scenario,
            result_status=scenario.expected_status,
            before=same,
            after=same,
            evidence_source="snapshot_delta",
        )

        assert record.passed is True, scenario.scenario_id
        assert record.observed is True


def test_rejection_status_without_absent_effect_fails():
    before = ObservedMatchState(frame=10, speed=1.0, resources={(0, 0): 10.0})
    after = ObservedMatchState(frame=10, speed=2.0, resources={(0, 0): 10.0})
    scenario = rejection_scenarios()[1]

    record = evidence_record(
        scenario,
        result_status=scenario.expected_status,
        before=before,
        after=after,
        evidence_source="state_stream",
    )

    assert record.passed is False
    assert record.failure_class == "unexpected_mutation"


def test_admin_cli_skip_live_writes_failing_missing_evidence_report(tmp_path):
    code = _admin_main(
        [
            "--skip-live",
            "--output-dir",
            str(tmp_path),
            "--repeat-index",
            "1",
        ]
    )

    assert code == 1
    summary = (tmp_path / "summary.csv").read_text(encoding="utf-8")
    assert "evidence_source" in summary
    assert "none" in summary
    assert "false" in summary
    report = (tmp_path / "run-report.md").read_text(encoding="utf-8")
    assert "success_criterion" in report
    assert "missing before/after state-stream evidence" in report


def test_replay_fixture_passes_only_with_behavioral_sources(tmp_path):
    replay_path = "tests/fixtures/admin_behavior/evidence-replay.json"
    code = _admin_main(
        [
            "--evidence-replay",
            replay_path,
            "--output-dir",
            str(tmp_path),
        ]
    )

    assert code == 0
    summary = (tmp_path / "summary.csv").read_text(encoding="utf-8")
    assert "none" not in summary
    assert "false" not in summary


def test_replay_missing_scenario_fails_closed():
    scenarios = success_scenarios()[:2]
    records = records_from_replay(
        scenarios,
        {
            "pause_match": {
                "result_status": "ADMIN_ACTION_EXECUTED",
                "evidence_source": "state_stream",
                "before": {"frame": 1},
                "after": {"frame": 1},
            }
        },
    )

    assert records[0].passed is True
    assert records[1].passed is False
    assert records[1].evidence_source == "none"

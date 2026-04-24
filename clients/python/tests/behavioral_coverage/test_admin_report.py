# SPDX-License-Identifier: GPL-2.0-only
from __future__ import annotations

import csv
import json

from highbar_client.behavioral_coverage.admin_actions import (
    AdminBehaviorRun,
    AdminCaller,
    AdminEvidenceRecord,
    AdminRole,
)
from highbar_client.behavioral_coverage.admin_report import (
    classify_failure,
    exit_code_for_records,
    render_markdown,
    write_artifacts,
)


def _record(*, passed: bool = True, category: str = "success", failure_class: str = "") -> AdminEvidenceRecord:
    return AdminEvidenceRecord(
        scenario_id="pause_match",
        action_name="pause",
        category=category,
        caller=AdminCaller("suite", AdminRole.OPERATOR),
        request={"action_seq": 1, "action": "pause"},
        result={"status": "ADMIN_ACTION_EXECUTED"},
        expected_observation="frame progression stops within 10s",
        actual_observation="frame stayed stable",
        observed=passed,
        evidence_source="state_stream" if passed else "none",
        passed=passed,
        diagnostics=[],
        log_location="logs/engine.log",
        failure_class=failure_class,
    )


def _run(records: list[AdminEvidenceRecord], tmp_path) -> AdminBehaviorRun:
    return AdminBehaviorRun(
        run_id="run-1",
        fixture_id="admin-behavior-local-v1",
        repeat_index=1,
        started_at="2026-04-24T00:00:00Z",
        completed_at="2026-04-24T00:00:01Z",
        prerequisite_status="ok",
        capabilities={"supported_actions": ["pause"]},
        records=records,
        cleanup_status="ok",
        exit_code=exit_code_for_records(records),
        report_path=str(tmp_path / "run-report.md"),
    )


def test_report_writes_jsonl_csv_markdown_and_repeat_summary(tmp_path):
    run = _run([_record()], tmp_path)

    write_artifacts(tmp_path, run)

    payload = json.loads((tmp_path / "evidence.jsonl").read_text(encoding="utf-8").strip())
    assert payload["scenario_id"] == "pause_match"
    assert payload["caller"]["role"] == "operator"

    with (tmp_path / "summary.csv").open(encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    assert rows[0]["failure_class"] == ""

    rendered = (tmp_path / "run-report.md").read_text(encoding="utf-8")
    assert "## Scenario Evidence" in rendered
    assert "frame progression stops within 10s" in rendered
    assert (tmp_path / "repeats" / "repeat-1.json").exists()


def test_report_renders_failure_details_and_exit_classifications(tmp_path):
    failed = _record(passed=False, category="success")
    run = _run([failed], tmp_path)

    rendered = render_markdown(run)

    assert "## Failure Details" in rendered
    assert classify_failure(failed) == "effect_not_observed"
    assert exit_code_for_records([failed]) == 1
    assert exit_code_for_records([], prerequisite_status="missing_runtime") == 77
    assert exit_code_for_records([_record(passed=False, category="cleanup")]) == 1
    assert exit_code_for_records([_record(passed=False, failure_class="internal_error")]) == 2

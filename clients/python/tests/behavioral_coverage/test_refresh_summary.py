# SPDX-License-Identifier: GPL-2.0-only
from __future__ import annotations

from highbar_client.behavioral_coverage.audit_runner import (
    collect_live_audit_run,
    refresh_summary_text,
)


def test_refresh_summary_contains_deliverables_and_counts():
    run = collect_live_audit_run()
    rendered = refresh_summary_text(run.summary)

    assert run.run_id in rendered
    assert "command-audit=refreshed" in rendered
    assert "verified=" in rendered


def test_partial_refresh_marks_failure_reasons(monkeypatch):
    monkeypatch.setenv("HIGHBAR_AUDIT_FAIL_ROWS", "cmd-move-unit")
    monkeypatch.setenv("HIGHBAR_AUDIT_TOPOLOGY_FAILURE", "launcher degraded")

    run = collect_live_audit_run()
    rendered = refresh_summary_text(run.summary)
    row = next(item for item in run.row_results if item.row_id == "cmd-move-unit")

    assert run.topology_status == "partial"
    assert row.freshness_state == "not-refreshed-live"
    assert row.failure_reason == "launcher degraded"
    assert "command-audit=partial" in rendered
    assert "launcher degraded" in rendered

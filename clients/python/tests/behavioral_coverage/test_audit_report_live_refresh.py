# SPDX-License-Identifier: GPL-2.0-only
from __future__ import annotations

from highbar_client.behavioral_coverage.audit_report import (
    render_command_audit,
    render_hypothesis_plan,
)
from highbar_client.behavioral_coverage.audit_runner import (
    build_audit_rows,
    build_hypothesis_plan,
    build_v2_v3_ledger,
    collect_live_audit_run,
)


def test_rendered_command_audit_includes_freshness_summary():
    run = collect_live_audit_run()
    rows = build_audit_rows(run=run)
    ledger = build_v2_v3_ledger(rows)

    rendered = render_command_audit(rows, ledger, run.summary, run)

    assert "Latest completed run" in rendered
    assert "Freshness" in rendered
    assert "Deliverables:" in rendered


def test_hypothesis_plan_renders_against_live_run():
    run = collect_live_audit_run()
    rows = build_audit_rows(run=run)
    entries = build_hypothesis_plan(rows)

    rendered = render_hypothesis_plan(entries, run.summary)

    assert run.run_id in rendered
    assert "Candidate 1" in rendered

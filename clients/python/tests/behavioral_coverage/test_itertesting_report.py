# SPDX-License-Identifier: GPL-2.0-only
from __future__ import annotations

from highbar_client.behavioral_coverage.itertesting_report import render_run_report
from highbar_client.behavioral_coverage.itertesting_runner import run_campaign


def test_report_renders_coverage_totals_and_unverified_sections(tmp_path):
    _campaign, runs = run_campaign(
        reports_dir=tmp_path,
        max_improvement_runs=0,
        allow_cheat_escalation=False,
        natural_first=True,
    )

    rendered = render_run_report(runs[0])

    assert "## Coverage Summary" in rendered
    assert "Tracked commands:" in rendered
    assert "## Still Unverified" in rendered


def test_report_renders_improvement_actions_and_deltas(tmp_path):
    _campaign, runs = run_campaign(
        reports_dir=tmp_path,
        max_improvement_runs=1,
        allow_cheat_escalation=False,
        natural_first=True,
    )

    rendered = render_run_report(runs[1])

    assert "## Compared With Previous Run" in rendered
    assert "Coverage delta:" in rendered
    assert "## Next Improvements" in rendered


def test_report_labels_cheat_assisted_totals(tmp_path):
    _campaign, runs = run_campaign(
        reports_dir=tmp_path,
        max_improvement_runs=2,
        allow_cheat_escalation=True,
        natural_first=True,
    )

    rendered = render_run_report(runs[-1])

    assert "Verified cheat-assisted:" in rendered
    assert "cheat-assisted" in rendered


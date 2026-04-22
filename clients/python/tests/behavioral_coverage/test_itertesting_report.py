# SPDX-License-Identifier: GPL-2.0-only
from __future__ import annotations

from highbar_client.behavioral_coverage.itertesting_report import render_run_report
from highbar_client.behavioral_coverage.itertesting_runner import run_campaign


def test_report_renders_required_sections_and_direct_split(tmp_path):
    campaign, runs = run_campaign(
        reports_dir=tmp_path,
        retry_intensity="standard",
        max_improvement_runs=2,
        allow_cheat_escalation=False,
        natural_first=True,
    )

    rendered = render_run_report(runs[-1], stop_decision=campaign.stop_decision)

    assert "## Run Metadata" in rendered
    assert "## Coverage Summary" in rendered
    assert "Directly verifiable total:" in rendered
    assert "Non-observable tracked total:" in rendered
    assert "## Intensity and Governance" in rendered


def test_report_includes_stop_reason_and_runtime_metrics(tmp_path):
    campaign, runs = run_campaign(
        reports_dir=tmp_path,
        retry_intensity="quick",
        max_improvement_runs=5,
        allow_cheat_escalation=False,
        natural_first=True,
    )

    rendered = render_run_report(runs[-1], stop_decision=campaign.stop_decision)

    assert "## Stop Reason" in rendered
    assert "Stop reason:" in rendered
    assert "Runtime at stop (seconds):" in rendered


def test_report_labels_natural_and_cheat_assisted_totals(tmp_path):
    campaign, runs = run_campaign(
        reports_dir=tmp_path,
        retry_intensity="deep",
        max_improvement_runs=8,
        allow_cheat_escalation=True,
        natural_first=True,
    )

    rendered = render_run_report(runs[-1], stop_decision=campaign.stop_decision)

    assert "Direct verified natural:" in rendered
    assert "Direct verified cheat-assisted:" in rendered


def test_report_lists_unverified_direct_commands_with_next_actions(tmp_path):
    _campaign, runs = run_campaign(
        reports_dir=tmp_path,
        retry_intensity="quick",
        max_improvement_runs=0,
        allow_cheat_escalation=False,
        natural_first=True,
    )

    rendered = render_run_report(runs[0])

    assert "## Unverified Direct Commands" in rendered
    assert "next action:" in rendered
    assert "## Instruction Updates" in rendered


def test_report_lists_newly_verified_commands_for_first_run(tmp_path):
    _campaign, runs = run_campaign(
        reports_dir=tmp_path,
        retry_intensity="quick",
        max_improvement_runs=0,
        allow_cheat_escalation=False,
        natural_first=True,
    )

    rendered = render_run_report(runs[0])

    assert "## Newly Verified Commands" in rendered
    assert "`cmd-attack`" in rendered


def test_report_renders_channel_health_and_failure_causes(tmp_path):
    _campaign, runs = run_campaign(
        reports_dir=tmp_path,
        retry_intensity="quick",
        max_improvement_runs=0,
        allow_cheat_escalation=False,
        natural_first=True,
    )

    rendered = render_run_report(runs[0])

    assert "## Fixture Provisioning" in rendered
    assert "## Channel Health" in rendered
    assert "## Failure Cause Summary" in rendered

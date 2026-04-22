# SPDX-License-Identifier: GPL-2.0-only
from __future__ import annotations

from highbar_client.behavioral_coverage.itertesting_report import render_run_report
from highbar_client.behavioral_coverage.itertesting_runner import build_run, run_campaign
from highbar_client.behavioral_coverage.registry import REGISTRY


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
    assert "### Fixture Class Statuses" in rendered
    assert "## Channel Health" in rendered
    assert "## Failure Cause Summary" in rendered
    assert "simplified bootstrap" not in rendered.lower()


def test_report_renders_blocked_contract_health_for_fixture_blocked_runs(tmp_path):
    run = build_run(
        campaign_id="campaign-1",
        sequence_index=0,
        reports_dir=tmp_path,
        live_rows=[
            {
                "arm_name": "load_units",
                "category": REGISTRY["load_units"].category,
                "dispatched": "false",
                "verified": "false",
                "evidence": "transport fixture missing for live validation",
                "error": "precondition_unmet",
            }
        ],
    )

    rendered = render_run_report(run)

    assert "## Contract Health" in rendered
    assert "- Status: blocked_foundational" in rendered
    assert "missing fixture" in rendered.lower()


def test_report_renders_fixture_class_status_and_shared_instance_detail(tmp_path):
    run = build_run(
        campaign_id="campaign-1",
        sequence_index=0,
        reports_dir=tmp_path,
        live_rows=[
            {
                "arm_name": "load_units",
                "category": REGISTRY["load_units"].category,
                "dispatched": "true",
                "verified": "false",
                "evidence": "transport fixture refreshed with payload fixture replacement",
                "error": "effect_not_observed",
            }
        ],
    )

    rendered = render_run_report(run)

    assert "Refreshed fixtures:" in rendered
    assert "`transport_unit`" in rendered
    assert "### Shared Fixture Instances" in rendered
    assert "replacement_of" not in rendered.lower()


def test_report_renders_contract_health_and_repro_sections(tmp_path):
    run = build_run(
        campaign_id="campaign-1",
        sequence_index=0,
        reports_dir=tmp_path,
        live_rows=[
            {
                "arm_name": "move_unit",
                "category": REGISTRY["move_unit"].category,
                "dispatched": "false",
                "verified": "false",
                "evidence": "batch target 4 disagreed with command unit 9",
                "error": "target_drift",
            }
        ],
    )

    rendered = render_run_report(run)

    assert "## Contract Health" in rendered
    assert "## Foundational Blockers" in rendered


def test_report_marks_ready_run_evidence_gaps_as_secondary_findings(tmp_path):
    run = build_run(
        campaign_id="campaign-1",
        sequence_index=0,
        reports_dir=tmp_path,
        live_rows=[
            {
                "arm_name": "patrol",
                "category": REGISTRY["patrol"].category,
                "dispatched": "true",
                "verified": "false",
                "evidence": "snapshot-diff predicate not yet implemented for this arm",
                "error": "effect_not_observed",
            }
        ],
    )

    rendered = render_run_report(run)

    assert "- Status: ready_for_itertesting" in rendered
    assert "secondary evidence or behavior follow-up" in rendered
    assert "## Foundational Blockers" not in rendered


def test_report_renders_exact_custom_command_inventory(tmp_path):
    run = build_run(
        campaign_id="campaign-1",
        sequence_index=0,
        reports_dir=tmp_path,
    )

    rendered = render_run_report(run)

    assert "## Command Semantic Inventory" in rendered
    assert "`32102` `MANUAL_LAUNCH`" in rendered
    assert "`34571` `PRIORITY`" in rendered
    assert "`37382` `WANT_CLOAK`" in rendered


def test_report_renders_semantic_gate_summary_when_present(tmp_path):
    run = build_run(
        campaign_id="campaign-1",
        sequence_index=0,
        reports_dir=tmp_path,
        live_rows=[
            {
                "arm_name": "set_wanted_max_speed",
                "category": REGISTRY["set_wanted_max_speed"].category,
                "dispatched": "false",
                "verified": "false",
                "evidence": "emprework mod option disabled for wanted-speed validation",
                "error": "precondition_unmet",
            }
        ],
    )

    rendered = render_run_report(run)

    assert "## Semantic Gates" in rendered
    assert "`cmd-set-wanted-max-speed` — mod-option" in rendered


def test_report_renders_unit_shape_semantic_gate_with_custom_command_id(tmp_path):
    run = build_run(
        campaign_id="campaign-1",
        sequence_index=0,
        reports_dir=tmp_path,
        live_rows=[
            {
                "arm_name": "dgun",
                "category": REGISTRY["dgun"].category,
                "dispatched": "false",
                "verified": "false",
                "evidence": "non-commander manual launch substitution (32102) means this unit does not receive the command descriptor",
                "error": "precondition_unmet",
            }
        ],
    )

    rendered = render_run_report(run)

    assert "`cmd-dgun` — unit-shape" in rendered
    assert "custom command id: 32102" in rendered

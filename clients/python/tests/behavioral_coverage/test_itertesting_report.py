# SPDX-License-Identifier: GPL-2.0-only
from __future__ import annotations

from highbar_client.behavioral_coverage.itertesting_report import render_run_report
from highbar_client.behavioral_coverage.itertesting_runner import build_run, run_campaign
from highbar_client.behavioral_coverage.registry import REGISTRY


def _hardening_live_rows():
    return [
        {
            "arm_name": "__runtime_capability_profile__",
            "profile_id": "cap-40-47-hello-static-map",
            "supported_callbacks": [40, 47],
            "supported_scopes": [
                "unit_def_lookup",
                "unit_def_name",
                "session_start_map",
            ],
            "unsupported_callback_groups": [
                "unit",
                "unitdef_except_name",
                "map",
            ],
            "map_data_source_status": "hello_static_map",
            "notes": "callback-limited host preserved unit-def lookup and session-start map payload",
            "recorded_at": "2026-04-23T02:42:47Z",
        },
        {
            "arm_name": "__bootstrap_readiness__",
            "readiness_status": "seeded_ready",
            "readiness_path": "explicit_seed",
            "first_required_step": "armmex",
            "economy_summary": "economy=metal:0.1/0.0/1500.0",
            "reason": "prepared live start already contained commander-built bootstrap fixtures: armmex, armsolar, armvp",
            "recorded_at": "2026-04-23T02:42:47Z",
        },
        {
            "arm_name": "__callback_diagnostic__",
            "snapshot_id": "callback-01",
            "capture_stage": "bootstrap_start",
            "availability_status": "cached",
            "source": "preserved_earlier_capture",
            "diagnostic_scope": ["commander_def", "build_options", "economy"],
            "summary": "late callback refresh unavailable; preserved earlier capture after relay loss",
            "captured_at": "2026-04-23T02:42:55Z",
        },
        {
            "arm_name": "__prerequisite_resolution__",
            "prerequisite_name": "armmex",
            "consumer": "live_closeout",
            "callback_path": "InvokeCallback/armmex",
            "resolved_def_id": 42,
            "resolution_status": "resolved",
            "reason": "resolved runtime def id for armmex during live bootstrap",
            "recorded_at": "2026-04-23T02:42:47Z",
        },
        {
            "arm_name": "__map_source_decision__",
            "consumer": "live_closeout",
            "selected_source": "hello_static_map",
            "metal_spot_count": 14,
            "reason": "used HelloResponse.static_map because callback map inspection is unsupported on this host",
            "recorded_at": "2026-04-23T02:42:47Z",
        },
        {
            "arm_name": "__standalone_build_probe__",
            "probe_id": "behavioral-build",
            "prerequisite_name": "armmex",
            "callback_path": "InvokeCallback/armmex",
            "resolved_def_id": 42,
            "resolution_status": "resolved",
            "resolution_reason": "resolved runtime def id for armmex",
            "map_source_consumer": "behavioral_build_probe",
            "map_source_selected_source": "hello_static_map",
            "map_source_metal_spot_count": 14,
            "map_source_reason": "used HelloResponse.static_map because callback map inspection is unsupported on this host",
            "capability_limit_summary": "deeper commander/build-option diagnostics are capability-limited on this host",
            "dispatch_result": "verified",
            "completed_at": "2026-04-23T02:42:52Z",
        },
        {
            "arm_name": "attack",
            "category": REGISTRY["attack"].category,
            "dispatched": "true",
            "verified": "false",
            "evidence": "place_target_on_ground Lua rewrite converted the unit target into map coordinates",
            "error": "effect_not_observed",
        },
    ]


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
    assert "### Transport Provisioning" in rendered
    assert "## Channel Health" in rendered
    assert "## Failure Cause Summary" in rendered
    assert "simplified bootstrap" not in rendered.lower()


def test_report_renders_bootstrap_callback_and_resolution_sections(tmp_path):
    run = build_run(
        campaign_id="campaign-1",
        sequence_index=0,
        reports_dir=tmp_path,
        live_rows=_hardening_live_rows(),
    )

    rendered = render_run_report(run)

    assert "## Bootstrap Readiness" in rendered
    assert "- Status: seeded_ready" in rendered
    assert "## Runtime Capability Profile" in rendered
    assert "hello_static_map" in rendered
    assert "## Callback Diagnostics" in rendered
    assert "preserved_earlier_capture" in rendered
    assert "## Runtime Prerequisite Resolution" in rendered
    assert "InvokeCallback/armmex" in rendered
    assert "## Map Source Decisions" in rendered
    assert "## Standalone Build Probe" in rendered
    assert "Capability limits: deeper commander/build-option diagnostics are capability-limited on this host" in rendered


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


def test_report_renders_interpretation_warnings_and_decision_trace(tmp_path):
    run = build_run(
        campaign_id="campaign-1",
        sequence_index=0,
        reports_dir=tmp_path,
        live_rows=[
            {
                "arm_name": "__future_runtime_fact__",
                "recorded_at": "2026-04-23T09:32:32Z",
                "detail": "new metadata type without an interpretation rule",
            }
        ],
    )

    rendered = render_run_report(run)

    assert "## Interpretation Warnings" in rendered
    assert "future_runtime_fact" in rendered
    assert "## Decision Trace" in rendered
    assert "Fully interpreted: no" in rendered


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
    assert "Resolution trace:" in rendered
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

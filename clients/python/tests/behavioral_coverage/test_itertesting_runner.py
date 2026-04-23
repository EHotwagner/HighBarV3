# SPDX-License-Identifier: GPL-2.0-only
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

import highbar_client.behavioral_coverage as behavioral_coverage
from highbar_client.behavioral_coverage.itertesting_campaign import decide_stop
from highbar_client.behavioral_coverage.itertesting_retry_policy import normalize_retry_policy
from highbar_client.behavioral_coverage.itertesting_runner import (
    build_run,
    campaign_dir,
    instruction_index_path,
    instruction_path,
    itertesting_main,
    load_instruction_store,
    load_run_manifest,
    make_run_id,
    parse_itertesting_args,
    run_campaign,
)
from highbar_client.behavioral_coverage.itertesting_types import (
    FailureCauseClassification,
    RunProgressSnapshot,
    manifest_dict,
)
from highbar_client.behavioral_coverage.registry import REGISTRY


def test_manifest_validation_and_round_trip(tmp_path):
    run = build_run(
        campaign_id="campaign-1",
        sequence_index=0,
        reports_dir=tmp_path,
    )
    bundle = tmp_path / run.run_id
    bundle.mkdir()
    manifest = bundle / "manifest.json"
    payload = manifest_dict(run)
    manifest.write_text(json.dumps(payload), encoding="utf-8")

    loaded = load_run_manifest(manifest)

    assert loaded.run_id == run.run_id
    assert len(loaded.command_records) == len(REGISTRY)
    assert loaded.contract_health_decision is not None
    assert loaded.fixture_provisioning is not None
    assert loaded.transport_provisioning is not None
    assert loaded.fixture_provisioning.class_statuses
    assert loaded.fixture_provisioning.shared_fixture_instances
    assert loaded.semantic_gates == run.semantic_gates


def test_run_id_collision_uses_deterministic_suffix(tmp_path):
    first = make_run_id(tmp_path)
    (tmp_path / first).mkdir()

    second = make_run_id(tmp_path)

    assert second.startswith(first)
    assert second.endswith("-02")


def test_cli_argument_parsing_supports_retry_intensity_and_governance_flags():
    args = parse_itertesting_args(
        [
            "--reports-dir",
            "reports/itertesting",
            "--retry-intensity",
            "deep",
            "--max-improvement-runs",
            "12",
            "--runtime-target-minutes",
            "20",
            "--allow-cheat-escalation",
            "--cheat-startscript",
            "tests/headless/scripts/cheats.startscript",
        ]
    )

    assert args.retry_intensity == "deep"
    assert args.max_improvement_runs == 12
    assert args.runtime_target_minutes == 20
    assert args.allow_cheat_escalation is True
    assert args.natural_first is True


def test_hard_cap_clamps_high_requested_retry_budget(tmp_path):
    campaign, runs = run_campaign(
        reports_dir=tmp_path,
        retry_intensity="deep",
        max_improvement_runs=100,
        allow_cheat_escalation=False,
        natural_first=True,
    )

    assert campaign.configured_improvement_runs == 100
    assert campaign.effective_improvement_runs == 10
    assert len(runs) <= 11


def test_stalled_campaign_stops_before_large_budget_is_consumed(tmp_path):
    campaign, runs = run_campaign(
        reports_dir=tmp_path,
        retry_intensity="quick",
        max_improvement_runs=100,
        allow_cheat_escalation=False,
        natural_first=True,
    )

    assert campaign.stop_decision is not None
    assert campaign.stop_decision.stop_reason == "stalled"
    assert len(runs) <= 4


def test_natural_first_defers_cheat_escalation_until_after_stall(tmp_path):
    campaign, runs = run_campaign(
        reports_dir=tmp_path,
        retry_intensity="deep",
        max_improvement_runs=8,
        allow_cheat_escalation=True,
        natural_first=True,
    )

    assert runs
    assert runs[0].summary.direct_verified_cheat_assisted == 0
    assert any(run.summary.direct_verified_cheat_assisted > 0 for run in runs[1:])
    assert campaign.stop_decision is not None


def test_profile_defaults_apply_when_max_improvement_runs_not_provided(tmp_path):
    campaign, _runs = run_campaign(
        reports_dir=tmp_path,
        retry_intensity="quick",
        max_improvement_runs=None,
        allow_cheat_escalation=False,
        natural_first=True,
    )

    assert campaign.configured_improvement_runs == 1
    assert campaign.effective_improvement_runs == 1


def test_runtime_guardrail_stop_decision_is_available():
    policy = normalize_retry_policy(
        campaign_id="campaign-test",
        retry_intensity="standard",
        max_improvement_runs=3,
        allow_cheat_escalation=False,
        natural_first=True,
        runtime_target_minutes=1,
    )
    snapshots = (
        RunProgressSnapshot(
            run_id="run-1",
            sequence_index=0,
            duration_seconds=0,
            direct_verified_natural=2,
            direct_verified_cheat_assisted=0,
            direct_unverified_total=10,
            non_observable_tracked=5,
            direct_gain_vs_previous=2,
            stall_detected=False,
            runtime_elapsed_seconds=61,
        ),
    )

    decision = decide_stop(
        policy=policy,
        snapshots=snapshots,
        final_run_id="run-1",
        budget_exhausted=False,
        now=datetime(2026, 4, 22, 10, 32, tzinfo=timezone.utc),
    )

    assert decision is not None
    assert decision.stop_reason == "runtime_guardrail"


def test_campaign_emits_stop_decision_artifact(tmp_path):
    campaign, _runs = run_campaign(
        reports_dir=tmp_path,
        retry_intensity="standard",
        max_improvement_runs=3,
        allow_cheat_escalation=False,
        natural_first=True,
    )

    assert campaign.stop_decision is not None
    decision_path = (
        campaign_dir(tmp_path, campaign.campaign_id) / "campaign-stop-decision.json"
    )
    assert decision_path.exists()


def test_instruction_store_reuse_updates_revisions_and_statuses(tmp_path):
    run_campaign(
        reports_dir=tmp_path,
        retry_intensity="standard",
        max_improvement_runs=1,
        allow_cheat_escalation=False,
        natural_first=True,
    )
    first = load_instruction_store(tmp_path)

    run_campaign(
        reports_dir=tmp_path,
        retry_intensity="standard",
        max_improvement_runs=1,
        allow_cheat_escalation=False,
        natural_first=True,
    )
    second = load_instruction_store(tmp_path)

    assert instruction_index_path(tmp_path).exists()
    assert instruction_path(tmp_path, "cmd-move-unit").exists()
    assert second["cmd-move-unit"].revision > first["cmd-move-unit"].revision
    assert second["cmd-move-unit"].status in {"active", "superseded", "retired"}
    assert "Build on saved instruction" not in second["cmd-move-unit"].instruction


def test_summary_tracks_direct_and_non_observable_splits(tmp_path):
    _campaign, runs = run_campaign(
        reports_dir=tmp_path,
        retry_intensity="standard",
        max_improvement_runs=2,
        allow_cheat_escalation=True,
        natural_first=True,
    )

    summary = runs[-1].summary
    assert (
        summary.directly_verifiable_total + summary.non_observable_tracked_total
        == summary.tracked_commands
    )
    assert (
        summary.direct_verified_natural + summary.direct_verified_cheat_assisted
        == summary.direct_verified_total
    )


def test_first_run_marks_verified_commands_as_newly_verified(tmp_path):
    _campaign, runs = run_campaign(
        reports_dir=tmp_path,
        retry_intensity="quick",
        max_improvement_runs=0,
        allow_cheat_escalation=False,
        natural_first=True,
    )

    assert runs[0].summary.newly_verified
    assert "cmd-attack" in runs[0].summary.newly_verified


def test_synthetic_run_records_fixture_provisioning_and_missing_fixture_causes(tmp_path):
    _campaign, runs = run_campaign(
        reports_dir=tmp_path,
        retry_intensity="quick",
        max_improvement_runs=0,
        allow_cheat_escalation=False,
        natural_first=True,
    )

    run = runs[0]

    assert run.fixture_profile is not None
    assert run.fixture_provisioning is not None
    assert run.transport_provisioning is not None
    assert "cmd-load-units" in run.fixture_provisioning.affected_command_ids
    class_statuses = {
        item.fixture_class: item for item in run.fixture_provisioning.class_statuses
    }
    assert class_statuses["transport_unit"].status == "missing"
    assert "cmd-load-units" in class_statuses["transport_unit"].affected_command_ids
    assert class_statuses["commander"].status == "provisioned"
    assert run.transport_provisioning.status == "missing"
    assert "cmd-load-units" in run.transport_provisioning.affected_command_ids
    assert any(
        item.fixture_class == "commander"
        for item in run.fixture_provisioning.shared_fixture_instances
    )
    causes = {item.command_id: item for item in run.failure_classifications}
    assert causes["cmd-load-units"].primary_cause == "missing_fixture"


def test_live_rows_can_unblock_shared_fixture_commands_when_fixture_is_available(tmp_path):
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
                "evidence": "transport fixture prepared and payload fixture prepared for load validation",
                "error": "effect_not_observed",
            }
        ],
    )

    assert run.fixture_provisioning is not None
    class_statuses = {
        item.fixture_class: item for item in run.fixture_provisioning.class_statuses
    }
    assert class_statuses["transport_unit"].status == "provisioned"
    assert class_statuses["payload_unit"].status == "provisioned"
    assert run.transport_provisioning is not None
    assert run.transport_provisioning.status == "provisioned"
    assert "cmd-load-units" not in class_statuses["transport_unit"].affected_command_ids
    causes = {item.command_id: item for item in run.failure_classifications}
    assert causes["cmd-load-units"].primary_cause == "predicate_or_evidence_gap"


def test_precise_missing_transport_detail_keeps_payload_provisioned(tmp_path):
    run = build_run(
        campaign_id="campaign-1",
        sequence_index=0,
        reports_dir=tmp_path,
        live_rows=[
            {
                "arm_name": "load_units",
                "category": REGISTRY["load_units"].category,
                "dispatched": "false",
                "verified": "na",
                "evidence": "live fixture dependency unavailable for this arm (transport_unit)",
                "error": "precondition_unmet",
            }
        ],
    )

    assert run.fixture_provisioning is not None
    class_statuses = {
        item.fixture_class: item for item in run.fixture_provisioning.class_statuses
    }
    assert class_statuses["transport_unit"].status == "missing"
    assert class_statuses["payload_unit"].status == "provisioned"
    assert run.transport_provisioning is not None
    assert run.transport_provisioning.status == "missing"


def test_refresh_failure_only_blocks_commands_that_depend_on_the_failed_fixture(tmp_path):
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
                "evidence": "transport fixture refresh_failed after payload stale event",
                "error": "precondition_unmet",
            }
        ],
    )

    assert run.fixture_provisioning is not None
    class_statuses = {
        item.fixture_class: item for item in run.fixture_provisioning.class_statuses
    }
    assert class_statuses["transport_unit"].status == "unusable"
    assert run.transport_provisioning is not None
    assert run.transport_provisioning.status == "unusable"
    assert "cmd-load-units" in class_statuses["transport_unit"].affected_command_ids
    assert "cmd-capture" not in class_statuses["transport_unit"].affected_command_ids
    assert any(
        item.fixture_class == "transport_unit"
        and item.usability_state == "refresh_failed"
        for item in run.fixture_provisioning.shared_fixture_instances
    )


def test_live_rows_block_contract_health_when_fixtures_are_missing(tmp_path):
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

    assert run.contract_health_decision is not None
    assert run.contract_health_decision.decision_status == "blocked_foundational"
    assert "live-closeout:missing-fixture" in run.contract_health_decision.blocking_issue_ids
    assert "missing fixture" in run.contract_health_decision.summary_message.lower()
    assert run.improvement_eligibility is not None
    assert run.improvement_eligibility.guidance_mode == "secondary_only"


def test_live_rows_promote_channel_failures_to_run_level_health_outcome(tmp_path):
    run = build_run(
        campaign_id="campaign-1",
        sequence_index=0,
        reports_dir=tmp_path,
        live_rows=[
            {
                "arm_name": "attack",
                "category": REGISTRY["attack"].category,
                "dispatched": "true",
                "verified": "true",
                "evidence": "enemy health dropped",
                "error": "",
            },
            {
                "arm_name": "fight",
                "category": REGISTRY["fight"].category,
                "dispatched": "false",
                "verified": "na",
                "evidence": "plugin command channel is not connected",
                "error": "dispatcher_rejected",
            },
        ],
    )

    assert run.channel_health is not None
    assert run.channel_health.status == "interrupted"
    assert run.channel_health.first_failure_stage == "dispatch"
    causes = {item.command_id: item for item in run.failure_classifications}
    assert causes["cmd-fight"].primary_cause == "transport_interruption"
    assert run.contract_health_decision is not None
    assert "live-closeout:transport-interruption" in run.contract_health_decision.blocking_issue_ids
    assert "transport interruption" in run.contract_health_decision.summary_message.lower()


def test_transport_provisioning_tracks_supported_variant_and_resolution_trace(tmp_path):
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
                "evidence": "preexisting transport armhvytrans reached load validation",
                "error": "effect_not_observed",
            }
        ],
    )

    assert run.transport_provisioning is not None
    assert run.transport_provisioning.status == "preexisting"
    assert run.transport_provisioning.candidates[0].variant_id == "armhvytrans"
    trace = {
        item.variant_id: item for item in run.transport_provisioning.resolution_trace
    }
    assert trace["armhvytrans"].resolution_status == "resolved"


def test_transport_payload_incompatibility_is_recorded_per_command(tmp_path):
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
                "evidence": "transport payload incompatible before load validation",
                "error": "precondition_unmet",
            }
        ],
    )

    assert run.transport_provisioning is not None
    assert run.transport_provisioning.status == "unusable"
    check = {
        item.command_id: item for item in run.transport_provisioning.compatibility_checks
    }["cmd-load-units"]
    assert check.result == "payload_incompatible"


def test_transport_fixture_status_diagnostics_are_preserved_in_blocking_reason(tmp_path):
    run = build_run(
        campaign_id="campaign-1",
        sequence_index=0,
        reports_dir=tmp_path,
        live_rows=[
            {
                "arm_name": "load_units",
                "category": REGISTRY["load_units"].category,
                "dispatched": "false",
                "verified": "na",
                "evidence": "live fixture dependency unavailable for this arm (transport_unit)",
                "fixture_status": (
                    "transport_debug factory_air=present "
                    "resolved_defs=armatlas:1,armhvytrans:1 "
                    "build_attempts=armatlas:dispatched_waited_no_ready_transport "
                    "pending=none ready=none "
                    "provisioning_action=dispatch_wait_completed attempted_variant=armatlas"
                ),
                "error": "precondition_unmet",
            }
        ],
    )

    record = {
        item.command_id: item for item in run.command_records
    }["cmd-load-units"]

    assert record.blocking_reason is not None
    assert "transport_debug" in record.blocking_reason
    assert "factory_air=present" in record.blocking_reason


def test_transport_status_ignores_non_transport_destroyed_evidence(tmp_path):
    run = build_run(
        campaign_id="campaign-1",
        sequence_index=0,
        reports_dir=tmp_path,
        live_rows=[
            {
                "arm_name": "attack",
                "category": REGISTRY["attack"].category,
                "dispatched": "true",
                "verified": "true",
                "evidence": "target 31603 destroyed",
                "error": "",
            },
            {
                "arm_name": "load_units",
                "category": REGISTRY["load_units"].category,
                "dispatched": "false",
                "verified": "na",
                "evidence": "live fixture dependency unavailable for this arm (transport_unit)",
                "fixture_status": (
                    "transport_debug factory_air=absent "
                    "resolved_defs=armatlas:0,armhvytrans:0 "
                    "build_attempts=none pending=none ready=none "
                    "provisioning_action=no_ready_factory_air"
                ),
                "error": "precondition_unmet",
            },
        ],
    )

    assert run.transport_provisioning is not None
    assert run.transport_provisioning.status == "missing"


def test_foundational_blockers_disable_normal_improvement_guidance(tmp_path):
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

    assert run.contract_health_decision is not None
    assert run.contract_health_decision.decision_status == "blocked_foundational"
    assert run.improvement_eligibility is not None
    assert run.improvement_eligibility.guidance_mode == "secondary_only"
    assert run.contract_issues
    assert run.deterministic_repros
    assert not run.improvement_actions


def test_pattern_review_blockers_have_no_normal_guidance_or_repro(tmp_path):
    run = build_run(
        campaign_id="campaign-1",
        sequence_index=0,
        reports_dir=tmp_path,
        live_rows=[
            {
                "arm_name": "move_unit",
                "category": REGISTRY["move_unit"].category,
                "dispatched": "true",
                "verified": "false",
                "evidence": "new foundational pattern needs pattern review",
                "error": "needs_pattern_review",
            }
        ],
    )

    assert run.contract_health_decision is not None
    assert run.contract_health_decision.decision_status == "needs_pattern_review"
    assert run.improvement_eligibility is not None
    assert run.improvement_eligibility.guidance_mode == "withheld"
    assert not run.deterministic_repros


def test_effect_not_observed_without_runtime_contract_signal_stays_secondary(tmp_path):
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

    assert run.channel_health is not None
    assert run.channel_health.status == "healthy"
    assert not run.contract_issues
    assert run.contract_health_decision is not None
    assert run.contract_health_decision.decision_status == "ready_for_itertesting"
    assert "downstream evidence" in run.contract_health_decision.summary_message.lower()
    causes = {item.command_id: item for item in run.failure_classifications}
    assert causes["cmd-patrol"].primary_cause == "predicate_or_evidence_gap"


def test_semantic_gate_rows_stay_channel_healthy_and_ready_for_itertesting(tmp_path):
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

    assert run.channel_health is not None
    assert run.channel_health.status == "healthy"
    assert run.contract_health_decision is not None
    assert run.contract_health_decision.decision_status == "ready_for_itertesting"
    assert run.semantic_gates
    assert run.semantic_gates[0].gate_kind == "mod-option"


def test_manual_launch_substitution_creates_unit_shape_semantic_gate(tmp_path):
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

    assert run.semantic_gates
    gate = {item.command_id: item for item in run.semantic_gates}["cmd-dgun"]
    assert gate.gate_kind == "unit-shape"
    assert gate.custom_command_id == 32102


def test_resolved_contract_issues_are_visible_in_later_run(tmp_path):
    first = build_run(
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

    second = build_run(
        campaign_id="campaign-1",
        sequence_index=1,
        reports_dir=tmp_path,
        previous_run=first,
        live_rows=[
            {
                "arm_name": "move_unit",
                "category": REGISTRY["move_unit"].category,
                "dispatched": "true",
                "verified": "true",
                "evidence": "move_unit verified after validator fix",
                "error": "",
            }
        ],
    )

    assert second.contract_health_decision is not None
    assert second.contract_health_decision.decision_status == "ready_for_itertesting"
    assert second.contract_health_decision.resolved_issue_ids == (
        first.contract_issues[0].issue_id,
    )


def test_campaign_stops_immediately_when_contract_health_is_blocked(tmp_path, monkeypatch):
    def fake_collect_live_rows(_args):
        return [
            {
                "arm_name": "move_unit",
                "category": REGISTRY["move_unit"].category,
                "dispatched": "false",
                "verified": "false",
                "evidence": "batch target 4 disagreed with command unit 9",
                "error": "target_drift",
            }
        ]

    monkeypatch.setattr(behavioral_coverage, "collect_live_rows", fake_collect_live_rows)

    campaign, runs = run_campaign(
        reports_dir=tmp_path,
        retry_intensity="standard",
        max_improvement_runs=3,
        allow_cheat_escalation=False,
        natural_first=True,
        skip_live=False,
        endpoint="unix:/tmp/unused.sock",
    )

    assert len(runs) == 1
    assert campaign.stop_decision is not None
    assert campaign.stop_decision.stop_reason == "foundational_blocked"


def test_summary_tracks_tuned_rule_count(tmp_path):
    _campaign, runs = run_campaign(
        reports_dir=tmp_path,
        retry_intensity="quick",
        max_improvement_runs=0,
        allow_cheat_escalation=False,
        natural_first=True,
    )

    assert runs[0].summary.arm_rules_tuned_count >= 3


def test_run_exposes_tuned_verification_rules_for_priority_arms(tmp_path):
    _campaign, runs = run_campaign(
        reports_dir=tmp_path,
        retry_intensity="quick",
        max_improvement_runs=0,
        allow_cheat_escalation=False,
        natural_first=True,
    )

    rules = {item.command_id: item for item in runs[0].verification_rules}

    assert rules["cmd-move-unit"].rule_mode == "movement_tuned"
    assert rules["cmd-fight"].rule_mode == "combat_tuned"
    assert rules["cmd-build-unit"].rule_mode == "construction_tuned"


def test_cli_emits_run_bundle(tmp_path):
    rc = itertesting_main(
        [
            "--reports-dir",
            str(tmp_path),
            "--retry-intensity",
            "standard",
            "--max-improvement-runs",
            "1",
        ]
    )

    bundles = list(tmp_path.glob("itertesting-*/manifest.json"))

    assert rc == 0
    assert bundles


def test_malformed_prior_manifest_is_rejected(tmp_path):
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps({"run_id": "bad"}), encoding="utf-8")

    with pytest.raises(ValueError):
        load_run_manifest(manifest)


def test_incomplete_run_bundle_is_rejected(tmp_path):
    manifest = tmp_path / "manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "run_id": "bad",
                "campaign_id": "campaign",
                "summary": {"run_id": "bad"},
                "command_records": [],
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError):
        load_run_manifest(manifest)

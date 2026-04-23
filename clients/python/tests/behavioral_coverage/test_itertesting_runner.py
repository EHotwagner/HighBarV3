# SPDX-License-Identifier: GPL-2.0-only
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

import highbar_client.behavioral_coverage as behavioral_coverage
import highbar_client.behavioral_coverage.bnv_watch as bnv_watch
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
    ViewerAccessRecord,
    WatchPreflightResult,
    WatchRequest,
    WatchedRunSession,
    manifest_dict,
)
from highbar_client.behavioral_coverage.registry import REGISTRY
from highbar_client.behavioral_coverage.watch_registry import (
    load_active_watch_index,
    upsert_watch_session,
)


def _live_rows_with_hardening_metadata():
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
            "readiness_status": "resource_starved",
            "readiness_path": "unavailable",
            "first_required_step": "armvp",
            "economy_summary": "economy=metal:0.1/0.0/1500.0",
            "reason": "first commander-built bootstrap step armvp would start from a resource-starved state",
            "recorded_at": "2026-04-23T02:42:47Z",
        },
        {
            "arm_name": "__callback_diagnostic__",
            "snapshot_id": "callback-01",
            "capture_stage": "bootstrap_start",
            "availability_status": "live",
            "source": "invoke_callback_live",
            "diagnostic_scope": ["commander_def", "build_options", "economy"],
            "summary": "commander_def=armcom commander_builds=armmex:1 economy=metal:0.1/0.0/1500.0",
            "captured_at": "2026-04-23T02:42:47Z",
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


def _fake_bnv_binary(tmp_path: Path) -> Path:
    path = tmp_path / "fake-bnv.sh"
    path.write_text("#!/usr/bin/env bash\nsleep 1\n", encoding="utf-8")
    path.chmod(0o755)
    return path


def _seed_graphical_watch_context(monkeypatch, binary: Path, *, pid: str = "101") -> None:
    monkeypatch.setenv("HIGHBAR_BAR_CLIENT_BINARY", str(binary))
    monkeypatch.setenv("HIGHBAR_ITERTESTING_WATCH_LAUNCHED", "true")
    monkeypatch.setenv("HIGHBAR_ITERTESTING_WATCH_ENGINE_PID", pid)
    monkeypatch.setenv(
        "HIGHBAR_ITERTESTING_WATCH_STARTSCRIPT",
        "tests/headless/scripts/minimal.startscript",
    )
    monkeypatch.setenv("HIGHBAR_WRITE_DIR", "/tmp/highbar-write")


def _active_watch_session(run_id: str) -> WatchedRunSession:
    return WatchedRunSession(
        run_id=run_id,
        campaign_id="campaign-1",
        run_lifecycle_state="active",
        watch_requested=True,
        watch_request=WatchRequest(
            request_id=f"watch-{run_id}",
            request_mode="launch-time",
            requested_at="2026-04-23T10:00:00Z",
            target_run_id=run_id,
            selection_mode="explicit",
            profile_ref="default",
            watch_required=True,
        ),
        preflight_result=WatchPreflightResult(
            status="ready",
            reason="BAR graphical client watch preflight succeeded",
            checked_at="2026-04-23T10:00:00Z",
            blocking=False,
        ),
        viewer_access=ViewerAccessRecord(
            availability_state="available",
            reason="graphical BAR client launched for watched run",
            launch_command=("spring", "--window", "tests/headless/scripts/minimal.startscript"),
            launched_at="2026-04-23T10:00:01Z",
            viewer_pid=101,
            last_transition_at="2026-04-23T10:00:01Z",
        ),
        report_path=str(Path("/tmp") / run_id / "run-report.md"),
    )


def _write_active_watch_manifest(reports_dir: Path, session: WatchedRunSession) -> Path:
    run = build_run(
        campaign_id=session.campaign_id or "campaign-1",
        sequence_index=0,
        reports_dir=reports_dir,
        run_id=session.run_id,
        watch_session=session,
    )
    bundle = reports_dir / session.run_id
    bundle.mkdir(parents=True, exist_ok=True)
    manifest_path = bundle / "manifest.json"
    manifest_path.write_text(json.dumps(manifest_dict(run)), encoding="utf-8")
    return manifest_path


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
    assert loaded.bootstrap_readiness is not None
    assert loaded.runtime_capability_profile is not None
    assert loaded.callback_diagnostics
    assert loaded.map_source_decisions
    assert loaded.fixture_provisioning.class_statuses
    assert loaded.fixture_provisioning.shared_fixture_instances
    assert loaded.semantic_gates == run.semantic_gates


def test_manifest_round_trip_preserves_bootstrap_and_probe_metadata(tmp_path):
    run = build_run(
        campaign_id="campaign-1",
        sequence_index=0,
        reports_dir=tmp_path,
        live_rows=_live_rows_with_hardening_metadata(),
    )
    bundle = tmp_path / run.run_id
    bundle.mkdir()
    manifest = bundle / "manifest.json"
    manifest.write_text(json.dumps(manifest_dict(run)), encoding="utf-8")

    loaded = load_run_manifest(manifest)

    assert loaded.bootstrap_readiness is not None
    assert loaded.bootstrap_readiness.readiness_status == "resource_starved"
    assert loaded.runtime_capability_profile is not None
    assert loaded.runtime_capability_profile.supported_callbacks == (40, 47)
    assert loaded.runtime_capability_profile.map_data_source_status == "hello_static_map"
    assert loaded.callback_diagnostics[0].availability_status == "live"
    assert loaded.prerequisite_resolution[0].resolved_def_id == 42
    assert loaded.map_source_decisions[0].selected_source == "hello_static_map"
    assert loaded.standalone_build_probe_outcome is not None
    assert loaded.standalone_build_probe_outcome.dispatch_result == "verified"
    assert loaded.standalone_build_probe_outcome.map_source_decision is not None
    assert (
        loaded.standalone_build_probe_outcome.map_source_decision.selected_source
        == "hello_static_map"
    )
    assert (
        loaded.standalone_build_probe_outcome.capability_limit_summary
        == "deeper commander/build-option diagnostics are capability-limited on this host"
    )


def test_bootstrap_blocked_live_rows_do_not_claim_unbuilt_fixtures(tmp_path):
    run = build_run(
        campaign_id="campaign-1",
        sequence_index=0,
        reports_dir=tmp_path,
        live_rows=[
            {
                "arm_name": "__bootstrap_readiness__",
                "readiness_status": "resource_starved",
                "readiness_path": "unavailable",
                "first_required_step": "armap",
                "economy_summary": "economy=metal:0.0/0.0/1950.0",
                "reason": "first commander-built bootstrap step armap would start from a resource-starved state",
                "recorded_at": "2026-04-23T09:32:32Z",
            }
        ],
    )

    assert run.fixture_provisioning is not None
    class_statuses = {
        item.fixture_class: item for item in run.fixture_provisioning.class_statuses
    }
    assert class_statuses["commander"].status == "provisioned"
    assert class_statuses["movement_lane"].status == "provisioned"
    assert class_statuses["resource_baseline"].status == "provisioned"
    assert class_statuses["builder"].status == "missing"
    assert class_statuses["cloakable"].status == "missing"
    assert class_statuses["hostile_target"].status == "missing"
    provisioned = set(run.fixture_provisioning.provisioned_fixture_classes)
    assert "builder" not in provisioned
    assert "cloakable" not in provisioned
    assert "hostile_target" not in provisioned


def test_latest_fixture_transition_wins_for_transport_unit(tmp_path):
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
            },
            {
                "arm_name": "unload_unit",
                "category": REGISTRY["unload_unit"].category,
                "dispatched": "true",
                "verified": "false",
                "evidence": "transport fixture refreshed with payload fixture replacement",
                "error": "effect_not_observed",
            },
        ],
    )

    latest_transport_transition = [
        item for item in run.fixture_transitions if item.fixture_class == "transport_unit"
    ][-1]

    assert latest_transport_transition.state == "refreshed"
    assert run.fixture_provisioning is not None
    class_statuses = {
        item.fixture_class: item for item in run.fixture_provisioning.class_statuses
    }
    assert class_statuses["transport_unit"].status == "refreshed"
    assert run.transport_decision is not None
    assert run.transport_decision.availability_status == "available"


def test_evidence_poor_live_run_keeps_transport_unknown(tmp_path):
    run = build_run(
        campaign_id="campaign-1",
        sequence_index=0,
        reports_dir=tmp_path,
        live_rows=[
            {
                "arm_name": "__bootstrap_readiness__",
                "readiness_status": "seeded_ready",
                "readiness_path": "explicit_seed",
                "first_required_step": "armmex",
                "economy_summary": "economy=metal:10.0/1.0/1500.0",
                "reason": "prepared live start already contained bootstrap fixtures",
                "recorded_at": "2026-04-23T09:32:32Z",
            },
            {
                "arm_name": "attack",
                "category": REGISTRY["attack"].category,
                "dispatched": "true",
                "verified": "false",
                "evidence": "place_target_on_ground Lua rewrite converted the unit target into map coordinates",
                "error": "effect_not_observed",
            },
        ],
    )

    assert run.transport_provisioning is not None
    assert run.transport_provisioning.status == "missing"
    assert run.transport_decision is not None
    assert run.transport_decision.availability_status == "unknown"
    assert run.transport_decision.explicit_evidence is False


def test_unknown_metadata_blocks_fully_interpreted_and_survives_manifest_round_trip(tmp_path):
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

    assert run.fully_interpreted is False
    assert run.interpretation_warnings
    assert run.interpretation_warnings[0].record_type == "future_runtime_fact"
    assert run.live_execution_capture is not None
    assert run.live_execution_capture.metadata_records[0].record_type == "future_runtime_fact"
    assert run.contract_health_decision is not None
    assert run.contract_health_decision.decision_status == "blocked_foundational"

    bundle = tmp_path / run.run_id
    bundle.mkdir()
    manifest = bundle / "manifest.json"
    manifest.write_text(json.dumps(manifest_dict(run)), encoding="utf-8")

    loaded = load_run_manifest(manifest)

    assert loaded.fully_interpreted is False
    assert loaded.interpretation_warnings[0].record_type == "future_runtime_fact"
    assert loaded.live_execution_capture is not None
    assert loaded.live_execution_capture.metadata_records[0].record_type == "future_runtime_fact"


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


def test_cli_argument_parsing_supports_watch_launch_and_attach_flags():
    launch_args = parse_itertesting_args(
        [
            "--watch",
            "--watch-profile",
            "default",
            "--watch-speed",
            "2",
        ]
    )
    attach_args = parse_itertesting_args(
        [
            "--watch-run",
            "run-1",
            "--watch-profile",
            "default",
        ]
    )
    auto_attach_args = parse_itertesting_args(
        [
            "--watch-run",
            "--watch-profile",
            "default",
        ]
    )

    assert launch_args.watch is True
    assert launch_args.watch_profile == "default"
    assert launch_args.watch_speed == 2.0
    assert attach_args.watch_run == "run-1"
    assert attach_args.watch is False
    assert auto_attach_args.watch_run == ""


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


def test_campaign_escalates_foundational_block_to_cheat_follow_up_when_allowed(
    tmp_path,
    monkeypatch,
):
    seen_startscripts = []

    def fake_collect_live_rows(args):
        seen_startscripts.append(args.startscript)
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
        max_improvement_runs=1,
        allow_cheat_escalation=True,
        natural_first=True,
        skip_live=False,
        endpoint="unix:/tmp/unused.sock",
    )

    assert len(runs) == 2
    assert seen_startscripts[0].endswith("minimal.startscript")
    assert seen_startscripts[1].endswith("cheats.startscript")
    assert runs[0].contract_health_decision is not None
    assert runs[1].sequence_index == 1
    assert campaign.stop_decision is not None
    assert campaign.stop_decision.stop_reason == "foundational_blocked"


def test_watch_preflight_failure_aborts_before_live_collection(tmp_path, monkeypatch):
    calls = 0

    def fake_collect_live_rows(_args):
        nonlocal calls
        calls += 1
        raise AssertionError("collect_live_rows should not be called after watch preflight failure")

    monkeypatch.setattr(behavioral_coverage, "collect_live_rows", fake_collect_live_rows)
    monkeypatch.delenv("HIGHBAR_BAR_CLIENT_BINARY", raising=False)
    monkeypatch.delenv("HIGHBAR_BNV_BINARY", raising=False)
    monkeypatch.delenv("SPRING_HEADLESS", raising=False)
    monkeypatch.delenv("HIGHBAR_WRITE_DIR", raising=False)

    campaign, runs = run_campaign(
        reports_dir=tmp_path,
        retry_intensity="quick",
        max_improvement_runs=0,
        allow_cheat_escalation=False,
        natural_first=True,
        skip_live=False,
        watch=True,
        watch_profile="default",
        endpoint="unix:/tmp/unused.sock",
    )

    assert calls == 0
    assert campaign.stop_decision is not None
    assert runs[0].watch_session is not None
    assert runs[0].watch_session.preflight_result is not None
    assert runs[0].watch_session.preflight_result.status == "viewer_missing"
    assert runs[0].watch_session.run_lifecycle_state == "failed"


def test_watch_launch_updates_manifest_and_index(tmp_path, monkeypatch):
    binary = _fake_bnv_binary(tmp_path)
    _seed_graphical_watch_context(monkeypatch, binary, pid="102")
    monkeypatch.setattr(bnv_watch, "apply_watch_speed", lambda speed: None)

    def fake_collect_live_rows(_args):
        return [
            {
                "arm_name": "attack",
                "category": REGISTRY["attack"].category,
                "dispatched": "true",
                "verified": "true",
                "evidence": "attack verified while watch mode was enabled",
                "error": "",
            }
        ]

    monkeypatch.setattr(behavioral_coverage, "collect_live_rows", fake_collect_live_rows)

    _campaign, runs = run_campaign(
        reports_dir=tmp_path,
        retry_intensity="quick",
        max_improvement_runs=0,
        allow_cheat_escalation=False,
        natural_first=True,
        skip_live=False,
        watch=True,
        watch_profile="default",
        watch_speed=2.0,
        endpoint="unix:/tmp/unused.sock",
    )

    run = runs[0]
    assert run.watch_session is not None
    assert run.watch_session.preflight_result is not None
    assert run.watch_session.preflight_result.status == "ready"
    assert run.watch_session.viewer_access is not None
    assert run.watch_session.viewer_access.availability_state == "available"

    manifest = load_run_manifest(tmp_path / run.run_id / "manifest.json")
    assert manifest.watch_session is not None
    assert manifest.watch_session.preflight_result is not None
    assert manifest.watch_session.preflight_result.status == "ready"
    assert manifest.watch_session.preflight_result.resolved_profile is not None
    assert manifest.watch_session.preflight_result.resolved_profile.watch_speed == 2.0
    assert manifest.watch_session.report_path.endswith("run-report.md")

    index = load_active_watch_index(tmp_path)
    entry = [item for item in index.entries if item.run_id == run.run_id][0]
    assert entry.watch_state == "completed"
    assert entry.compatible_for_attach is False
    assert entry.report_path.endswith("run-report.md")


def test_attach_later_cli_resolves_explicit_run_id(tmp_path, monkeypatch):
    binary = _fake_bnv_binary(tmp_path)
    _seed_graphical_watch_context(monkeypatch, binary, pid="103")
    session = _active_watch_session("run-1")
    manifest_path = _write_active_watch_manifest(tmp_path, session)
    upsert_watch_session(
        tmp_path,
        session,
        updated_at="2026-04-23T10:00:01Z",
        manifest_path=str(manifest_path),
    )

    rc = itertesting_main(
        [
            "--reports-dir",
            str(tmp_path),
            "--watch-run",
            "run-1",
            "--watch-profile",
            "default",
        ]
    )

    assert rc == 0
    index = load_active_watch_index(tmp_path)
    entry = [item for item in index.entries if item.run_id == "run-1"][0]
    assert entry.compatible_for_attach is True


def test_attach_later_cli_rejects_ambiguous_auto_selection(tmp_path, monkeypatch):
    binary = _fake_bnv_binary(tmp_path)
    _seed_graphical_watch_context(monkeypatch, binary, pid="104")
    session_1 = _active_watch_session("run-1")
    session_2 = _active_watch_session("run-2")
    manifest_path_1 = _write_active_watch_manifest(tmp_path, session_1)
    manifest_path_2 = _write_active_watch_manifest(tmp_path, session_2)
    upsert_watch_session(
        tmp_path,
        session_1,
        updated_at="2026-04-23T10:00:01Z",
        manifest_path=str(manifest_path_1),
    )
    upsert_watch_session(
        tmp_path,
        session_2,
        updated_at="2026-04-23T10:01:01Z",
        manifest_path=str(manifest_path_2),
    )

    rc = itertesting_main(
        [
            "--reports-dir",
            str(tmp_path),
            "--watch-run",
            "--watch-profile",
            "default",
        ]
    )

    assert rc == 1


def test_non_watch_live_campaign_leaves_watch_session_empty(tmp_path, monkeypatch):
    def fake_collect_live_rows(_args):
        return [
            {
                "arm_name": "attack",
                "category": REGISTRY["attack"].category,
                "dispatched": "true",
                "verified": "true",
                "evidence": "attack verified without watch mode",
                "error": "",
            }
        ]

    monkeypatch.setattr(behavioral_coverage, "collect_live_rows", fake_collect_live_rows)

    _campaign, runs = run_campaign(
        reports_dir=tmp_path,
        retry_intensity="quick",
        max_improvement_runs=0,
        allow_cheat_escalation=False,
        natural_first=True,
        skip_live=False,
        endpoint="unix:/tmp/unused.sock",
    )

    assert runs[0].watch_session is None


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

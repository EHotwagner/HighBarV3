# SPDX-License-Identifier: GPL-2.0-only
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

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

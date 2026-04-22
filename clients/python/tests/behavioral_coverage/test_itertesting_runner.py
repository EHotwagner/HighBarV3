# SPDX-License-Identifier: GPL-2.0-only
from __future__ import annotations

import json
from pathlib import Path

import pytest

from highbar_client.behavioral_coverage.itertesting_runner import (
    build_run,
    instruction_index_path,
    instruction_path,
    itertesting_main,
    load_instruction_store,
    load_run_manifest,
    make_run_id,
    parse_itertesting_args,
    run_campaign,
)
from highbar_client.behavioral_coverage.itertesting_types import manifest_dict
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


def test_cli_argument_parsing_supports_cheat_flags():
    args = parse_itertesting_args(
        [
            "--reports-dir",
            "reports/itertesting",
            "--max-improvement-runs",
            "3",
            "--allow-cheat-escalation",
            "--cheat-startscript",
            "tests/headless/scripts/cheats.startscript",
        ]
    )

    assert args.max_improvement_runs == 3
    assert args.allow_cheat_escalation is True
    assert args.natural_first is True


def test_manifest_shape_and_command_coverage(tmp_path):
    campaign, runs = run_campaign(
        reports_dir=tmp_path,
        max_improvement_runs=0,
        allow_cheat_escalation=False,
        natural_first=True,
    )

    run = runs[0]

    assert campaign.run_ids == (run.run_id,)
    assert run.summary.tracked_commands == len(REGISTRY)
    assert {item.command_id for item in run.command_records} == {
        f"cmd-{name.replace('_', '-')}" for name in REGISTRY
    }


def test_dispatch_only_never_verifies():
    run = build_run(
        campaign_id="campaign-1",
        sequence_index=0,
        reports_dir=Path("."),
    )
    dispatch_only = [
        item
        for item in run.command_records
        if item.evidence_kind == "dispatch-only"
    ]

    assert dispatch_only
    assert all(not item.verified for item in dispatch_only)


def test_retry_budget_and_previous_run_comparison(tmp_path):
    campaign, runs = run_campaign(
        reports_dir=tmp_path,
        max_improvement_runs=1,
        allow_cheat_escalation=False,
        natural_first=True,
    )

    assert len(runs) == 2
    assert campaign.final_status == "budget_exhausted"
    assert runs[1].previous_run_comparison is not None
    assert runs[1].previous_run_comparison.coverage_delta > 0


def test_natural_first_cheat_escalation(tmp_path):
    campaign, runs = run_campaign(
        reports_dir=tmp_path,
        max_improvement_runs=2,
        allow_cheat_escalation=True,
        natural_first=True,
    )

    assert len(runs) == 3
    assert runs[0].summary.verified_cheat_assisted == 0
    assert runs[1].summary.verified_cheat_assisted == 0
    assert runs[2].summary.verified_cheat_assisted > 0
    assert campaign.final_status in {"stalled", "budget_exhausted"}


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


def test_cli_emits_run_bundle(tmp_path):
    rc = itertesting_main(
        [
            "--reports-dir",
            str(tmp_path),
            "--max-improvement-runs",
            "0",
        ]
    )

    bundles = list(tmp_path.glob("itertesting-*/manifest.json"))

    assert rc == 0
    assert bundles


def test_campaign_writes_reusable_instruction_files(tmp_path):
    _campaign, runs = run_campaign(
        reports_dir=tmp_path,
        max_improvement_runs=0,
        allow_cheat_escalation=False,
        natural_first=True,
    )

    store = load_instruction_store(tmp_path)

    assert instruction_index_path(tmp_path).exists()
    assert instruction_path(tmp_path, "cmd-move-unit").exists()
    assert store["cmd-move-unit"].revision == 1
    assert store["cmd-move-unit"].status == "active"
    assert store["cmd-move-unit"].action_type == "timing-change"
    assert store["cmd-move-unit"].source_run_id == runs[0].run_id


def test_future_campaign_reuses_saved_instructions(tmp_path):
    run_campaign(
        reports_dir=tmp_path,
        max_improvement_runs=0,
        allow_cheat_escalation=False,
        natural_first=True,
    )

    _campaign, runs = run_campaign(
        reports_dir=tmp_path,
        max_improvement_runs=0,
        allow_cheat_escalation=False,
        natural_first=True,
    )

    move_unit = next(
        item for item in runs[0].command_records if item.command_id == "cmd-move-unit"
    )
    store = load_instruction_store(tmp_path)

    assert move_unit.verified is True
    assert "saved instruction" in move_unit.evidence_summary
    assert store["cmd-move-unit"].revision == 2
    assert store["cmd-move-unit"].status == "applied"

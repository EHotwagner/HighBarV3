# SPDX-License-Identifier: GPL-2.0-only
from __future__ import annotations

from highbar_client.behavioral_coverage.audit_runner import (
    collect_live_audit_run,
    serialize_manifest,
    load_manifest,
)


def test_live_manifest_round_trip(tmp_path):
    run = collect_live_audit_run()
    manifest_path = serialize_manifest(run, tmp_path / f"{run.run_id}.json")
    loaded = load_manifest(manifest_path)

    assert loaded.run_id == run.run_id
    assert loaded.completed_at is not None
    assert len(loaded.row_results) == 74
    assert {item.deliverable_name for item in loaded.deliverables} == {
        "command-audit",
        "hypothesis-plan",
        "v2-v3-ledger",
    }
    assert loaded.summary.not_refreshed_count == 0


def test_partial_manifest_captures_partial_status(monkeypatch, tmp_path):
    monkeypatch.setenv("HIGHBAR_AUDIT_SESSION_FAILURE", "gateway disconnected")
    monkeypatch.setenv("HIGHBAR_AUDIT_FAIL_RPCS", "Save")

    run = collect_live_audit_run()
    manifest_path = serialize_manifest(run, tmp_path / f"{run.run_id}.json")
    loaded = load_manifest(manifest_path)

    assert loaded.session_status == "partial"
    assert loaded.summary.not_refreshed_count >= 1
    assert any(item.status == "partial" for item in loaded.deliverables)

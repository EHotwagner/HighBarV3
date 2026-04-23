# SPDX-License-Identifier: GPL-2.0-only
from __future__ import annotations

from highbar_client.behavioral_coverage.bootstrap import BootstrapContext
from highbar_client.behavioral_coverage.live_execution import (
    build_live_execution_capture,
    metadata_envelopes_from_bootstrap_context,
)


def test_bootstrap_context_metadata_is_captured_as_typed_envelopes():
    ctx = BootstrapContext()
    ctx.bootstrap_readiness = {
        "readiness_status": "seeded_ready",
        "readiness_path": "explicit_seed",
        "recorded_at": "2026-04-23T02:42:47Z",
    }
    ctx.runtime_capability_profile = {
        "profile_id": "cap-40-47",
        "supported_callbacks": [40, 47],
        "recorded_at": "2026-04-23T02:42:47Z",
    }
    ctx.callback_diagnostics.append(
        {
            "snapshot_id": "callback-01",
            "capture_stage": "bootstrap_start",
            "availability_status": "live",
            "captured_at": "2026-04-23T02:42:47Z",
        }
    )

    records = metadata_envelopes_from_bootstrap_context(ctx)

    assert [item.record_type for item in records] == [
        "bootstrap_readiness",
        "runtime_capability_profile",
        "callback_diagnostic",
    ]
    assert records[0].payload["readiness_status"] == "seeded_ready"
    assert records[1].payload["profile_id"] == "cap-40-47"


def test_live_execution_capture_separates_command_rows_from_metadata_rows():
    capture = build_live_execution_capture(
        run_id="run-1",
        setup_mode="natural",
        live_rows=[
            {
                "arm_name": "__bootstrap_readiness__",
                "readiness_status": "resource_starved",
                "readiness_path": "unavailable",
                "recorded_at": "2026-04-23T02:42:47Z",
            },
            {
                "arm_name": "attack",
                "category": "channel_a_command",
                "dispatched": "true",
                "verified": "false",
                "evidence": "effect not observed",
                "error": "effect_not_observed",
            },
        ],
        collection_notes=("synthetic collection for test",),
    )

    assert capture.run_id == "run-1"
    assert capture.collection_notes == ("synthetic collection for test",)
    assert len(capture.command_rows) == 1
    assert capture.command_rows[0]["arm_name"] == "attack"
    assert len(capture.metadata_records) == 1
    assert capture.metadata_records[0].record_type == "bootstrap_readiness"

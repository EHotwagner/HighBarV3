# SPDX-License-Identifier: GPL-2.0-only
from __future__ import annotations

from highbar_client.behavioral_coverage.metadata_records import (
    interpretation_rule_for_record_type,
    metadata_envelope_from_row,
    metadata_rows_for_envelopes,
    split_command_and_metadata_rows,
)


def test_known_metadata_rows_round_trip_through_envelopes():
    live_rows = [
        {
            "arm_name": "__bootstrap_readiness__",
            "readiness_status": "seeded_ready",
            "readiness_path": "explicit_seed",
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
    ]

    command_rows, metadata_records = split_command_and_metadata_rows(live_rows)

    assert len(command_rows) == 1
    assert command_rows[0]["arm_name"] == "attack"
    assert len(metadata_records) == 1
    assert metadata_records[0].record_type == "bootstrap_readiness"
    assert metadata_records[0].interpretation_status == "handled"

    round_trip_rows = metadata_rows_for_envelopes(metadata_records)

    assert round_trip_rows[0]["arm_name"] == live_rows[0]["arm_name"]
    assert round_trip_rows[0]["readiness_status"] == live_rows[0]["readiness_status"]
    assert round_trip_rows[0]["readiness_path"] == live_rows[0]["readiness_path"]
    assert round_trip_rows[0]["recorded_at"] == live_rows[0]["recorded_at"]


def test_unknown_metadata_records_are_preserved_and_marked_unhandled():
    envelope = metadata_envelope_from_row(
        {
            "arm_name": "__future_runtime_fact__",
            "recorded_at": "2026-04-23T02:42:47Z",
            "detail": "new metadata the runner does not know yet",
        },
        sequence_index=3,
    )

    assert envelope.record_type == "future_runtime_fact"
    assert envelope.interpretation_status == "unhandled"
    assert envelope.payload["detail"] == "new metadata the runner does not know yet"
    assert interpretation_rule_for_record_type(envelope.record_type) is None


def test_known_record_types_have_single_authoritative_rules():
    for record_type in (
        "bootstrap_readiness",
        "runtime_capability_profile",
        "callback_diagnostic",
        "prerequisite_resolution",
        "map_source_decision",
        "standalone_build_probe",
    ):
        rule = interpretation_rule_for_record_type(record_type)

        assert rule is not None
        assert rule.record_type == record_type
        assert rule.owner_module.endswith("run_interpretation")

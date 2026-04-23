# SPDX-License-Identifier: GPL-2.0-only
"""Typed metadata record definitions and row/envelope conversion helpers."""

from __future__ import annotations

from typing import Any

from .itertesting_types import MetadataInterpretationRule, MetadataRecordEnvelope


KNOWN_METADATA_RECORD_TYPES: tuple[str, ...] = (
    "bootstrap_readiness",
    "runtime_capability_profile",
    "callback_diagnostic",
    "prerequisite_resolution",
    "map_source_decision",
    "standalone_build_probe",
)

RECORD_TYPE_TO_MARKER: dict[str, str] = {
    "bootstrap_readiness": "__bootstrap_readiness__",
    "runtime_capability_profile": "__runtime_capability_profile__",
    "callback_diagnostic": "__callback_diagnostic__",
    "prerequisite_resolution": "__prerequisite_resolution__",
    "map_source_decision": "__map_source_decision__",
    "standalone_build_probe": "__standalone_build_probe__",
}
MARKER_TO_RECORD_TYPE = {value: key for key, value in RECORD_TYPE_TO_MARKER.items()}

METADATA_INTERPRETATION_RULES: tuple[MetadataInterpretationRule, ...] = (
    MetadataInterpretationRule(
        record_type="bootstrap_readiness",
        consumer="bootstrap_readiness",
        required_fields=("readiness_status", "readiness_path"),
        fallback_behavior="preserve_and_block",
        owner_module="highbar_client.behavioral_coverage.run_interpretation",
        warning_template="bootstrap readiness metadata is incomplete",
    ),
    MetadataInterpretationRule(
        record_type="runtime_capability_profile",
        consumer="runtime_capability_profile",
        required_fields=("profile_id",),
        fallback_behavior="warning_only",
        owner_module="highbar_client.behavioral_coverage.run_interpretation",
        warning_template="runtime capability metadata is incomplete",
    ),
    MetadataInterpretationRule(
        record_type="callback_diagnostic",
        consumer="callback_diagnostic",
        required_fields=("snapshot_id",),
        fallback_behavior="warning_only",
        owner_module="highbar_client.behavioral_coverage.run_interpretation",
        warning_template="callback diagnostic metadata is incomplete",
    ),
    MetadataInterpretationRule(
        record_type="prerequisite_resolution",
        consumer="prerequisite_resolution",
        required_fields=("prerequisite_name", "resolution_status"),
        fallback_behavior="warning_only",
        owner_module="highbar_client.behavioral_coverage.run_interpretation",
        warning_template="prerequisite resolution metadata is incomplete",
    ),
    MetadataInterpretationRule(
        record_type="map_source_decision",
        consumer="map_source_decision",
        required_fields=("consumer", "selected_source"),
        fallback_behavior="warning_only",
        owner_module="highbar_client.behavioral_coverage.run_interpretation",
        warning_template="map-source decision metadata is incomplete",
    ),
    MetadataInterpretationRule(
        record_type="standalone_build_probe",
        consumer="standalone_build_probe",
        required_fields=("probe_id", "dispatch_result"),
        fallback_behavior="warning_only",
        owner_module="highbar_client.behavioral_coverage.run_interpretation",
        warning_template="standalone build probe metadata is incomplete",
    ),
)


def interpretation_rule_for_record_type(
    record_type: str,
) -> MetadataInterpretationRule | None:
    for rule in METADATA_INTERPRETATION_RULES:
        if rule.record_type == record_type:
            return rule
    return None


def marker_for_record_type(record_type: str) -> str:
    return RECORD_TYPE_TO_MARKER.get(record_type, f"__{record_type}__")


def record_type_for_marker(marker: str) -> str:
    if marker in MARKER_TO_RECORD_TYPE:
        return MARKER_TO_RECORD_TYPE[marker]
    trimmed = marker.strip("_")
    return trimmed or "unknown"


def is_metadata_row(row: dict[str, Any]) -> bool:
    return str(row.get("arm_name", "")).startswith("__")


def metadata_envelope(
    *,
    record_type: str,
    payload: dict[str, Any],
    source_layer: str = "live_execution",
    sequence_index: int = 0,
    recorded_at: str | None = None,
) -> MetadataRecordEnvelope:
    timestamp = str(
        recorded_at
        or payload.get("recorded_at")
        or payload.get("captured_at")
        or payload.get("completed_at")
        or ""
    )
    interpretation_status = (
        "handled"
        if interpretation_rule_for_record_type(record_type) is not None
        else "unhandled"
    )
    return MetadataRecordEnvelope(
        record_type=record_type,
        source_layer=source_layer,  # type: ignore[arg-type]
        sequence_index=sequence_index,
        payload=dict(payload),
        recorded_at=timestamp,
        interpretation_status=interpretation_status,  # type: ignore[arg-type]
    )


def metadata_envelope_from_row(
    row: dict[str, Any],
    *,
    sequence_index: int,
) -> MetadataRecordEnvelope:
    marker = str(row.get("arm_name", ""))
    payload = {
        key: value
        for key, value in row.items()
        if key not in {"arm_name", "category", "dispatched", "verified", "evidence", "error"}
    }
    return metadata_envelope(
        record_type=record_type_for_marker(marker),
        payload=payload,
        sequence_index=sequence_index,
    )


def row_from_metadata_envelope(
    envelope: MetadataRecordEnvelope,
) -> dict[str, Any]:
    row = {
        "arm_name": marker_for_record_type(envelope.record_type),
        "category": "metadata",
        "dispatched": "na",
        "verified": "na",
        "evidence": "",
        "error": "",
    }
    row.update(envelope.payload)
    return row


def split_command_and_metadata_rows(
    live_rows: list[dict[str, Any]] | tuple[dict[str, Any], ...] | None,
) -> tuple[tuple[dict[str, Any], ...], tuple[MetadataRecordEnvelope, ...]]:
    if not live_rows:
        return (), ()
    command_rows: list[dict[str, Any]] = []
    metadata_rows: list[MetadataRecordEnvelope] = []
    for index, row in enumerate(live_rows):
        if is_metadata_row(row):
            metadata_rows.append(
                metadata_envelope_from_row(row, sequence_index=len(metadata_rows))
            )
            continue
        command_rows.append(dict(row))
    return tuple(command_rows), tuple(metadata_rows)


def metadata_rows_for_envelopes(
    envelopes: tuple[MetadataRecordEnvelope, ...] | list[MetadataRecordEnvelope],
) -> list[dict[str, Any]]:
    return [row_from_metadata_envelope(item) for item in envelopes]

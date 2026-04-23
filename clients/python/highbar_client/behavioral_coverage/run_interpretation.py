# SPDX-License-Identifier: GPL-2.0-only
"""Interpret typed live metadata and command evidence into bundle state."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from .bootstrap import (
    DEFAULT_LIVE_FIXTURE_CLASSES,
    OPTIONAL_LIVE_FIXTURE_CLASSES,
    all_live_fixture_classes,
    build_fixture_class_statuses,
    build_shared_fixture_instance,
    fixture_classes_for_command,
    is_transport_dependent_command,
    supported_transport_variants,
    transport_dependent_command_ids,
)
from .itertesting_types import (
    BootstrapReadinessAssessment,
    CallbackDiagnosticSnapshot,
    DecisionTraceEntry,
    FixtureProvisioningResult,
    FixtureStateTransition,
    LiveExecutionCapture,
    MapDataSourceDecision,
    MetadataRecordEnvelope,
    RunInterpretationResult,
    RunModeEvidencePolicy,
    RuntimeCapabilityProfile,
    RuntimePrerequisiteResolutionRecord,
    StandaloneBuildProbeOutcome,
    TransportAvailabilityDecision,
    TransportCandidate,
    TransportCompatibilityCheck,
    TransportLifecycleEvent,
    TransportProvisioningResult,
    TransportResolutionTrace,
    SupportedTransportVariant,
    InterpretationWarning,
)
from .live_failure_classification import default_live_fixture_profile
from .metadata_records import interpretation_rule_for_record_type


_FIXTURE_KEYWORDS: dict[str, tuple[str, ...]] = {
    "damaged_friendly": ("damaged", "repair"),
    "reclaim_target": ("reclaim",),
    "transport_unit": ("transport", "load", "unload"),
    "payload_unit": ("payload", "load", "unload"),
    "capturable_target": ("capture", "capturable"),
    "restore_target": ("restore",),
    "wreck_target": ("wreck", "resurrect"),
    "custom_target": ("custom",),
}
_UNUSABLE_FIXTURE_TOKENS = (
    "refresh_failed",
    "refresh failed",
    "stale",
    "destroyed",
    "out_of_range",
    "out of range",
    "consumed",
    "unusable",
)
_REFRESHED_FIXTURE_TOKENS = ("refreshed", "replacement", "replaced")
_MISSING_FIXTURE_TOKENS = (
    "live fixture dependency unavailable",
    "fixture missing",
    "missing fixture",
    "not provisioned by the live bootstrap context",
)
_TRANSPORT_PREEXISTING_TOKENS = (
    "preexisting transport",
    "reused transport",
    "transport reuse",
)
_TRANSPORT_PROVISIONED_TOKENS = (
    "transport fixture prepared",
    "natural transport",
    "transport provisioned",
)
_TRANSPORT_REPLACED_TOKENS = ("transport replaced", "replacement transport")
_TRANSPORT_FALLBACK_TOKENS = (
    "fallback transport",
    "fallback spawn",
    "cheat-assisted transport",
)
_TRANSPORT_PAYLOAD_INCOMPATIBLE_TOKENS = (
    "payload incompatible",
    "transport-payload incompatible",
    "transport payload incompatible",
)
_BOOTSTRAP_BLOCKED_BASELINE_FIXTURE_CLASSES = frozenset(
    {"commander", "movement_lane", "resource_baseline"}
)


def utc_now_iso() -> str:
    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def default_run_mode_evidence_policy(
    *,
    setup_mode: str,
    has_live_command_rows: bool,
) -> RunModeEvidencePolicy:
    if not has_live_command_rows:
        baseline = (
            tuple(sorted(all_live_fixture_classes()))
            if setup_mode == "cheat-assisted"
            else DEFAULT_LIVE_FIXTURE_CLASSES
        )
        return RunModeEvidencePolicy(
            setup_mode=setup_mode,  # type: ignore[arg-type]
            baseline_guaranteed_fixtures=baseline,
            transport_default_status="mode_qualified_non_live",
            counts_as_live_evidence=False,
            policy_reason=(
                "run completed without live command evidence; baseline fixture and "
                "transport claims remain mode-qualified non-live"
            ),
        )
    baseline = (
        tuple(sorted(all_live_fixture_classes()))
        if setup_mode == "cheat-assisted"
        else DEFAULT_LIVE_FIXTURE_CLASSES
    )
    return RunModeEvidencePolicy(
        setup_mode=setup_mode,  # type: ignore[arg-type]
        baseline_guaranteed_fixtures=baseline,
        transport_default_status="unknown",
        counts_as_live_evidence=True,
        policy_reason=(
            "live command evidence is present; baseline guarantees may seed interpretation "
            "but final claims require explicit evidence transitions"
        ),
    )


def _append_transition(
    history: dict[str, list[FixtureStateTransition]],
    *,
    fixture_class: str,
    state: str,
    observed_source: str,
    detail: str,
    affected_commands: tuple[str, ...],
    recorded_at: str,
) -> None:
    history.setdefault(fixture_class, []).append(
        FixtureStateTransition(
            fixture_class=fixture_class,
            state=state,  # type: ignore[arg-type]
            observed_source=observed_source,
            detail=detail,
            affected_commands=affected_commands,
            recorded_at=recorded_at,
        )
    )


def _precise_missing_fixture_classes(detail: str) -> tuple[str, ...]:
    marker = "live fixture dependency unavailable for this arm ("
    start = detail.find(marker)
    if start == -1:
        return ()
    start += len(marker)
    end = detail.find(")", start)
    if end == -1:
        return ()
    return tuple(
        token.strip()
        for token in detail[start:end].split(",")
        if token.strip()
    )


def _transport_variant_payload_rules() -> tuple[SupportedTransportVariant, ...]:
    return tuple(sorted(supported_transport_variants(), key=lambda item: item.priority))


def _transport_variant_id_from_detail(detail: str) -> str | None:
    lowered = detail.lower()
    for variant in supported_transport_variants():
        if variant.variant_id in lowered or variant.def_name in lowered:
            return variant.variant_id
    return None


def _transport_command_scope(
    command_rows: tuple[dict[str, Any], ...],
) -> tuple[str, ...]:
    commands = {
        _command_id(row.get("arm_name", ""))
        for row in command_rows
        if is_transport_dependent_command(_command_id(row.get("arm_name", "")))
    }
    return tuple(sorted(commands)) or transport_dependent_command_ids()


def _transport_status_from_rows(
    command_rows: tuple[dict[str, Any], ...],
) -> tuple[str, str, str | None]:
    detail = " ".join(
        str(part or "")
        for row in command_rows
        if is_transport_dependent_command(_command_id(row.get("arm_name", "")))
        for part in (
            row.get("evidence", ""),
            row.get("error", ""),
            row.get("fixture_status", ""),
        )
    ).lower()
    variant_id = _transport_variant_id_from_detail(detail)
    if any(token in detail for token in _TRANSPORT_FALLBACK_TOKENS):
        return (
            "fallback_provisioned",
            "transport coverage required explicit fallback provisioning",
            variant_id,
        )
    if any(token in detail for token in _TRANSPORT_REPLACED_TOKENS):
        return (
            "replaced",
            "transport coverage replaced an earlier unusable candidate",
            variant_id,
        )
    if any(token in detail for token in _REFRESHED_FIXTURE_TOKENS):
        return (
            "refreshed",
            "transport coverage was refreshed after a stale or lost candidate",
            variant_id,
        )
    if any(token in detail for token in _TRANSPORT_PREEXISTING_TOKENS):
        return (
            "preexisting",
            "transport coverage reused a preexisting live candidate",
            variant_id,
        )
    if any(token in detail for token in _UNUSABLE_FIXTURE_TOKENS) or any(
        token in detail for token in _TRANSPORT_PAYLOAD_INCOMPATIBLE_TOKENS
    ):
        return (
            "unusable",
            "transport coverage became unusable for one or more dependent commands",
            variant_id,
        )
    if any(token in detail for token in _MISSING_FIXTURE_TOKENS):
        return (
            "missing",
            "transport coverage was not available when dependent commands were attempted",
            variant_id,
        )
    if any(token in detail for token in _TRANSPORT_PROVISIONED_TOKENS):
        return (
            "provisioned",
            "transport coverage was provisioned during the live workflow",
            variant_id,
        )
    if any(
        row.get("arm_name", "") in {
            "load_units",
            "load_units_area",
            "load_onto",
            "unload_unit",
            "unload_units_area",
        }
        and row.get("dispatched") == "true"
        for row in command_rows
    ):
        return (
            "provisioned",
            "transport coverage was available because transport commands reached live evaluation",
            variant_id,
        )
    return (
        "missing",
        "transport coverage was not exercised or recorded in the run bundle",
        variant_id,
    )


def _transport_candidates_and_events(
    *,
    run_id: str,
    completed_at: str,
    status: str,
    status_reason: str,
    variant_id: str | None,
    command_rows: tuple[dict[str, Any], ...],
) -> tuple[tuple[TransportCandidate, ...], tuple[TransportLifecycleEvent, ...], str | None]:
    command_scope = _transport_command_scope(command_rows)
    chosen_variant_id = variant_id or _transport_variant_payload_rules()[0].variant_id
    if status == "missing":
        return (
            (),
            (
                TransportLifecycleEvent(
                    event_id=f"{run_id}:transport:provision-failed",
                    event_type="provision_failed",
                    candidate_id=None,
                    command_scope=command_scope,
                    reason=status_reason,
                    recorded_at=completed_at,
                ),
            ),
            None,
        )
    readiness_state = "ready"
    payload_compatibility = "compatible"
    provenance = "preexisting"
    event_type = "discovered"
    if status == "provisioned":
        provenance = "naturally_provisioned"
        event_type = "provision_succeeded"
    elif status == "refreshed":
        provenance = "refreshed"
        event_type = "refreshed"
    elif status == "replaced":
        provenance = "replaced"
        event_type = "replaced"
    elif status == "fallback_provisioned":
        provenance = "fallback_provisioned"
        event_type = "fallback_used"
    elif status == "unusable":
        readiness_state = "refresh_failed"
        payload_compatibility = "incompatible"
        event_type = "compatibility_failed"
    candidate = TransportCandidate(
        candidate_id=f"{run_id}:transport:01",
        variant_id=chosen_variant_id,
        unit_id=1,
        provenance=provenance,  # type: ignore[arg-type]
        readiness_state=readiness_state,  # type: ignore[arg-type]
        payload_compatibility=payload_compatibility,  # type: ignore[arg-type]
        discovered_at=completed_at,
        supersedes_candidate_id=(
            f"{run_id}:transport:00" if status == "replaced" else None
        ),
    )
    events: list[TransportLifecycleEvent] = []
    if status in {"provisioned", "fallback_provisioned"}:
        events.append(
            TransportLifecycleEvent(
                event_id=f"{run_id}:transport:provision-started",
                event_type="provision_started",
                candidate_id=None,
                command_scope=command_scope,
                reason="transport provisioning started before dependent command evaluation",
                recorded_at=completed_at,
            )
        )
    events.append(
        TransportLifecycleEvent(
            event_id=f"{run_id}:transport:{event_type}",
            event_type=event_type,  # type: ignore[arg-type]
            candidate_id=candidate.candidate_id,
            command_scope=command_scope,
            reason=status_reason,
            recorded_at=completed_at,
        )
    )
    if status == "replaced":
        events.insert(
            0,
            TransportLifecycleEvent(
                event_id=f"{run_id}:transport:lost",
                event_type="lost",
                candidate_id=f"{run_id}:transport:00",
                command_scope=command_scope,
                reason="earlier transport candidate was lost before a replacement was selected",
                recorded_at=completed_at,
            )
        )
    return (candidate,), tuple(events), candidate.candidate_id


def _transport_compatibility_checks(
    *,
    command_rows: tuple[dict[str, Any], ...],
    completed_at: str,
    candidate_id: str | None,
    status: str,
) -> tuple[TransportCompatibilityCheck, ...]:
    checks: list[TransportCompatibilityCheck] = []
    for row in command_rows:
        command_id = _command_id(row.get("arm_name", ""))
        if not is_transport_dependent_command(command_id):
            continue
        detail = " ".join(
            str(part or "")
            for part in (row.get("evidence", ""), row.get("error", ""))
        ).lower()
        result = "compatible"
        blocking_reason = None
        if any(token in detail for token in _TRANSPORT_PAYLOAD_INCOMPATIBLE_TOKENS):
            result = "payload_incompatible"
            blocking_reason = "selected transport could not safely carry the pending payload"
        elif status == "missing":
            result = "candidate_missing"
            blocking_reason = "no usable transport candidate was available for this command"
        elif status == "unusable":
            result = "candidate_unusable"
            blocking_reason = (
                "the transport candidate became unusable before this command could be evaluated"
            )
        checks.append(
            TransportCompatibilityCheck(
                command_id=command_id,
                candidate_id=candidate_id,
                payload_unit_id=(
                    1
                    if "payload" in detail or row.get("arm_name", "").startswith("load_")
                    else None
                ),
                result=result,  # type: ignore[arg-type]
                blocking_reason=blocking_reason,
                checked_at=completed_at,
            )
        )
    return tuple(checks)


def _transport_resolution_trace(
    command_rows: tuple[dict[str, Any], ...],
) -> tuple[TransportResolutionTrace, ...]:
    detail = " ".join(
        str(part or "")
        for row in command_rows
        if is_transport_dependent_command(_command_id(row.get("arm_name", "")))
        for part in (row.get("evidence", ""), row.get("error", ""), row.get("fixture_status", ""))
    ).lower()
    traces: list[TransportResolutionTrace] = []
    for variant in _transport_variant_payload_rules():
        variant_seen = variant.variant_id in detail or variant.def_name in detail
        traces.append(
            TransportResolutionTrace(
                variant_id=variant.variant_id,
                callback_path=f"InvokeCallback/{variant.def_name}",
                resolved_def_id=None,
                resolution_status="resolved" if variant_seen else "missing",
                reason=(
                    f"{variant.def_name} appeared in live transport evidence"
                    if variant_seen
                    else "live bundle did not record runtime def resolution for this variant"
                ),
            )
        )
    return tuple(traces)


def transport_provisioning_for_capture(
    *,
    run_id: str,
    capture: LiveExecutionCapture,
    completed_at: str,
) -> TransportProvisioningResult:
    status, reason, variant_id = _transport_status_from_rows(capture.command_rows)
    candidates, lifecycle_events, active_candidate_id = _transport_candidates_and_events(
        run_id=run_id,
        completed_at=completed_at,
        status=status,
        status_reason=reason,
        variant_id=variant_id,
        command_rows=capture.command_rows,
    )
    compatibility_checks = _transport_compatibility_checks(
        command_rows=capture.command_rows,
        completed_at=completed_at,
        candidate_id=active_candidate_id,
        status=status,
    )
    affected_command_ids = tuple(
        sorted(
            check.command_id
            for check in compatibility_checks
            if check.result != "compatible"
        )
    )
    if status in {"missing", "unusable"} and not affected_command_ids:
        affected_command_ids = _transport_command_scope(capture.command_rows)
    return TransportProvisioningResult(
        run_id=run_id,
        supported_variants=_transport_variant_payload_rules(),
        active_candidate_id=active_candidate_id,
        candidates=candidates,
        lifecycle_events=lifecycle_events,
        compatibility_checks=compatibility_checks,
        resolution_trace=_transport_resolution_trace(capture.command_rows),
        status=status,  # type: ignore[arg-type]
        affected_command_ids=affected_command_ids,
        completed_at=completed_at,
    )


def _shared_fixture_instances_for_run(
    *,
    class_statuses,
    completed_at: str,
) -> tuple[tuple[Any, ...], dict[str, tuple[str, ...]]]:
    instances: list[Any] = []
    for status in class_statuses:
        if status.status == "provisioned":
            instance_id = f"{status.fixture_class}-instance-01"
            instances.append(
                build_shared_fixture_instance(
                    fixture_class=status.fixture_class,
                    instance_id=instance_id,
                    backing_id=f"{status.fixture_class}-backing-01",
                    last_ready_at=completed_at,
                )
            )
        elif status.status == "refreshed":
            previous_id = f"{status.fixture_class}-instance-00"
            instance_id = f"{status.fixture_class}-instance-01"
            instances.append(
                build_shared_fixture_instance(
                    fixture_class=status.fixture_class,
                    instance_id=previous_id,
                    backing_id=f"{status.fixture_class}-backing-00",
                    usability_state="stale",
                    refresh_count=0,
                    last_ready_at=None,
                )
            )
            instances.append(
                build_shared_fixture_instance(
                    fixture_class=status.fixture_class,
                    instance_id=instance_id,
                    backing_id=f"{status.fixture_class}-backing-01",
                    usability_state="ready",
                    refresh_count=1,
                    last_ready_at=completed_at,
                    replacement_of=previous_id,
                )
            )
        elif status.status == "unusable":
            instances.append(
                build_shared_fixture_instance(
                    fixture_class=status.fixture_class,
                    instance_id=f"{status.fixture_class}-instance-00",
                    backing_id=f"{status.fixture_class}-backing-00",
                    usability_state="refresh_failed",
                    refresh_count=0,
                    last_ready_at=None,
                )
            )
    if not instances:
        return (), {}
    ready_map = {
        status.fixture_class: tuple(
            instance.instance_id
            for instance in instances
            if instance.fixture_class == status.fixture_class
            and instance.usability_state == "ready"
        )
        for status in class_statuses
    }
    return tuple(instances), ready_map


def _command_id(arm_name: str) -> str:
    return f"cmd-{arm_name.replace('_', '-')}"


def _records_of_type(
    metadata_records: tuple[MetadataRecordEnvelope, ...],
    record_type: str,
) -> tuple[MetadataRecordEnvelope, ...]:
    return tuple(item for item in metadata_records if item.record_type == record_type)


def _interpret_metadata(
    *,
    run_id: str,
    metadata_records: tuple[MetadataRecordEnvelope, ...],
    command_rows: tuple[dict[str, Any], ...],
) -> tuple[
    BootstrapReadinessAssessment,
    RuntimeCapabilityProfile,
    tuple[CallbackDiagnosticSnapshot, ...],
    tuple[RuntimePrerequisiteResolutionRecord, ...],
    tuple[MapDataSourceDecision, ...],
    StandaloneBuildProbeOutcome | None,
    tuple[InterpretationWarning, ...],
    tuple[DecisionTraceEntry, ...],
]:
    recorded_at = utc_now_iso()
    warnings: list[InterpretationWarning] = []
    trace: list[DecisionTraceEntry] = []
    for envelope in metadata_records:
        rule = interpretation_rule_for_record_type(envelope.record_type)
        missing_fields = ()
        if rule is not None:
            missing_fields = tuple(
                field
                for field in rule.required_fields
                if envelope.payload.get(field) is None
            )
        if rule is None:
            warnings.append(
                InterpretationWarning(
                    warning_id=f"{run_id}:{envelope.record_type}:{envelope.sequence_index}",
                    record_type=envelope.record_type,
                    severity="blocking_warning",
                    message=(
                        f"metadata record `{envelope.record_type}` was preserved without "
                        "an interpretation rule"
                    ),
                    blocks_full_interpretation=True,
                    recorded_at=envelope.recorded_at or recorded_at,
                )
            )
            continue
        if missing_fields:
            blocks = rule.fallback_behavior == "preserve_and_block"
            warnings.append(
                InterpretationWarning(
                    warning_id=f"{run_id}:{envelope.record_type}:{envelope.sequence_index}",
                    record_type=envelope.record_type,
                    severity="blocking_warning" if blocks else "warning",
                    message=(
                        rule.warning_template
                        or f"{envelope.record_type} metadata is missing required fields"
                    )
                    + f": {', '.join(missing_fields)}",
                    blocks_full_interpretation=blocks,
                    recorded_at=envelope.recorded_at or recorded_at,
                )
            )
        trace.append(
            DecisionTraceEntry(
                decision_id=f"{run_id}:{envelope.record_type}:{envelope.sequence_index}",
                concern=rule.consumer,
                source_layer=envelope.source_layer,
                record_type=envelope.record_type,
                rule_owner=rule.owner_module,
                detail=f"metadata record interpreted for {rule.consumer}",
            )
        )

    bootstrap_records = _records_of_type(metadata_records, "bootstrap_readiness")
    if bootstrap_records:
        payload = bootstrap_records[-1].payload
        bootstrap = BootstrapReadinessAssessment(
            run_id=run_id,
            readiness_status=payload.get("readiness_status", "unknown"),
            readiness_path=payload.get("readiness_path", "unavailable"),
            first_required_step=payload.get("first_required_step", "armmex"),
            economy_summary=payload.get("economy_summary", "unknown"),
            reason=payload.get("reason", "bootstrap readiness metadata recorded"),
            recorded_at=payload.get("recorded_at", recorded_at),
        )
    elif not command_rows:
        bootstrap = BootstrapReadinessAssessment(
            run_id=run_id,
            readiness_status="unknown",
            readiness_path="unavailable",
            first_required_step="armmex",
            economy_summary="unknown",
            reason="synthetic run without live bootstrap evidence",
            recorded_at=recorded_at,
        )
    else:
        detail = " ".join(str(row.get("evidence", "") or "") for row in command_rows)
        if "resource_starved" in detail:
            bootstrap = BootstrapReadinessAssessment(
                run_id=run_id,
                readiness_status="resource_starved",
                readiness_path="unavailable",
                first_required_step="armmex",
                economy_summary="unknown",
                reason=detail.strip(),
                recorded_at=recorded_at,
            )
        else:
            bootstrap = BootstrapReadinessAssessment(
                run_id=run_id,
                readiness_status="unknown",
                readiness_path="unavailable",
                first_required_step="armmex",
                economy_summary="unknown",
                reason="live rows did not include explicit bootstrap readiness metadata",
                recorded_at=recorded_at,
            )

    capability_records = _records_of_type(metadata_records, "runtime_capability_profile")
    if capability_records:
        payload = capability_records[-1].payload
        runtime_capability = RuntimeCapabilityProfile(
            profile_id=payload.get("profile_id", "runtime-capability-profile"),
            supported_callbacks=tuple(payload.get("supported_callbacks", ())),
            supported_scopes=tuple(payload.get("supported_scopes", ())),
            unsupported_callback_groups=tuple(
                payload.get("unsupported_callback_groups", ())
            ),
            map_data_source_status=payload.get("map_data_source_status", "missing"),
            notes=payload.get("notes", ""),
            recorded_at=payload.get("recorded_at", recorded_at),
        )
    elif not command_rows:
        runtime_capability = RuntimeCapabilityProfile(
            profile_id="runtime-capability-synthetic",
            supported_callbacks=(),
            supported_scopes=(),
            unsupported_callback_groups=(),
            map_data_source_status="missing",
            notes="synthetic run without live capability metadata",
            recorded_at=recorded_at,
        )
    else:
        has_prerequisite_lookup = bool(
            _records_of_type(metadata_records, "prerequisite_resolution")
        )
        runtime_capability = RuntimeCapabilityProfile(
            profile_id="runtime-capability-implicit",
            supported_callbacks=(40, 47) if has_prerequisite_lookup else (),
            supported_scopes=(
                ("unit_def_lookup", "unit_def_name") if has_prerequisite_lookup else ()
            ),
            unsupported_callback_groups=(),
            map_data_source_status="missing",
            notes="live rows did not include runtime capability metadata",
            recorded_at=recorded_at,
        )

    callback_records = _records_of_type(metadata_records, "callback_diagnostic")
    if callback_records:
        callback_diagnostics = tuple(
            CallbackDiagnosticSnapshot(
                snapshot_id=item.payload.get("snapshot_id", f"callback-{index:02d}"),
                capture_stage=item.payload.get("capture_stage", "bootstrap_start"),
                availability_status=item.payload.get("availability_status", "missing"),
                source=item.payload.get("source", "not_available"),
                diagnostic_scope=tuple(item.payload.get("diagnostic_scope", ())),
                summary=item.payload.get("summary", ""),
                captured_at=item.payload.get("captured_at", recorded_at),
            )
            for index, item in enumerate(callback_records, start=1)
        )
    elif not command_rows:
        callback_diagnostics = (
            CallbackDiagnosticSnapshot(
                snapshot_id="callback-01",
                capture_stage="bootstrap_start",
                availability_status="missing",
                source="not_available",
                diagnostic_scope=("commander_def", "build_options", "economy"),
                summary="synthetic run without live callback diagnostics",
                captured_at=recorded_at,
            ),
        )
    else:
        callback_diagnostics = (
            CallbackDiagnosticSnapshot(
                snapshot_id="callback-01",
                capture_stage="bootstrap_failure",
                availability_status="missing",
                source="not_available",
                diagnostic_scope=("commander_def", "build_options", "economy"),
                summary="live rows did not include callback diagnostic metadata",
                captured_at=recorded_at,
            ),
        )

    prerequisite_resolution = tuple(
        RuntimePrerequisiteResolutionRecord(
            prerequisite_name=item.payload.get("prerequisite_name", ""),
            consumer=item.payload.get("consumer", "live_closeout"),
            callback_path=item.payload.get("callback_path", ""),
            resolved_def_id=item.payload.get("resolved_def_id"),
            resolution_status=item.payload.get("resolution_status", "missing"),
            reason=item.payload.get("reason", ""),
            recorded_at=item.payload.get("recorded_at", recorded_at),
        )
        for item in _records_of_type(metadata_records, "prerequisite_resolution")
    )

    map_source_records = _records_of_type(metadata_records, "map_source_decision")
    if map_source_records:
        map_source_decisions = tuple(
            MapDataSourceDecision(
                consumer=item.payload.get("consumer", "live_closeout"),
                selected_source=item.payload.get("selected_source", "missing"),
                metal_spot_count=item.payload.get("metal_spot_count", 0),
                reason=item.payload.get("reason", ""),
                recorded_at=item.payload.get("recorded_at", recorded_at),
            )
            for item in map_source_records
        )
    else:
        map_source_decisions = (
            MapDataSourceDecision(
                consumer="live_closeout",
                selected_source="missing",
                metal_spot_count=0,
                reason=(
                    "synthetic run without live map-source metadata"
                    if not command_rows
                    else "live rows did not include map-source metadata"
                ),
                recorded_at=recorded_at,
            ),
        )

    standalone_records = _records_of_type(metadata_records, "standalone_build_probe")
    if standalone_records:
        payload = standalone_records[-1].payload
        standalone_probe = StandaloneBuildProbeOutcome(
            probe_id=payload.get("probe_id", "behavioral-build"),
            prerequisite_name=payload.get("prerequisite_name", "armmex"),
            resolution_record=RuntimePrerequisiteResolutionRecord(
                prerequisite_name=payload.get("prerequisite_name", "armmex"),
                consumer="behavioral_build_probe",
                callback_path=payload.get("callback_path", ""),
                resolved_def_id=payload.get("resolved_def_id"),
                resolution_status=payload.get("resolution_status", "missing"),
                reason=payload.get("resolution_reason", ""),
                recorded_at=payload.get("recorded_at", recorded_at),
            ),
            map_source_decision=(
                MapDataSourceDecision(
                    consumer=payload.get("map_source_consumer", "behavioral_build_probe"),
                    selected_source=payload.get("map_source_selected_source", "missing"),
                    metal_spot_count=payload.get("map_source_metal_spot_count", 0),
                    reason=payload.get("map_source_reason", ""),
                    recorded_at=payload.get(
                        "map_source_recorded_at",
                        payload.get("recorded_at", recorded_at),
                    ),
                )
                if (
                    payload.get("map_source_selected_source") is not None
                    or payload.get("map_source_reason") is not None
                )
                else None
            ),
            dispatch_result=payload.get("dispatch_result", "blocked"),
            capability_limit_summary=payload.get("capability_limit_summary"),
            failure_reason=payload.get("failure_reason"),
            completed_at=payload.get("completed_at", recorded_at),
        )
    else:
        standalone_probe = None

    return (
        bootstrap,
        runtime_capability,
        callback_diagnostics,
        prerequisite_resolution,
        map_source_decisions,
        standalone_probe,
        tuple(warnings),
        tuple(trace),
    )


def _build_fixture_transition_history(
    *,
    capture: LiveExecutionCapture,
    policy: RunModeEvidencePolicy,
    bootstrap_readiness: BootstrapReadinessAssessment,
) -> tuple[FixtureStateTransition, ...]:
    recorded_at = capture.collected_at or utc_now_iso()
    history: dict[str, list[FixtureStateTransition]] = {}
    baseline_state = (
        "preexisting"
        if policy.counts_as_live_evidence
        else "mode_qualified_non_live"
    )
    for fixture_class in sorted(policy.baseline_guaranteed_fixtures):
        _append_transition(
            history,
            fixture_class=fixture_class,
            state=baseline_state,
            observed_source="run_mode_policy",
            detail=policy.policy_reason,
            affected_commands=(),
            recorded_at=recorded_at,
        )
    if (
        bootstrap_readiness.readiness_status not in {"natural_ready", "seeded_ready"}
        and capture.metadata_records
    ):
        for fixture_class in sorted(
            set(all_live_fixture_classes()).difference(
                _BOOTSTRAP_BLOCKED_BASELINE_FIXTURE_CLASSES
            )
        ):
            _append_transition(
                history,
                fixture_class=fixture_class,
                state="missing",
                observed_source="live_execution",
                detail=(
                    "live bootstrap blocked before fixture provisioning could establish "
                    "this dependency"
                ),
                affected_commands=tuple(
                    fixture_classes_for_command(command_id)
                    for command_id in ()
                ),
                recorded_at=bootstrap_readiness.recorded_at,
            )
    for row in capture.command_rows:
        command_id = _command_id(row.get("arm_name", ""))
        detail = " ".join(
            str(part or "")
            for part in (
                row.get("evidence", ""),
                row.get("error", ""),
                row.get("fixture_status", ""),
            )
        ).lower()
        required_fixture_classes = fixture_classes_for_command(command_id)
        row_recorded_at = str(row.get("recorded_at") or recorded_at)
        if row.get("error") == "precondition_unmet" and any(
            token in detail for token in _MISSING_FIXTURE_TOKENS
        ):
            precise_missing = _precise_missing_fixture_classes(detail)
            missing_fixture_classes = precise_missing or required_fixture_classes
            for fixture_class in missing_fixture_classes:
                _append_transition(
                    history,
                    fixture_class=fixture_class,
                    state="missing",
                    observed_source="live_execution",
                    detail=(
                        f"{fixture_class} was still unavailable when {command_id} was attempted"
                    ),
                    affected_commands=(command_id,),
                    recorded_at=row_recorded_at,
                )
            for fixture_class in required_fixture_classes:
                if fixture_class in missing_fixture_classes:
                    continue
                _append_transition(
                    history,
                    fixture_class=fixture_class,
                    state="provisioned",
                    observed_source="live_execution",
                    detail=(
                        f"{fixture_class} remained available while {command_id} was blocked on another prerequisite"
                    ),
                    affected_commands=(command_id,),
                    recorded_at=row_recorded_at,
                )
            continue
        if row.get("dispatched") == "true" or row.get("verified") == "true":
            for fixture_class in required_fixture_classes:
                _append_transition(
                    history,
                    fixture_class=fixture_class,
                    state="provisioned",
                    observed_source="live_execution",
                    detail=f"{command_id} reached live evaluation with the fixture available",
                    affected_commands=(command_id,),
                    recorded_at=row_recorded_at,
                )
        for fixture_class, keywords in _FIXTURE_KEYWORDS.items():
            if not any(keyword in detail for keyword in keywords):
                continue
            state = "provisioned"
            reason = f"{fixture_class} was provisioned from live setup evidence"
            if any(token in detail for token in _UNUSABLE_FIXTURE_TOKENS):
                state = "unusable"
                reason = (
                    f"{fixture_class} became unusable before dependent commands could run"
                )
            elif any(token in detail for token in _REFRESHED_FIXTURE_TOKENS):
                state = "refreshed"
                reason = f"{fixture_class} was refreshed after a stale or consumed instance"
            _append_transition(
                history,
                fixture_class=fixture_class,
                state=state,
                observed_source="live_execution",
                detail=reason,
                affected_commands=(command_id,),
                recorded_at=row_recorded_at,
            )
    if not history:
        for fixture_class in sorted(all_live_fixture_classes()):
            state = (
                "mode_qualified_non_live"
                if not policy.counts_as_live_evidence
                else "missing"
            )
            detail = (
                policy.policy_reason
                if not policy.counts_as_live_evidence
                else "no live fixture evidence was recorded for this class"
            )
            _append_transition(
                history,
                fixture_class=fixture_class,
                state=state,
                observed_source="run_mode_policy",
                detail=detail,
                affected_commands=(),
                recorded_at=recorded_at,
            )
    return tuple(
        transition
        for fixture_class in sorted(history)
        for transition in history[fixture_class]
    )


def fixture_provisioning_for_transitions(
    *,
    run_id: str,
    fixture_transitions: tuple[FixtureStateTransition, ...],
    completed_at: str,
) -> FixtureProvisioningResult:
    latest_by_class: dict[str, FixtureStateTransition] = {}
    for transition in fixture_transitions:
        latest_by_class[transition.fixture_class] = transition
    provisioned: list[str] = []
    missing: list[str] = []
    refreshed: list[str] = []
    unusable: list[str] = []
    reasons = {
        fixture_class: transition.detail
        for fixture_class, transition in latest_by_class.items()
    }
    for fixture_class in sorted(all_live_fixture_classes()):
        transition = latest_by_class.get(fixture_class)
        state = transition.state if transition is not None else "missing"
        if state in {"preexisting", "provisioned"}:
            provisioned.append(fixture_class)
        elif state in {"refreshed", "replaced"}:
            refreshed.append(fixture_class)
        elif state in {"unusable", "invalidated"}:
            unusable.append(fixture_class)
        elif state == "mode_qualified_non_live":
            if fixture_class in DEFAULT_LIVE_FIXTURE_CLASSES:
                provisioned.append(fixture_class)
            else:
                missing.append(fixture_class)
        else:
            missing.append(fixture_class)
    class_statuses = build_fixture_class_statuses(
        updated_at=completed_at,
        provisioned_fixture_classes=tuple(provisioned),
        missing_fixture_classes=tuple(missing),
        refreshed_fixture_classes=tuple(refreshed),
        unusable_fixture_classes=tuple(unusable),
        transition_reason_by_class=reasons,
        supported_command_ids=default_live_fixture_profile().supported_command_ids,
    )
    shared_fixture_instances, ready_ids_by_class = _shared_fixture_instances_for_run(
        class_statuses=class_statuses,
        completed_at=completed_at,
    )
    class_statuses = build_fixture_class_statuses(
        updated_at=completed_at,
        provisioned_fixture_classes=tuple(provisioned),
        missing_fixture_classes=tuple(missing),
        refreshed_fixture_classes=tuple(refreshed),
        unusable_fixture_classes=tuple(unusable),
        ready_instance_ids_by_class=ready_ids_by_class,
        transition_reason_by_class=reasons,
        supported_command_ids=default_live_fixture_profile().supported_command_ids,
    )
    affected_command_ids = tuple(
        sorted(
            {
                command_id
                for status in class_statuses
                for command_id in status.affected_command_ids
            }
        )
    )
    missing_fixture_classes = tuple(
        status.fixture_class
        for status in class_statuses
        if status.status in {"missing", "unusable"}
    )
    provisioned_fixture_classes = tuple(
        status.fixture_class
        for status in class_statuses
        if status.status in {"provisioned", "refreshed"}
    )
    return FixtureProvisioningResult(
        run_id=run_id,
        profile_id=default_live_fixture_profile().profile_id,
        provisioned_fixture_classes=provisioned_fixture_classes,
        missing_fixture_classes=missing_fixture_classes,
        affected_command_ids=affected_command_ids,
        completed_at=completed_at,
        class_statuses=class_statuses,
        shared_fixture_instances=shared_fixture_instances,
    )


def transport_decision_from_result(
    *,
    policy: RunModeEvidencePolicy,
    transport_provisioning: TransportProvisioningResult,
    fixture_transitions: tuple[FixtureStateTransition, ...],
) -> TransportAvailabilityDecision:
    transport_history = tuple(
        item for item in fixture_transitions if item.fixture_class == "transport_unit"
    )
    authoritative_transition = transport_history[-1] if transport_history else None
    status = transport_provisioning.status
    availability_status = "unknown"
    explicit_evidence = False
    reason = "transport evidence was not interpreted"
    if status in {"preexisting", "provisioned", "refreshed", "replaced", "fallback_provisioned"}:
        availability_status = "available"
        explicit_evidence = True
        reason = authoritative_transition.detail if authoritative_transition else "transport was explicitly available"
    elif status == "unusable":
        availability_status = "missing"
        explicit_evidence = True
        reason = authoritative_transition.detail if authoritative_transition else "transport became unusable"
    else:
        if policy.transport_default_status == "mode_qualified_non_live":
            availability_status = "mode_qualified_non_live"
            reason = policy.policy_reason
        elif transport_provisioning.compatibility_checks:
            availability_status = "unproven"
            reason = "transport-dependent commands were observed without explicit transport availability evidence"
        else:
            availability_status = "unknown"
            reason = "live run did not establish explicit transport evidence"
    return TransportAvailabilityDecision(
        availability_status=availability_status,  # type: ignore[arg-type]
        explicit_evidence=explicit_evidence,
        authoritative_transition=authoritative_transition,
        reason=reason,
        diagnostic_history=transport_history,
    )


def interpret_live_execution_capture(
    *,
    run_id: str,
    capture: LiveExecutionCapture,
) -> tuple[
    RunModeEvidencePolicy,
    RunInterpretationResult,
    FixtureProvisioningResult,
    TransportProvisioningResult,
]:
    completed_at = capture.collected_at or utc_now_iso()
    policy = default_run_mode_evidence_policy(
        setup_mode=capture.setup_mode,
        has_live_command_rows=bool(capture.command_rows),
    )
    (
        bootstrap_readiness,
        runtime_capability_profile,
        callback_diagnostics,
        prerequisite_resolution,
        map_source_decisions,
        standalone_probe,
        interpretation_warnings,
        metadata_trace,
    ) = _interpret_metadata(
        run_id=run_id,
        metadata_records=capture.metadata_records,
        command_rows=capture.command_rows,
    )
    fixture_transitions = _build_fixture_transition_history(
        capture=capture,
        policy=policy,
        bootstrap_readiness=bootstrap_readiness,
    )
    transport_provisioning = transport_provisioning_for_capture(
        run_id=run_id,
        capture=capture,
        completed_at=completed_at,
    )
    fixture_provisioning = fixture_provisioning_for_transitions(
        run_id=run_id,
        fixture_transitions=fixture_transitions,
        completed_at=completed_at,
    )
    transport_decision = transport_decision_from_result(
        policy=policy,
        transport_provisioning=transport_provisioning,
        fixture_transitions=fixture_transitions,
    )
    decision_trace = list(metadata_trace)
    for transition in fixture_transitions:
        decision_trace.append(
            DecisionTraceEntry(
                decision_id=f"{run_id}:fixture:{transition.fixture_class}",
                concern=f"fixture:{transition.fixture_class}",
                source_layer=transition.observed_source,
                record_type=None,
                rule_owner="highbar_client.behavioral_coverage.run_interpretation",
                detail=transition.detail,
            )
        )
    decision_trace.append(
        DecisionTraceEntry(
            decision_id=f"{run_id}:transport",
            concern="transport_availability",
            source_layer=(
                transport_decision.authoritative_transition.observed_source
                if transport_decision.authoritative_transition is not None
                else "run_mode_policy"
            ),
            record_type="transport_unit",
            rule_owner="highbar_client.behavioral_coverage.run_interpretation",
            detail=transport_decision.reason,
        )
    )
    result = RunInterpretationResult(
        bootstrap_readiness=bootstrap_readiness,
        runtime_capability_profile=runtime_capability_profile,
        prerequisite_resolution=prerequisite_resolution,
        map_source_decisions=map_source_decisions,
        standalone_build_probe_outcome=standalone_probe,
        callback_diagnostics=callback_diagnostics,
        fixture_transitions=fixture_transitions,
        transport_decision=transport_decision,
        interpretation_warnings=interpretation_warnings,
        decision_trace=tuple(decision_trace),
        fully_interpreted=not any(
            warning.blocks_full_interpretation for warning in interpretation_warnings
        ),
    )
    return policy, result, fixture_provisioning, transport_provisioning

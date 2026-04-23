# SPDX-License-Identifier: GPL-2.0-only
"""Filesystem-backed Itertesting campaign runner."""

from __future__ import annotations

import argparse
import json
import os
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .audit_inventory import ENGINE_PIN, GAMETYPE_PIN, repo_root
from .audit_runner import deterministic_repros_for_issues
from .bootstrap import (
    DEFAULT_LIVE_FIXTURE_CLASSES,
    OPTIONAL_LIVE_FIXTURE_CLASSES,
    build_fixture_class_statuses,
    build_shared_fixture_instance,
    fixture_classes_for_command,
    is_transport_dependent_command,
    supported_transport_variants,
    transport_dependent_command_ids,
)
from .itertesting_campaign import (
    apply_progress_metrics_to_run,
    decide_stop,
    final_status_for_decision,
    progress_snapshot_for_run,
    should_enable_cheat_escalation,
    with_stall_flag,
)
from .itertesting_report import render_run_report
from .itertesting_retry_policy import (
    configured_vs_effective_runs,
    disproportionate_intensity_warning,
    normalize_retry_policy,
)
from .itertesting_types import (
    ArmVerificationRule,
    BootstrapReadinessAssessment,
    CampaignStopDecision,
    CallbackDiagnosticSnapshot,
    ChannelHealthOutcome,
    CommandSemanticGate,
    CommandContractIssue,
    CommandVerificationRecord,
    ContractHealthDecision,
    DeterministicRepro,
    FailureCauseClassification,
    FixtureProvisioningResult,
    ImprovementEligibility,
    ImprovementAction,
    ImprovementInstruction,
    ItertestingCampaign,
    ItertestingRun,
    LiveFixtureProfile,
    RetryIntensityName,
    RunProgressSnapshot,
    RunComparison,
    RunSummary,
    RuntimePrerequisiteResolutionRecord,
    StandaloneBuildProbeOutcome,
    SupportedTransportVariant,
    TransportCandidate,
    TransportCompatibilityCheck,
    TransportLifecycleEvent,
    TransportProvisioningResult,
    TransportResolutionTrace,
    manifest_dict,
    run_from_dict,
)
from .live_failure_classification import (
    classify_failure_cause,
    default_live_fixture_profile,
    default_verification_rules,
    is_channel_failure_signal,
    normalize_contract_issues,
)
from .predicates import semantic_gate_metadata
from .registry import REGISTRY


_ALWAYS_NATURAL = {"attack", "build_unit", "self_destruct"}
_NATURAL_IMPROVABLE = {"fight", "move_unit", "patrol"}
_CHEAT_ONLY = {"give_me", "give_me_new_unit"}
_SAVED_INSTRUCTION_PREFIX = "Build on saved instruction r"


def utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def format_timestamp(instant: datetime) -> str:
    return instant.isoformat().replace("+00:00", "Z")


def default_reports_dir() -> Path:
    return repo_root() / "reports" / "itertesting"


def ensure_reports_dir(reports_dir: Path) -> Path:
    reports_dir.mkdir(parents=True, exist_ok=True)
    return reports_dir


def make_run_id(reports_dir: Path, now: datetime | None = None) -> str:
    instant = now or utc_now()
    base = instant.strftime("itertesting-%Y%m%dT%H%M%SZ")
    if not (reports_dir / base).exists():
        return base
    suffix = 2
    while (reports_dir / f"{base}-{suffix:02d}").exists():
        suffix += 1
    return f"{base}-{suffix:02d}"


def run_dir(reports_dir: Path, run_id: str) -> Path:
    return reports_dir / run_id


def instructions_dir(reports_dir: Path) -> Path:
    return reports_dir / "instructions"


def instruction_index_path(reports_dir: Path) -> Path:
    return instructions_dir(reports_dir) / "index.json"


def instruction_path(reports_dir: Path, command_id: str) -> Path:
    return instructions_dir(reports_dir) / f"{command_id}.json"


def _command_id(arm_name: str) -> str:
    return f"cmd-{arm_name.replace('_', '-')}"


def _action_id(command_id: str, sequence_index: int) -> str:
    return f"{command_id}-{sequence_index:02d}"


def load_instruction_store(reports_dir: Path) -> dict[str, ImprovementInstruction]:
    index_path = instruction_index_path(reports_dir)
    if not index_path.exists():
        return {}
    payload = json.loads(index_path.read_text(encoding="utf-8"))
    return {
        item["command_id"]: ImprovementInstruction(**item)
        for item in payload.get("instructions", ())
    }


def write_instruction_store(
    reports_dir: Path,
    instructions: dict[str, ImprovementInstruction],
) -> Path:
    base = instructions_dir(reports_dir)
    base.mkdir(parents=True, exist_ok=True)
    for command_id, instruction in sorted(instructions.items()):
        instruction_path(reports_dir, command_id).write_text(
            json.dumps(instruction.__dict__, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    index_path = instruction_index_path(reports_dir)
    index_path.write_text(
        json.dumps(
            {
                "instructions": [
                    instruction.__dict__
                    for _command_id, instruction in sorted(instructions.items())
                ]
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    return index_path


def _instruction_detail(
    prior_instruction: ImprovementInstruction | None,
    default_detail: str,
) -> str:
    if prior_instruction is None:
        return default_detail
    prior_detail = _instruction_body(prior_instruction.instruction)
    return (
        f"Build on saved instruction r{prior_instruction.revision}: "
        f"{prior_detail}"
    )


def _instruction_body(instruction: str) -> str:
    detail = instruction.strip()
    while detail.startswith(_SAVED_INSTRUCTION_PREFIX):
        _prefix, _separator, remainder = detail.partition(": ")
        if not remainder:
            break
        detail = remainder.strip()
    return detail


def _verification_rule_map() -> dict[str, ArmVerificationRule]:
    return {
        rule.command_id: rule
        for rule in default_verification_rules()
    }


def _fixture_profile() -> LiveFixtureProfile:
    return default_live_fixture_profile()


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


def _transport_variant_id_from_detail(detail: str) -> str | None:
    lowered = detail.lower()
    for variant in supported_transport_variants():
        if variant.variant_id in lowered or variant.def_name in lowered:
            return variant.variant_id
    return None


def _transport_variant_payload_rules() -> tuple[SupportedTransportVariant, ...]:
    return tuple(sorted(supported_transport_variants(), key=lambda item: item.priority))


def _transport_resolution_trace(
    live_rows: list[dict] | None,
) -> tuple[TransportResolutionTrace, ...]:
    detail = " ".join(
        str(part or "")
        for row in (live_rows or ())
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


def _transport_status_from_rows(
    live_rows: list[dict] | None,
) -> tuple[str, str, str | None]:
    detail = " ".join(
        str(part or "")
        for row in (live_rows or ())
        if is_transport_dependent_command(_command_id(row.get("arm_name", "")))
        for part in (row.get("evidence", ""), row.get("error", ""), row.get("fixture_status", ""))
    ).lower()
    variant_id = _transport_variant_id_from_detail(detail)
    if any(token in detail for token in _TRANSPORT_FALLBACK_TOKENS):
        return "fallback_provisioned", "transport coverage required explicit fallback provisioning", variant_id
    if any(token in detail for token in _TRANSPORT_REPLACED_TOKENS):
        return "replaced", "transport coverage replaced an earlier unusable candidate", variant_id
    if any(token in detail for token in _REFRESHED_FIXTURE_TOKENS):
        return "refreshed", "transport coverage was refreshed after a stale or lost candidate", variant_id
    if any(token in detail for token in _TRANSPORT_PREEXISTING_TOKENS):
        return "preexisting", "transport coverage reused a preexisting live candidate", variant_id
    if any(token in detail for token in _UNUSABLE_FIXTURE_TOKENS) or any(
        token in detail for token in _TRANSPORT_PAYLOAD_INCOMPATIBLE_TOKENS
    ):
        return "unusable", "transport coverage became unusable for one or more dependent commands", variant_id
    if any(token in detail for token in _MISSING_FIXTURE_TOKENS):
        return "missing", "transport coverage was not available when dependent commands were attempted", variant_id
    if any(token in detail for token in _TRANSPORT_PROVISIONED_TOKENS):
        return "provisioned", "transport coverage was provisioned during the live workflow", variant_id
    if any(
        row.get("arm_name", "") in {"load_units", "load_units_area", "load_onto", "unload_unit", "unload_units_area"}
        and row.get("dispatched") == "true"
        for row in (live_rows or ())
    ):
        return "provisioned", "transport coverage was available because transport commands reached live evaluation", variant_id
    return "missing", "transport coverage was not exercised or recorded in the run bundle", variant_id


def _transport_command_scope(
    live_rows: list[dict] | None,
) -> tuple[str, ...]:
    commands = {
        _command_id(row.get("arm_name", ""))
        for row in (live_rows or ())
        if is_transport_dependent_command(_command_id(row.get("arm_name", "")))
    }
    return tuple(sorted(commands)) or transport_dependent_command_ids()


def _transport_candidates_and_events(
    *,
    run_id: str,
    completed_at: str,
    status: str,
    status_reason: str,
    variant_id: str | None,
    live_rows: list[dict] | None,
) -> tuple[tuple[TransportCandidate, ...], tuple[TransportLifecycleEvent, ...], str | None]:
    command_scope = _transport_command_scope(live_rows)
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
            ),
        )
    return (candidate,), tuple(events), candidate.candidate_id


def _transport_compatibility_checks(
    *,
    live_rows: list[dict] | None,
    completed_at: str,
    candidate_id: str | None,
    status: str,
) -> tuple[TransportCompatibilityCheck, ...]:
    checks: list[TransportCompatibilityCheck] = []
    for row in live_rows or ():
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
            blocking_reason = "the transport candidate became unusable before this command could be evaluated"
        checks.append(
            TransportCompatibilityCheck(
                command_id=command_id,
                candidate_id=candidate_id,
                payload_unit_id=1 if "payload" in detail or row.get("arm_name", "").startswith("load_") else None,
                result=result,  # type: ignore[arg-type]
                blocking_reason=blocking_reason,
                checked_at=completed_at,
            )
        )
    return tuple(checks)


def _transport_provisioning_for_run(
    run_id: str,
    *,
    live_rows: list[dict] | None,
    completed_at: str,
) -> TransportProvisioningResult:
    status, reason, variant_id = _transport_status_from_rows(live_rows)
    candidates, lifecycle_events, active_candidate_id = _transport_candidates_and_events(
        run_id=run_id,
        completed_at=completed_at,
        status=status,
        status_reason=reason,
        variant_id=variant_id,
        live_rows=live_rows,
    )
    compatibility_checks = _transport_compatibility_checks(
        live_rows=live_rows,
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
        affected_command_ids = _transport_command_scope(live_rows)
    return TransportProvisioningResult(
        run_id=run_id,
        supported_variants=_transport_variant_payload_rules(),
        active_candidate_id=active_candidate_id,
        candidates=candidates,
        lifecycle_events=lifecycle_events,
        compatibility_checks=compatibility_checks,
        resolution_trace=_transport_resolution_trace(live_rows),
        status=status,  # type: ignore[arg-type]
        affected_command_ids=affected_command_ids,
        completed_at=completed_at,
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


def _infer_fixture_observations(
    live_rows: list[dict] | None,
    *,
    cheat_enabled: bool,
) -> tuple[set[str], set[str], set[str], set[str], dict[str, str]]:
    provisioned = set(DEFAULT_LIVE_FIXTURE_CLASSES)
    missing = set(OPTIONAL_LIVE_FIXTURE_CLASSES)
    refreshed: set[str] = set()
    unusable: set[str] = set()
    reasons: dict[str, str] = {
        fixture_class: "baseline fixture dependency was available for the run"
        for fixture_class in DEFAULT_LIVE_FIXTURE_CLASSES
    }

    if cheat_enabled:
        provisioned.update(OPTIONAL_LIVE_FIXTURE_CLASSES)
        missing.clear()
        for fixture_class in OPTIONAL_LIVE_FIXTURE_CLASSES:
            reasons[fixture_class] = "fixture was provisioned through cheat-assisted live setup"

    for row in live_rows or ():
        if row.get("category") != "channel_a_command":
            continue
        arm_name = row.get("arm_name", "")
        command_id = _command_id(arm_name)
        detail = " ".join(
            str(part or "")
            for part in (
                row.get("evidence", ""),
                row.get("error", ""),
                row.get("fixture_status", ""),
            )
        ).lower()
        required_fixture_classes = fixture_classes_for_command(command_id)
        if row.get("error") == "precondition_unmet" and any(
            token in detail for token in _MISSING_FIXTURE_TOKENS
        ):
            precise_missing = _precise_missing_fixture_classes(detail)
            missing_fixture_classes = precise_missing or required_fixture_classes
            for fixture_class in missing_fixture_classes:
                provisioned.discard(fixture_class)
                refreshed.discard(fixture_class)
                unusable.discard(fixture_class)
                missing.add(fixture_class)
                reasons[fixture_class] = (
                    f"{fixture_class} was still unavailable when {command_id} was attempted"
                )
            for fixture_class in required_fixture_classes:
                if fixture_class in missing_fixture_classes:
                    continue
                provisioned.add(fixture_class)
                missing.discard(fixture_class)
                reasons.setdefault(
                    fixture_class,
                    f"{fixture_class} remained available while {command_id} was blocked on another prerequisite",
                )
            continue
        if row.get("dispatched") == "true" or row.get("verified") == "true":
            for fixture_class in required_fixture_classes:
                provisioned.add(fixture_class)
                missing.discard(fixture_class)
                reasons.setdefault(
                    fixture_class,
                    f"{command_id} reached live evaluation with the fixture available",
                )
        for fixture_class, keywords in _FIXTURE_KEYWORDS.items():
            if any(keyword in detail for keyword in keywords):
                if any(token in detail for token in _UNUSABLE_FIXTURE_TOKENS):
                    provisioned.discard(fixture_class)
                    missing.discard(fixture_class)
                    refreshed.discard(fixture_class)
                    unusable.add(fixture_class)
                    reasons[fixture_class] = (
                        f"{fixture_class} became unusable before dependent commands could run"
                    )
                    continue
                provisioned.add(fixture_class)
                missing.discard(fixture_class)
                if any(token in detail for token in _REFRESHED_FIXTURE_TOKENS):
                    refreshed.add(fixture_class)
                    reasons[fixture_class] = (
                        f"{fixture_class} was refreshed after a stale or consumed instance"
                    )
                else:
                    reasons.setdefault(
                        fixture_class,
                        f"{fixture_class} was provisioned from live setup evidence",
                    )

    missing.difference_update(provisioned)
    missing.difference_update(unusable)
    provisioned.difference_update(unusable)
    return provisioned, missing, refreshed, unusable, reasons


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


def _fixture_provisioning_for_run(
    run_id: str,
    *,
    cheat_enabled: bool,
    live_rows: list[dict] | None,
) -> tuple[FixtureProvisioningResult, TransportProvisioningResult]:
    completed_at = format_timestamp(utc_now())
    transport_provisioning = _transport_provisioning_for_run(
        run_id,
        live_rows=live_rows,
        completed_at=completed_at,
    )
    provisioned, missing, refreshed, unusable, reasons = _infer_fixture_observations(
        live_rows,
        cheat_enabled=cheat_enabled,
    )
    if transport_provisioning.status in {"preexisting", "provisioned", "fallback_provisioned"}:
        provisioned.add("transport_unit")
        missing.discard("transport_unit")
        refreshed.discard("transport_unit")
        unusable.discard("transport_unit")
    elif transport_provisioning.status in {"refreshed", "replaced"}:
        provisioned.discard("transport_unit")
        missing.discard("transport_unit")
        refreshed.add("transport_unit")
        unusable.discard("transport_unit")
    elif transport_provisioning.status == "unusable":
        provisioned.discard("transport_unit")
        missing.discard("transport_unit")
        refreshed.discard("transport_unit")
        unusable.add("transport_unit")
    else:
        provisioned.discard("transport_unit")
        refreshed.discard("transport_unit")
        unusable.discard("transport_unit")
        missing.add("transport_unit")
    reasons["transport_unit"] = {
        "preexisting": "transport coverage reused a preexisting live transport candidate",
        "provisioned": "transport coverage was provisioned through the live workflow",
        "refreshed": "transport coverage was refreshed after the first candidate went stale",
        "replaced": "transport coverage replaced a lost transport candidate",
        "fallback_provisioned": "transport coverage required explicit fallback provisioning",
        "missing": "transport coverage remained unavailable for dependent commands",
        "unusable": "transport coverage became unusable before dependent commands completed",
    }[transport_provisioning.status]
    class_statuses = build_fixture_class_statuses(
        updated_at=completed_at,
        provisioned_fixture_classes=tuple(sorted(provisioned)),
        missing_fixture_classes=tuple(sorted(missing)),
        refreshed_fixture_classes=tuple(sorted(refreshed)),
        unusable_fixture_classes=tuple(sorted(unusable)),
        transition_reason_by_class=reasons,
        supported_command_ids=_fixture_profile().supported_command_ids,
    )
    shared_fixture_instances, ready_ids_by_class = _shared_fixture_instances_for_run(
        class_statuses=class_statuses,
        completed_at=completed_at,
    )
    class_statuses = build_fixture_class_statuses(
        updated_at=completed_at,
        provisioned_fixture_classes=tuple(sorted(provisioned)),
        missing_fixture_classes=tuple(sorted(missing)),
        refreshed_fixture_classes=tuple(sorted(refreshed)),
        unusable_fixture_classes=tuple(sorted(unusable)),
        ready_instance_ids_by_class=ready_ids_by_class,
        transition_reason_by_class=reasons,
        supported_command_ids=_fixture_profile().supported_command_ids,
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
    fixture_provisioning = FixtureProvisioningResult(
        run_id=run_id,
        profile_id=_fixture_profile().profile_id,
        provisioned_fixture_classes=provisioned_fixture_classes,
        missing_fixture_classes=missing_fixture_classes,
        affected_command_ids=affected_command_ids,
        completed_at=completed_at,
        class_statuses=class_statuses,
        shared_fixture_instances=shared_fixture_instances,
    )
    return fixture_provisioning, transport_provisioning


def _channel_health_for_run(
    run_id: str,
    records: tuple[CommandVerificationRecord, ...],
    live_rows: list[dict] | None,
) -> ChannelHealthOutcome:
    failure_index: int | None = None
    failure_signal = ""
    if live_rows:
        for index, row in enumerate(live_rows):
            detail = f"{row.get('evidence', '')} {row.get('error', '')}".strip()
            if is_channel_failure_signal(detail):
                failure_index = index
                failure_signal = detail
                break
    if failure_index is None:
        return ChannelHealthOutcome(
            run_id=run_id,
            status="healthy",
            first_failure_stage=None,
            failure_signal="",
            commands_attempted_before_failure=sum(
                1 for item in records if item.attempt_status != "blocked"
            ),
            recovery_attempted=False,
            finalized_at=format_timestamp(utc_now()),
        )
    return ChannelHealthOutcome(
        run_id=run_id,
        status="interrupted",
        first_failure_stage="dispatch",
        failure_signal=failure_signal,
        commands_attempted_before_failure=failure_index,
        recovery_attempted=True,
        finalized_at=format_timestamp(utc_now()),
    )


def _metadata_rows(
    live_rows: list[dict] | None,
    marker: str,
) -> tuple[dict[str, Any], ...]:
    if not live_rows:
        return ()
    return tuple(
        row
        for row in live_rows
        if str(row.get("arm_name", "")) == marker
    )


def _actual_live_rows(live_rows: list[dict] | None) -> list[dict] | None:
    if live_rows is None:
        return None
    return [
        row
        for row in live_rows
        if not str(row.get("arm_name", "")).startswith("__")
    ]


def _bootstrap_readiness_for_run(
    run_id: str,
    live_rows: list[dict] | None,
) -> BootstrapReadinessAssessment:
    recorded_at = format_timestamp(utc_now())
    metadata = _metadata_rows(live_rows, "__bootstrap_readiness__")
    if metadata:
        payload = metadata[-1]
        return BootstrapReadinessAssessment(
            run_id=run_id,
            readiness_status=payload.get("readiness_status", "unknown"),
            readiness_path=payload.get("readiness_path", "unavailable"),
            first_required_step=payload.get("first_required_step", "armmex"),
            economy_summary=payload.get("economy_summary", "unknown"),
            reason=payload.get("reason", "bootstrap readiness metadata recorded"),
            recorded_at=payload.get("recorded_at", recorded_at),
        )
    if not live_rows:
        return BootstrapReadinessAssessment(
            run_id=run_id,
            readiness_status="unknown",
            readiness_path="unavailable",
            first_required_step="armmex",
            economy_summary="unknown",
            reason="synthetic run without live bootstrap evidence",
            recorded_at=recorded_at,
        )
    detail = " ".join(
        str(row.get("evidence", "") or "")
        for row in _actual_live_rows(live_rows) or ()
    )
    if "resource_starved" in detail:
        return BootstrapReadinessAssessment(
            run_id=run_id,
            readiness_status="resource_starved",
            readiness_path="unavailable",
            first_required_step="armmex",
            economy_summary="unknown",
            reason=detail.strip(),
            recorded_at=recorded_at,
        )
    return BootstrapReadinessAssessment(
        run_id=run_id,
        readiness_status="unknown",
        readiness_path="unavailable",
        first_required_step="armmex",
        economy_summary="unknown",
        reason="live rows did not include explicit bootstrap readiness metadata",
        recorded_at=recorded_at,
    )


def _callback_diagnostics_for_run(
    live_rows: list[dict] | None,
) -> tuple[CallbackDiagnosticSnapshot, ...]:
    recorded_at = format_timestamp(utc_now())
    metadata = _metadata_rows(live_rows, "__callback_diagnostic__")
    if metadata:
        return tuple(
            CallbackDiagnosticSnapshot(
                snapshot_id=payload.get("snapshot_id", f"callback-{index:02d}"),
                capture_stage=payload.get("capture_stage", "bootstrap_start"),
                availability_status=payload.get("availability_status", "missing"),
                source=payload.get("source", "not_available"),
                diagnostic_scope=tuple(payload.get("diagnostic_scope", ())),
                summary=payload.get("summary", ""),
                captured_at=payload.get("captured_at", recorded_at),
            )
            for index, payload in enumerate(metadata, start=1)
        )
    if not live_rows:
        return (
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
    return (
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


def _prerequisite_resolution_for_run(
    live_rows: list[dict] | None,
) -> tuple[RuntimePrerequisiteResolutionRecord, ...]:
    recorded_at = format_timestamp(utc_now())
    metadata = _metadata_rows(live_rows, "__prerequisite_resolution__")
    return tuple(
        RuntimePrerequisiteResolutionRecord(
            prerequisite_name=payload.get("prerequisite_name", ""),
            consumer=payload.get("consumer", "live_closeout"),
            callback_path=payload.get("callback_path", ""),
            resolved_def_id=payload.get("resolved_def_id"),
            resolution_status=payload.get("resolution_status", "missing"),
            reason=payload.get("reason", ""),
            recorded_at=payload.get("recorded_at", recorded_at),
        )
        for payload in metadata
    )


def _standalone_build_probe_outcome_for_run(
    live_rows: list[dict] | None,
) -> StandaloneBuildProbeOutcome | None:
    metadata = _metadata_rows(live_rows, "__standalone_build_probe__")
    if not metadata:
        return None
    payload = metadata[-1]
    resolution = RuntimePrerequisiteResolutionRecord(
        prerequisite_name=payload.get("prerequisite_name", "armmex"),
        consumer="behavioral_build_probe",
        callback_path=payload.get("callback_path", ""),
        resolved_def_id=payload.get("resolved_def_id"),
        resolution_status=payload.get("resolution_status", "missing"),
        reason=payload.get("resolution_reason", ""),
        recorded_at=payload.get("recorded_at", format_timestamp(utc_now())),
    )
    return StandaloneBuildProbeOutcome(
        probe_id=payload.get("probe_id", "behavioral-build"),
        prerequisite_name=payload.get("prerequisite_name", "armmex"),
        resolution_record=resolution,
        dispatch_result=payload.get("dispatch_result", "blocked"),
        failure_reason=payload.get("failure_reason"),
        completed_at=payload.get("completed_at", format_timestamp(utc_now())),
    )


def _failure_classifications_for_run(
    records: tuple[CommandVerificationRecord, ...],
    fixture_provisioning: FixtureProvisioningResult,
    transport_provisioning: TransportProvisioningResult,
    channel_health: ChannelHealthOutcome,
    verification_rules: tuple[ArmVerificationRule, ...],
) -> tuple[FailureCauseClassification, ...]:
    rules = {rule.command_id: rule for rule in verification_rules}
    out: list[FailureCauseClassification] = []
    for record in records:
        if record.verified or record.category in {"channel_b_query", "channel_c_lua"}:
            continue
        rule = rules.get(record.command_id)
        if rule is None:
            rule = ArmVerificationRule(
                command_id=record.command_id,
                rule_mode="generic",
                expected_effect="no explicit rule recorded",
                evidence_window_shape="default verification window",
                predicate_family="generic_snapshot_or_dispatch",
                fallback_classification="behavioral_failure",
            )
        out.append(
            classify_failure_cause(
                record,
                fixture_provisioning,
                transport_provisioning,
                channel_health,
                rule,
            )
        )
    return tuple(out)


def _semantic_gates_for_run(
    records: tuple[CommandVerificationRecord, ...],
    failure_classifications: tuple[FailureCauseClassification, ...],
) -> tuple[CommandSemanticGate, ...]:
    classification_by_command = {
        item.command_id: item for item in failure_classifications
    }
    gates: list[CommandSemanticGate] = []
    for record in records:
        classification = classification_by_command.get(record.command_id)
        if classification is None:
            continue
        detail = record.blocking_reason or record.evidence_summary or ""
        gate = semantic_gate_metadata(record.command_id, detail)
        if gate is None:
            continue
        gate_kind, gate_detail, custom_command_id = gate
        gates.append(
            CommandSemanticGate(
                command_id=record.command_id,
                run_id=record.source_run_id,
                gate_kind=gate_kind,  # type: ignore[arg-type]
                detail=gate_detail,
                source_scope=classification.source_scope,
                custom_command_id=custom_command_id,
            )
        )
    return tuple(gates)


def _improvement_defaults(
    arm_name: str,
    sequence_index: int,
    prior_instruction: ImprovementInstruction | None,
) -> tuple[str, str]:
    if arm_name in _NATURAL_IMPROVABLE:
        return (
            "candidate",
            _instruction_detail(
                prior_instruction,
                "Retry with stronger timing and target preparation.",
            ),
        )
    if arm_name in _CHEAT_ONLY:
        return (
            "candidate",
            _instruction_detail(
                prior_instruction,
                "Escalate only after natural progress stops.",
            ),
        )
    if prior_instruction is not None and prior_instruction.status == "exhausted":
        return ("exhausted", _instruction_detail(prior_instruction, prior_instruction.instruction))
    if sequence_index >= 1:
        return (
            "exhausted",
            _instruction_detail(
                prior_instruction,
                "No better action remains after the first retry.",
            ),
        )
    return (
        "candidate",
        _instruction_detail(
            prior_instruction,
            "Collect a more specific setup or evidence plan before retrying.",
        ),
    )


def _record_for_command(
    run_id: str,
    arm_name: str,
    sequence_index: int,
    cheat_enabled: bool,
    prior_instruction: ImprovementInstruction | None = None,
) -> CommandVerificationRecord:
    case = REGISTRY[arm_name]
    command_id = _command_id(arm_name)
    if arm_name in _ALWAYS_NATURAL:
        return CommandVerificationRecord(
            command_id=command_id,
            command_name=arm_name,
            category=case.category,
            attempt_status="verified",
            verification_mode="natural",
            evidence_kind="game-state",
            verified=True,
            source_run_id=run_id,
            evidence_summary=f"{arm_name} produced direct observable state change.",
        )
    if arm_name in _NATURAL_IMPROVABLE:
        if sequence_index >= 1 or (
            sequence_index == 0
            and prior_instruction is not None
            and prior_instruction.action_type == "timing-change"
            and prior_instruction.status in {"active", "applied"}
        ):
            return CommandVerificationRecord(
                command_id=command_id,
                command_name=arm_name,
                category=case.category,
                attempt_status="verified",
                verification_mode="natural",
                evidence_kind="live-artifact",
                verified=True,
                source_run_id=run_id,
                evidence_summary=(
                    f"{arm_name} gained direct evidence after reusing a saved instruction."
                    if sequence_index == 0 and prior_instruction is not None
                    else f"{arm_name} gained direct evidence after a targeted retry."
                ),
                improvement_state="applied",
                improvement_note=_instruction_detail(
                    prior_instruction,
                    "Applied a tighter verify window and stronger target preparation.",
                ),
            )
        return CommandVerificationRecord(
            command_id=command_id,
            command_name=arm_name,
            category=case.category,
            attempt_status="inconclusive",
            verification_mode="natural",
            evidence_kind="dispatch-only",
            verified=False,
            source_run_id=run_id,
            blocking_reason="dispatch observed but direct evidence remained ambiguous",
            improvement_state="candidate",
            improvement_note=_instruction_detail(
                prior_instruction,
                "Retry with stronger timing and target preparation.",
            ),
        )
    if arm_name in _CHEAT_ONLY:
        if cheat_enabled:
            return CommandVerificationRecord(
                command_id=command_id,
                command_name=arm_name,
                category=case.category,
                attempt_status="verified",
                verification_mode="cheat-assisted",
                evidence_kind="game-state",
                verified=True,
                source_run_id=run_id,
                evidence_summary=f"{arm_name} verified after cheat-backed setup.",
                setup_actions=("enabled cheats", "provisioned prerequisite units"),
                improvement_state="applied",
                improvement_note="Escalated after the natural path had no better setup option.",
            )
        return CommandVerificationRecord(
            command_id=command_id,
            command_name=arm_name,
            category=case.category,
            attempt_status="blocked",
            verification_mode="not-attempted",
            evidence_kind="none",
            verified=False,
            source_run_id=run_id,
            blocking_reason="requires cheat-backed setup for direct verification",
            improvement_state="candidate",
            improvement_note=_instruction_detail(
                prior_instruction,
                "Escalate only after natural progress stops.",
            ),
        )
    if case.category == "channel_c_lua":
        return CommandVerificationRecord(
            command_id=command_id,
            command_name=arm_name,
            category=case.category,
            attempt_status="inconclusive",
            verification_mode="natural",
            evidence_kind="dispatch-only",
            verified=False,
            source_run_id=run_id,
            blocking_reason="Lua-only command has no direct game-state evidence in this harness",
            improvement_state="exhausted",
            improvement_note=_instruction_detail(
                prior_instruction,
                "No better direct evidence path exists without transport changes.",
            ),
        )
    if case.category == "channel_b_query":
        return CommandVerificationRecord(
            command_id=command_id,
            command_name=arm_name,
            category=case.category,
            attempt_status="blocked",
            verification_mode="natural",
            evidence_kind="none",
            verified=False,
            source_run_id=run_id,
            blocking_reason="query arm does not create a directly verifiable state mutation",
            improvement_state="exhausted",
            improvement_note=_instruction_detail(
                prior_instruction,
                "No better action remains inside the current harness scope.",
            ),
        )
    return CommandVerificationRecord(
        command_id=command_id,
        command_name=arm_name,
        category=case.category,
        attempt_status="blocked",
        verification_mode="natural",
        evidence_kind="none",
        verified=False,
        source_run_id=run_id,
        blocking_reason="target/setup path is still unavailable in the current harness",
        improvement_state=(
            "exhausted"
            if sequence_index >= 1
            or (prior_instruction is not None and prior_instruction.status == "exhausted")
            else "candidate"
        ),
        improvement_note=_instruction_detail(
            prior_instruction,
            (
                "No better action remains after the first retry."
                if sequence_index >= 1
                else "Collect a more specific setup or evidence plan before retrying."
            ),
        ),
    )


def _build_actions(
    records: tuple[CommandVerificationRecord, ...],
    current_run_id: str,
    next_run_token: str,
    cheat_enabled: bool,
    prior_instructions: dict[str, ImprovementInstruction],
) -> tuple[ImprovementAction, ...]:
    actions: list[ImprovementAction] = []
    for record in records:
        if record.verified:
            if record.improvement_state == "applied":
                actions.append(
                    ImprovementAction(
                        action_id=_action_id(record.command_id, 0),
                        command_id=record.command_id,
                        action_type=(
                            "cheat-escalation"
                            if record.verification_mode == "cheat-assisted"
                            else "timing-change"
                        ),
                        trigger_reason="prior run left the command unverified",
                        applies_to_run_id=current_run_id,
                        status="applied",
                        details=record.improvement_note or "Applied a targeted retry change.",
                    )
                )
            continue
        if record.command_name in _NATURAL_IMPROVABLE:
            action_type = "timing-change"
            details = "Retry with a narrower target window and stronger evidence capture."
        elif record.command_name in _CHEAT_ONLY and not cheat_enabled:
            action_type = "cheat-escalation"
            details = "Escalate to the cheat startscript if natural progress stalls."
        elif record.improvement_state == "candidate":
            action_type = "setup-change"
            details = record.improvement_note or "Retry with improved setup."
        else:
            action_type = "skip-no-better-action"
            details = record.improvement_note or "No better next action remains."
        actions.append(
            ImprovementAction(
                action_id=_action_id(
                    record.command_id,
                    prior_instructions.get(record.command_id, None).revision
                    if record.command_id in prior_instructions
                    else 0,
                ),
                command_id=record.command_id,
                action_type=action_type,
                trigger_reason=record.blocking_reason or "unverified",
                applies_to_run_id=next_run_token,
                status="planned",
                details=details,
            )
        )
    return tuple(actions)


def _build_live_args(
    *,
    endpoint: str,
    startscript: str,
    gameseed: str,
    output_dir: Path,
    threshold: float,
    run_index: int,
) -> argparse.Namespace:
    return argparse.Namespace(
        endpoint=endpoint,
        startscript=startscript,
        gameseed=gameseed,
        output_dir=str(output_dir),
        threshold=threshold,
        run_index=run_index,
        skip_live=False,
    )


def _record_from_live_row(
    *,
    run_id: str,
    row: dict,
    sequence_index: int,
    cheat_enabled: bool,
    prior_instruction: ImprovementInstruction | None,
) -> CommandVerificationRecord:
    arm_name = row["arm_name"]
    command_id = _command_id(arm_name)
    evidence = row.get("evidence", "")
    fixture_status = row.get("fixture_status", "")
    detail = (
        f"{evidence} | {fixture_status}"
        if evidence and fixture_status
        else (fixture_status or evidence)
    )
    error = row.get("error", "")
    dispatched = row.get("dispatched") == "true"
    verified = row.get("verified")
    verification_mode = (
        "cheat-assisted"
        if cheat_enabled and arm_name in _CHEAT_ONLY
        else "natural"
    )
    if is_channel_failure_signal(f"{detail} {error}"):
        return CommandVerificationRecord(
            command_id=command_id,
            command_name=arm_name,
            category=row["category"],
            attempt_status="blocked",
            verification_mode="not-attempted" if not dispatched else verification_mode,
            evidence_kind="none" if not dispatched else "dispatch-only",
            verified=False,
            source_run_id=run_id,
            blocking_reason="plugin command channel is not connected",
            improvement_state="candidate",
            improvement_note=_instruction_detail(
                prior_instruction,
                "Retry after restoring the plugin command channel.",
            ),
        )
    if verified == "true":
        return CommandVerificationRecord(
            command_id=command_id,
            command_name=arm_name,
            category=row["category"],
            attempt_status="verified",
            verification_mode=verification_mode,
            evidence_kind="game-state" if detail else "live-artifact",
            verified=True,
            source_run_id=run_id,
            evidence_summary=detail or f"{arm_name} verified via live behavioral coverage.",
            setup_actions=(
                ("enabled cheats",) if verification_mode == "cheat-assisted" else ()
            ),
            improvement_state=(
                "applied" if prior_instruction is not None or arm_name in _NATURAL_IMPROVABLE else "none"
            ),
            improvement_note=(
                _instruction_detail(prior_instruction, detail or "Applied live verification guidance.")
                if prior_instruction is not None or arm_name in _NATURAL_IMPROVABLE
                else ""
            ),
        )

    if verified == "false":
        if error in {"effect_not_observed"}:
            attempt_status = "inconclusive"
            evidence_kind = "dispatch-only" if dispatched else "none"
        elif error in {"target_unit_destroyed"}:
            attempt_status = "blocked"
            evidence_kind = "none"
        else:
            attempt_status = "failed"
            evidence_kind = "none"
        improvement_state, improvement_note = _improvement_defaults(
            arm_name,
            sequence_index,
            prior_instruction,
        )
        return CommandVerificationRecord(
            command_id=command_id,
            command_name=arm_name,
            category=row["category"],
            attempt_status=attempt_status,
            verification_mode=verification_mode if dispatched else "not-attempted",
            evidence_kind=evidence_kind,
            verified=False,
            source_run_id=run_id,
            blocking_reason=detail or error or "live behavioral verification failed",
            improvement_state=improvement_state,  # type: ignore[arg-type]
            improvement_note=improvement_note,
        )

    if error == "not_wire_observable":
        attempt_status = "inconclusive"
        evidence_kind = "dispatch-only"
        improvement_state = "exhausted"
        improvement_note = _instruction_detail(
            prior_instruction,
            "No better direct evidence path exists without transport changes.",
        )
    elif error == "precondition_unmet":
        attempt_status = "blocked"
        evidence_kind = "none"
        improvement_state, improvement_note = _improvement_defaults(
            arm_name,
            sequence_index,
            prior_instruction,
        )
    elif error == "dispatcher_rejected":
        attempt_status = "failed"
        evidence_kind = "none"
        improvement_state, improvement_note = _improvement_defaults(
            arm_name,
            sequence_index,
            prior_instruction,
        )
    else:
        attempt_status = "blocked"
        evidence_kind = "dispatch-only" if dispatched else "none"
        improvement_state, improvement_note = _improvement_defaults(
            arm_name,
            sequence_index,
            prior_instruction,
        )
    return CommandVerificationRecord(
        command_id=command_id,
        command_name=arm_name,
        category=row["category"],
        attempt_status=attempt_status,
        verification_mode=verification_mode if dispatched else "not-attempted",
        evidence_kind=evidence_kind,
        verified=False,
        source_run_id=run_id,
        blocking_reason=detail or error or "live behavioral verification unavailable",
        improvement_state=improvement_state,  # type: ignore[arg-type]
        improvement_note=improvement_note,
    )


def _summary_for_run(
    run_id: str,
    records: tuple[CommandVerificationRecord, ...],
    previous_run: ItertestingRun | None,
    failure_classifications: tuple[FailureCauseClassification, ...],
    channel_health: ChannelHealthOutcome,
    verification_rules: tuple[ArmVerificationRule, ...],
    contract_issues: tuple[CommandContractIssue, ...],
    improvement_eligibility: ImprovementEligibility,
) -> RunSummary:
    previous_map = {}
    if previous_run is not None:
        previous_map = {
            item.command_id: item for item in previous_run.command_records
        }
    newly_verified = tuple(
        item.command_id
        for item in records
        if item.verified
        and (
            previous_run is None
            or not previous_map.get(item.command_id, item).verified
        )
    )
    regressed = tuple(
        item.command_id
        for item in records
        if not item.verified and previous_map.get(item.command_id, item).verified
    )
    stalled = tuple(
        item.command_id
        for item in records
        if (not item.verified) and item.improvement_state == "exhausted"
    )
    cause_totals = {
        "missing_fixture": 0,
        "transport_interruption": 0,
        "predicate_or_evidence_gap": 0,
        "behavioral_failure": 0,
    }
    for item in failure_classifications:
        cause_totals[item.primary_cause] += 1
    return RunSummary(
        run_id=run_id,
        tracked_commands=len(records),
        verified_total=sum(1 for item in records if item.verified),
        verified_natural=sum(
            1
            for item in records
            if item.verified and item.verification_mode == "natural"
        ),
        verified_cheat_assisted=sum(
            1
            for item in records
            if item.verified and item.verification_mode == "cheat-assisted"
        ),
        inconclusive_total=sum(
            1 for item in records if item.attempt_status == "inconclusive"
        ),
        blocked_total=sum(1 for item in records if item.attempt_status == "blocked"),
        failed_total=sum(1 for item in records if item.attempt_status == "failed"),
        newly_verified=newly_verified,
        regressed=regressed,
        stalled=stalled,
        direct_commands_blocked_by_fixture=cause_totals["missing_fixture"],
        transport_interrupted=channel_health.status != "healthy",
        arm_rules_tuned_count=sum(
            1 for item in verification_rules if item.rule_mode != "generic"
        ),
        manual_restart_required=False,
        missing_fixture_total=cause_totals["missing_fixture"],
        transport_interruption_total=cause_totals["transport_interruption"],
        predicate_or_evidence_gap_total=cause_totals["predicate_or_evidence_gap"],
        behavioral_failure_total=cause_totals["behavioral_failure"],
        foundational_blocker_total=len(contract_issues),
        pattern_review_total=sum(
            1 for item in contract_issues if item.issue_class == "needs_pattern_review"
        ),
        contract_health_status=improvement_eligibility.contract_health_status,
        improvement_guidance_mode=improvement_eligibility.guidance_mode,
    )


def _resolved_issue_ids(
    current_issues: tuple[CommandContractIssue, ...],
    previous_run: ItertestingRun | None,
) -> tuple[str, ...]:
    if previous_run is None:
        return ()
    current_keys = {
        (item.command_id, item.issue_class) for item in current_issues
    }
    resolved = [
        item.issue_id
        for item in previous_run.contract_issues
        if (item.command_id, item.issue_class) not in current_keys
        and item.status != "resolved_in_later_run"
    ]
    return tuple(sorted(resolved))


def _contract_health_for_run(
    *,
    run_id: str,
    command_records: tuple[CommandVerificationRecord, ...],
    contract_issues: tuple[CommandContractIssue, ...],
    deterministic_repros: tuple[DeterministicRepro, ...],
    previous_run: ItertestingRun | None,
    failure_classifications: tuple[FailureCauseClassification, ...],
    semantic_gates: tuple[CommandSemanticGate, ...],
    actions: tuple[ImprovementAction, ...],
    enforce_live_closeout_gate: bool,
) -> tuple[ContractHealthDecision, ImprovementEligibility]:
    blocking = tuple(item for item in contract_issues if item.blocks_improvement)
    resolved_issue_ids = _resolved_issue_ids(contract_issues, previous_run)
    repro_issue_ids = {item.issue_id for item in deterministic_repros}
    live_closeout_blockers: list[str] = []
    live_closeout_reasons: list[str] = []
    if enforce_live_closeout_gate:
        records_by_command = {item.command_id: item for item in command_records}
        relevant_classifications = [
            item
            for item in failure_classifications
            if (
                records_by_command.get(item.command_id) is None
                or records_by_command[item.command_id].blocking_reason
                != "row missing from live run"
            )
        ]
        cause_names = {item.primary_cause for item in relevant_classifications}
        if "transport_interruption" in cause_names:
            live_closeout_blockers.append("live-closeout:transport-interruption")
            live_closeout_reasons.append("transport interruption")
        if "missing_fixture" in cause_names:
            live_closeout_blockers.append("live-closeout:missing-fixture")
            live_closeout_reasons.append("missing fixture coverage")
    needs_pattern_review = any(
        item.issue_class == "needs_pattern_review" or item.issue_id not in repro_issue_ids
        for item in blocking
    )
    recorded_at = format_timestamp(utc_now())
    semantic_gate_map = {item.command_id: item.gate_kind for item in semantic_gates}
    visible_downstream_findings = tuple(
        (
            f"{item.command_id}:semantic-gate:{semantic_gate_map[item.command_id]}"
            if item.command_id in semantic_gate_map
            else f"{item.command_id}:{item.primary_cause}"
        )
        for item in failure_classifications
    )
    if needs_pattern_review and blocking:
        decision = ContractHealthDecision(
            run_id=run_id,
            decision_status="needs_pattern_review",
            blocking_issue_ids=tuple(item.issue_id for item in blocking),
            summary_message="Foundational command-contract blockers require pattern review before normal Itertesting guidance.",
            stop_or_proceed="proceed_but_flag_review",
            recorded_at=recorded_at,
            resolved_issue_ids=resolved_issue_ids,
        )
        eligibility = ImprovementEligibility(
            run_id=run_id,
            contract_health_status=decision.decision_status,
            guidance_mode="withheld",
            visible_downstream_findings=visible_downstream_findings,
            normal_improvement_actions=(),
            withheld_reason="A foundational blocker has no deterministic repro and needs pattern review.",
        )
        return decision, eligibility
    if blocking or live_closeout_blockers:
        blocking_issue_ids = tuple(item.issue_id for item in blocking) + tuple(
            live_closeout_blockers
        )
        if blocking and live_closeout_reasons:
            summary_message = (
                "Foundational command-contract blockers were detected, and live closeout evidence "
                f"remains untrustworthy because {' and '.join(live_closeout_reasons)} still blocks "
                "normal Itertesting tuning."
            )
            withheld_reason = (
                "Normal improvement guidance is withheld while foundational blockers remain open and "
                "the live closeout workflow is still blocked."
            )
        elif blocking:
            summary_message = (
                "Foundational command-contract blockers were detected. Repair them before normal "
                "Itertesting tuning."
            )
            withheld_reason = (
                "Normal improvement guidance is withheld while foundational blockers remain open."
            )
        else:
            summary_message = (
                "Live closeout evidence remains blocked because "
                f"{' and '.join(live_closeout_reasons)} still prevents trustworthy command evaluation."
            )
            withheld_reason = (
                "Normal improvement guidance is withheld until the live closeout workflow stops "
                "reporting transport interruptions or missing fixture blockers."
            )
        decision = ContractHealthDecision(
            run_id=run_id,
            decision_status="blocked_foundational",
            blocking_issue_ids=blocking_issue_ids,
            summary_message=summary_message,
            stop_or_proceed="stop_for_repair",
            recorded_at=recorded_at,
            resolved_issue_ids=resolved_issue_ids,
        )
        eligibility = ImprovementEligibility(
            run_id=run_id,
            contract_health_status=decision.decision_status,
            guidance_mode="secondary_only",
            visible_downstream_findings=visible_downstream_findings,
            normal_improvement_actions=(),
            withheld_reason=withheld_reason,
        )
        return decision, eligibility
    decision = ContractHealthDecision(
        run_id=run_id,
        decision_status="ready_for_itertesting",
        blocking_issue_ids=(),
        summary_message=(
            "No foundational command-contract blockers were detected; remaining "
            "unverified rows are downstream evidence or behavior follow-up."
            if failure_classifications
            else "No foundational command-contract blockers were detected."
        ),
        stop_or_proceed="proceed_with_improvement",
        recorded_at=recorded_at,
        resolved_issue_ids=resolved_issue_ids,
    )
    eligibility = ImprovementEligibility(
        run_id=run_id,
        contract_health_status=decision.decision_status,
        guidance_mode="normal",
        visible_downstream_findings=visible_downstream_findings,
        normal_improvement_actions=tuple(item.details for item in actions),
    )
    return decision, eligibility


def _comparison_for_run(
    current_run: ItertestingRun,
    previous_run: ItertestingRun | None,
) -> RunComparison | None:
    if previous_run is None:
        return None
    previous_map = {item.command_id: item for item in previous_run.command_records}
    changed_commands = tuple(
        item.command_id
        for item in current_run.command_records
        if previous_map.get(item.command_id) != item
    )
    applied = tuple(
        item.action_id for item in current_run.improvement_actions if item.status == "applied"
    )
    coverage_delta = (
        current_run.summary.verified_total - previous_run.summary.verified_total
    )
    natural_delta = (
        current_run.summary.verified_natural - previous_run.summary.verified_natural
    )
    cheat_delta = (
        current_run.summary.verified_cheat_assisted
        - previous_run.summary.verified_cheat_assisted
    )
    return RunComparison(
        previous_run_id=previous_run.run_id,
        current_run_id=current_run.run_id,
        coverage_delta=coverage_delta,
        natural_delta=natural_delta,
        cheat_delta=cheat_delta,
        changed_commands=changed_commands,
        improvement_actions_applied=applied,
        stall_detected=coverage_delta <= 0,
    )


def build_run(
    *,
    campaign_id: str,
    sequence_index: int,
    reports_dir: Path,
    previous_run: ItertestingRun | None = None,
    cheat_enabled: bool = False,
    prior_instructions: dict[str, ImprovementInstruction] | None = None,
    live_rows: list[dict] | None = None,
) -> ItertestingRun:
    started = utc_now()
    run_id = make_run_id(reports_dir, started)
    loaded_instructions = prior_instructions or {}
    actual_live_rows = _actual_live_rows(live_rows)
    fixture_profile = _fixture_profile()
    verification_rules = default_verification_rules()
    if live_rows is None:
        command_records = tuple(
            _record_for_command(
                run_id,
                arm_name,
                sequence_index,
                cheat_enabled,
                loaded_instructions.get(_command_id(arm_name)),
            )
            for arm_name in sorted(REGISTRY)
        )
        fixture_provisioning, transport_provisioning = _fixture_provisioning_for_run(
            run_id,
            cheat_enabled=cheat_enabled,
            live_rows=None,
        )
    else:
        row_map = {item["arm_name"]: item for item in actual_live_rows or ()}
        command_records = tuple(
            _record_from_live_row(
                run_id=run_id,
                row=row_map.get(
                    arm_name,
                    {
                        "arm_name": arm_name,
                        "category": REGISTRY[arm_name].category,
                        "dispatched": "false",
                        "verified": "na",
                        "evidence": "row missing from live run",
                        "error": "precondition_unmet",
                    },
                ),
                sequence_index=sequence_index,
                cheat_enabled=cheat_enabled,
                prior_instruction=loaded_instructions.get(_command_id(arm_name)),
            )
            for arm_name in sorted(REGISTRY)
        )
        fixture_provisioning, transport_provisioning = _fixture_provisioning_for_run(
            run_id,
            cheat_enabled=cheat_enabled,
            live_rows=actual_live_rows,
        )
    bootstrap_readiness = _bootstrap_readiness_for_run(run_id, live_rows)
    callback_diagnostics = _callback_diagnostics_for_run(live_rows)
    prerequisite_resolution = _prerequisite_resolution_for_run(live_rows)
    standalone_build_probe_outcome = _standalone_build_probe_outcome_for_run(live_rows)
    channel_health = _channel_health_for_run(run_id, command_records, actual_live_rows)
    failure_classifications = _failure_classifications_for_run(
        command_records,
        fixture_provisioning,
        transport_provisioning,
        channel_health,
        verification_rules,
    )
    semantic_gates = _semantic_gates_for_run(
        command_records,
        failure_classifications,
    )
    provisional_actions = _build_actions(
        command_records,
        current_run_id=run_id,
        next_run_token=f"{campaign_id}-next-{sequence_index + 1}",
        cheat_enabled=cheat_enabled,
        prior_instructions=loaded_instructions,
    )
    contract_issues = normalize_contract_issues(
        run_id=run_id,
        records=command_records,
        live_rows=live_rows,
        previous_issues=previous_run.contract_issues if previous_run is not None else (),
    )
    deterministic_repros = deterministic_repros_for_issues(contract_issues)
    contract_health_decision, improvement_eligibility = _contract_health_for_run(
        run_id=run_id,
        command_records=command_records,
        contract_issues=contract_issues,
        deterministic_repros=deterministic_repros,
        previous_run=previous_run,
        failure_classifications=failure_classifications,
        semantic_gates=semantic_gates,
        actions=provisional_actions,
        enforce_live_closeout_gate=live_rows is not None,
    )
    actions = (
        provisional_actions
        if improvement_eligibility.guidance_mode == "normal"
        else ()
    )
    summary = _summary_for_run(
        run_id,
        command_records,
        previous_run,
        failure_classifications,
        channel_health,
        verification_rules,
        contract_issues,
        improvement_eligibility,
    )
    setup_mode = (
        "cheat-assisted"
        if summary.verified_total and summary.verified_total == summary.verified_cheat_assisted
        else "mixed"
        if summary.verified_cheat_assisted
        else "natural"
    )
    run = ItertestingRun(
        run_id=run_id,
        campaign_id=campaign_id,
        started_at=format_timestamp(started),
        completed_at=format_timestamp(utc_now()),
        sequence_index=sequence_index,
        engine_pin=ENGINE_PIN,
        gametype_pin=GAMETYPE_PIN,
        setup_mode=setup_mode,
        command_records=command_records,
        improvement_actions=actions,
        summary=summary,
        fixture_profile=fixture_profile,
        fixture_provisioning=fixture_provisioning,
        transport_provisioning=transport_provisioning,
        bootstrap_readiness=bootstrap_readiness,
        callback_diagnostics=callback_diagnostics,
        prerequisite_resolution=prerequisite_resolution,
        standalone_build_probe_outcome=standalone_build_probe_outcome,
        channel_health=channel_health,
        verification_rules=verification_rules,
        failure_classifications=failure_classifications,
        semantic_gates=semantic_gates,
        contract_issues=contract_issues,
        deterministic_repros=deterministic_repros,
        contract_health_decision=contract_health_decision,
        improvement_eligibility=improvement_eligibility,
    )
    comparison = _comparison_for_run(run, previous_run)
    return replace(run, previous_run_comparison=comparison)


def write_run_bundle(
    run: ItertestingRun,
    reports_dir: Path,
    *,
    stop_decision: CampaignStopDecision | None = None,
) -> Path:
    bundle_dir = run_dir(reports_dir, run.run_id)
    bundle_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = bundle_dir / "manifest.json"
    manifest_path.write_text(
        json.dumps(manifest_dict(run), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    report_path = bundle_dir / "run-report.md"
    report_path.write_text(
        render_run_report(
            run,
            stop_reason=(stop_decision.stop_reason if stop_decision else None),
            stop_decision=stop_decision,
        ),
        encoding="utf-8",
    )
    if stop_decision is not None:
        (bundle_dir / "stop-decision.json").write_text(
            json.dumps(stop_decision.__dict__, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    return bundle_dir


def campaign_dir(reports_dir: Path, campaign_id: str) -> Path:
    return reports_dir / campaign_id


def write_campaign_stop_decision(
    reports_dir: Path, stop_decision: CampaignStopDecision
) -> Path:
    base = campaign_dir(reports_dir, stop_decision.campaign_id)
    base.mkdir(parents=True, exist_ok=True)
    path = base / "campaign-stop-decision.json"
    path.write_text(
        json.dumps(stop_decision.__dict__, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return path


def load_run_manifest(path: Path) -> ItertestingRun:
    payload = json.loads(path.read_text(encoding="utf-8"))
    required = {"run_id", "campaign_id", "summary", "command_records"}
    missing = sorted(required - payload.keys())
    if missing:
        raise ValueError(f"manifest missing required fields: {', '.join(missing)}")
    if not payload["command_records"]:
        raise ValueError("manifest has no command_records")
    return run_from_dict(payload)


def latest_run_manifest(reports_dir: Path) -> Path | None:
    manifests = sorted(reports_dir.glob("itertesting-*/manifest.json"))
    return manifests[-1] if manifests else None


def _next_instruction_revision(
    prior_instruction: ImprovementInstruction | None,
) -> int:
    if prior_instruction is None:
        return 1
    return prior_instruction.revision + 1


def update_instruction_store(
    reports_dir: Path,
    run: ItertestingRun,
    prior_instructions: dict[str, ImprovementInstruction],
) -> tuple[dict[str, ImprovementInstruction], tuple[ImprovementInstruction, ...]]:
    if (
        run.improvement_eligibility is not None
        and run.improvement_eligibility.guidance_mode != "normal"
    ):
        return dict(prior_instructions), ()
    updated = dict(prior_instructions)
    action_map = {item.command_id: item for item in run.improvement_actions}
    timestamp = run.completed_at or run.started_at
    updates_for_run: list[ImprovementInstruction] = []
    for record in run.command_records:
        prior = updated.get(record.command_id)
        action = action_map.get(record.command_id)
        if record.improvement_state == "none" and action is None:
            continue
        if record.verified and record.improvement_state == "applied":
            action_type = action.action_type if action is not None else "timing-change"
            status = "superseded" if prior is not None else "retired"
            instruction = _instruction_body(
                record.improvement_note or (
                    action.details if action is not None else "Applied a targeted retry change."
                )
            )
            trigger_reason = action.trigger_reason if action is not None else ""
        elif record.improvement_state == "candidate":
            action_type = action.action_type if action is not None else "setup-change"
            status = "active"
            instruction = _instruction_body(
                record.improvement_note or (
                    action.details if action is not None else "Retry with improved setup."
                )
            )
            trigger_reason = record.blocking_reason or (
                action.trigger_reason if action is not None else ""
            )
        else:
            action_type = (
                action.action_type if action is not None else "skip-no-better-action"
            )
            status = "retired"
            instruction = _instruction_body(
                record.improvement_note or (
                    action.details if action is not None else "No better next action remains."
                )
            )
            trigger_reason = record.blocking_reason or (
                action.trigger_reason if action is not None else ""
            )
        instruction = ImprovementInstruction(
            command_id=record.command_id,
            revision=_next_instruction_revision(prior),
            action_type=action_type,
            status=status,
            instruction=instruction,
            updated_at=timestamp,
            source_run_id=run.run_id,
            trigger_reason=trigger_reason,
        )
        updated[record.command_id] = instruction
        updates_for_run.append(instruction)
    write_instruction_store(reports_dir, updated)
    ordered_updates = tuple(sorted(updates_for_run, key=lambda item: item.command_id))
    return updated, ordered_updates


def run_campaign(
    *,
    reports_dir: Path,
    max_improvement_runs: int | None,
    retry_intensity: RetryIntensityName = "standard",
    allow_cheat_escalation: bool,
    natural_first: bool,
    runtime_target_minutes: int = 15,
    endpoint: str | None = None,
    startscript: str = "tests/headless/scripts/minimal.startscript",
    cheat_startscript: str = "tests/headless/scripts/cheats.startscript",
    gameseed: str = "0x42424242",
    threshold: float = 0.50,
    skip_live: bool = True,
) -> tuple[ItertestingCampaign, tuple[ItertestingRun, ...]]:
    ensure_reports_dir(reports_dir)
    campaign_started = utc_now()
    campaign_id = campaign_started.strftime("itertesting-campaign-%Y%m%dT%H%M%SZ")
    policy = normalize_retry_policy(
        campaign_id=campaign_id,
        retry_intensity=retry_intensity,
        max_improvement_runs=max_improvement_runs,
        allow_cheat_escalation=allow_cheat_escalation,
        natural_first=natural_first,
        runtime_target_minutes=runtime_target_minutes,
    )
    configured_runs, effective_runs = configured_vs_effective_runs(policy)
    instruction_store = load_instruction_store(reports_dir)
    runs: list[ItertestingRun] = []
    progress_snapshots: list[RunProgressSnapshot] = []
    previous_run: ItertestingRun | None = None
    stop_decision: CampaignStopDecision | None = None
    final_status = "budget_exhausted"
    for sequence_index in range(effective_runs + 1):
        cheat_enabled = should_enable_cheat_escalation(
            policy=policy,
            snapshots=tuple(progress_snapshots),
            sequence_index=sequence_index,
        )
        live_rows: list[dict] | None = None
        if not skip_live:
            from . import collect_live_rows

            live_args = _build_live_args(
                endpoint=endpoint or os.environ.get("HIGHBAR_COORDINATOR", "unix:/tmp/hb-run/hb-coord.sock"),
                startscript=cheat_startscript if cheat_enabled else startscript,
                gameseed=gameseed,
                output_dir=reports_dir / "_live-artifacts",
                threshold=threshold,
                run_index=sequence_index,
            )
            live_rows = collect_live_rows(live_args)
        run = build_run(
            campaign_id=campaign_id,
            sequence_index=sequence_index,
            reports_dir=reports_dir,
            previous_run=previous_run,
            cheat_enabled=cheat_enabled,
            prior_instructions=instruction_store,
            live_rows=live_rows,
        )
        elapsed_seconds = int((utc_now() - campaign_started).total_seconds())
        snapshot = progress_snapshot_for_run(
            run=run,
            previous_snapshot=(
                progress_snapshots[-1] if progress_snapshots else None
            ),
            runtime_elapsed_seconds=elapsed_seconds,
        )
        candidate_snapshots = tuple([*progress_snapshots, snapshot])
        snapshot = with_stall_flag(snapshot, candidate_snapshots, policy)
        candidate_snapshots = tuple([*progress_snapshots, snapshot])
        warning = disproportionate_intensity_warning(policy, candidate_snapshots)
        run = apply_progress_metrics_to_run(
            run=run,
            snapshot=snapshot,
            configured_improvement_runs=configured_runs,
            effective_improvement_runs=effective_runs,
            retry_intensity_profile=policy.selected_profile.profile_name,
            disproportionate_warning=warning,
        )
        budget_exhausted = sequence_index >= effective_runs
        if (
            run.contract_health_decision is not None
            and run.contract_health_decision.decision_status != "ready_for_itertesting"
        ):
            stop_decision = CampaignStopDecision(
                decision_id=f"stop-{utc_now().strftime('%Y%m%dT%H%M%SZ')}",
                campaign_id=policy.campaign_id,
                final_run_id=run.run_id,
                stop_reason="foundational_blocked",
                direct_verified_total=run.summary.direct_verified_total,
                target_direct_verified=policy.direct_target_min,
                target_met=False,
                runtime_elapsed_seconds=elapsed_seconds,
                message=run.contract_health_decision.summary_message,
                created_at=format_timestamp(utc_now()),
            )
        else:
            stop_decision = decide_stop(
                policy=policy,
                snapshots=candidate_snapshots,
                final_run_id=run.run_id,
                budget_exhausted=budget_exhausted,
            )
        if (
            stop_decision is not None
            and stop_decision.stop_reason == "stalled"
            and not cheat_enabled
            and sequence_index < effective_runs
            and should_enable_cheat_escalation(
                policy=policy,
                snapshots=candidate_snapshots,
                sequence_index=sequence_index + 1,
            )
        ):
            stop_decision = None
        instruction_store, instruction_updates = update_instruction_store(
            reports_dir,
            run,
            instruction_store,
        )
        run = replace(run, instruction_updates=instruction_updates)
        write_run_bundle(run, reports_dir, stop_decision=stop_decision)
        runs.append(run)
        progress_snapshots.append(snapshot)
        previous_run = run
        if stop_decision is not None:
            final_status = final_status_for_decision(stop_decision.stop_reason)
            break
    if runs and stop_decision is None:
        stop_decision = decide_stop(
            policy=policy,
            snapshots=tuple(progress_snapshots),
            final_run_id=runs[-1].run_id,
            budget_exhausted=True,
        )
        if stop_decision is not None:
            final_status = final_status_for_decision(stop_decision.stop_reason)

    if stop_decision is not None:
        write_campaign_stop_decision(reports_dir, stop_decision)

    campaign = ItertestingCampaign(
        campaign_id=campaign_id,
        started_at=format_timestamp(campaign_started),
        completed_at=format_timestamp(utc_now()),
        max_improvement_runs=configured_runs,
        natural_first=natural_first,
        run_ids=tuple(run.run_id for run in runs),
        final_status=final_status,  # type: ignore[arg-type]
        stop_reason=stop_decision.stop_reason if stop_decision else "budget_exhausted",
        retry_intensity=retry_intensity,
        configured_improvement_runs=configured_runs,
        effective_improvement_runs=effective_runs,
        target_direct_verified=policy.direct_target_min,
        runtime_target_minutes=policy.runtime_target_minutes,
        stop_decision=stop_decision,
    )
    return campaign, tuple(runs)


def parse_itertesting_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="highbar_client.behavioral_coverage itertesting")
    parser.add_argument(
        "--endpoint",
        default=os.environ.get("HIGHBAR_COORDINATOR", "unix:/tmp/hb-run/hb-coord.sock"),
        help="gRPC endpoint of the running coordinator",
    )
    parser.add_argument(
        "--startscript",
        default="tests/headless/scripts/minimal.startscript",
        help="path to the natural startscript used for the live run",
    )
    parser.add_argument(
        "--reports-dir",
        default=str(default_reports_dir()),
        help="directory for timestamped Itertesting run bundles",
    )
    parser.add_argument(
        "--max-improvement-runs",
        type=int,
        default=None,
        help="requested follow-up improvement runs; defaults are profile-driven",
    )
    parser.add_argument(
        "--retry-intensity",
        choices=("quick", "standard", "deep"),
        default="standard",
        help="retry envelope profile for quick/standard/deep campaigns",
    )
    parser.add_argument(
        "--allow-cheat-escalation",
        action="store_true",
        help="allow cheat-backed setup after natural progress stalls",
    )
    parser.add_argument(
        "--cheat-startscript",
        default="tests/headless/scripts/cheats.startscript",
        help="path recorded when cheat escalation is enabled",
    )
    parser.add_argument(
        "--gameseed",
        default="0x42424242",
        help="gameseed recorded for live campaigns",
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=float(os.environ.get("HIGHBAR_BEHAVIORAL_THRESHOLD", "0.50")),
        help="behavioral threshold forwarded to live row collection",
    )
    parser.add_argument(
        "--natural-first",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="require natural attempts before cheat escalation",
    )
    parser.add_argument(
        "--runtime-target-minutes",
        type=int,
        default=15,
        help="runtime governance target for successful campaigns",
    )
    parser.add_argument(
        "--skip-live",
        action="store_true",
        help="skip the coordinator/gateway session and use the synthetic campaign model",
    )
    return parser.parse_args(argv)


def itertesting_main(argv: list[str] | None = None) -> int:
    args = parse_itertesting_args(argv)
    reports_dir = ensure_reports_dir(Path(args.reports_dir))
    campaign, runs = run_campaign(
        reports_dir=reports_dir,
        max_improvement_runs=(
            max(args.max_improvement_runs, 0)
            if args.max_improvement_runs is not None
            else None
        ),
        retry_intensity=args.retry_intensity,
        allow_cheat_escalation=args.allow_cheat_escalation,
        natural_first=args.natural_first,
        runtime_target_minutes=max(args.runtime_target_minutes, 1),
        endpoint=args.endpoint,
        startscript=args.startscript,
        cheat_startscript=args.cheat_startscript,
        gameseed=args.gameseed,
        threshold=args.threshold,
        skip_live=args.skip_live,
    )
    latest = runs[-1]
    print(
        f"itertesting: run={latest.run_id} direct_verified="
        f"{latest.summary.direct_verified_total}/{latest.summary.directly_verifiable_total} "
        f"natural={latest.summary.direct_verified_natural} "
        f"cheat={latest.summary.direct_verified_cheat_assisted}"
    )
    print(f"itertesting: campaign={campaign.campaign_id} status={campaign.final_status}")
    print(
        "itertesting: retries "
        f"configured={campaign.configured_improvement_runs} "
        f"effective={campaign.effective_improvement_runs} "
        f"profile={campaign.retry_intensity}"
    )
    if campaign.stop_decision is not None:
        print(
            f"itertesting: stop_reason={campaign.stop_decision.stop_reason} "
            f"runtime_seconds={campaign.stop_decision.runtime_elapsed_seconds}"
        )
    print(f"itertesting: reports={reports_dir}")
    if args.allow_cheat_escalation:
        print(f"itertesting: cheat-startscript={args.cheat_startscript}")
    print(f"itertesting: instructions={instructions_dir(reports_dir)}")
    return 0

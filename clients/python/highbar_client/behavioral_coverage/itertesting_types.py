# SPDX-License-Identifier: GPL-2.0-only
"""Structured manifest and policy types for Itertesting campaign runs."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Literal, Optional


AttemptStatus = Literal["verified", "inconclusive", "blocked", "failed"]
VerificationMode = Literal["natural", "cheat-assisted", "not-attempted"]
EvidenceKind = Literal["game-state", "live-artifact", "dispatch-only", "none"]
ImprovementState = Literal["none", "candidate", "applied", "exhausted"]
FixtureFallbackBehavior = Literal["classify_missing_fixture", "interrupt_run"]
ChannelHealthStatus = Literal["healthy", "degraded", "recovered", "interrupted"]
ChannelFailureStage = Literal["startup", "dispatch", "verification", "shutdown"]
VerificationRuleMode = Literal[
    "generic",
    "movement_tuned",
    "combat_tuned",
    "construction_tuned",
]
FailureCause = Literal[
    "missing_fixture",
    "transport_interruption",
    "predicate_or_evidence_gap",
    "behavioral_failure",
]
SemanticGateKind = Literal[
    "helper-parity",
    "lua-rewrite",
    "unit-shape",
    "mod-option",
]
FixtureProvisioningStrategy = Literal[
    "baseline",
    "shared-instance",
    "refreshable-shared-instance",
]
FixtureBlockingFallback = Literal[
    "missing_fixture",
    "transport_interruption_only_if_session_unhealthy",
]
TransportProvisioningStatus = Literal[
    "preexisting",
    "provisioned",
    "refreshed",
    "replaced",
    "fallback_provisioned",
    "missing",
    "unusable",
]
TransportResolutionSource = Literal[
    "invoke_callback",
    "preexisting_snapshot",
    "audit_reference",
]
TransportProvisioningMode = Literal[
    "reuse-only",
    "natural-build",
    "fallback-spawn",
]
TransportCandidateProvenance = Literal[
    "preexisting",
    "naturally_provisioned",
    "refreshed",
    "replaced",
    "fallback_provisioned",
]
TransportCandidateReadinessState = Literal[
    "ready",
    "pending",
    "lost",
    "stale",
    "incompatible",
    "refresh_failed",
]
TransportPayloadCompatibility = Literal[
    "compatible",
    "incompatible",
    "not_checked",
]
TransportLifecycleEventType = Literal[
    "discovered",
    "provision_started",
    "provision_succeeded",
    "refreshed",
    "replaced",
    "lost",
    "fallback_used",
    "compatibility_failed",
    "provision_failed",
]
TransportCompatibilityResult = Literal[
    "compatible",
    "candidate_missing",
    "candidate_unusable",
    "payload_incompatible",
]
TransportResolutionStatus = Literal["resolved", "missing", "relay_unavailable"]
FixtureClassState = Literal[
    "planned",
    "provisioned",
    "refreshed",
    "missing",
    "unusable",
]
SharedFixtureBackingKind = Literal["unit", "feature", "area", "target-handle"]
SharedFixtureUsabilityState = Literal[
    "ready",
    "consumed",
    "destroyed",
    "out_of_range",
    "stale",
    "refresh_failed",
]
FailureSourceScope = Literal[
    "bootstrap",
    "channel_health",
    "verification_rule",
    "command_outcome",
]
ContractIssueSourceScope = Literal[
    "validator",
    "queue_normalization",
    "dispatcher",
    "run_classification",
    "repro_followup",
]
FoundationalIssueClass = Literal[
    "target_drift",
    "validation_gap",
    "inert_dispatch",
    "needs_pattern_review",
]
ContractIssueStatus = Literal[
    "open",
    "reproduced",
    "resolved_in_later_run",
    "needs_new_pattern_review",
]
ContractHealthStatus = Literal[
    "ready_for_itertesting",
    "blocked_foundational",
    "needs_pattern_review",
]
ContractHealthAction = Literal[
    "stop_for_repair",
    "proceed_with_improvement",
    "proceed_but_flag_review",
]
GuidanceMode = Literal["withheld", "secondary_only", "normal"]
ActionType = Literal[
    "setup-change",
    "target-change",
    "evidence-change",
    "timing-change",
    "cheat-escalation",
    "skip-no-better-action",
]
ActionStatus = Literal["planned", "applied", "superseded", "rejected"]
InstructionStatus = Literal[
    "active",
    "superseded",
    "retired",
    "applied",
    "exhausted",
]
SetupMode = Literal["natural", "mixed", "cheat-assisted"]
CampaignFinalStatus = Literal[
    "improved",
    "stalled",
    "budget_exhausted",
    "runtime_guardrail",
    "aborted",
    "interrupted",
    "blocked_foundational",
]
RetryIntensityName = Literal["quick", "standard", "deep"]
StopReason = Literal[
    "target_reached",
    "stalled",
    "budget_exhausted",
    "runtime_guardrail",
    "interrupted",
    "foundational_blocked",
]


@dataclass(frozen=True)
class CommandVerificationRecord:
    command_id: str
    command_name: str
    category: str
    attempt_status: AttemptStatus
    verification_mode: VerificationMode
    evidence_kind: EvidenceKind
    verified: bool
    source_run_id: str
    evidence_summary: str = ""
    evidence_artifact_path: Optional[str] = None
    blocking_reason: Optional[str] = None
    setup_actions: tuple[str, ...] = ()
    improvement_state: ImprovementState = "none"
    improvement_note: str = ""


@dataclass(frozen=True)
class LiveFixtureProfile:
    profile_id: str
    fixture_classes: tuple[str, ...]
    supported_command_ids: tuple[str, ...]
    optional_fixture_classes: tuple[str, ...] = ()
    provisioning_budget_seconds: int = 0
    fallback_behavior: FixtureFallbackBehavior = "classify_missing_fixture"


@dataclass(frozen=True)
class CommandFixtureDependency:
    command_id: str
    required_fixture_classes: tuple[str, ...]
    provisioning_strategy: FixtureProvisioningStrategy
    blocking_fallback: FixtureBlockingFallback


@dataclass(frozen=True)
class SharedFixtureInstance:
    instance_id: str
    fixture_class: str
    backing_kind: SharedFixtureBackingKind
    backing_id: str
    usability_state: SharedFixtureUsabilityState
    refresh_count: int
    last_ready_at: str | None
    replacement_of: str | None = None


@dataclass(frozen=True)
class FixtureClassStatus:
    fixture_class: str
    status: FixtureClassState
    planned_command_ids: tuple[str, ...]
    ready_instance_ids: tuple[str, ...]
    last_transition_reason: str
    affected_command_ids: tuple[str, ...]
    updated_at: str


@dataclass(frozen=True)
class FixtureProvisioningResult:
    run_id: str
    profile_id: str
    provisioned_fixture_classes: tuple[str, ...]
    missing_fixture_classes: tuple[str, ...]
    affected_command_ids: tuple[str, ...]
    completed_at: str
    class_statuses: tuple[FixtureClassStatus, ...] = ()
    shared_fixture_instances: tuple[SharedFixtureInstance, ...] = ()


@dataclass(frozen=True)
class SupportedTransportVariant:
    variant_id: str
    def_name: str
    resolution_source: TransportResolutionSource
    provisioning_mode: TransportProvisioningMode
    payload_rules: tuple[str, ...]
    priority: int


@dataclass(frozen=True)
class TransportResolutionTrace:
    variant_id: str
    callback_path: str
    resolved_def_id: int | None
    resolution_status: TransportResolutionStatus
    reason: str


@dataclass(frozen=True)
class TransportCandidate:
    candidate_id: str
    variant_id: str
    unit_id: int
    provenance: TransportCandidateProvenance
    readiness_state: TransportCandidateReadinessState
    payload_compatibility: TransportPayloadCompatibility
    discovered_at: str
    supersedes_candidate_id: str | None = None


@dataclass(frozen=True)
class TransportLifecycleEvent:
    event_id: str
    event_type: TransportLifecycleEventType
    candidate_id: str | None
    command_scope: tuple[str, ...]
    reason: str
    recorded_at: str


@dataclass(frozen=True)
class TransportCompatibilityCheck:
    command_id: str
    candidate_id: str | None
    payload_unit_id: int | None
    result: TransportCompatibilityResult
    blocking_reason: str | None
    checked_at: str


@dataclass(frozen=True)
class TransportProvisioningResult:
    run_id: str
    supported_variants: tuple[SupportedTransportVariant, ...]
    active_candidate_id: str | None
    candidates: tuple[TransportCandidate, ...]
    lifecycle_events: tuple[TransportLifecycleEvent, ...]
    compatibility_checks: tuple[TransportCompatibilityCheck, ...]
    resolution_trace: tuple[TransportResolutionTrace, ...]
    status: TransportProvisioningStatus
    affected_command_ids: tuple[str, ...]
    completed_at: str


@dataclass(frozen=True)
class ChannelHealthOutcome:
    run_id: str
    status: ChannelHealthStatus
    first_failure_stage: Optional[ChannelFailureStage]
    failure_signal: str
    commands_attempted_before_failure: int
    recovery_attempted: bool
    finalized_at: str


@dataclass(frozen=True)
class ArmVerificationRule:
    command_id: str
    rule_mode: VerificationRuleMode
    expected_effect: str
    evidence_window_shape: str
    predicate_family: str
    fallback_classification: FailureCause


@dataclass(frozen=True)
class FailureCauseClassification:
    command_id: str
    run_id: str
    primary_cause: FailureCause
    supporting_detail: str
    source_scope: FailureSourceScope


@dataclass(frozen=True)
class CommandSemanticGate:
    command_id: str
    run_id: str
    gate_kind: SemanticGateKind
    detail: str
    source_scope: FailureSourceScope
    custom_command_id: int | None = None


@dataclass(frozen=True)
class DeterministicRepro:
    repro_id: str
    issue_id: str
    command_id: str
    repro_kind: Literal["unit", "integration", "headless", "pytest", "audit"]
    entrypoint: str
    expected_signal: str
    independently_runnable: bool
    arguments: tuple[str, ...] = ()
    artifact_path: Optional[str] = None


@dataclass(frozen=True)
class CommandContractIssue:
    issue_id: str
    run_id: str
    command_id: str
    issue_class: FoundationalIssueClass
    primary_cause: str
    evidence_summary: str
    source_scope: ContractIssueSourceScope
    blocks_improvement: bool
    status: ContractIssueStatus


@dataclass(frozen=True)
class ContractHealthDecision:
    run_id: str
    decision_status: ContractHealthStatus
    blocking_issue_ids: tuple[str, ...]
    summary_message: str
    stop_or_proceed: ContractHealthAction
    recorded_at: str
    resolved_issue_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class ImprovementEligibility:
    run_id: str
    contract_health_status: ContractHealthStatus
    guidance_mode: GuidanceMode
    visible_downstream_findings: tuple[str, ...]
    normal_improvement_actions: tuple[str, ...]
    withheld_reason: Optional[str] = None


@dataclass(frozen=True)
class ImprovementAction:
    action_id: str
    command_id: str
    action_type: ActionType
    trigger_reason: str
    applies_to_run_id: str
    status: ActionStatus
    details: str


@dataclass(frozen=True)
class ImprovementInstruction:
    command_id: str
    revision: int
    action_type: ActionType
    status: InstructionStatus
    instruction: str
    updated_at: str
    source_run_id: str
    trigger_reason: str = ""


@dataclass(frozen=True)
class RetryIntensityProfile:
    profile_name: RetryIntensityName
    configured_improvement_runs: int
    effective_improvement_runs: int
    stall_window_runs: int
    min_direct_gain_in_window: int
    allow_cheat_escalation: bool
    runtime_target_minutes: int


@dataclass(frozen=True)
class CampaignRetryPolicy:
    campaign_id: str
    selected_profile: RetryIntensityProfile
    global_improvement_run_cap: int
    direct_target_min: int
    runtime_target_minutes: int
    natural_first: bool
    warning_threshold_runs_without_gain: int


@dataclass(frozen=True)
class RunProgressSnapshot:
    run_id: str
    sequence_index: int
    duration_seconds: int
    direct_verified_natural: int
    direct_verified_cheat_assisted: int
    direct_unverified_total: int
    non_observable_tracked: int
    direct_gain_vs_previous: int
    stall_detected: bool
    runtime_elapsed_seconds: int


@dataclass(frozen=True)
class CampaignStopDecision:
    decision_id: str
    campaign_id: str
    final_run_id: str
    stop_reason: StopReason
    direct_verified_total: int
    target_direct_verified: int
    target_met: bool
    runtime_elapsed_seconds: int
    message: str
    created_at: str


@dataclass(frozen=True)
class RunSummary:
    run_id: str
    tracked_commands: int
    verified_total: int
    verified_natural: int
    verified_cheat_assisted: int
    inconclusive_total: int
    blocked_total: int
    failed_total: int
    newly_verified: tuple[str, ...] = ()
    regressed: tuple[str, ...] = ()
    stalled: tuple[str, ...] = ()
    directly_verifiable_total: int = 0
    direct_verified_total: int = 0
    direct_verified_natural: int = 0
    direct_verified_cheat_assisted: int = 0
    direct_unverified_total: int = 0
    non_observable_tracked_total: int = 0
    runtime_elapsed_seconds: int = 0
    disproportionate_intensity_warning: bool = False
    configured_improvement_runs: int = 0
    effective_improvement_runs: int = 0
    retry_intensity_profile: RetryIntensityName = "standard"
    direct_commands_blocked_by_fixture: int = 0
    transport_interrupted: bool = False
    arm_rules_tuned_count: int = 0
    manual_restart_required: bool = False
    missing_fixture_total: int = 0
    transport_interruption_total: int = 0
    predicate_or_evidence_gap_total: int = 0
    behavioral_failure_total: int = 0
    foundational_blocker_total: int = 0
    pattern_review_total: int = 0
    contract_health_status: ContractHealthStatus = "ready_for_itertesting"
    improvement_guidance_mode: GuidanceMode = "normal"


@dataclass(frozen=True)
class RunComparison:
    previous_run_id: str
    current_run_id: str
    coverage_delta: int
    natural_delta: int
    cheat_delta: int
    changed_commands: tuple[str, ...]
    improvement_actions_applied: tuple[str, ...]
    stall_detected: bool


@dataclass(frozen=True)
class ItertestingRun:
    run_id: str
    campaign_id: str
    started_at: str
    completed_at: Optional[str]
    sequence_index: int
    engine_pin: str
    gametype_pin: str
    setup_mode: SetupMode
    command_records: tuple[CommandVerificationRecord, ...]
    improvement_actions: tuple[ImprovementAction, ...]
    summary: RunSummary
    instruction_updates: tuple[ImprovementInstruction, ...] = ()
    previous_run_comparison: Optional[RunComparison] = None
    fixture_profile: LiveFixtureProfile | None = None
    fixture_provisioning: FixtureProvisioningResult | None = None
    transport_provisioning: TransportProvisioningResult | None = None
    channel_health: ChannelHealthOutcome | None = None
    verification_rules: tuple[ArmVerificationRule, ...] = ()
    failure_classifications: tuple[FailureCauseClassification, ...] = ()
    semantic_gates: tuple[CommandSemanticGate, ...] = ()
    contract_issues: tuple[CommandContractIssue, ...] = ()
    deterministic_repros: tuple[DeterministicRepro, ...] = ()
    contract_health_decision: ContractHealthDecision | None = None
    improvement_eligibility: ImprovementEligibility | None = None


@dataclass(frozen=True)
class ItertestingCampaign:
    campaign_id: str
    started_at: str
    completed_at: Optional[str]
    max_improvement_runs: int
    natural_first: bool
    run_ids: tuple[str, ...]
    final_status: CampaignFinalStatus
    stop_reason: str
    retry_intensity: RetryIntensityName = "standard"
    configured_improvement_runs: int = 0
    effective_improvement_runs: int = 0
    target_direct_verified: int = 20
    runtime_target_minutes: int = 15
    stop_decision: CampaignStopDecision | None = None


def manifest_dict(run: ItertestingRun) -> dict[str, Any]:
    return asdict(run)


def _command_record_from_dict(payload: dict[str, Any]) -> CommandVerificationRecord:
    return CommandVerificationRecord(
        command_id=payload["command_id"],
        command_name=payload["command_name"],
        category=payload["category"],
        attempt_status=payload["attempt_status"],
        verification_mode=payload["verification_mode"],
        evidence_kind=payload["evidence_kind"],
        verified=payload["verified"],
        source_run_id=payload["source_run_id"],
        evidence_summary=payload.get("evidence_summary", ""),
        evidence_artifact_path=payload.get("evidence_artifact_path"),
        blocking_reason=payload.get("blocking_reason"),
        setup_actions=tuple(payload.get("setup_actions", ())),
        improvement_state=payload.get("improvement_state", "none"),
        improvement_note=payload.get("improvement_note", ""),
    )


def _fixture_profile_from_dict(payload: dict[str, Any]) -> LiveFixtureProfile:
    return LiveFixtureProfile(
        profile_id=payload["profile_id"],
        fixture_classes=tuple(payload.get("fixture_classes", ())),
        supported_command_ids=tuple(payload.get("supported_command_ids", ())),
        optional_fixture_classes=tuple(payload.get("optional_fixture_classes", ())),
        provisioning_budget_seconds=payload.get("provisioning_budget_seconds", 0),
        fallback_behavior=payload.get(
            "fallback_behavior", "classify_missing_fixture"
        ),
    )


def _fixture_class_status_from_dict(payload: dict[str, Any]) -> FixtureClassStatus:
    return FixtureClassStatus(
        fixture_class=payload["fixture_class"],
        status=payload.get("status", "planned"),
        planned_command_ids=tuple(payload.get("planned_command_ids", ())),
        ready_instance_ids=tuple(payload.get("ready_instance_ids", ())),
        last_transition_reason=payload.get("last_transition_reason", ""),
        affected_command_ids=tuple(payload.get("affected_command_ids", ())),
        updated_at=payload["updated_at"],
    )


def _shared_fixture_instance_from_dict(
    payload: dict[str, Any],
) -> SharedFixtureInstance:
    return SharedFixtureInstance(
        instance_id=payload["instance_id"],
        fixture_class=payload["fixture_class"],
        backing_kind=payload.get("backing_kind", "target-handle"),
        backing_id=payload.get("backing_id", ""),
        usability_state=payload.get("usability_state", "ready"),
        refresh_count=payload.get("refresh_count", 0),
        last_ready_at=payload.get("last_ready_at"),
        replacement_of=payload.get("replacement_of"),
    )


def _supported_transport_variant_from_dict(
    payload: dict[str, Any],
) -> SupportedTransportVariant:
    return SupportedTransportVariant(
        variant_id=payload["variant_id"],
        def_name=payload["def_name"],
        resolution_source=payload.get("resolution_source", "audit_reference"),
        provisioning_mode=payload.get("provisioning_mode", "reuse-only"),
        payload_rules=tuple(payload.get("payload_rules", ())),
        priority=payload.get("priority", 0),
    )


def _transport_resolution_trace_from_dict(
    payload: dict[str, Any],
) -> TransportResolutionTrace:
    return TransportResolutionTrace(
        variant_id=payload["variant_id"],
        callback_path=payload.get("callback_path", ""),
        resolved_def_id=payload.get("resolved_def_id"),
        resolution_status=payload.get("resolution_status", "missing"),
        reason=payload.get("reason", ""),
    )


def _transport_candidate_from_dict(payload: dict[str, Any]) -> TransportCandidate:
    return TransportCandidate(
        candidate_id=payload["candidate_id"],
        variant_id=payload["variant_id"],
        unit_id=payload.get("unit_id", 0),
        provenance=payload.get("provenance", "preexisting"),
        readiness_state=payload.get("readiness_state", "pending"),
        payload_compatibility=payload.get("payload_compatibility", "not_checked"),
        discovered_at=payload["discovered_at"],
        supersedes_candidate_id=payload.get("supersedes_candidate_id"),
    )


def _transport_lifecycle_event_from_dict(
    payload: dict[str, Any],
) -> TransportLifecycleEvent:
    return TransportLifecycleEvent(
        event_id=payload["event_id"],
        event_type=payload.get("event_type", "discovered"),
        candidate_id=payload.get("candidate_id"),
        command_scope=tuple(payload.get("command_scope", ())),
        reason=payload.get("reason", ""),
        recorded_at=payload["recorded_at"],
    )


def _transport_compatibility_check_from_dict(
    payload: dict[str, Any],
) -> TransportCompatibilityCheck:
    return TransportCompatibilityCheck(
        command_id=payload["command_id"],
        candidate_id=payload.get("candidate_id"),
        payload_unit_id=payload.get("payload_unit_id"),
        result=payload.get("result", "candidate_missing"),
        blocking_reason=payload.get("blocking_reason"),
        checked_at=payload["checked_at"],
    )


def _transport_provisioning_from_dict(
    payload: dict[str, Any],
) -> TransportProvisioningResult:
    return TransportProvisioningResult(
        run_id=payload["run_id"],
        supported_variants=tuple(
            _supported_transport_variant_from_dict(item)
            for item in payload.get("supported_variants", ())
        ),
        active_candidate_id=payload.get("active_candidate_id"),
        candidates=tuple(
            _transport_candidate_from_dict(item)
            for item in payload.get("candidates", ())
        ),
        lifecycle_events=tuple(
            _transport_lifecycle_event_from_dict(item)
            for item in payload.get("lifecycle_events", ())
        ),
        compatibility_checks=tuple(
            _transport_compatibility_check_from_dict(item)
            for item in payload.get("compatibility_checks", ())
        ),
        resolution_trace=tuple(
            _transport_resolution_trace_from_dict(item)
            for item in payload.get("resolution_trace", ())
        ),
        status=payload.get("status", "missing"),
        affected_command_ids=tuple(payload.get("affected_command_ids", ())),
        completed_at=payload["completed_at"],
    )


def _fixture_provisioning_from_dict(
    payload: dict[str, Any],
) -> FixtureProvisioningResult:
    return FixtureProvisioningResult(
        run_id=payload["run_id"],
        profile_id=payload["profile_id"],
        provisioned_fixture_classes=tuple(payload.get("provisioned_fixture_classes", ())),
        missing_fixture_classes=tuple(payload.get("missing_fixture_classes", ())),
        affected_command_ids=tuple(payload.get("affected_command_ids", ())),
        completed_at=payload["completed_at"],
        class_statuses=tuple(
            _fixture_class_status_from_dict(item)
            for item in payload.get("class_statuses", ())
        ),
        shared_fixture_instances=tuple(
            _shared_fixture_instance_from_dict(item)
            for item in payload.get("shared_fixture_instances", ())
        ),
    )


def _channel_health_from_dict(payload: dict[str, Any]) -> ChannelHealthOutcome:
    return ChannelHealthOutcome(
        run_id=payload["run_id"],
        status=payload["status"],
        first_failure_stage=payload.get("first_failure_stage"),
        failure_signal=payload.get("failure_signal", ""),
        commands_attempted_before_failure=payload.get(
            "commands_attempted_before_failure", 0
        ),
        recovery_attempted=payload.get("recovery_attempted", False),
        finalized_at=payload["finalized_at"],
    )


def _verification_rule_from_dict(payload: dict[str, Any]) -> ArmVerificationRule:
    return ArmVerificationRule(
        command_id=payload["command_id"],
        rule_mode=payload.get("rule_mode", "generic"),
        expected_effect=payload.get("expected_effect", ""),
        evidence_window_shape=payload.get("evidence_window_shape", ""),
        predicate_family=payload.get("predicate_family", ""),
        fallback_classification=payload.get(
            "fallback_classification", "behavioral_failure"
        ),
    )


def _failure_classification_from_dict(
    payload: dict[str, Any],
) -> FailureCauseClassification:
    return FailureCauseClassification(
        command_id=payload["command_id"],
        run_id=payload["run_id"],
        primary_cause=payload["primary_cause"],
        supporting_detail=payload.get("supporting_detail", ""),
        source_scope=payload.get("source_scope", "command_outcome"),
    )


def _semantic_gate_from_dict(payload: dict[str, Any]) -> CommandSemanticGate:
    return CommandSemanticGate(
        command_id=payload["command_id"],
        run_id=payload["run_id"],
        gate_kind=payload["gate_kind"],
        detail=payload.get("detail", ""),
        source_scope=payload.get("source_scope", "verification_rule"),
        custom_command_id=payload.get("custom_command_id"),
    )


def _deterministic_repro_from_dict(payload: dict[str, Any]) -> DeterministicRepro:
    return DeterministicRepro(
        repro_id=payload["repro_id"],
        issue_id=payload["issue_id"],
        command_id=payload["command_id"],
        repro_kind=payload["repro_kind"],
        entrypoint=payload["entrypoint"],
        expected_signal=payload["expected_signal"],
        independently_runnable=payload.get("independently_runnable", True),
        arguments=tuple(payload.get("arguments", ())),
        artifact_path=payload.get("artifact_path"),
    )


def _contract_issue_from_dict(payload: dict[str, Any]) -> CommandContractIssue:
    return CommandContractIssue(
        issue_id=payload["issue_id"],
        run_id=payload["run_id"],
        command_id=payload["command_id"],
        issue_class=payload["issue_class"],
        primary_cause=payload["primary_cause"],
        evidence_summary=payload.get("evidence_summary", ""),
        source_scope=payload.get("source_scope", "run_classification"),
        blocks_improvement=payload.get("blocks_improvement", True),
        status=payload.get("status", "open"),
    )


def _contract_health_decision_from_dict(
    payload: dict[str, Any],
) -> ContractHealthDecision:
    return ContractHealthDecision(
        run_id=payload["run_id"],
        decision_status=payload["decision_status"],
        blocking_issue_ids=tuple(payload.get("blocking_issue_ids", ())),
        summary_message=payload.get("summary_message", ""),
        stop_or_proceed=payload.get("stop_or_proceed", "proceed_with_improvement"),
        recorded_at=payload["recorded_at"],
        resolved_issue_ids=tuple(payload.get("resolved_issue_ids", ())),
    )


def _improvement_eligibility_from_dict(
    payload: dict[str, Any],
) -> ImprovementEligibility:
    return ImprovementEligibility(
        run_id=payload["run_id"],
        contract_health_status=payload["contract_health_status"],
        guidance_mode=payload.get("guidance_mode", "normal"),
        visible_downstream_findings=tuple(payload.get("visible_downstream_findings", ())),
        normal_improvement_actions=tuple(payload.get("normal_improvement_actions", ())),
        withheld_reason=payload.get("withheld_reason"),
    )


def _improvement_action_from_dict(payload: dict[str, Any]) -> ImprovementAction:
    return ImprovementAction(
        action_id=payload["action_id"],
        command_id=payload["command_id"],
        action_type=payload["action_type"],
        trigger_reason=payload["trigger_reason"],
        applies_to_run_id=payload["applies_to_run_id"],
        status=payload["status"],
        details=payload["details"],
    )


def _summary_from_dict(payload: dict[str, Any]) -> RunSummary:
    return RunSummary(
        run_id=payload["run_id"],
        tracked_commands=payload["tracked_commands"],
        verified_total=payload["verified_total"],
        verified_natural=payload["verified_natural"],
        verified_cheat_assisted=payload["verified_cheat_assisted"],
        inconclusive_total=payload["inconclusive_total"],
        blocked_total=payload["blocked_total"],
        failed_total=payload["failed_total"],
        newly_verified=tuple(payload.get("newly_verified", ())),
        regressed=tuple(payload.get("regressed", ())),
        stalled=tuple(payload.get("stalled", ())),
        directly_verifiable_total=payload.get("directly_verifiable_total", 0),
        direct_verified_total=payload.get("direct_verified_total", payload["verified_total"]),
        direct_verified_natural=payload.get("direct_verified_natural", payload["verified_natural"]),
        direct_verified_cheat_assisted=payload.get(
            "direct_verified_cheat_assisted", payload["verified_cheat_assisted"]
        ),
        direct_unverified_total=payload.get("direct_unverified_total", 0),
        non_observable_tracked_total=payload.get("non_observable_tracked_total", 0),
        runtime_elapsed_seconds=payload.get("runtime_elapsed_seconds", 0),
        disproportionate_intensity_warning=payload.get(
            "disproportionate_intensity_warning", False
        ),
        configured_improvement_runs=payload.get("configured_improvement_runs", 0),
        effective_improvement_runs=payload.get("effective_improvement_runs", 0),
        retry_intensity_profile=payload.get("retry_intensity_profile", "standard"),
        direct_commands_blocked_by_fixture=payload.get(
            "direct_commands_blocked_by_fixture", 0
        ),
        transport_interrupted=payload.get("transport_interrupted", False),
        arm_rules_tuned_count=payload.get("arm_rules_tuned_count", 0),
        manual_restart_required=payload.get("manual_restart_required", False),
        missing_fixture_total=payload.get("missing_fixture_total", 0),
        transport_interruption_total=payload.get("transport_interruption_total", 0),
        predicate_or_evidence_gap_total=payload.get(
            "predicate_or_evidence_gap_total", 0
        ),
        behavioral_failure_total=payload.get("behavioral_failure_total", 0),
        foundational_blocker_total=payload.get("foundational_blocker_total", 0),
        pattern_review_total=payload.get("pattern_review_total", 0),
        contract_health_status=payload.get(
            "contract_health_status", "ready_for_itertesting"
        ),
        improvement_guidance_mode=payload.get("improvement_guidance_mode", "normal"),
    )


def _comparison_from_dict(payload: dict[str, Any]) -> RunComparison:
    return RunComparison(
        previous_run_id=payload["previous_run_id"],
        current_run_id=payload["current_run_id"],
        coverage_delta=payload["coverage_delta"],
        natural_delta=payload["natural_delta"],
        cheat_delta=payload["cheat_delta"],
        changed_commands=tuple(payload.get("changed_commands", ())),
        improvement_actions_applied=tuple(payload.get("improvement_actions_applied", ())),
        stall_detected=payload["stall_detected"],
    )


def run_from_dict(payload: dict[str, Any]) -> ItertestingRun:
    comparison = payload.get("previous_run_comparison")
    return ItertestingRun(
        run_id=payload["run_id"],
        campaign_id=payload["campaign_id"],
        started_at=payload["started_at"],
        completed_at=payload.get("completed_at"),
        sequence_index=payload["sequence_index"],
        engine_pin=payload["engine_pin"],
        gametype_pin=payload["gametype_pin"],
        setup_mode=payload["setup_mode"],
        command_records=tuple(
            _command_record_from_dict(item) for item in payload["command_records"]
        ),
        improvement_actions=tuple(
            _improvement_action_from_dict(item)
            for item in payload.get("improvement_actions", ())
        ),
        instruction_updates=tuple(
            ImprovementInstruction(**item)
            for item in payload.get("instruction_updates", ())
        ),
        summary=_summary_from_dict(payload["summary"]),
        previous_run_comparison=(
            _comparison_from_dict(comparison) if comparison else None
        ),
        fixture_profile=(
            _fixture_profile_from_dict(payload["fixture_profile"])
            if payload.get("fixture_profile")
            else None
        ),
        fixture_provisioning=(
            _fixture_provisioning_from_dict(payload["fixture_provisioning"])
            if payload.get("fixture_provisioning")
            else None
        ),
        transport_provisioning=(
            _transport_provisioning_from_dict(payload["transport_provisioning"])
            if payload.get("transport_provisioning")
            else None
        ),
        channel_health=(
            _channel_health_from_dict(payload["channel_health"])
            if payload.get("channel_health")
            else None
        ),
        verification_rules=tuple(
            _verification_rule_from_dict(item)
            for item in payload.get("verification_rules", ())
        ),
        failure_classifications=tuple(
            _failure_classification_from_dict(item)
            for item in payload.get("failure_classifications", ())
        ),
        semantic_gates=tuple(
            _semantic_gate_from_dict(item)
            for item in payload.get("semantic_gates", ())
        ),
        contract_issues=tuple(
            _contract_issue_from_dict(item)
            for item in payload.get("contract_issues", ())
        ),
        deterministic_repros=tuple(
            _deterministic_repro_from_dict(item)
            for item in payload.get("deterministic_repros", ())
        ),
        contract_health_decision=(
            _contract_health_decision_from_dict(payload["contract_health_decision"])
            if payload.get("contract_health_decision")
            else None
        ),
        improvement_eligibility=(
            _improvement_eligibility_from_dict(payload["improvement_eligibility"])
            if payload.get("improvement_eligibility")
            else None
        ),
    )

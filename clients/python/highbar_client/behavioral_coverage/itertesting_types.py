# SPDX-License-Identifier: GPL-2.0-only
"""Structured manifest and policy types for Itertesting campaign runs."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Literal, Optional


AttemptStatus = Literal["verified", "inconclusive", "blocked", "failed"]
VerificationMode = Literal["natural", "cheat-assisted", "not-attempted"]
EvidenceKind = Literal["game-state", "live-artifact", "dispatch-only", "none"]
ImprovementState = Literal["none", "candidate", "applied", "exhausted"]
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
]
RetryIntensityName = Literal["quick", "standard", "deep"]
StopReason = Literal[
    "target_reached",
    "stalled",
    "budget_exhausted",
    "runtime_guardrail",
    "interrupted",
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
    )

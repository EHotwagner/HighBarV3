# SPDX-License-Identifier: GPL-2.0-only
"""Campaign governance helpers for Itertesting retry tuning."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone

from .itertesting_types import (
    CampaignRetryPolicy,
    CampaignStopDecision,
    CommandVerificationRecord,
    ItertestingRun,
    RunProgressSnapshot,
)


_NON_OBSERVABLE_CATEGORIES = {"channel_b_query", "channel_c_lua"}


def _directly_verifiable(record: CommandVerificationRecord) -> bool:
    return record.category not in _NON_OBSERVABLE_CATEGORIES


def _direct_counts(run: ItertestingRun) -> tuple[int, int, int, int]:
    direct_records = [item for item in run.command_records if _directly_verifiable(item)]
    direct_verified_natural = sum(
        1
        for item in direct_records
        if item.verified and item.verification_mode == "natural"
    )
    direct_verified_cheat = sum(
        1
        for item in direct_records
        if item.verified and item.verification_mode == "cheat-assisted"
    )
    direct_verified_total = direct_verified_natural + direct_verified_cheat
    direct_unverified_total = len(direct_records) - direct_verified_total
    return (
        len(direct_records),
        direct_verified_natural,
        direct_verified_cheat,
        direct_unverified_total,
    )


def non_observable_tracked_total(run: ItertestingRun) -> int:
    return sum(1 for item in run.command_records if not _directly_verifiable(item))


def progress_snapshot_for_run(
    *,
    run: ItertestingRun,
    previous_snapshot: RunProgressSnapshot | None,
    runtime_elapsed_seconds: int,
) -> RunProgressSnapshot:
    (
        _direct_total,
        direct_verified_natural,
        direct_verified_cheat,
        direct_unverified_total,
    ) = _direct_counts(run)

    previous_total = 0
    if previous_snapshot is not None:
        previous_total = (
            previous_snapshot.direct_verified_natural
            + previous_snapshot.direct_verified_cheat_assisted
        )

    direct_total = direct_verified_natural + direct_verified_cheat
    return RunProgressSnapshot(
        run_id=run.run_id,
        sequence_index=run.sequence_index,
        duration_seconds=0,
        direct_verified_natural=direct_verified_natural,
        direct_verified_cheat_assisted=direct_verified_cheat,
        direct_unverified_total=direct_unverified_total,
        non_observable_tracked=non_observable_tracked_total(run),
        direct_gain_vs_previous=direct_total - previous_total,
        stall_detected=False,
        runtime_elapsed_seconds=max(runtime_elapsed_seconds, 0),
    )


def stall_detected(
    *,
    snapshots: tuple[RunProgressSnapshot, ...],
    stall_window_runs: int,
    min_direct_gain_in_window: int,
) -> bool:
    if stall_window_runs <= 0 or len(snapshots) < stall_window_runs:
        return False
    window = snapshots[-stall_window_runs:]
    gain = sum(max(snapshot.direct_gain_vs_previous, 0) for snapshot in window)
    return gain < max(min_direct_gain_in_window, 0)


def with_stall_flag(
    snapshot: RunProgressSnapshot,
    snapshots: tuple[RunProgressSnapshot, ...],
    policy: CampaignRetryPolicy,
) -> RunProgressSnapshot:
    detected = stall_detected(
        snapshots=snapshots,
        stall_window_runs=policy.selected_profile.stall_window_runs,
        min_direct_gain_in_window=policy.selected_profile.min_direct_gain_in_window,
    )
    return replace(snapshot, stall_detected=detected)


def should_enable_cheat_escalation(
    *,
    policy: CampaignRetryPolicy,
    snapshots: tuple[RunProgressSnapshot, ...],
    sequence_index: int,
) -> bool:
    if not policy.selected_profile.allow_cheat_escalation:
        return False
    if not policy.natural_first:
        return sequence_index >= 0
    if sequence_index == 0:
        return False
    return stall_detected(
        snapshots=snapshots,
        stall_window_runs=policy.selected_profile.stall_window_runs,
        min_direct_gain_in_window=policy.selected_profile.min_direct_gain_in_window,
    )


def _stop_message(stop_reason: str) -> str:
    messages = {
        "target_reached": "Directly verifiable target reached.",
        "stalled": "No meaningful direct verified gain across the stall window.",
        "budget_exhausted": "Configured improvement run budget was exhausted.",
        "runtime_guardrail": "Runtime governance guardrail ended the campaign.",
        "interrupted": "Campaign was interrupted by external termination.",
    }
    return messages.get(stop_reason, "Campaign stopped.")


def decide_stop(
    *,
    policy: CampaignRetryPolicy,
    snapshots: tuple[RunProgressSnapshot, ...],
    final_run_id: str,
    budget_exhausted: bool,
    interrupted: bool = False,
    now: datetime | None = None,
) -> CampaignStopDecision | None:
    if not snapshots:
        return None

    latest = snapshots[-1]
    direct_verified_total = (
        latest.direct_verified_natural + latest.direct_verified_cheat_assisted
    )
    target_met = direct_verified_total >= policy.direct_target_min

    stop_reason: str | None = None
    if target_met:
        stop_reason = "target_reached"
    elif interrupted:
        stop_reason = "interrupted"
    elif (
        latest.runtime_elapsed_seconds
        >= max(policy.runtime_target_minutes, 1) * 60
    ):
        stop_reason = "runtime_guardrail"
    elif stall_detected(
        snapshots=snapshots,
        stall_window_runs=policy.selected_profile.stall_window_runs,
        min_direct_gain_in_window=policy.selected_profile.min_direct_gain_in_window,
    ):
        stop_reason = "stalled"
    elif budget_exhausted:
        stop_reason = "budget_exhausted"

    if stop_reason is None:
        return None

    created = now or datetime.now(timezone.utc).replace(microsecond=0)
    return CampaignStopDecision(
        decision_id=f"stop-{created.strftime('%Y%m%dT%H%M%SZ')}",
        campaign_id=policy.campaign_id,
        final_run_id=final_run_id,
        stop_reason=stop_reason,  # type: ignore[arg-type]
        direct_verified_total=direct_verified_total,
        target_direct_verified=policy.direct_target_min,
        target_met=target_met,
        runtime_elapsed_seconds=latest.runtime_elapsed_seconds,
        message=_stop_message(stop_reason),
        created_at=created.isoformat().replace("+00:00", "Z"),
    )


def final_status_for_decision(stop_reason: str) -> str:
    mapping = {
        "target_reached": "improved",
        "stalled": "stalled",
        "budget_exhausted": "budget_exhausted",
        "runtime_guardrail": "runtime_guardrail",
        "interrupted": "interrupted",
    }
    return mapping.get(stop_reason, "aborted")


def apply_progress_metrics_to_run(
    *,
    run: ItertestingRun,
    snapshot: RunProgressSnapshot,
    configured_improvement_runs: int,
    effective_improvement_runs: int,
    retry_intensity_profile: str,
    disproportionate_warning: bool,
) -> ItertestingRun:
    summary = replace(
        run.summary,
        directly_verifiable_total=(
            snapshot.direct_verified_natural
            + snapshot.direct_verified_cheat_assisted
            + snapshot.direct_unverified_total
        ),
        direct_verified_total=(
            snapshot.direct_verified_natural + snapshot.direct_verified_cheat_assisted
        ),
        direct_verified_natural=snapshot.direct_verified_natural,
        direct_verified_cheat_assisted=snapshot.direct_verified_cheat_assisted,
        direct_unverified_total=snapshot.direct_unverified_total,
        non_observable_tracked_total=snapshot.non_observable_tracked,
        runtime_elapsed_seconds=snapshot.runtime_elapsed_seconds,
        disproportionate_intensity_warning=disproportionate_warning,
        configured_improvement_runs=configured_improvement_runs,
        effective_improvement_runs=effective_improvement_runs,
        retry_intensity_profile=retry_intensity_profile,  # type: ignore[arg-type]
    )
    return replace(run, summary=summary)

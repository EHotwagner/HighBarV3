# SPDX-License-Identifier: GPL-2.0-only
"""Retry-intensity policy normalization and guardrail helpers."""

from __future__ import annotations

from .itertesting_types import CampaignRetryPolicy, RetryIntensityProfile, RetryIntensityName, RunProgressSnapshot


GLOBAL_IMPROVEMENT_RUN_CAP = 10
DIRECT_TARGET_MIN = 20
DEFAULT_RUNTIME_TARGET_MINUTES = 15

_PROFILE_DEFAULTS: dict[RetryIntensityName, int] = {
    "quick": 1,
    "standard": 3,
    "deep": 8,
}

_PROFILE_STALL_WINDOWS: dict[RetryIntensityName, int] = {
    "quick": 1,
    "standard": 2,
    "deep": 3,
}

_PROFILE_MIN_GAIN: dict[RetryIntensityName, int] = {
    "quick": 1,
    "standard": 1,
    "deep": 2,
}

_PROFILE_WARNING_THRESHOLD: dict[RetryIntensityName, int] = {
    "quick": 1,
    "standard": 2,
    "deep": 3,
}


def clamp_improvement_runs(configured_improvement_runs: int) -> tuple[int, bool]:
    configured = max(configured_improvement_runs, 0)
    effective = min(configured, GLOBAL_IMPROVEMENT_RUN_CAP)
    return effective, effective != configured


def normalize_retry_policy(
    *,
    campaign_id: str,
    retry_intensity: RetryIntensityName,
    max_improvement_runs: int | None,
    allow_cheat_escalation: bool,
    natural_first: bool,
    runtime_target_minutes: int = DEFAULT_RUNTIME_TARGET_MINUTES,
) -> CampaignRetryPolicy:
    if retry_intensity not in _PROFILE_DEFAULTS:
        raise ValueError(
            "invalid retry intensity; expected one of: quick, standard, deep"
        )

    configured = (
        max_improvement_runs
        if max_improvement_runs is not None
        else _PROFILE_DEFAULTS[retry_intensity]
    )
    effective, _cap_applied = clamp_improvement_runs(configured)

    profile = RetryIntensityProfile(
        profile_name=retry_intensity,
        configured_improvement_runs=max(configured, 0),
        effective_improvement_runs=effective,
        stall_window_runs=_PROFILE_STALL_WINDOWS[retry_intensity],
        min_direct_gain_in_window=_PROFILE_MIN_GAIN[retry_intensity],
        allow_cheat_escalation=allow_cheat_escalation,
        runtime_target_minutes=max(runtime_target_minutes, 1),
    )

    return CampaignRetryPolicy(
        campaign_id=campaign_id,
        selected_profile=profile,
        global_improvement_run_cap=GLOBAL_IMPROVEMENT_RUN_CAP,
        direct_target_min=DIRECT_TARGET_MIN,
        runtime_target_minutes=max(runtime_target_minutes, 1),
        natural_first=natural_first,
        warning_threshold_runs_without_gain=_PROFILE_WARNING_THRESHOLD[retry_intensity],
    )


def configured_vs_effective_runs(policy: CampaignRetryPolicy) -> tuple[int, int]:
    return (
        policy.selected_profile.configured_improvement_runs,
        policy.selected_profile.effective_improvement_runs,
    )


def disproportionate_intensity_warning(
    policy: CampaignRetryPolicy,
    snapshots: tuple[RunProgressSnapshot, ...],
) -> bool:
    threshold = policy.warning_threshold_runs_without_gain
    if threshold <= 0 or len(snapshots) < threshold:
        return False

    recent = snapshots[-threshold:]
    no_recent_gain = all(snapshot.direct_gain_vs_previous <= 0 for snapshot in recent)
    current_total = (
        recent[-1].direct_verified_natural + recent[-1].direct_verified_cheat_assisted
    )
    profile_is_deep = policy.selected_profile.profile_name == "deep"

    return no_recent_gain and not (
        current_total >= policy.direct_target_min and not profile_is_deep
    )

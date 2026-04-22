# SPDX-License-Identifier: GPL-2.0-only
"""Shared live-hardening fixture, rule, and failure-cause helpers."""

from __future__ import annotations

from .bootstrap import (
    DEFAULT_LIVE_FIXTURE_CLASSES,
    OPTIONAL_LIVE_FIXTURE_CLASSES,
    fixture_classes_for_command,
)
from .itertesting_types import (
    ArmVerificationRule,
    ChannelHealthOutcome,
    CommandVerificationRecord,
    FailureCauseClassification,
    FixtureProvisioningResult,
    LiveFixtureProfile,
)
from .registry import REGISTRY


_TUNED_RULES: dict[str, ArmVerificationRule] = {
    "cmd-move-unit": ArmVerificationRule(
        command_id="cmd-move-unit",
        rule_mode="movement_tuned",
        expected_effect="the issued unit makes a durable position change toward the ordered point",
        evidence_window_shape="short movement settle window with snapshot delta slack",
        predicate_family="position_delta",
        fallback_classification="predicate_or_evidence_gap",
    ),
    "cmd-fight": ArmVerificationRule(
        command_id="cmd-fight",
        rule_mode="combat_tuned",
        expected_effect="the ordered unit closes distance or starts combat against a valid hostile target",
        evidence_window_shape="combat warmup window with delayed engagement evidence",
        predicate_family="health_or_position_delta",
        fallback_classification="predicate_or_evidence_gap",
    ),
    "cmd-build-unit": ArmVerificationRule(
        command_id="cmd-build-unit",
        rule_mode="construction_tuned",
        expected_effect="a new friendly construction site appears and build progress begins",
        evidence_window_shape="construction startup window with build-progress confirmation",
        predicate_family="build_progress_delta",
        fallback_classification="predicate_or_evidence_gap",
    ),
}

_CHANNEL_FAILURE_SIGNALS = (
    "plugin command channel is not connected",
    "cmd-ch disconnected",
    "command channel disconnected",
)


def default_live_fixture_profile() -> LiveFixtureProfile:
    supported = tuple(
        sorted(
            command_id
            for command_id, case in (
                (f"cmd-{arm_name.replace('_', '-')}", entry)
                for arm_name, entry in REGISTRY.items()
            )
            if case.category == "channel_a_command"
        )
    )
    return LiveFixtureProfile(
        profile_id="default-live-fixture-profile",
        fixture_classes=DEFAULT_LIVE_FIXTURE_CLASSES,
        supported_command_ids=supported,
        optional_fixture_classes=OPTIONAL_LIVE_FIXTURE_CLASSES,
        provisioning_budget_seconds=90,
        fallback_behavior="classify_missing_fixture",
    )


def default_verification_rules() -> tuple[ArmVerificationRule, ...]:
    rules: list[ArmVerificationRule] = []
    for arm_name, case in sorted(REGISTRY.items()):
        if case.category != "channel_a_command":
            continue
        command_id = f"cmd-{arm_name.replace('_', '-')}"
        rules.append(
            _TUNED_RULES.get(
                command_id,
                ArmVerificationRule(
                    command_id=command_id,
                    rule_mode="generic",
                    expected_effect=case.rationale or f"{arm_name} produces its expected live effect",
                    evidence_window_shape=f"default {case.verify_window_frames}-frame verification window",
                    predicate_family="generic_snapshot_or_dispatch",
                    fallback_classification="behavioral_failure",
                ),
            )
        )
    return tuple(rules)


def verification_rule_for_command(command_id: str) -> ArmVerificationRule:
    for rule in default_verification_rules():
        if rule.command_id == command_id:
            return rule
    return ArmVerificationRule(
        command_id=command_id,
        rule_mode="generic",
        expected_effect="no explicit live rule recorded",
        evidence_window_shape="default verification window",
        predicate_family="generic_snapshot_or_dispatch",
        fallback_classification="behavioral_failure",
    )


def missing_fixture_classes_for_command(
    command_id: str,
    provisioned_fixture_classes: tuple[str, ...],
) -> tuple[str, ...]:
    provisioned = set(provisioned_fixture_classes)
    return tuple(
        fixture
        for fixture in fixture_classes_for_command(command_id)
        if fixture not in provisioned
    )


def affected_commands_for_missing_fixtures(
    missing_fixture_classes: tuple[str, ...],
) -> tuple[str, ...]:
    missing = set(missing_fixture_classes)
    affected = [
        command_id
        for command_id in default_live_fixture_profile().supported_command_ids
        if missing.intersection(fixture_classes_for_command(command_id))
    ]
    return tuple(sorted(affected))


def is_channel_failure_signal(detail: str | None) -> bool:
    lowered = (detail or "").lower()
    return any(signal in lowered for signal in _CHANNEL_FAILURE_SIGNALS)


def classify_failure_cause(
    record: CommandVerificationRecord,
    fixture_provisioning: FixtureProvisioningResult,
    channel_health: ChannelHealthOutcome,
    verification_rule: ArmVerificationRule,
) -> FailureCauseClassification:
    detail = record.blocking_reason or record.evidence_summary or "no detail recorded"

    if (
        channel_health.status != "healthy"
        and (
            is_channel_failure_signal(detail)
            or record.command_id not in fixture_provisioning.affected_command_ids
        )
    ):
        return FailureCauseClassification(
            command_id=record.command_id,
            run_id=record.source_run_id,
            primary_cause="transport_interruption",
            supporting_detail=detail,
            source_scope="channel_health",
        )

    missing_fixture_classes = missing_fixture_classes_for_command(
        record.command_id,
        fixture_provisioning.provisioned_fixture_classes,
    )
    if record.command_id in fixture_provisioning.affected_command_ids or missing_fixture_classes:
        joined = ", ".join(missing_fixture_classes) or detail
        return FailureCauseClassification(
            command_id=record.command_id,
            run_id=record.source_run_id,
            primary_cause="missing_fixture",
            supporting_detail=f"missing fixture classes: {joined}",
            source_scope="bootstrap",
        )

    if record.attempt_status == "inconclusive" or verification_rule.fallback_classification == "predicate_or_evidence_gap":
        return FailureCauseClassification(
            command_id=record.command_id,
            run_id=record.source_run_id,
            primary_cause="predicate_or_evidence_gap",
            supporting_detail=detail,
            source_scope="verification_rule",
        )

    return FailureCauseClassification(
        command_id=record.command_id,
        run_id=record.source_run_id,
        primary_cause="behavioral_failure",
        supporting_detail=detail,
        source_scope="command_outcome",
    )

# SPDX-License-Identifier: GPL-2.0-only
"""Shared live-hardening fixture, rule, and failure-cause helpers."""

from __future__ import annotations

from .bootstrap import (
    DEFAULT_LIVE_FIXTURE_CLASSES,
    OPTIONAL_LIVE_FIXTURE_CLASSES,
    affected_commands_for_fixture_classes,
    command_fixture_dependency,
    fixture_classes_for_command,
)
from .itertesting_types import (
    ArmVerificationRule,
    ChannelHealthOutcome,
    CommandContractIssue,
    CommandVerificationRecord,
    FailureCauseClassification,
    FixtureProvisioningResult,
    LiveFixtureProfile,
    TransportProvisioningResult,
)
from .predicates import semantic_gate_metadata
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
_INERT_DISPATCH_SIGNALS = (
    "inert dispatch",
    "effective no-op",
    "no meaningful engine effect",
    "maps to no meaningful engine effect",
)
_INTENTIONALLY_EFFECT_FREE = {
    "cmd-stop",
    "cmd-wait",
    "cmd-timed-wait",
    "cmd-squad-wait",
    "cmd-death-wait",
    "cmd-gather-wait",
    "cmd-set-wanted-max-speed",
    "cmd-set-fire-state",
    "cmd-set-move-state",
    "cmd-set-on-off",
    "cmd-set-repeat",
    "cmd-stockpile",
}


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
    return unavailable_fixture_classes_for_command(
        command_id,
        class_statuses=(),
        provisioned_fixture_classes=provisioned_fixture_classes,
    )


def unavailable_fixture_classes_for_command(
    command_id: str,
    *,
    class_statuses,
    provisioned_fixture_classes: tuple[str, ...] = (),
) -> tuple[str, ...]:
    if command_id == "cmd-self-destruct":
        disposable_fixture_classes = (
            "builder",
            "cloakable",
            "payload_unit",
            "damaged_friendly",
        )
        if class_statuses:
            status_by_class = {
                item.fixture_class: item.status for item in class_statuses
            }
            if any(
                status_by_class.get(fixture_class) == "provisioned"
                for fixture_class in disposable_fixture_classes
            ):
                return ()
            return tuple(
                fixture_class
                for fixture_class in ("builder", "cloakable")
                if status_by_class.get(fixture_class) in {"missing", "unusable"}
            )
        provisioned = set(provisioned_fixture_classes)
        if set(disposable_fixture_classes).intersection(provisioned):
            return ()
        return ("builder", "cloakable")
    if class_statuses:
        status_by_class = {
            item.fixture_class: item.status for item in class_statuses
        }
        return tuple(
            fixture_class
            for fixture_class in fixture_classes_for_command(command_id)
            if status_by_class.get(fixture_class) in {"missing", "unusable"}
        )
    provisioned = set(provisioned_fixture_classes)
    return tuple(
        fixture
        for fixture in fixture_classes_for_command(command_id)
        if fixture not in provisioned
    )


def precise_missing_fixture_classes_from_detail(
    detail: str | None,
) -> tuple[str, ...]:
    lowered = (detail or "").strip()
    marker = "live fixture dependency unavailable for this arm ("
    start = lowered.find(marker)
    if start == -1:
        return ()
    start += len(marker)
    end = lowered.find(")", start)
    if end == -1:
        return ()
    inside = lowered[start:end]
    parts = tuple(
        token.strip()
        for token in inside.split(",")
        if token.strip()
    )
    return parts


def affected_commands_for_missing_fixtures(
    missing_fixture_classes: tuple[str, ...],
) -> tuple[str, ...]:
    return affected_commands_for_fixture_classes(
        missing_fixture_classes,
        supported_command_ids=default_live_fixture_profile().supported_command_ids,
    )


def is_channel_failure_signal(detail: str | None) -> bool:
    lowered = (detail or "").lower()
    return any(signal in lowered for signal in _CHANNEL_FAILURE_SIGNALS)


def is_intentionally_effect_free(command_id: str) -> bool:
    return command_id in _INTENTIONALLY_EFFECT_FREE


def has_explicit_inert_dispatch_signal(detail: str | None) -> bool:
    lowered = (detail or "").lower()
    return any(signal in lowered for signal in _INERT_DISPATCH_SIGNALS)


def _issue_source_scope(issue_class: str) -> str:
    if issue_class == "target_drift":
        return "validator"
    if issue_class == "validation_gap":
        return "run_classification"
    if issue_class == "inert_dispatch":
        return "dispatcher"
    return "repro_followup"


def classify_foundational_issue(
    record: CommandVerificationRecord,
    live_row: dict | None = None,
) -> tuple[str, str] | None:
    detail = " ".join(
        part
        for part in (
            record.blocking_reason or "",
            record.evidence_summary or "",
            (live_row or {}).get("error", ""),
            (live_row or {}).get("evidence", ""),
        )
        if part
    ).strip()
    lowered = detail.lower()

    if any(
        token in lowered
        for token in (
            "target_drift",
            "target drift",
            "mismatched target_unit_id",
            "conflicting unit ids",
            "batch target",
        )
    ):
        return "target_drift", detail or "batch target drift reached the workflow"

    if is_intentionally_effect_free(record.command_id):
        return None

    if any(
        token in lowered
        for token in ("needs pattern review", "needs_pattern_review", "new foundational pattern")
    ):
        return "needs_pattern_review", detail or "foundational issue needs a new pattern review"

    if any(
        token in lowered
        for token in (
            "validation_gap",
            "validation gap",
            "invalid_argument",
            "non-finite",
            "malformed",
            "semantic validation",
        )
    ):
        return "validation_gap", detail or "semantically invalid command reached late handling"

    if live_row is not None and (
        (live_row or {}).get("error") in {"dispatcher_rejected", "validation_gap"}
        and (live_row or {}).get("dispatched") != "true"
    ):
        return "validation_gap", detail or "dispatcher rejected a command the validator did not reject"

    if has_explicit_inert_dispatch_signal(detail):
        return "inert_dispatch", detail or "dispatch accepted the command without a durable effect"

    return None


def normalize_contract_issues(
    *,
    run_id: str,
    records: tuple[CommandVerificationRecord, ...],
    live_rows: list[dict] | None = None,
    previous_issues: tuple[CommandContractIssue, ...] = (),
) -> tuple[CommandContractIssue, ...]:
    previous_by_key = {
        (item.command_id, item.issue_class): item for item in previous_issues
    }
    row_map = {item["arm_name"]: item for item in (live_rows or [])}
    seen: set[tuple[str, str]] = set()
    issues: list[CommandContractIssue] = []
    for record in records:
        classified = classify_foundational_issue(
            record,
            live_row=row_map.get(record.command_name),
        )
        if classified is None:
            continue
        issue_class, cause = classified
        key = (record.command_id, issue_class)
        if key in seen:
            continue
        seen.add(key)
        previous = previous_by_key.get(key)
        status = (
            "needs_new_pattern_review"
            if issue_class == "needs_pattern_review"
            else "reproduced"
            if previous is not None and previous.status != "resolved_in_later_run"
            else "open"
        )
        detail = (
            record.blocking_reason
            or record.evidence_summary
            or "foundational command-contract issue detected"
        )
        issues.append(
            CommandContractIssue(
                issue_id=f"{run_id}:{record.command_id}:{issue_class}",
                run_id=run_id,
                command_id=record.command_id,
                issue_class=issue_class,  # type: ignore[arg-type]
                primary_cause=cause,
                evidence_summary=detail,
                source_scope=_issue_source_scope(issue_class),  # type: ignore[arg-type]
                blocks_improvement=True,
                status=status,  # type: ignore[arg-type]
            )
        )
    return tuple(sorted(issues, key=lambda item: (item.command_id, item.issue_class)))


def classify_failure_cause(
    record: CommandVerificationRecord,
    fixture_provisioning: FixtureProvisioningResult,
    transport_provisioning: TransportProvisioningResult,
    channel_health: ChannelHealthOutcome,
    verification_rule: ArmVerificationRule,
) -> FailureCauseClassification:
    detail = record.blocking_reason or record.evidence_summary or "no detail recorded"
    dependency = command_fixture_dependency(record.command_id)

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

    unavailable_fixture_classes = unavailable_fixture_classes_for_command(
        record.command_id,
        class_statuses=fixture_provisioning.class_statuses,
        provisioned_fixture_classes=fixture_provisioning.provisioned_fixture_classes,
    )
    precise_unavailable_fixture_classes = precise_missing_fixture_classes_from_detail(
        detail
    )
    if precise_unavailable_fixture_classes:
        unavailable_fixture_classes = precise_unavailable_fixture_classes
    if (
        record.command_id in fixture_provisioning.affected_command_ids
        or unavailable_fixture_classes
        or dependency.blocking_fallback == "missing_fixture"
        and any(
            fixture_class in fixture_provisioning.missing_fixture_classes
            for fixture_class in dependency.required_fixture_classes
        )
    ):
        joined = ", ".join(unavailable_fixture_classes) or detail
        transport_detail = detail
        for check in transport_provisioning.compatibility_checks:
            if check.command_id == record.command_id and check.blocking_reason:
                transport_detail = check.blocking_reason
                break
        return FailureCauseClassification(
            command_id=record.command_id,
            run_id=record.source_run_id,
            primary_cause="missing_fixture",
            supporting_detail=f"missing fixture classes: {joined}; {transport_detail}",
            source_scope="bootstrap",
        )

    semantic_gate = semantic_gate_metadata(record.command_id, detail)
    if semantic_gate is not None:
        gate_kind, gate_detail, _custom_command_id = semantic_gate
        gate_label = (
            "helper-parity gap"
            if gate_kind == "helper-parity"
            else f"{gate_kind.replace('-', ' ')} gate"
        )
        return FailureCauseClassification(
            command_id=record.command_id,
            run_id=record.source_run_id,
            primary_cause="predicate_or_evidence_gap",
            supporting_detail=f"semantic gate ({gate_label}): {gate_detail}",
            source_scope="verification_rule",
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

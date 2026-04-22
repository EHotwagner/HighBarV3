# SPDX-License-Identifier: GPL-2.0-only
from __future__ import annotations

from highbar_client.behavioral_coverage.itertesting_types import (
    ChannelHealthOutcome,
    CommandVerificationRecord,
    FixtureProvisioningResult,
)
from highbar_client.behavioral_coverage.live_failure_classification import (
    classify_foundational_issue,
    classify_failure_cause,
    default_live_fixture_profile,
    is_intentionally_effect_free,
    default_verification_rules,
    missing_fixture_classes_for_command,
)


def test_default_fixture_profile_covers_expected_direct_commands():
    profile = default_live_fixture_profile()

    assert profile.profile_id == "default-live-fixture-profile"
    assert "builder" in profile.fixture_classes
    assert "cmd-fight" in profile.supported_command_ids
    assert profile.fallback_behavior == "classify_missing_fixture"


def test_verification_rules_tune_move_fight_and_build():
    rules = {item.command_id: item for item in default_verification_rules()}

    assert rules["cmd-move-unit"].rule_mode == "movement_tuned"
    assert rules["cmd-fight"].rule_mode == "combat_tuned"
    assert rules["cmd-build-unit"].rule_mode == "construction_tuned"


def test_missing_fixture_helper_returns_command_specific_gap():
    missing = missing_fixture_classes_for_command(
        "cmd-load-units",
        provisioned_fixture_classes=("commander", "builder"),
    )

    assert missing == ("transport_unit", "payload_unit")


def test_transport_interruption_overrides_other_failure_causes():
    record = CommandVerificationRecord(
        command_id="cmd-fight",
        command_name="fight",
        category="channel_a_command",
        attempt_status="blocked",
        verification_mode="not-attempted",
        evidence_kind="none",
        verified=False,
        source_run_id="run-1",
        blocking_reason="plugin command channel is not connected",
    )
    fixture = FixtureProvisioningResult(
        run_id="run-1",
        profile_id="default-live-fixture-profile",
        provisioned_fixture_classes=("commander", "builder", "hostile_target"),
        missing_fixture_classes=(),
        affected_command_ids=(),
        completed_at="2026-04-22T10:15:00Z",
    )
    channel = ChannelHealthOutcome(
        run_id="run-1",
        status="interrupted",
        first_failure_stage="dispatch",
        failure_signal="plugin command channel is not connected",
        commands_attempted_before_failure=3,
        recovery_attempted=True,
        finalized_at="2026-04-22T10:16:00Z",
    )
    rule = {
        item.command_id: item for item in default_verification_rules()
    }["cmd-fight"]

    classification = classify_failure_cause(record, fixture, channel, rule)

    assert classification.primary_cause == "transport_interruption"
    assert classification.source_scope == "channel_health"


def test_target_drift_is_promoted_to_foundational_issue():
    record = CommandVerificationRecord(
        command_id="cmd-move-unit",
        command_name="move_unit",
        category="channel_a_command",
        attempt_status="failed",
        verification_mode="natural",
        evidence_kind="none",
        verified=False,
        source_run_id="run-1",
        blocking_reason="target_drift: batch target 4 disagreed with command unit 9",
    )

    issue = classify_foundational_issue(record)

    assert issue is not None
    assert issue[0] == "target_drift"


def test_intentionally_effect_free_commands_do_not_become_inert_dispatch():
    record = CommandVerificationRecord(
        command_id="cmd-stop",
        command_name="stop",
        category="channel_a_command",
        attempt_status="inconclusive",
        verification_mode="natural",
        evidence_kind="dispatch-only",
        verified=False,
        source_run_id="run-1",
        blocking_reason="dispatch observed but direct evidence remained ambiguous",
    )

    issue = classify_foundational_issue(record)

    assert is_intentionally_effect_free("cmd-stop") is True
    assert issue is None

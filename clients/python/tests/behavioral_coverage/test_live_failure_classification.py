# SPDX-License-Identifier: GPL-2.0-only
from __future__ import annotations

from highbar_client.behavioral_coverage.itertesting_types import (
    ChannelHealthOutcome,
    CommandVerificationRecord,
    FixtureClassStatus,
    FixtureProvisioningResult,
)
from highbar_client.behavioral_coverage.live_failure_classification import (
    classify_foundational_issue,
    classify_failure_cause,
    default_live_fixture_profile,
    is_intentionally_effect_free,
    default_verification_rules,
    missing_fixture_classes_for_command,
    precise_missing_fixture_classes_from_detail,
    unavailable_fixture_classes_for_command,
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


def test_build_unit_missing_fixture_helper_does_not_require_extra_builder():
    missing = missing_fixture_classes_for_command(
        "cmd-build-unit",
        provisioned_fixture_classes=("commander", "resource_baseline"),
    )

    assert missing == ()


def test_self_destruct_missing_fixture_helper_accepts_builder_as_alternative():
    missing = missing_fixture_classes_for_command(
        "cmd-self-destruct",
        provisioned_fixture_classes=("commander", "builder"),
    )

    assert missing == ()


def test_self_destruct_missing_fixture_helper_accepts_payload_as_alternative():
    missing = missing_fixture_classes_for_command(
        "cmd-self-destruct",
        provisioned_fixture_classes=("commander", "payload_unit"),
    )

    assert missing == ()


def test_class_status_helper_treats_unusable_fixture_as_missing_for_command():
    missing = unavailable_fixture_classes_for_command(
        "cmd-load-units",
        class_statuses=(
            FixtureClassStatus(
                fixture_class="transport_unit",
                status="unusable",
                planned_command_ids=("cmd-load-units",),
                ready_instance_ids=(),
                last_transition_reason="transport fixture refresh failed",
                affected_command_ids=("cmd-load-units",),
                updated_at="2026-04-22T10:15:00Z",
            ),
            FixtureClassStatus(
                fixture_class="payload_unit",
                status="provisioned",
                planned_command_ids=("cmd-load-units",),
                ready_instance_ids=("payload-unit-instance-01",),
                last_transition_reason="payload fixture was ready",
                affected_command_ids=(),
                updated_at="2026-04-22T10:15:00Z",
            ),
        ),
    )

    assert missing == ("transport_unit",)


def test_self_destruct_class_status_helper_accepts_builder_as_alternative():
    missing = unavailable_fixture_classes_for_command(
        "cmd-self-destruct",
        class_statuses=(
            FixtureClassStatus(
                fixture_class="builder",
                status="provisioned",
                planned_command_ids=("cmd-self-destruct",),
                ready_instance_ids=("builder-instance-01",),
                last_transition_reason="builder fixture was ready",
                affected_command_ids=(),
                updated_at="2026-04-22T10:15:00Z",
            ),
            FixtureClassStatus(
                fixture_class="cloakable",
                status="missing",
                planned_command_ids=("cmd-self-destruct",),
                ready_instance_ids=(),
                last_transition_reason="cloakable fixture was not provisioned",
                affected_command_ids=("cmd-self-destruct",),
                updated_at="2026-04-22T10:15:00Z",
            ),
        ),
    )

    assert missing == ()


def test_self_destruct_class_status_helper_accepts_payload_as_alternative():
    missing = unavailable_fixture_classes_for_command(
        "cmd-self-destruct",
        class_statuses=(
            FixtureClassStatus(
                fixture_class="payload_unit",
                status="provisioned",
                planned_command_ids=("cmd-self-destruct",),
                ready_instance_ids=("payload-unit-instance-01",),
                last_transition_reason="payload fixture was ready",
                affected_command_ids=(),
                updated_at="2026-04-22T10:15:00Z",
            ),
            FixtureClassStatus(
                fixture_class="builder",
                status="missing",
                planned_command_ids=("cmd-self-destruct",),
                ready_instance_ids=(),
                last_transition_reason="builder fixture was not provisioned",
                affected_command_ids=("cmd-self-destruct",),
                updated_at="2026-04-22T10:15:00Z",
            ),
        ),
    )

    assert missing == ()


def test_precise_missing_fixture_classes_are_parsed_from_live_detail():
    missing = precise_missing_fixture_classes_from_detail(
        "live fixture dependency unavailable for this arm (transport_unit)"
    )

    assert missing == ("transport_unit",)


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


def test_authoritative_class_statuses_drive_missing_fixture_classification():
    record = CommandVerificationRecord(
        command_id="cmd-load-units",
        command_name="load_units",
        category="channel_a_command",
        attempt_status="blocked",
        verification_mode="not-attempted",
        evidence_kind="none",
        verified=False,
        source_run_id="run-1",
        blocking_reason="transport fixture refresh failed before load evaluation",
    )
    fixture = FixtureProvisioningResult(
        run_id="run-1",
        profile_id="default-live-fixture-profile",
        provisioned_fixture_classes=("commander", "builder", "payload_unit"),
        missing_fixture_classes=("transport_unit",),
        affected_command_ids=("cmd-load-units",),
        completed_at="2026-04-22T10:15:00Z",
        class_statuses=(
            FixtureClassStatus(
                fixture_class="transport_unit",
                status="unusable",
                planned_command_ids=("cmd-load-units", "cmd-unload-unit"),
                ready_instance_ids=(),
                last_transition_reason="transport fixture refresh failed",
                affected_command_ids=("cmd-load-units", "cmd-unload-unit"),
                updated_at="2026-04-22T10:15:00Z",
            ),
        ),
    )
    channel = ChannelHealthOutcome(
        run_id="run-1",
        status="healthy",
        first_failure_stage=None,
        failure_signal="",
        commands_attempted_before_failure=3,
        recovery_attempted=False,
        finalized_at="2026-04-22T10:16:00Z",
    )
    rule = {
        item.command_id: item for item in default_verification_rules()
    }["cmd-load-units"]

    classification = classify_failure_cause(record, fixture, channel, rule)

    assert classification.primary_cause == "missing_fixture"
    assert "transport_unit" in classification.supporting_detail


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


def test_generic_effect_not_observed_does_not_become_foundational_inert_dispatch():
    record = CommandVerificationRecord(
        command_id="cmd-patrol",
        command_name="patrol",
        category="channel_a_command",
        attempt_status="inconclusive",
        verification_mode="natural",
        evidence_kind="dispatch-only",
        verified=False,
        source_run_id="run-1",
        blocking_reason="snapshot-diff predicate not yet implemented for this arm",
    )

    issue = classify_foundational_issue(
        record,
        live_row={
            "dispatched": "true",
            "verified": "false",
            "error": "effect_not_observed",
            "evidence": "snapshot-diff predicate not yet implemented for this arm",
        },
    )

    assert issue is None


def test_explicit_inert_dispatch_signal_still_becomes_foundational_issue():
    record = CommandVerificationRecord(
        command_id="cmd-fight",
        command_name="fight",
        category="channel_a_command",
        attempt_status="inconclusive",
        verification_mode="natural",
        evidence_kind="dispatch-only",
        verified=False,
        source_run_id="run-1",
        blocking_reason="inert dispatch left no durable effect",
    )

    issue = classify_foundational_issue(
        record,
        live_row={
            "dispatched": "true",
            "verified": "false",
            "error": "effect_not_observed",
            "evidence": "inert dispatch left no durable effect",
        },
    )

    assert issue is not None
    assert issue[0] == "inert_dispatch"


def test_semantic_gate_helper_parity_is_reported_in_supporting_detail():
    record = CommandVerificationRecord(
        command_id="cmd-set-wanted-max-speed",
        command_name="set_wanted_max_speed",
        category="channel_a_command",
        attempt_status="inconclusive",
        verification_mode="natural",
        evidence_kind="dispatch-only",
        verified=False,
        source_run_id="run-1",
        blocking_reason="local helper parity gap: CCircuitUnit::CmdWantedSpeed remained a no-op",
    )
    fixture = FixtureProvisioningResult(
        run_id="run-1",
        profile_id="default-live-fixture-profile",
        provisioned_fixture_classes=("commander",),
        missing_fixture_classes=(),
        affected_command_ids=(),
        completed_at="2026-04-22T10:15:00Z",
    )
    channel = ChannelHealthOutcome(
        run_id="run-1",
        status="healthy",
        first_failure_stage=None,
        failure_signal="",
        commands_attempted_before_failure=1,
        recovery_attempted=False,
        finalized_at="2026-04-22T10:16:00Z",
    )
    rule = {
        item.command_id: item for item in default_verification_rules()
    }["cmd-set-wanted-max-speed"]

    classification = classify_failure_cause(record, fixture, channel, rule)

    assert classification.primary_cause == "predicate_or_evidence_gap"
    assert "semantic gate (helper-parity gap)" in classification.supporting_detail


def test_semantic_gate_mod_option_is_reported_in_supporting_detail():
    record = CommandVerificationRecord(
        command_id="cmd-set-wanted-max-speed",
        command_name="set_wanted_max_speed",
        category="channel_a_command",
        attempt_status="blocked",
        verification_mode="not-attempted",
        evidence_kind="none",
        verified=False,
        source_run_id="run-1",
        blocking_reason="emprework mod option disabled for wanted-speed validation",
    )
    fixture = FixtureProvisioningResult(
        run_id="run-1",
        profile_id="default-live-fixture-profile",
        provisioned_fixture_classes=("commander",),
        missing_fixture_classes=(),
        affected_command_ids=(),
        completed_at="2026-04-22T10:15:00Z",
    )
    channel = ChannelHealthOutcome(
        run_id="run-1",
        status="healthy",
        first_failure_stage=None,
        failure_signal="",
        commands_attempted_before_failure=1,
        recovery_attempted=False,
        finalized_at="2026-04-22T10:16:00Z",
    )
    rule = {
        item.command_id: item for item in default_verification_rules()
    }["cmd-set-wanted-max-speed"]

    classification = classify_failure_cause(record, fixture, channel, rule)

    assert "semantic gate (mod option gate)" in classification.supporting_detail


def test_semantic_gate_lua_rewrite_is_reported_in_supporting_detail():
    record = CommandVerificationRecord(
        command_id="cmd-attack",
        command_name="attack",
        category="channel_a_command",
        attempt_status="inconclusive",
        verification_mode="natural",
        evidence_kind="dispatch-only",
        verified=False,
        source_run_id="run-1",
        blocking_reason="place_target_on_ground Lua rewrite converted the unit target into map coordinates",
    )
    fixture = FixtureProvisioningResult(
        run_id="run-1",
        profile_id="default-live-fixture-profile",
        provisioned_fixture_classes=("commander", "hostile_target"),
        missing_fixture_classes=(),
        affected_command_ids=(),
        completed_at="2026-04-22T10:15:00Z",
    )
    channel = ChannelHealthOutcome(
        run_id="run-1",
        status="healthy",
        first_failure_stage=None,
        failure_signal="",
        commands_attempted_before_failure=1,
        recovery_attempted=False,
        finalized_at="2026-04-22T10:16:00Z",
    )
    rule = {item.command_id: item for item in default_verification_rules()}["cmd-attack"]

    classification = classify_failure_cause(record, fixture, channel, rule)

    assert "semantic gate (lua rewrite gate)" in classification.supporting_detail


def test_semantic_gate_unit_shape_is_reported_for_manual_launch_substitution():
    record = CommandVerificationRecord(
        command_id="cmd-dgun",
        command_name="dgun",
        category="channel_a_command",
        attempt_status="blocked",
        verification_mode="not-attempted",
        evidence_kind="none",
        verified=False,
        source_run_id="run-1",
        blocking_reason="non-commander manual launch substitution (32102) means this unit does not receive the command descriptor",
    )
    fixture = FixtureProvisioningResult(
        run_id="run-1",
        profile_id="default-live-fixture-profile",
        provisioned_fixture_classes=("commander", "hostile_target"),
        missing_fixture_classes=(),
        affected_command_ids=(),
        completed_at="2026-04-22T10:15:00Z",
    )
    channel = ChannelHealthOutcome(
        run_id="run-1",
        status="healthy",
        first_failure_stage=None,
        failure_signal="",
        commands_attempted_before_failure=1,
        recovery_attempted=False,
        finalized_at="2026-04-22T10:16:00Z",
    )
    rule = {item.command_id: item for item in default_verification_rules()}["cmd-dgun"]

    classification = classify_failure_cause(record, fixture, channel, rule)

    assert "semantic gate (unit shape gate)" in classification.supporting_detail

# SPDX-License-Identifier: GPL-2.0-only
"""Markdown rendering for Itertesting run bundles."""

from __future__ import annotations

from .bootstrap import fixture_classes_for_custom_command_id
from .itertesting_types import CampaignStopDecision, ItertestingRun
from .upstream_fixture_intelligence import all_custom_command_inventory


_NON_OBSERVABLE_CATEGORIES = {"channel_b_query", "channel_c_lua"}


def _is_direct(record) -> bool:
    return record.category not in _NON_OBSERVABLE_CATEGORIES


def render_run_report(
    run: ItertestingRun,
    stop_reason: str | None = None,
    stop_decision: CampaignStopDecision | None = None,
) -> str:
    direct_target = (
        stop_decision.target_direct_verified if stop_decision is not None else 20
    )
    direct_target_met = run.summary.direct_verified_total >= direct_target

    lines = [
        "# Itertesting Run Report",
        "",
        "## Run Metadata",
        "",
        f"- Run id: `{run.run_id}`",
        f"- Campaign id: `{run.campaign_id}`",
        f"- Sequence index: {run.sequence_index}",
        f"- Setup mode: {run.setup_mode}",
        f"- Started: {run.started_at}",
        f"- Completed: {run.completed_at or 'incomplete'}",
        "",
        "## Coverage Summary",
        "",
        f"- Tracked commands total: {run.summary.tracked_commands}",
        f"- Directly verifiable total: {run.summary.directly_verifiable_total}",
        f"- Direct verified natural: {run.summary.direct_verified_natural}",
        (
            "- Direct verified cheat-assisted: "
            f"{run.summary.direct_verified_cheat_assisted}"
        ),
        f"- Direct verified total: {run.summary.direct_verified_total}",
        f"- Direct unverified total: {run.summary.direct_unverified_total}",
        (
            "- Non-observable tracked total: "
            f"{run.summary.non_observable_tracked_total}"
        ),
        (
            f"- Direct target ({direct_target}) met: "
            f"{'yes' if direct_target_met else 'no'}"
        ),
        (
            "- Runtime elapsed seconds: "
            f"{run.summary.runtime_elapsed_seconds}"
        ),
        "",
    ]

    if run.previous_run_comparison is not None:
        cmp = run.previous_run_comparison
        result = (
            "stalled"
            if cmp.stall_detected
            else "improved"
            if cmp.coverage_delta > 0
            else "regressed"
        )
        lines.extend(
            [
                "## Compared With Previous Run",
                "",
                f"- Previous run id: `{cmp.previous_run_id}`",
                f"- Coverage delta: {cmp.coverage_delta:+d}",
                f"- Natural delta: {cmp.natural_delta:+d}",
                f"- Cheat-assisted delta: {cmp.cheat_delta:+d}",
                f"- Run result: {result}",
                "",
            ]
        )

    lines.extend(
        [
            "## Intensity and Governance",
            "",
            (
                "- Configured improvement runs: "
                f"{run.summary.configured_improvement_runs}"
            ),
            (
                "- Effective improvement runs: "
                f"{run.summary.effective_improvement_runs}"
            ),
            (
                "- Retry intensity profile: "
                f"{run.summary.retry_intensity_profile}"
            ),
            (
                "- Disproportionate intensity warning: "
                f"{'yes' if run.summary.disproportionate_intensity_warning else 'no'}"
            ),
            "",
        ]
    )

    if stop_decision is not None or stop_reason is not None:
        lines.extend(["## Stop Reason", ""])
        if stop_decision is not None:
            lines.extend(
                [
                    f"- Stop reason: {stop_decision.stop_reason}",
                    (
                        "- Direct verified at stop: "
                        f"{stop_decision.direct_verified_total}/"
                        f"{stop_decision.target_direct_verified}"
                    ),
                    (
                        "- Runtime at stop (seconds): "
                        f"{stop_decision.runtime_elapsed_seconds}"
                    ),
                    f"- Message: {stop_decision.message}",
                ]
            )
        else:
            lines.append(f"- Stop reason: {stop_reason}")
        lines.append("")

    if run.bootstrap_readiness is not None:
        lines.extend(
            [
                "## Bootstrap Readiness",
                "",
                f"- Status: {run.bootstrap_readiness.readiness_status}",
                f"- Path: {run.bootstrap_readiness.readiness_path}",
                f"- First required step: {run.bootstrap_readiness.first_required_step or 'unknown'}",
                f"- Economy: {run.bootstrap_readiness.economy_summary or 'unknown'}",
                f"- Reason: {run.bootstrap_readiness.reason or 'none'}",
                "",
            ]
        )

    if run.callback_diagnostics:
        lines.extend(["## Callback Diagnostics", ""])
        for snapshot in run.callback_diagnostics:
            scope = ", ".join(snapshot.diagnostic_scope) or "none"
            lines.extend(
                [
                    (
                        f"- `{snapshot.snapshot_id}` — {snapshot.capture_stage} — "
                        f"{snapshot.availability_status} — {snapshot.source}"
                    ),
                    f"  scope: {scope}",
                    f"  summary: {snapshot.summary or 'none'}",
                ]
            )
        lines.append("")

    if run.prerequisite_resolution:
        lines.extend(["## Runtime Prerequisite Resolution", ""])
        for item in run.prerequisite_resolution:
            resolved_def_id = (
                str(item.resolved_def_id)
                if item.resolved_def_id is not None
                else "unresolved"
            )
            lines.extend(
                [
                    (
                        f"- `{item.prerequisite_name}` — {item.consumer} — "
                        f"{item.resolution_status} — def_id: {resolved_def_id}"
                    ),
                    f"  callback path: {item.callback_path or 'none'}",
                    f"  reason: {item.reason or 'none'}",
                ]
            )
        lines.append("")

    if run.standalone_build_probe_outcome is not None:
        probe = run.standalone_build_probe_outcome
        resolved_def_id = (
            str(probe.resolution_record.resolved_def_id)
            if probe.resolution_record.resolved_def_id is not None
            else "unresolved"
        )
        lines.extend(
            [
                "## Standalone Build Probe",
                "",
                f"- Probe id: `{probe.probe_id}`",
                f"- Prerequisite: `{probe.prerequisite_name}`",
                f"- Dispatch result: {probe.dispatch_result}",
                (
                    "- Resolution: "
                    f"{probe.resolution_record.resolution_status} "
                    f"(def_id: {resolved_def_id})"
                ),
                (
                    "- Failure reason: "
                    f"{probe.failure_reason or 'none'}"
                ),
                "",
            ]
        )

    if run.fixture_profile is not None and run.fixture_provisioning is not None:
        refreshed = [
            item.fixture_class
            for item in run.fixture_provisioning.class_statuses
            if item.status == "refreshed"
        ]
        unusable = [
            item.fixture_class
            for item in run.fixture_provisioning.class_statuses
            if item.status == "unusable"
        ]
        lines.extend(
            [
                "## Fixture Provisioning",
                "",
                f"- Profile id: `{run.fixture_profile.profile_id}`",
                (
                    "- Planned fixtures: "
                    + ", ".join(
                        sorted(
                            {
                                *run.fixture_profile.fixture_classes,
                                *run.fixture_profile.optional_fixture_classes,
                            }
                        )
                    )
                ),
                (
                    "- Provisioned fixtures: "
                    + ", ".join(run.fixture_provisioning.provisioned_fixture_classes)
                ),
                (
                    "- Refreshed fixtures: "
                    + (", ".join(refreshed) if refreshed else "none")
                ),
                (
                    "- Missing fixtures: "
                    + (
                        ", ".join(run.fixture_provisioning.missing_fixture_classes)
                        if run.fixture_provisioning.missing_fixture_classes
                        else "none"
                    )
                ),
                (
                    "- Unusable fixtures: "
                    + (", ".join(unusable) if unusable else "none")
                ),
                (
                    "- Affected commands: "
                    + (
                        ", ".join(run.fixture_provisioning.affected_command_ids)
                        if run.fixture_provisioning.affected_command_ids
                        else "none"
                    )
                ),
                (
                    "- Commands blocked by fixture: "
                    f"{run.summary.direct_commands_blocked_by_fixture}"
                ),
                "",
            ]
        )
        if run.fixture_provisioning.class_statuses:
            lines.extend(["### Fixture Class Statuses", ""])
            for status in run.fixture_provisioning.class_statuses:
                planned = ", ".join(status.planned_command_ids) or "none"
                affected = ", ".join(status.affected_command_ids) or "none"
                ready = ", ".join(status.ready_instance_ids) or "none"
                lines.extend(
                    [
                        (
                            f"- `{status.fixture_class}` — {status.status} — "
                            f"ready instances: {ready}"
                        ),
                        f"  planned commands: {planned}",
                        f"  affected commands: {affected}",
                        f"  reason: {status.last_transition_reason}",
                    ]
                )
            lines.append("")
        if run.fixture_provisioning.shared_fixture_instances:
            lines.extend(["### Shared Fixture Instances", ""])
            for instance in run.fixture_provisioning.shared_fixture_instances:
                lines.append(
                    (
                        f"- `{instance.instance_id}` — {instance.fixture_class} — "
                        f"{instance.usability_state} — {instance.backing_kind}:{instance.backing_id}"
                    )
                )
            lines.append("")
        if run.transport_provisioning is not None:
            lines.extend(
                [
                    "### Transport Provisioning",
                    "",
                    f"- Status: {run.transport_provisioning.status}",
                    (
                        "- Active candidate: "
                        f"{run.transport_provisioning.active_candidate_id or 'none'}"
                    ),
                    (
                        "- Affected transport commands: "
                        + (
                            ", ".join(run.transport_provisioning.affected_command_ids)
                            if run.transport_provisioning.affected_command_ids
                            else "none"
                        )
                    ),
                ]
            )
            if run.transport_provisioning.candidates:
                lines.append("- Candidate chain:")
                for candidate in run.transport_provisioning.candidates:
                    lines.append(
                        (
                            f"  `{candidate.candidate_id}` — {candidate.variant_id} — "
                            f"{candidate.provenance} — {candidate.readiness_state} — "
                            f"payload: {candidate.payload_compatibility}"
                        )
                    )
            if run.transport_provisioning.lifecycle_events:
                lines.append("- Lifecycle events:")
                for event in run.transport_provisioning.lifecycle_events:
                    scope = ", ".join(event.command_scope) or "none"
                    lines.append(
                        f"  `{event.event_type}` — commands: {scope} — {event.reason}"
                    )
            if run.transport_provisioning.compatibility_checks:
                lines.append("- Compatibility checks:")
                for check in run.transport_provisioning.compatibility_checks:
                    lines.append(
                        (
                            f"  `{check.command_id}` — {check.result} — "
                            f"{check.blocking_reason or 'compatible'}"
                        )
                    )
            if run.transport_provisioning.resolution_trace:
                lines.append("- Resolution trace:")
                for trace in run.transport_provisioning.resolution_trace:
                    resolved_def_id = (
                        str(trace.resolved_def_id)
                        if trace.resolved_def_id is not None
                        else "unresolved"
                    )
                    lines.append(
                        (
                            f"  `{trace.variant_id}` — {trace.callback_path} — "
                            f"{trace.resolution_status} — def_id: {resolved_def_id} — "
                            f"{trace.reason}"
                        )
                    )
            lines.append("")

    inventory = all_custom_command_inventory()
    if inventory:
        lines.extend(["## Command Semantic Inventory", ""])
        for item in inventory:
            fixture_classes = ", ".join(
                fixture_classes_for_custom_command_id(item.command_id)
            )
            lines.append(
                (
                    f"- `{item.command_id}` `{item.command_name}` — "
                    f"`{item.owner_gadget}` — units: {item.eligible_unit_rule} — "
                    f"evidence: {item.expected_evidence_channel} — "
                    f"fixtures: {fixture_classes}"
                )
            )
        lines.append("")

    if run.channel_health is not None:
        lines.extend(
            [
                "## Channel Health",
                "",
                f"- Status: {run.channel_health.status}",
                (
                    "- First failure stage: "
                    f"{run.channel_health.first_failure_stage or 'none'}"
                ),
                (
                    "- Failure signal: "
                    f"{run.channel_health.failure_signal or 'none'}"
                ),
                (
                    "- Commands attempted before failure: "
                    f"{run.channel_health.commands_attempted_before_failure}"
                ),
                (
                    "- Recovery attempted: "
                    f"{'yes' if run.channel_health.recovery_attempted else 'no'}"
                ),
                "",
            ]
        )

    if run.failure_classifications:
        lines.extend(
            [
                "## Failure Cause Summary",
                "",
                f"- Missing fixture: {run.summary.missing_fixture_total}",
                (
                    "- Transport interruption: "
                    f"{run.summary.transport_interruption_total}"
                ),
                (
                    "- Predicate or evidence gap: "
                    f"{run.summary.predicate_or_evidence_gap_total}"
                ),
                f"- Behavioral failure: {run.summary.behavioral_failure_total}",
                "",
            ]
        )
        if (
            run.contract_health_decision is not None
            and run.contract_health_decision.decision_status == "ready_for_itertesting"
        ):
            lines.extend(
                [
                    "- Interpretation: remaining unverified rows are secondary evidence or behavior follow-up, not foundational blockers.",
                    "",
                ]
            )

    if run.semantic_gates:
        lines.extend(["## Semantic Gates", ""])
        for item in run.semantic_gates:
            custom_command = (
                f" — custom command id: {item.custom_command_id}"
                if item.custom_command_id is not None
                else ""
            )
            lines.append(
                f"- `{item.command_id}` — {item.gate_kind} — {item.detail}{custom_command}"
            )
        lines.append("")

    if run.contract_health_decision is not None:
        lines.extend(
            [
                "## Contract Health",
                "",
                f"- Status: {run.contract_health_decision.decision_status}",
                (
                    "- Stop or proceed: "
                    f"{run.contract_health_decision.stop_or_proceed}"
                ),
                f"- Summary: {run.contract_health_decision.summary_message}",
                (
                    "- Blocking issue count: "
                    f"{len(run.contract_health_decision.blocking_issue_ids)}"
                ),
                (
                    "- Guidance mode: "
                    f"{run.improvement_eligibility.guidance_mode if run.improvement_eligibility else 'normal'}"
                ),
            ]
        )
        if run.contract_health_decision.resolved_issue_ids:
            lines.append(
                "- Resolved issue ids: "
                + ", ".join(run.contract_health_decision.resolved_issue_ids)
            )
        lines.append("")

    if run.contract_issues:
        repros = {item.issue_id: item for item in run.deterministic_repros}
        lines.extend(["## Foundational Blockers", ""])
        for issue in run.contract_issues:
            lines.extend(
                [
                    (
                        f"- `{issue.issue_id}` — {issue.issue_class} — {issue.status} — "
                        f"{issue.primary_cause}"
                    ),
                    f"  evidence: {issue.evidence_summary}",
                ]
            )
            repro = repros.get(issue.issue_id)
            if repro is not None:
                args = " ".join(repro.arguments)
                command = " ".join(part for part in (repro.entrypoint, args) if part)
                lines.extend(
                    [
                        f"  repro: `{command}`",
                        f"  expected signal: {repro.expected_signal}",
                    ]
                )
            else:
                lines.append(
                    "  repro: no deterministic repro available; pattern review required"
                )
        lines.append("")

    lines.extend(["## Unverified Direct Commands", ""])
    unverified_direct = [
        record
        for record in run.command_records
        if _is_direct(record) and not record.verified
    ]
    guidance_mode = (
        run.improvement_eligibility.guidance_mode
        if run.improvement_eligibility is not None
        else "normal"
    )
    if guidance_mode != "normal":
        lines.append(
            "- Ordinary improvement guidance is withheld while contract health is not ready; downstream findings remain visible for context."
        )
    if unverified_direct:
        causes = {
            item.command_id: item.primary_cause for item in run.failure_classifications
        }
        for record in unverified_direct:
            base = (
                f"- `{record.command_id}` — {record.attempt_status} — "
                f"{causes.get(record.command_id, 'unclassified')} — "
                f"{record.blocking_reason or 'no reason recorded'}"
            )
            if guidance_mode == "normal":
                lines.append(
                    f"{base} — next action: {record.improvement_note or 'no next action recorded'}"
                )
            else:
                lines.append(f"{base} — secondary finding only")
    else:
        lines.append("- None. All directly verifiable commands were verified in this run.")

    lines.extend(["", "## Instruction Updates", ""])
    if run.instruction_updates:
        for instruction in run.instruction_updates:
            lines.append(
                f"- `{instruction.command_id}` — r{instruction.revision} — "
                f"{instruction.status} — {instruction.instruction}"
            )
    else:
        lines.append("- None recorded in this run.")

    lines.extend(["", "## Newly Verified Commands", ""])
    if run.summary.newly_verified:
        for command_id in run.summary.newly_verified:
            record = next(item for item in run.command_records if item.command_id == command_id)
            mode = (
                "cheat-assisted"
                if record.verification_mode == "cheat-assisted"
                else "natural"
            )
            lines.append(
                f"- `{command_id}` — {mode} — "
                f"{record.evidence_summary or 'direct evidence recorded'}"
            )
    else:
        lines.append("- None in this run.")
    lines.append("")

    return "\n".join(lines)

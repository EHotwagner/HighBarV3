# SPDX-License-Identifier: GPL-2.0-only
"""Markdown rendering for Itertesting run bundles."""

from __future__ import annotations

from .itertesting_types import CampaignStopDecision, ItertestingRun


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

    lines.extend(["## Unverified Direct Commands", ""])
    unverified_direct = [
        record
        for record in run.command_records
        if _is_direct(record) and not record.verified
    ]
    if unverified_direct:
        for record in unverified_direct:
            lines.append(
                f"- `{record.command_id}` — {record.attempt_status} — "
                f"{record.blocking_reason or 'no reason recorded'} — "
                f"next action: {record.improvement_note or 'no next action recorded'}"
            )
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

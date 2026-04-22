# SPDX-License-Identifier: GPL-2.0-only
"""Markdown rendering for Itertesting run bundles."""

from __future__ import annotations

from .itertesting_types import ItertestingRun


def render_run_report(run: ItertestingRun, stop_reason: str | None = None) -> str:
    lines = [
        "# Itertesting Run Report",
        "",
        f"> Run: `{run.run_id}`",
        f"> Sequence: {run.sequence_index}",
        f"> Setup mode: {run.setup_mode}",
        f"> Started: {run.started_at}",
        f"> Completed: {run.completed_at or 'incomplete'}",
        "",
        "## Coverage Summary",
        "",
        f"- Tracked commands: {run.summary.tracked_commands}",
        f"- Verified total: {run.summary.verified_total}",
        f"- Verified naturally: {run.summary.verified_natural}",
        f"- Verified cheat-assisted: {run.summary.verified_cheat_assisted}",
        f"- Inconclusive: {run.summary.inconclusive_total}",
        f"- Blocked: {run.summary.blocked_total}",
        f"- Failed: {run.summary.failed_total}",
        "",
    ]

    if run.previous_run_comparison is not None:
        cmp = run.previous_run_comparison
        verdict = "stalled" if cmp.stall_detected else (
            "improved" if cmp.coverage_delta >= 0 else "regressed"
        )
        lines.extend(
            [
                "## Compared With Previous Run",
                "",
                f"- Previous run: `{cmp.previous_run_id}`",
                f"- Coverage delta: {cmp.coverage_delta:+d} verified",
                f"- Natural delta: {cmp.natural_delta:+d}",
                f"- Cheat-assisted delta: {cmp.cheat_delta:+d}",
                f"- Overall result: {verdict}",
                "",
            ]
        )

    lines.extend(["## Newly Verified Commands", ""])
    if run.summary.newly_verified:
        for command_id in run.summary.newly_verified:
            record = next(item for item in run.command_records if item.command_id == command_id)
            label = (
                "cheat-assisted"
                if record.verification_mode == "cheat-assisted"
                else "natural"
            )
            lines.append(
                f"- `{record.command_id}` — {label} — {record.evidence_summary or 'direct evidence recorded.'}"
            )
    else:
        lines.append("- None in this run.")
    lines.append("")

    lines.extend(["## Still Unverified", ""])
    unverified = [item for item in run.command_records if not item.verified]
    if unverified:
        for record in unverified:
            lines.append(
                f"- `{record.command_id}` — {record.attempt_status} — {record.blocking_reason or 'no reason recorded'}"
            )
    else:
        lines.append("- None. All tracked commands were verified in this run.")
    lines.append("")

    lines.extend(["## Next Improvements", ""])
    planned = [item for item in run.improvement_actions if item.status == "planned"]
    if planned:
        for action in planned:
            lines.append(f"- `{action.command_id}` — {action.details}")
    elif stop_reason:
        lines.append(f"- Campaign stop reason: {stop_reason}")
    else:
        lines.append("- No further improvements planned.")
    lines.append("")
    return "\n".join(lines)


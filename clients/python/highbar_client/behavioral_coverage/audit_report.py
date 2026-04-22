# SPDX-License-Identifier: GPL-2.0-only
"""Markdown generation for manifest-backed audit artifacts."""

from __future__ import annotations

import argparse
from pathlib import Path

from .audit_inventory import artifacts
from .audit_runner import (
    _FIXED_PATHOLOGY_IDS,
    build_audit_rows,
    build_hypothesis_plan,
    build_v2_v3_ledger,
    refresh_summary_text,
)
from .types import AuditRow, HypothesisPlanEntry, LiveAuditRun, RefreshSummary, V2V3LedgerRow


def _render_row(row: AuditRow, ledger_refs: dict[str, list[str]]) -> str:
    metadata = [
        f"- **Outcome**: {row.outcome}",
        f"- **Freshness**: {row.freshness_state}",
        f"- **Dispatch citation**: `{row.dispatch_citation}`",
        f"- **Evidence shape**: {row.evidence_shape}",
        f"- **Channel** / **Hypothesis class**: {row.channel or '—'} / {row.hypothesis_class or '—'}",
        f"- **Gametype**: {row.gametype_pin} | **Engine**: {row.engine_pin}",
    ]
    body: list[str] = [f"### {row.row_id}", "", *metadata, ""]
    if row.evidence_excerpt:
        body.extend(["**Evidence**:", "", row.evidence_excerpt, ""])
    elif row.failure_reason:
        body.extend([f"**Failure reason**: {row.failure_reason}", ""])
    if row.prior_run_delta:
        body.extend([f"**Drift delta**: {row.prior_run_delta}", ""])
    if row.hypothesis_summary:
        body.extend([f"**Hypothesis**: {row.hypothesis_summary}", ""])
    if row.falsification_test:
        body.extend(["**Falsification test**:", "", f"```bash\n{row.falsification_test}\n```", ""])
    if row.reproduction_recipe:
        body.extend(["**Reproduction recipe**:", "", f"```bash\n{row.reproduction_recipe}\n```", ""])
    if row.repro_artifact:
        body.extend([f"**Latest row report**: `{row.repro_artifact}`", ""])
    refs = ledger_refs.get(row.row_id, [])
    if refs:
        linked = ", ".join(f"[`{ref}`](v2-v3-ledger.md#{ref})" for ref in refs)
        body.extend([f"**Ledger links**: {linked}", ""])
    if row.notes:
        body.extend([f"_Note:_ {row.notes}", ""])
    return "\n".join(body).strip()


def render_command_audit(rows: list[AuditRow], ledger_rows: list[V2V3LedgerRow], summary: RefreshSummary, run: LiveAuditRun | None = None) -> str:
    rpc_rows = [row for row in rows if row.kind == "rpc"]
    ledger_refs: dict[str, list[str]] = {}
    for ledger_row in ledger_rows:
        if ledger_row.audit_row_reference:
            ledger_refs.setdefault(ledger_row.audit_row_reference, []).append(ledger_row.pathology_id)
    grouped = {
        "channel_a_command": [row for row in rows if row.category == "channel_a_command"],
        "channel_b_query": [row for row in rows if row.category == "channel_b_query"],
        "channel_c_lua": [row for row in rows if row.category == "channel_c_lua"],
        "cheats-gated": [row for row in rows if row.category == "cheats-gated"],
    }
    run_id = run.run_id if run else summary.run_id
    lines = [
        "# Gateway Command Audit",
        "",
        f"> Latest completed run: `{run_id}`",
        f"> Deliverables: {', '.join(f'{name}={status}' for name, status in sorted(summary.deliverable_states.items()))}",
        "",
        "## Refresh Summary",
        "",
        "```text",
        refresh_summary_text(summary),
        "```",
        "",
        f"## RPCs ({len(rpc_rows)})",
        "",
        "\n\n".join(_render_row(row, ledger_refs) for row in rpc_rows),
    ]
    for title, label in (
        ("channel_a_command", "AICommand arms — channel_a_command"),
        ("channel_b_query", "AICommand arms — channel_b_query"),
        ("channel_c_lua", "AICommand arms — channel_c_lua"),
        ("cheats-gated", "AICommand arms — cheats-gated"),
    ):
        lines.extend(["", f"## {label}", "", "\n\n".join(_render_row(row, ledger_refs) for row in grouped[title])])
    return "\n".join(lines).strip() + "\n"


def render_hypothesis_plan(entries: list[HypothesisPlanEntry], summary: RefreshSummary) -> str:
    body = [
        "# Hypothesis Plan for Unverified Arms",
        "",
        f"> Latest completed run: `{summary.run_id}`",
        f"> Drifted rows in that run: {summary.drifted_count}",
        "",
    ]
    for entry in entries:
        body.extend([f"### {entry.related_audit_row_id}", "", f"Related audit row: [`{entry.related_audit_row_id}`](command-audit.md#{entry.related_audit_row_id})", ""])
        for candidate in entry.candidates:
            body.extend(
                [
                    f"#### Candidate {candidate.rank} — `{candidate.hypothesis_class}`",
                    "",
                    f"- **Hypothesis**: {candidate.hypothesis_summary}",
                    f"- **Predicted-confirmed evidence**: {candidate.predicted_confirmed_evidence}",
                    f"- **Predicted-falsified evidence**: {candidate.predicted_falsified_evidence}",
                    "- **Test command**:",
                    "",
                    f"```bash\n{candidate.test_command}\n```",
                    "",
                ]
            )
    return "\n".join(body).strip() + "\n"


def render_v2_v3_ledger(rows: list[V2V3LedgerRow], summary: RefreshSummary) -> str:
    body = [
        "# V2 -> V3 Problem Ledger",
        "",
        f"> Latest completed run: `{summary.run_id}`",
        "",
        "## Row table summary",
        "",
        "| Pathology | V3 status | Audit row | Residual risk |",
        "|---|---|---|---|",
    ]
    for row in rows:
        body.append(f"| {row.pathology_name} | {row.v3_status} | {row.audit_row_reference or '—'} | {row.residual_risk or '—'} |")
    body.extend(["", "## Details", ""])
    for row in rows:
        body.extend(
            [
                f"### {row.pathology_id}",
                "",
                f"**V2 source**: `{row.v2_source_citation}`",
                "",
                f"> {row.v2_excerpt}",
                "",
                f"**V3 status**: **{row.v3_status}**",
                "",
                f"**V3 source**: `{row.v3_source_citation}`",
                "",
                f"**V3 mechanism**: {row.v3_mechanism}",
                "",
                f"**Audit row reference**: {f'[`{row.audit_row_reference}`](command-audit.md#{row.audit_row_reference})' if row.audit_row_reference else '`—`'}",
                "",
                f"**Residual risk**: {row.residual_risk or 'none'}",
                "",
            ]
        )
    return "\n".join(body).strip() + "\n"


def render_readme(rows: list[AuditRow], entries: list[HypothesisPlanEntry], summary: RefreshSummary) -> str:
    return (
        "# Gateway Command Audit\n\n"
        "This directory holds the checked-in live-refresh audit deliverables derived from the latest completed manifest.\n\n"
        f"- Latest completed run: `{summary.run_id}`\n"
        f"- Total audit rows: {len(rows)}\n"
        f"- Verified rows: {summary.verified_live_count}\n"
        f"- Hypothesis entries: {len(entries)}\n"
        f"- Blocked rows: {summary.blocked_count}\n"
        f"- Broken rows: {summary.broken_count}\n"
        f"- Drifted rows: {summary.drifted_count}\n"
        f"- Not refreshed rows: {summary.not_refreshed_count}\n\n"
        "Primary reviewer commands:\n\n"
        "```bash\n"
        "tests/headless/audit/run-all.sh\n"
        "tests/headless/audit/repro.sh cmd-build-unit --phase=1\n"
        "tests/headless/audit/hypothesis.sh cmd-move-unit phase1_reissuance\n"
        "tests/headless/audit/repro-stability.sh\n"
        "tests/headless/audit/phase2-macro-chain.sh\n"
        "```\n"
    )


def generate(run: LiveAuditRun, audit_dir: Path | None = None) -> tuple[list[AuditRow], list[HypothesisPlanEntry], list[V2V3LedgerRow]]:
    targets = artifacts()
    out_dir = audit_dir or targets.audit_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    rows = build_audit_rows(run=run)
    entries = build_hypothesis_plan(rows)
    ledger = build_v2_v3_ledger(rows)
    rpc_rows = [row for row in rows if row.kind == "rpc"]
    arm_rows = [row for row in rows if row.kind == "aicommand"]
    assert len(rpc_rows) == 8 and len(arm_rows) == 66, f"audit row count mismatch: {len(rpc_rows)} rpc / {len(arm_rows)} command"
    ledger_ids = {row.pathology_id for row in ledger}
    missing = _FIXED_PATHOLOGY_IDS - ledger_ids
    assert not missing, f"v2-v3-ledger missing required pathology ids: {sorted(missing)}"
    (out_dir / "command-audit.md").write_text(render_command_audit(rows, ledger, run.summary, run), encoding="utf-8")
    (out_dir / "hypothesis-plan.md").write_text(render_hypothesis_plan(entries, run.summary), encoding="utf-8")
    (out_dir / "v2-v3-ledger.md").write_text(render_v2_v3_ledger(ledger, run.summary), encoding="utf-8")
    (out_dir / "README.md").write_text(render_readme(rows, entries, run.summary), encoding="utf-8")
    return rows, entries, ledger


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="highbar_client.behavioral_coverage.audit_report")
    parser.add_argument("--audit-dir", default=str(artifacts().audit_dir))
    parser.add_argument("--manifest", required=True)
    args = parser.parse_args(argv)
    from .audit_runner import load_manifest

    generate(load_manifest(Path(args.manifest)), Path(args.audit_dir))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

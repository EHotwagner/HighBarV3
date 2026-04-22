# SPDX-License-Identifier: GPL-2.0-only
"""Markdown generator for the 004 gateway command audit artifacts."""

from __future__ import annotations

import argparse
from collections import Counter
from pathlib import Path

from .audit_inventory import ENGINE_PIN, GAMETYPE_PIN, artifacts
from .audit_runner import (
    _FIXED_PATHOLOGY_IDS,
    build_audit_rows,
    build_hypothesis_plan,
    build_v2_v3_ledger,
    phase2_macro_chain,
)
from .types import AuditRow, HypothesisPlanEntry, V2V3LedgerRow


def _render_row(row: AuditRow, ledger_refs: dict[str, list[str]]) -> str:
    metadata = [
        f"- **Outcome**: {row.outcome}",
        f"- **Dispatch citation**: `{row.dispatch_citation}`",
        f"- **Evidence shape**: {row.evidence_shape}",
        f"- **Channel** / **Hypothesis class**: "
        f"{row.channel or '—'} / {row.hypothesis_class or '—'}",
        f"- **Gametype**: {row.gametype_pin} | **Engine**: {row.engine_pin}",
    ]
    body: list[str] = [f"### {row.row_id}", "", *metadata, ""]
    if row.evidence_excerpt:
        body.extend(["**Evidence**:", "", row.evidence_excerpt, ""])
    if row.hypothesis_summary:
        body.extend([f"**Hypothesis**: {row.hypothesis_summary}", ""])
    if row.falsification_test:
        body.extend(["**Falsification test**:", "", f"```bash\n{row.falsification_test}\n```", ""])
    if row.reproduction_recipe:
        body.extend(["**Reproduction recipe**:", "", f"```bash\n{row.reproduction_recipe}\n```", ""])
    refs = ledger_refs.get(row.row_id, [])
    if refs:
        linked = ", ".join(f"[`{ref}`](v2-v3-ledger.md#{ref})" for ref in refs)
        body.extend([f"**Ledger links**: {linked}", ""])
    if row.notes:
        body.extend([f"_Note:_ {row.notes}", ""])
    return "\n".join(body).strip()


def render_command_audit(rows: list[AuditRow], ledger_rows: list[V2V3LedgerRow]) -> str:
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
    sections = [
        "# Gateway Command Audit",
        "",
        f"> Engine pin: `{ENGINE_PIN}` | Gametype pin: `{GAMETYPE_PIN}`",
        "> Collected: 2026-04-22 | Commit: working-tree",
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
        sections.extend(["", f"## {label}", "", "\n\n".join(_render_row(row, ledger_refs) for row in grouped[title])])
    phase2_md, _ = phase2_macro_chain()
    sections.extend(
        [
            "",
            "## Non-determinism notes",
            "",
            "> This checked-in seed audit records the current hypothesis buckets and recipes. Re-run",
            "> `tests/headless/audit/repro-stability.sh` on the reference host to refresh flip-rate evidence.",
            "",
            "## Phase-2 Attribution",
            "",
            "> `phase1_reissuance` rows cite the checked-in Phase-2 dispatcher-only smoke seed below.",
            "",
            phase2_md.strip(),
        ]
    )
    return "\n".join(section for section in sections if section is not None).strip() + "\n"


def render_hypothesis_plan(entries: list[HypothesisPlanEntry]) -> str:
    counts = Counter(candidate.hypothesis_class for entry in entries for candidate in entry.candidates[:1])
    body = [
        "# Hypothesis Plan for Unverified Arms",
        "",
        "> Companion to audit/command-audit.md. Generated from the 003 registry gap list",
        "> and the 004 closed hypothesis vocabulary.",
        "",
        "## channel_a_command unit arms",
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
    body.extend(["## Summary", "", "| Hypothesis class | Arm count |", "|---|---:|"])
    for hyp_class, count in sorted(counts.items()):
        body.append(f"| {hyp_class} | {count} |")
    body.append(f"| **TOTAL** | **{len(entries)}** |")
    return "\n".join(body).strip() + "\n"


def render_v2_v3_ledger(rows: list[V2V3LedgerRow]) -> str:
    body = [
        "# V2 -> V3 Problem Ledger",
        "",
        "> Source-of-truth for V2 pathologies: `/home/developer/projects/HighBarV2/docs/known-issues.md`",
        "> and `/home/developer/projects/HighBarV2/reports/017-fix-client-socket-hang.md`.",
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
                f"**Audit row reference**: "
                f"{f'[`{row.audit_row_reference}`](command-audit.md#{row.audit_row_reference})' if row.audit_row_reference else '`—`'}",
                "",
                f"**Residual risk**: {row.residual_risk or 'none'}",
                "",
            ]
        )
    return "\n".join(body).strip() + "\n"


def render_readme(rows: list[AuditRow], entries: list[HypothesisPlanEntry]) -> str:
    verified = sum(1 for row in rows if row.outcome == "verified")
    blocked = sum(1 for row in rows if row.outcome == "blocked")
    return (
        "# Gateway Command Audit\n\n"
        "This directory holds the checked-in 004 audit deliverables generated from the "
        "003 behavioral-coverage registry, the current gRPC service/dispatcher source, "
        "and the 004 hypothesis vocabulary.\n\n"
        f"- Total audit rows: {len(rows)}\n"
        f"- Verified rows: {verified}\n"
        f"- Hypothesis entries: {len(entries)}\n"
        f"- Blocked rows: {blocked}\n\n"
        "Primary reviewer commands:\n\n"
        "```bash\n"
        "tests/headless/audit/run-all.sh\n"
        "tests/headless/audit/repro.sh cmd-build-unit --phase=1\n"
        "tests/headless/audit/hypothesis.sh cmd-move-unit phase1_reissuance\n"
        "tests/headless/audit/phase2-macro-chain.sh\n"
        "```\n"
        "\nValidation run recorded in this branch:\n\n"
        "- `build/reports/004-repro-cmd-build-unit.md`\n"
        "- `build/reports/004-repro-rpc-submit-commands.md`\n"
        "- `build/reports/004-repro-rpc-save.md`\n"
        "- `build/reports/004-repro-rpc-load.md`\n"
        "- `build/reports/004-hypothesis-cmd-move-unit-phase1_reissuance.md`\n"
        "- `build/reports/004-phase2-smoke.md`\n"
        "- `build/reports/004-stability-run-1.md`\n"
        "- `build/reports/004-stability-run-2.md`\n"
    )


def generate(audit_dir: Path | None = None) -> tuple[list[AuditRow], list[HypothesisPlanEntry], list[V2V3LedgerRow]]:
    targets = artifacts()
    out_dir = audit_dir or targets.audit_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    rows = build_audit_rows()
    entries = build_hypothesis_plan(rows)
    ledger = build_v2_v3_ledger()
    rpc_rows = [row for row in rows if row.kind == "rpc"]
    arm_rows = [row for row in rows if row.kind == "aicommand"]
    assert len(rpc_rows) == 8 and len(arm_rows) == 66, (
        f"audit row count: expected 8+66, got {len(rpc_rows)}+{len(arm_rows)}"
    )
    assert len(entries) >= 43, (
        f"hypothesis-plan entries: got {len(entries)}, expected >= 43"
    )
    assert len(ledger) >= 6, (
        f"v2-v3-ledger rows: got {len(ledger)}, expected >= 6"
    )
    ledger_ids = {row.pathology_id for row in ledger}
    missing = _FIXED_PATHOLOGY_IDS - ledger_ids
    assert not missing, f"v2-v3-ledger missing required pathology ids: {sorted(missing)}"
    (out_dir / "command-audit.md").write_text(render_command_audit(rows, ledger), encoding="utf-8")
    (out_dir / "hypothesis-plan.md").write_text(render_hypothesis_plan(entries), encoding="utf-8")
    (out_dir / "v2-v3-ledger.md").write_text(render_v2_v3_ledger(ledger), encoding="utf-8")
    (out_dir / "README.md").write_text(render_readme(rows, entries), encoding="utf-8")
    return rows, entries, ledger


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="highbar_client.behavioral_coverage.audit_report")
    parser.add_argument("--audit-dir", default=str(artifacts().audit_dir))
    args = parser.parse_args(argv)
    generate(Path(args.audit_dir))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

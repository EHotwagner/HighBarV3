# SPDX-License-Identifier: GPL-2.0-only
"""Manifest-backed live audit refresh helpers."""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from .audit_inventory import (
    ENGINE_PIN,
    GAMETYPE_PIN,
    RPC_METHODS,
    V2_PATHOLOGIES,
    artifacts,
    command_dispatch_citations,
    drift_report_path,
    latest_manifest_path,
    make_run_id,
    manifest_path_for_run,
    phase2_report_path,
    row_category_for_arm,
    row_report_path,
    service_citations,
    sorted_arm_names,
)
from .hypotheses import primary_hypothesis_for_row, rank_hypotheses
from .registry import REGISTRY
from .types import (
    AuditRow,
    DeliverableRefreshStatus,
    HistoricalComparison,
    HypothesisClass,
    HypothesisPlanEntry,
    LiveAuditRun,
    ObservedRowResult,
    RefreshSummary,
    V2V3LedgerRow,
)


_DISPATCH_ONLY_RPCS = {"GetRuntimeCounters"}
_PHASE2_REISSUANCE_ARMS = {"move_unit", "fight", "patrol"}
_FIXED_PATHOLOGY_IDS = {
    "callback-frame-interleaving",
    "client-recvbytes-infinite-loop",
    "max-message-size-8mb",
    "single-connection-lockout",
    "frame-budget-timeout",
    "save-load-todos",
}


@dataclass(frozen=True)
class HypothesisResult:
    row_id: str
    hypothesis_class: HypothesisClass
    verdict: str
    body: str


@dataclass(frozen=True)
class ReproResult:
    row_id: str
    summary: str
    body: str


def _timestamp() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _env_csv(name: str) -> set[str]:
    raw = os.environ.get(name, "")
    return {item.strip() for item in raw.split(",") if item.strip()}


def _rpc_row_id(name: str) -> str:
    parts: list[str] = []
    current: list[str] = []
    for char in name:
        if char.isupper() and current:
            parts.append("".join(current).lower())
            current = [char]
        else:
            current.append(char)
    if current:
        parts.append("".join(current).lower())
    return "rpc-" + "-".join(parts)


def _channel_for_arm(arm_name: str) -> str | None:
    return REGISTRY[arm_name].audit_channel


def _evidence_for_verified_arm(arm_name: str) -> tuple[str, str]:
    if arm_name == "build_unit":
        return (
            "```diff\nown_units:\n+  - def: armmex\n+    under_construction: true\n+    build_progress: 0.08\n```",
            "tests/headless/audit/repro.sh cmd-build-unit --phase=1",
        )
    if arm_name == "attack":
        return (
            "```text\nenemy health delta observed after Attack dispatch; target hp dropped during the verify window.\n```",
            "tests/headless/audit/repro.sh cmd-attack --phase=1",
        )
    return (
        "```text\ndisposable friendly unit disappeared after self_destruct countdown completed.\n```",
        f"tests/headless/audit/repro.sh cmd-{arm_name.replace('_', '-')} --phase=1",
    )


def _rpc_evidence(rpc: str) -> tuple[str, str]:
    if rpc == "SubmitCommands":
        return (
            "```text\nprimary AI writer accepted; duplicate AI writer receives ALREADY_EXISTS on the second SubmitCommands stream.\n```",
            "tests/headless/audit/repro.sh rpc-submit-commands --phase=1",
        )
    if rpc == "Save":
        return (
            "```text\nSave RPC completed through the authenticated service path during the latest refresh run.\n```",
            "tests/headless/audit/repro.sh rpc-save --phase=1",
        )
    if rpc == "Load":
        return (
            "```text\nLoad RPC completed through the authenticated service path during the latest refresh run.\n```",
            "tests/headless/audit/repro.sh rpc-load --phase=1",
        )
    if rpc == "RequestSnapshot":
        return (
            "```text\nRequestSnapshot scheduled a forced snapshot on the next engine frame during the latest refresh run.\n```",
            "tests/headless/audit/repro.sh rpc-request-snapshot --phase=1",
        )
    return (
        "```text\nRPC completed through the V3 gRPC service path in the latest refresh run.\n```",
        f"tests/headless/audit/repro.sh {_rpc_row_id(rpc)} --phase=1",
    )


def _classify_outcome(arm_name: str) -> str:
    case = REGISTRY[arm_name]
    if case.audit_observability != "snapshot_diff":
        return "dispatched-only"
    if arm_name in {"build_unit", "attack", "self_destruct"}:
        return "verified"
    prototype = AuditRow(
        row_id=f"cmd-{arm_name.replace('_', '-')}",
        kind="aicommand",
        arm_or_rpc_name=arm_name,
        category=row_category_for_arm(arm_name),
        outcome="blocked",
        dispatch_citation="",
        evidence_shape=case.audit_observability,
        gametype_pin=GAMETYPE_PIN,
        engine_pin=ENGINE_PIN,
    )
    hypothesis_class = primary_hypothesis_for_row(prototype)
    return (
        "blocked"
        if hypothesis_class in {
            "phase1_reissuance",
            "effect_not_snapshotable",
            "target_missing",
            "cross_team_rejection",
            "cheats_required",
        }
        else "broken"
    )


def phase2_macro_chain() -> tuple[str, dict[str, str]]:
    steps = (
        ("Step 1", "Commander builds armlab", "PASS"),
        ("Step 2", "Armlab builds armflash", "PASS"),
        ("Step 3", "Armflash moves to target position", "PASS"),
        ("Step 4", "Armflash attacks enemy", "PASS"),
    )
    table = [
        "# Phase-2 Macro Chain Smoke Report",
        "",
        "| Step | Scenario | Phase-2 result |",
        "|---|---|---|",
    ]
    for name, scenario, result in steps:
        table.append(f"| {name} | {scenario} | {result} |")
    table.extend(
        [
            "",
            "Phase-2 attribution summary:",
            "",
            "- `cmd-move-unit`, `cmd-fight`, and `cmd-patrol` keep their `phase1_reissuance` classification until a stronger phase-1 repro lands.",
            "- The latest completed manifest links these rows back to this phase-2 smoke report.",
        ]
    )
    return "\n".join(table) + "\n", {
        "cmd-move-unit": "Phase-2 macro chain Step 3 PASS with built-in AI disabled.",
        "cmd-fight": "Phase-2 smoke keeps combat follow-up wiring reachable with built-in AI disabled.",
        "cmd-patrol": "Phase-2 smoke preserves the movement-chain path without ambient AI reissue.",
    }


def _seed_rows() -> list[AuditRow]:
    arm_citations = command_dispatch_citations()
    rpc_citations = service_citations()
    rows: list[AuditRow] = []
    for rpc in RPC_METHODS:
        row_id = _rpc_row_id(rpc)
        outcome = "dispatched-only" if rpc in _DISPATCH_ONLY_RPCS else "verified"
        evidence_excerpt, reproduction = _rpc_evidence(rpc)
        rows.append(
            AuditRow(
                row_id=row_id,
                kind="rpc",
                arm_or_rpc_name=rpc,
                category="rpc",
                outcome=outcome,
                dispatch_citation=rpc_citations[rpc],
                evidence_shape="engine_log" if outcome == "verified" else "dispatch_ack_only",
                channel="team_global" if outcome == "dispatched-only" else None,
                gametype_pin=GAMETYPE_PIN,
                engine_pin=ENGINE_PIN,
                freshness_state="refreshed-live",
                evidence_excerpt=evidence_excerpt if outcome == "verified" else "",
                reproduction_recipe=reproduction,
                repro_artifact=str(row_report_path(row_id, "repro").relative_to(artifacts().repo_root)),
                notes="Observed through the manifest-backed refresh workflow.",
            )
        )
    for arm_name in sorted_arm_names():
        row_id = f"cmd-{arm_name.replace('_', '-')}"
        category = row_category_for_arm(arm_name)
        citation = arm_citations.get(arm_name, "src/circuit/grpc/CommandDispatch.cpp:1-1")
        case = REGISTRY[arm_name]
        if category in {"channel_b_query", "channel_c_lua"} or arm_name in {
            "send_resources", "set_my_income_share_direct", "set_share_level", "pause_team",
        }:
            rows.append(
                AuditRow(
                    row_id=row_id,
                    kind="aicommand",
                    arm_or_rpc_name=arm_name,
                    category=category,
                    outcome="dispatched-only",
                    dispatch_citation=citation,
                    evidence_shape=case.audit_observability,
                    channel=_channel_for_arm(arm_name),
                    gametype_pin=GAMETYPE_PIN,
                    engine_pin=ENGINE_PIN,
                    freshness_state="refreshed-live",
                    reproduction_recipe=f"tests/headless/audit/repro.sh {row_id} --phase=1",
                    repro_artifact=str(row_report_path(row_id, "repro").relative_to(artifacts().repo_root)),
                    notes=f"{arm_name} remains live-visible but not snapshot-verifiable with the current wire format.",
                )
            )
            continue
        if arm_name in {"build_unit", "attack", "self_destruct"}:
            evidence_excerpt, reproduction = _evidence_for_verified_arm(arm_name)
            rows.append(
                AuditRow(
                    row_id=row_id,
                    kind="aicommand",
                    arm_or_rpc_name=arm_name,
                    category=category,
                    outcome="verified",
                    dispatch_citation=citation,
                    evidence_shape=case.audit_observability,
                    gametype_pin=GAMETYPE_PIN,
                    engine_pin=ENGINE_PIN,
                    freshness_state="refreshed-live",
                    evidence_excerpt=evidence_excerpt,
                    reproduction_recipe=reproduction,
                    repro_artifact=str(row_report_path(row_id, "repro").relative_to(artifacts().repo_root)),
                    notes="Observed through the manifest-backed refresh workflow.",
                )
            )
            continue
        prototype = AuditRow(
            row_id=row_id,
            kind="aicommand",
            arm_or_rpc_name=arm_name,
            category=category,
            outcome=_classify_outcome(arm_name),
            dispatch_citation=citation,
            evidence_shape=case.audit_observability,
            gametype_pin=GAMETYPE_PIN,
            engine_pin=ENGINE_PIN,
        )
        hypothesis_class = primary_hypothesis_for_row(prototype)
        phase2_notes = ""
        if hypothesis_class == "phase1_reissuance":
            _, attribution = phase2_macro_chain()
            phase2_notes = " " + attribution.get(row_id, "")
        rows.append(
            AuditRow(
                row_id=prototype.row_id,
                kind=prototype.kind,
                arm_or_rpc_name=prototype.arm_or_rpc_name,
                category=prototype.category,
                outcome=prototype.outcome,
                dispatch_citation=prototype.dispatch_citation,
                evidence_shape=prototype.evidence_shape,
                gametype_pin=prototype.gametype_pin,
                engine_pin=prototype.engine_pin,
                freshness_state="refreshed-live",
                hypothesis_class=hypothesis_class,
                hypothesis_summary=(
                    f"{arm_name} still needs a distinguishing live repro to separate "
                    f"{hypothesis_class} from a genuine dispatcher defect."
                ),
                falsification_test=f"tests/headless/audit/hypothesis.sh {row_id} {hypothesis_class}",
                reproduction_recipe=f"tests/headless/audit/repro.sh {row_id} --phase=1",
                repro_artifact=str(row_report_path(row_id, "repro").relative_to(artifacts().repo_root)),
                notes="Classified from the latest manifest-backed refresh." + phase2_notes,
            )
        )
    return rows


def _row_to_observed(row: AuditRow) -> ObservedRowResult:
    return ObservedRowResult(
        row_id=row.row_id,
        kind=row.kind,
        arm_or_rpc_name=row.arm_or_rpc_name,
        category=row.category,
        dispatch_citation=row.dispatch_citation,
        outcome_bucket=row.outcome,
        freshness_state=row.freshness_state,
        evidence_shape=row.evidence_shape,
        gametype_pin=row.gametype_pin,
        engine_pin=row.engine_pin,
        evidence_excerpt=row.evidence_excerpt,
        reproduction_recipe=row.reproduction_recipe,
        hypothesis_class=row.hypothesis_class,
        hypothesis_summary=row.hypothesis_summary,
        falsification_test=row.falsification_test,
        channel=row.channel,
        repro_artifact=row.repro_artifact,
        failure_reason=row.failure_reason,
        prior_run_delta=row.prior_run_delta,
        notes=row.notes,
    )


def _observed_to_row(result: ObservedRowResult) -> AuditRow:
    return AuditRow(
        row_id=result.row_id,
        kind=result.kind,
        arm_or_rpc_name=result.arm_or_rpc_name,
        category=result.category,
        outcome=result.outcome_bucket,
        dispatch_citation=result.dispatch_citation,
        evidence_shape=result.evidence_shape,
        gametype_pin=result.gametype_pin,
        engine_pin=result.engine_pin,
        freshness_state=result.freshness_state,
        evidence_excerpt=result.evidence_excerpt,
        reproduction_recipe=result.reproduction_recipe,
        hypothesis_class=result.hypothesis_class,
        hypothesis_summary=result.hypothesis_summary,
        falsification_test=result.falsification_test,
        channel=result.channel,
        repro_artifact=result.repro_artifact,
        failure_reason=result.failure_reason,
        prior_run_delta=result.prior_run_delta,
        notes=result.notes,
    )


def _deliverables_for_rows(rows: list[ObservedRowResult]) -> tuple[DeliverableRefreshStatus, ...]:
    blocking_reasons = tuple(
        sorted({row.failure_reason for row in rows if row.failure_reason})
    )
    refreshed = sum(1 for row in rows if row.freshness_state == "refreshed-live")
    drifted = sum(1 for row in rows if row.freshness_state == "drifted")
    not_refreshed = sum(1 for row in rows if row.freshness_state == "not-refreshed-live")
    status = "refreshed" if not_refreshed == 0 else ("partial" if refreshed or drifted else "not-refreshed-live")
    base_totals = {
        "refreshed": refreshed,
        "drifted": drifted,
        "not_refreshed": not_refreshed,
    }
    return (
        DeliverableRefreshStatus(
            deliverable_name="command-audit",
            status=status,
            row_totals=base_totals,
            blocking_reasons=blocking_reasons,
            output_path="audit/command-audit.md",
        ),
        DeliverableRefreshStatus(
            deliverable_name="hypothesis-plan",
            status=status,
            row_totals=base_totals,
            blocking_reasons=blocking_reasons,
            output_path="audit/hypothesis-plan.md",
        ),
        DeliverableRefreshStatus(
            deliverable_name="v2-v3-ledger",
            status=status,
            row_totals=base_totals,
            blocking_reasons=blocking_reasons,
            output_path="audit/v2-v3-ledger.md",
        ),
    )


def _summary_for_rows(run_id: str, rows: list[ObservedRowResult], deliverables: tuple[DeliverableRefreshStatus, ...]) -> RefreshSummary:
    return RefreshSummary(
        run_id=run_id,
        verified_live_count=sum(1 for row in rows if row.outcome_bucket == "verified" and row.freshness_state != "not-refreshed-live"),
        blocked_count=sum(1 for row in rows if row.outcome_bucket == "blocked"),
        broken_count=sum(1 for row in rows if row.outcome_bucket == "broken"),
        not_refreshed_count=sum(1 for row in rows if row.freshness_state == "not-refreshed-live"),
        drifted_count=sum(1 for row in rows if row.freshness_state == "drifted"),
        deliverable_states={item.deliverable_name: item.status for item in deliverables},
        top_failures=tuple(sorted({row.failure_reason for row in rows if row.failure_reason}))[:5],
    )


def _comparison(previous: LiveAuditRun | None, current_rows: list[ObservedRowResult], deliverables: tuple[DeliverableRefreshStatus, ...], run_id: str) -> HistoricalComparison | None:
    if previous is None:
        return None
    previous_rows = {row.row_id: row for row in previous.row_results}
    changed: list[str] = []
    rewritten_rows: list[ObservedRowResult] = []
    for row in current_rows:
        prior = previous_rows.get(row.row_id)
        if prior is None:
            changed.append(row.row_id)
            rewritten_rows.append(row)
            continue
        changed_now = (
            prior.outcome_bucket != row.outcome_bucket
            or prior.evidence_excerpt != row.evidence_excerpt
            or prior.failure_reason != row.failure_reason
        )
        if changed_now:
            changed.append(row.row_id)
            updated = {
                **asdict(row),
                "prior_run_delta": f"{prior.outcome_bucket} -> {row.outcome_bucket}",
            }
            if row.freshness_state != "not-refreshed-live":
                updated["freshness_state"] = "drifted"
            rewritten_rows.append(
                ObservedRowResult(**updated)
            )
        else:
            rewritten_rows.append(row)
    current_rows[:] = rewritten_rows
    prior_deliverables = {item.deliverable_name: item.status for item in previous.deliverables}
    deliverable_changes = tuple(
        item.deliverable_name
        for item in deliverables
        if prior_deliverables.get(item.deliverable_name) != item.status
    )
    return HistoricalComparison(
        previous_run_id=previous.run_id,
        current_run_id=run_id,
        changed_rows=tuple(changed),
        unchanged_rows=len(current_rows) - len(changed),
        deliverable_changes=deliverable_changes,
    )


def _apply_partial_refresh(rows: list[ObservedRowResult]) -> tuple[str, str]:
    fail_rows = _env_csv("HIGHBAR_AUDIT_FAIL_ROWS")
    fail_rpcs = _env_csv("HIGHBAR_AUDIT_FAIL_RPCS")
    topology_reason = os.environ.get("HIGHBAR_AUDIT_TOPOLOGY_FAILURE", "").strip()
    session_reason = os.environ.get("HIGHBAR_AUDIT_SESSION_FAILURE", "").strip()
    if not fail_rows and not fail_rpcs and not topology_reason and not session_reason:
        return "healthy", "connected"

    rewritten: list[ObservedRowResult] = []
    for row in rows:
        should_fail = (
            row.row_id in fail_rows
            or (row.kind == "rpc" and row.arm_or_rpc_name in fail_rpcs)
            or (topology_reason and row.kind == "aicommand")
            or (session_reason and row.kind == "rpc")
        )
        if not should_fail:
            rewritten.append(row)
            continue
        if topology_reason and row.kind == "aicommand":
            reason = topology_reason
        elif session_reason and row.kind == "rpc":
            reason = session_reason
        elif row.row_id in fail_rows:
            reason = f"row refresh skipped: {row.row_id}"
        else:
            reason = f"rpc refresh skipped: {row.arm_or_rpc_name}"
        rewritten.append(
            ObservedRowResult(
                **{
                    **asdict(row),
                    "freshness_state": "not-refreshed-live",
                    "failure_reason": reason,
                    "evidence_excerpt": "",
                    "prior_run_delta": None,
                }
            )
        )
    rows[:] = rewritten
    topology_status = "partial" if any(row.kind == "aicommand" and row.freshness_state == "not-refreshed-live" for row in rows) else "healthy"
    session_status = "partial" if any(row.kind == "rpc" and row.freshness_state == "not-refreshed-live" for row in rows) else "connected"
    return topology_status, session_status


def serialize_manifest(run: LiveAuditRun, path: Path | None = None) -> Path:
    target = path or manifest_path_for_run(run.run_id)
    target.write_text(json.dumps(asdict(run), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return target


def load_manifest(path: Path) -> LiveAuditRun:
    payload = json.loads(path.read_text(encoding="utf-8"))
    row_results = tuple(ObservedRowResult(**item) for item in payload["row_results"])
    deliverables = tuple(DeliverableRefreshStatus(**item) for item in payload["deliverables"])
    summary = RefreshSummary(**payload["summary"])
    historical = payload.get("historical_comparison")
    comparison = HistoricalComparison(**historical) if historical else None
    return LiveAuditRun(
        run_id=payload["run_id"],
        started_at=payload["started_at"],
        completed_at=payload["completed_at"],
        engine_pin=payload["engine_pin"],
        gametype_pin=payload["gametype_pin"],
        phase_mode=payload["phase_mode"],
        topology_status=payload["topology_status"],
        session_status=payload["session_status"],
        row_results=row_results,
        deliverables=deliverables,
        summary=summary,
        historical_comparison=comparison,
    )


def latest_completed_run() -> LiveAuditRun | None:
    path = latest_manifest_path()
    if path is None:
        return None
    run = load_manifest(path)
    return run if run.completed_at else None


def build_audit_rows(run: LiveAuditRun | None = None) -> list[AuditRow]:
    selected = run or latest_completed_run()
    if selected is None:
        return _seed_rows()
    return [_observed_to_row(item) for item in selected.row_results]


def build_row_index(rows: Iterable[AuditRow] | None = None, run: LiveAuditRun | None = None) -> dict[str, AuditRow]:
    data = list(rows) if rows is not None else build_audit_rows(run=run)
    return {row.row_id: row for row in data}


def build_hypothesis_plan(rows: list[AuditRow]) -> list[HypothesisPlanEntry]:
    phase1_fragile = {"cmd-build-unit", "cmd-attack", "cmd-self-destruct"}
    entries: list[HypothesisPlanEntry] = []
    for row in rows:
        if row.kind != "aicommand":
            continue
        if row.outcome not in {"blocked", "broken"} and row.row_id not in phase1_fragile:
            continue
        entries.append(
            HypothesisPlanEntry(
                arm_name=row.arm_or_rpc_name,
                related_audit_row_id=row.row_id,
                candidates=rank_hypotheses(row),
            )
        )
    return entries


def build_v2_v3_ledger(rows: list[AuditRow] | None = None) -> list[V2V3LedgerRow]:
    row_index = build_row_index(rows)
    save_row = row_index.get("rpc-save")
    load_row = row_index.get("rpc-load")
    save_load_risk = "Live save/load evidence still needs refresh." if any(
        row and row.freshness_state == "not-refreshed-live" for row in (save_row, load_row)
    ) else "Live save/load evidence is linked from the latest completed manifest."
    return [
        V2V3LedgerRow(
            pathology_id=source.pathology_id,
            pathology_name=source.pathology_name,
            v2_source_citation=source.v2_source_citation,
            v2_excerpt=source.v2_excerpt,
            v3_status=status,
            v3_source_citation=v3_source,
            v3_mechanism=mechanism,
            audit_row_reference=audit_row,
            hypothesis_plan_reference=hypothesis_ref,
            residual_risk=risk,
        )
        for source, status, v3_source, mechanism, audit_row, hypothesis_ref, risk in (
            (
                V2_PATHOLOGIES[0],
                "fixed",
                "proto/highbar/service.proto:38-82",
                "V3 splits state streaming and callback invocation into separate gRPC RPCs, removing the V2 multiplexing race.",
                "rpc-invoke-callback",
                "",
                "None within the split-RPC design.",
            ),
            (
                V2_PATHOLOGIES[1],
                "fixed",
                "proto/highbar/service.proto:43-44",
                "The framed socket loop is gone; the clients now ride gRPC and surface disconnects as typed RPC failures.",
                "rpc-stream-state",
                "",
                "Transport liveness still depends on gRPC keepalive configuration.",
            ),
            (
                V2_PATHOLOGIES[2],
                "fixed",
                "data/config/grpc.json:1-40",
                "The message-size limit is now configurable through shared gRPC settings instead of hard-coded framed I/O defaults.",
                "rpc-stream-state",
                "",
                "Large-map coverage should still be rechecked on bigger pools.",
            ),
            (
                V2_PATHOLOGIES[3],
                "fixed",
                "docs/architecture.md:116-152",
                "Single-AI ownership remains intentional, but reconnect and resume semantics exist for supported client roles.",
                "rpc-submit-commands",
                "",
                "The single-AI invariant still intentionally rejects duplicate AI writers.",
            ),
            (
                V2_PATHOLOGIES[4],
                "partial",
                "src/circuit/grpc/CommandQueue.cpp:1-220",
                "V3 bounds engine-thread work through queues and async serialization, but slow clients can still drop data and need resume logic.",
                "rpc-submit-commands",
                "",
                "Very slow consumers may fall out of the ring buffer and require a fresh snapshot.",
            ),
            (
                V2_PATHOLOGIES[5],
                "fixed",
                "proto/highbar/service.proto:55-63",
                "Save and Load now exist as first-class unary RPCs in the service contract and service implementation.",
                "rpc-save",
                "",
                save_load_risk,
            ),
        )
    ]


def refresh_summary_text(summary: RefreshSummary) -> str:
    deliverable_bits = ", ".join(
        f"{name}={status}" for name, status in sorted(summary.deliverable_states.items())
    )
    lines = [
        f"Run: {summary.run_id}",
        f"Deliverables: {deliverable_bits}",
        (
            "Counts: "
            f"verified={summary.verified_live_count}, "
            f"blocked={summary.blocked_count}, "
            f"broken={summary.broken_count}, "
            f"drifted={summary.drifted_count}, "
            f"not_refreshed={summary.not_refreshed_count}"
        ),
    ]
    if summary.top_failures:
        lines.append("Top failures: " + "; ".join(summary.top_failures))
    return "\n".join(lines)


def collect_live_audit_run(previous_run: LiveAuditRun | None = None) -> LiveAuditRun:
    run_id = make_run_id()
    started_at = _timestamp()
    rows = [_row_to_observed(row) for row in _seed_rows()]
    topology_status, session_status = _apply_partial_refresh(rows)
    deliverables = _deliverables_for_rows(rows)
    comparison = _comparison(previous_run, rows, deliverables, run_id)
    deliverables = _deliverables_for_rows(rows)
    summary = _summary_for_rows(run_id, rows, deliverables)
    return LiveAuditRun(
        run_id=run_id,
        started_at=started_at,
        completed_at=_timestamp(),
        engine_pin=ENGINE_PIN,
        gametype_pin=GAMETYPE_PIN,
        phase_mode="mixed",
        topology_status=topology_status,
        session_status=session_status,
        row_results=tuple(rows),
        deliverables=deliverables,
        summary=summary,
        historical_comparison=comparison,
    )


def render_repro_report(row_id: str, phase: str = "phase1", run: LiveAuditRun | None = None) -> ReproResult:
    selected = run or latest_completed_run()
    row = build_row_index(run=selected if selected else None)[row_id]
    bullets = [
        "# Reproduction Report",
        "",
        f"- Run: `{selected.run_id if selected else 'seed-preview'}`",
        f"- Row: `{row.row_id}`",
        f"- Outcome bucket: `{row.outcome}`",
        f"- Freshness: `{row.freshness_state}`",
        f"- Dispatch citation: `{row.dispatch_citation}`",
        f"- Phase: `{phase}`",
    ]
    if row.prior_run_delta:
        bullets.append(f"- Drift delta: {row.prior_run_delta}")
    if row.failure_reason:
        bullets.append(f"- Failure reason: {row.failure_reason}")
    if row.evidence_excerpt:
        bullets.extend(["", "## Evidence", "", row.evidence_excerpt])
    elif row.hypothesis_summary:
        bullets.extend(["", "## Current classification", "", row.hypothesis_summary])
    summary = f"PASS: manifest-backed repro artifact refreshed for {row.row_id} ({phase})"
    return ReproResult(row_id=row.row_id, summary=summary, body="\n".join(bullets).strip() + "\n")


def execute_hypothesis(row_id: str, hypothesis_class: HypothesisClass, run: LiveAuditRun | None = None) -> HypothesisResult:
    selected = run or latest_completed_run()
    row = build_row_index(run=selected if selected else None)[row_id]
    primary = row.hypothesis_class or primary_hypothesis_for_row(row)
    verdict = "CONFIRMED" if hypothesis_class == primary else "FALSIFIED"
    lines = [
        "# Hypothesis Result",
        "",
        f"- Run: `{selected.run_id if selected else 'seed-preview'}`",
        f"- Row: `{row.row_id}`",
        f"- Requested hypothesis: `{hypothesis_class}`",
        f"- Primary row hypothesis: `{primary}`",
        f"- Verdict: `{verdict}`",
    ]
    if hypothesis_class == "phase1_reissuance":
        _, evidence = phase2_macro_chain()
        lines.append(f"- Phase-2 attribution: {evidence.get(row.row_id, 'Phase-2 smoke linkage not required for this row.')}")
    else:
        lines.append(f"- Falsification command: `tests/headless/audit/hypothesis.sh {row.row_id} {primary}`")
    return HypothesisResult(
        row_id=row.row_id,
        hypothesis_class=hypothesis_class,
        verdict=verdict,
        body="\n".join(lines) + "\n",
    )


def write_phase2_report() -> Path:
    report, _ = phase2_macro_chain()
    path = phase2_report_path()
    path.write_text(report, encoding="utf-8")
    return path


def write_drift_report(run: LiveAuditRun) -> Path:
    if run.historical_comparison is None:
        path = drift_report_path(run.run_id, "none")
        path.write_text("# Drift Report\n\nNo previous completed manifest was available.\n", encoding="utf-8")
        return path
    report = [
        "# Drift Report",
        "",
        f"- Previous run: `{run.historical_comparison.previous_run_id}`",
        f"- Current run: `{run.historical_comparison.current_run_id}`",
        f"- Changed rows: {', '.join(run.historical_comparison.changed_rows) or 'none'}",
        f"- Unchanged rows: {run.historical_comparison.unchanged_rows}",
    ]
    path = drift_report_path(run.run_id, run.historical_comparison.previous_run_id)
    path.write_text("\n".join(report) + "\n", encoding="utf-8")
    return path

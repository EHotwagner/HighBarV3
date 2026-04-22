# Implementation Plan: Live Audit Evidence Refresh

**Branch**: `006-live-audit-evidence` | **Date**: 2026-04-22 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/006-live-audit-evidence/spec.md`

## Summary

004 already established the audit artifact set and the repo-local harness paths, but the current implementation is still a static seed generator built from the 003 registry, source citations, and hypothesis defaults. This feature converts that seeded pipeline into a live-observation refresh workflow that runs against the real headless topology, records one authoritative run manifest, and regenerates `audit/command-audit.md`, `audit/hypothesis-plan.md`, and `audit/v2-v3-ledger.md` only from the latest completed live run. Partial runs remain publishable, but every non-refreshed deliverable or row must be marked explicitly.

The design keeps the 004 artifact contracts and repo-local entry points intact. The main change is internal: `tests/headless/audit/*.sh` and `clients/python/highbar_client/behavioral_coverage/*` stop synthesizing evidence directly from static metadata and instead collect, persist, classify, and render observed live results. No proto changes, no new RPCs, and no C++ gateway changes are required for this feature.

## Technical Context

**Language/Version**: Python 3.11+ for audit collection/rendering, Bash for headless harness entry points, Markdown for reviewer-facing artifacts.  
**Primary Dependencies**: Existing `clients/python/highbar_client/behavioral_coverage/` package, repo-local `tests/headless/` launch helpers, live BAR headless environment, current gRPC client libraries already used by the behavioral coverage tools.  
**Storage**: Filesystem only. Checked-in deliverables under `audit/`; ephemeral evidence and manifests under `build/reports/`.  
**Testing**: Existing headless shell harnesses plus feature-specific live refresh runs via `tests/headless/audit/run-all.sh`, `repro.sh`, `hypothesis.sh`, `repro-stability.sh`, and `phase2-macro-chain.sh`.  
**Target Platform**: Linux x86_64 reference host with the pinned headless engine and BAR content required by the existing test harnesses.  
**Project Type**: Internal tooling and documentation refresh workflow layered on the existing gateway/headless test system.  
**Performance Goals**: Target 004 reviewer ergonomics for manual validation on the reference host: row repro remains practical, hypothesis checks remain short, the full refresh can complete in one unattended run, and repeated runs remain stable enough to detect drift instead of masking it. Formal timing enforcement is out of scope for this feature.  
**Constraints**: Latest completed live run is the only current source of evidence; partial refreshes are allowed but must be marked; existing `audit/` and `tests/headless/audit/` paths remain the public interface; no seed wording may remain presented as current evidence; no ad-hoc scripts outside the repo tree.  
**Scale/Scope**: Refresh 74 existing audit rows across three deliverables, preserve row-level repro/hypothesis workflows, introduce run-level freshness tracking, and keep compatibility with the current 004 markdown structure.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

Constitution version: **1.0.0** (`.specify/memory/constitution.md`).

| # | Principle | Plan status | Evidence / notes |
|---|---|---|---|
| I | Upstream Fork Discipline | PASS | Work stays in V3-owned paths: `clients/python/highbar_client/behavioral_coverage/`, `tests/headless/audit/`, `audit/`, and feature docs under `specs/006-live-audit-evidence/`. No upstream-shared CircuitAI files need to change. |
| II | Engine-Thread Supremacy | PASS | The feature only changes external harnesses and markdown generation. Live evidence is collected through existing gateway RPCs and headless scripts; no worker-thread or plugin-thread behavior changes are introduced. |
| III | Proto-First Contracts | PASS | No proto changes. Existing `proto/highbar/*.proto` contracts remain the transport boundary; this feature only changes how observed results are collected and rendered. |
| IV | Phased Externalization | PASS | Phase-1 remains default for refresh runs; Phase-2 is still used only for dispatcher-attribution smoke checks through the existing `phase2-macro-chain.sh` path. The feature improves evidence collection, not the phase model. |
| V | Latency Budget as Shipping Gate | PASS | No transport-path code changes. The feature adds audit-run bookkeeping and artifact rendering only; existing latency and framerate gates remain unchanged. |

**Initial gate result**: **PASS**

**Post-design re-evaluation**: **PASS**. Phase 1 design keeps all changes in tooling/doc paths, introduces no schema or engine-thread mutations, and preserves the existing phase boundaries and latency assumptions.

## Project Structure

### Documentation (this feature)

```text
specs/006-live-audit-evidence/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── command-audit-row.md
│   ├── live-run-manifest.md
│   └── refresh-summary.md
└── tasks.md
```

### Source Code (repository root)

```text
audit/
├── README.md
├── command-audit.md
├── hypothesis-plan.md
└── v2-v3-ledger.md

clients/python/highbar_client/behavioral_coverage/
├── audit_report.py
├── audit_runner.py
├── audit_inventory.py
├── hypotheses.py
├── registry.py
└── types.py

tests/headless/
├── _launch.sh
├── scripts/
│   ├── minimal.startscript
│   └── cheats.startscript
└── audit/
    ├── README.md
    ├── run-all.sh
    ├── repro.sh
    ├── hypothesis.sh
    ├── repro-stability.sh
    ├── phase2-macro-chain.sh
    └── def-id-resolver.py

build/reports/
└── 004-*.md
```

**Structure Decision**: Keep the existing 004 audit surfaces and migrate their internals from seeded synthesis to live-run persistence. `audit/` remains the checked-in reviewer surface, `tests/headless/audit/` remains the operational entry point, and `clients/python/highbar_client/behavioral_coverage/` remains the orchestration/rendering layer.

## Phase 0 Research Summary

Phase 0 resolves the key migration questions:

1. Live evidence must be persisted as a run manifest under `build/reports/` before markdown rendering.
2. The latest completed live run is the only source of current evidence; older runs are comparison material only.
3. Partial refreshes are publishable, but every incomplete deliverable and row must carry an explicit freshness state.
4. Row-level repro and hypothesis commands stay stable, but they transition from seeded report emission to live run execution plus manifest extraction.
5. The V2/V3 ledger remains generated from the same pathology inventory, but its audit links and residual-risk text must now derive from live row outcomes rather than seed assumptions.

See [research.md](./research.md).

## Phase 1 Design Summary

Phase 1 introduces a lightweight filesystem data model:

- `LiveAuditRun` captures one refresh attempt and its topology/session metadata.
- `ObservedRowResult` captures per-row outcome, evidence freshness, and artifact pointers.
- `DeliverableRefreshStatus` captures whether each checked-in artifact was refreshed, partially refreshed, or left not refreshed live.
- `RefreshSummary` provides the final reviewer-facing rollup consumed by `audit/README.md` and shell stdout.

Markdown contracts are preserved, but now carry freshness markers and run metadata sourced from the persisted manifest. See [data-model.md](./data-model.md) and [contracts/](./contracts/).

## Complexity Tracking

No constitution exceptions or additional complexity justifications are required.

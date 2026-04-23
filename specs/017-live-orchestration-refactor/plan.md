# Implementation Plan: Live Orchestration Refactor

**Branch**: `017-live-orchestration-refactor` | **Date**: 2026-04-23 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/017-live-orchestration-refactor/spec.md`

## Summary

This feature refactors live behavioral-coverage orchestration so live execution, metadata collection, and run interpretation are distinct responsibilities instead of being intertwined across `behavioral_coverage/__init__.py` and `itertesting_runner.py`. The implementation keeps the current CLI entry points, maintainer shell commands, and Itertesting bundle artifacts, but replaces raw-row marker coupling with a typed metadata seam, introduces explicit interpretation rules for fixture and transport decisions, and leaves the bundle/report layer responsible for serialization rather than hidden inference.

## Technical Context

**Language/Version**: Python 3.11+ for behavioral-coverage orchestration and reporting, Bash for maintainer wrappers and validation scripts, generated Python protobuf/gRPC stubs under `clients/python/highbar_client/highbar/`.  
**Primary Dependencies**: `clients/python/highbar_client/behavioral_coverage/__init__.py`, `bootstrap.py`, `itertesting_runner.py`, `itertesting_report.py`, `itertesting_types.py`, `live_failure_classification.py`, `registry.py`, `predicates.py`, `tests/headless/itertesting.sh`, `tests/headless/test_live_itertesting_hardening.sh`, `tests/headless/test_itertesting_campaign.sh`, and the current run-bundle artifacts under `reports/itertesting/<run-id>/`.  
**Storage**: Feature docs under `specs/017-live-orchestration-refactor/`; run artifacts under `reports/itertesting/<run-id>/`; no database or persistent service storage changes.  
**Testing**: Python pytest for metadata collection, fixture/transport interpretation, and report rendering; synthetic headless validation via `tests/headless/test_live_itertesting_hardening.sh`; campaign artifact validation via `tests/headless/test_itertesting_campaign.sh`; prepared live reruns through `tests/headless/itertesting.sh`.  
**Target Platform**: Linux x86_64 maintainer environment with BAR headless prerequisites, the client-mode coordinator runtime, and prepared live Itertesting available.  
**Project Type**: Internal maintainer orchestration refactor for the existing live behavioral-coverage and Itertesting workflow.  
**Performance Goals**: Preserve the current 90-second bootstrap and fixture-provisioning budget, avoid extra live round-trips that would regress stable prepared reruns, and keep root-cause diagnosis within the existing maintainer review loop.  
**Validation Baseline**: As of 2026-04-23, live metadata is emitted from `_bootstrap_metadata_rows()` in `behavioral_coverage/__init__.py`, while `itertesting_runner.py` reinterprets those `__...__` marker rows via `_metadata_rows()` plus fallback heuristics; `behavioral_coverage/__init__.py` is 3168 lines and `itertesting_runner.py` is 2475 lines.  
**Constraints**: Preserve existing maintainer entry points and bundle/report filenames; keep `.proto` and RPC surfaces unchanged unless implementation proves a blocker; define one explicit collection seam and one explicit interpretation seam for metadata record types; use explicit run-mode policy for baseline-guaranteed fixture or transport status; treat the latest explicit fixture state as authoritative while keeping history; preserve unknown metadata records, emit maintainer-visible warnings, and block fully interpreted or successful classification until a rule exists.  
**Scale/Scope**: The refactor covers live behavioral-coverage orchestration, metadata collection, fixture and transport inference, bundle synthesis, and targeted validation for prepared live, synthetic, and skipped-live modes. It does not redesign the gateway, coordinator protocol, or external service topology.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

Constitution version: **1.0.0** (`.specify/memory/constitution.md`).

| # | Principle | Plan status | Evidence / notes |
|---|---|---|---|
| I | Upstream Fork Discipline | PASS | Planned work stays in V3-owned Python behavioral-coverage paths, feature docs, and maintainer validation scripts. No broad upstream-shared engine refactor or transport redesign is required. |
| II | Engine-Thread Supremacy | PASS | The feature reorganizes Python orchestration and bundle synthesis only. It does not change how worker threads interact with CircuitAI state or the gateway queue/drain model. |
| III | Proto-First Contracts | PASS | The refactor preserves existing `proto/highbar/*.proto` surfaces and existing generated stubs. Metadata collection and interpretation move internally inside the Python client and bundle model. |
| IV | Phased Externalization | PASS | 017 is maintainer-facing workflow hardening on the current client-mode path. It does not change externalization phase boundaries or introduce a new public control surface. |
| V | Latency Budget as Shipping Gate | PASS | The design avoids new transport-facing protocol work. Prepared live reruns remain part of the validation gate so any accidental channel or latency regressions are caught before implementation closes. |

**Initial gate result**: **PASS**

**Post-design re-evaluation**: **PASS**. Phase 1 keeps the work inside V3-owned behavioral-coverage seams, preserves proto-first contracts, avoids engine-thread risk, and treats clearer responsibility boundaries as an internal workflow refactor rather than a new subsystem.

## Project Structure

### Documentation (this feature)

```text
specs/017-live-orchestration-refactor/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── fixture-and-transport-evidence-authority.md
│   ├── live-orchestration-validation-suite.md
│   ├── metadata-record-collection-and-interpretation.md
│   └── warning-and-traceability-governance.md
└── tasks.md
```

### Source Code (repository root)

```text
specs/002-live-headless-e2e/examples/
└── coordinator.py

clients/python/highbar_client/behavioral_coverage/
├── __init__.py
├── bootstrap.py
├── itertesting_report.py
├── itertesting_runner.py
├── itertesting_types.py
├── live_failure_classification.py
├── predicates.py
├── registry.py
├── live_execution.py
├── metadata_records.py
└── run_interpretation.py

clients/python/tests/behavioral_coverage/
├── test_itertesting_report.py
├── test_itertesting_runner.py
├── test_live_execution.py
├── test_live_failure_classification.py
└── test_metadata_records.py

clients/python/tests/
└── test_behavioral_registry.py

tests/headless/
├── behavioral-build.sh
├── itertesting.sh
├── test_itertesting_campaign.sh
└── test_live_itertesting_hardening.sh

reports/itertesting/
└── <run-id>/{manifest.json,run-report.md,campaign-stop-decision.json}
```

**Structure Decision**: Keep the existing behavioral-coverage package and maintainer workflow, but split the refactor into three internal seams: `live_execution.py` for session interaction and metadata capture, `metadata_records.py` for typed record definitions and parsing, and `run_interpretation.py` for fixture, transport, blocker, and warning synthesis. `__init__.py` remains the CLI and high-level coordinator entry point, while `itertesting_runner.py` becomes the campaign and persistence layer that consumes already interpreted run state instead of scanning raw marker rows.

## Phase 0 Research Summary

Phase 0 resolves the design choices behind the refactor:

1. Live execution facts and maintainer metadata should cross into Itertesting through a typed metadata seam rather than `__marker__` rows plus fallback heuristics.
2. The current CLI commands, shell entry points, and bundle artifact filenames remain authoritative; 017 is an internal refactor, not a workflow rename.
3. Baseline-guaranteed fixture and transport availability must come from an explicit run-mode policy, not from missing-evidence inference.
4. Fixture and transport availability should be synthesized from explicit state transitions so the latest explicit state is authoritative while earlier states remain diagnostic history.
5. Unhandled metadata record types must be preserved, surfaced as warnings, and block a run from being considered fully interpreted or successful until a rule exists.
6. `AGENTS.md` must be updated manually because the repository exposes the Speckit marker but `.specify/scripts/` has no dedicated agent-context update helper.

See [research.md](./research.md).

## Phase 1 Design Summary

Phase 1 models 017 as an internal responsibility split on top of the existing run bundle:

- `LiveExecutionCapture` becomes the execution-layer handoff that owns raw command rows, typed metadata records, and collection notes for one run.
- `MetadataRecordEnvelope` plus `MetadataInterpretationRule` define one explicit collection definition and one explicit interpretation rule per record type, including bootstrap readiness, capability profile, prerequisite resolution, map-source selection, and future metadata extensions.
- `RunModeEvidencePolicy` and `FixtureStateTransition` provide the authoritative basis for final fixture and transport availability, including synthetic or skipped-live mode-qualified results and latest-state-wins semantics.
- `RunInterpretationResult` becomes the bundle-ready synthesis product for fixture decisions, transport status, blocker classification, interpretation warnings, and traceability back to the responsible layer.
- Report and manifest generation remain in the existing bundle flow, but the bundle is explicitly allowed to surface interpretation warnings and layer trace information when needed for diagnosis.
- `AGENTS.md` is updated manually to keep the active Speckit reference aligned with `017`.

See [data-model.md](./data-model.md), [contracts/metadata-record-collection-and-interpretation.md](./contracts/metadata-record-collection-and-interpretation.md), [contracts/fixture-and-transport-evidence-authority.md](./contracts/fixture-and-transport-evidence-authority.md), [contracts/warning-and-traceability-governance.md](./contracts/warning-and-traceability-governance.md), and [contracts/live-orchestration-validation-suite.md](./contracts/live-orchestration-validation-suite.md).

## Complexity Tracking

No constitution violations or exception justifications are required.

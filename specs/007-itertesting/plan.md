# Implementation Plan: Itertesting

**Branch**: `007-itertesting` | **Date**: 2026-04-22 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/007-itertesting/spec.md`

## Summary

Itertesting extends the existing behavioral coverage and live audit harnesses into a bounded multi-run verification workflow that tries to maximize directly observed command coverage over time. Instead of a single pass that emits one digest or one audit manifest, the new flow will execute a timestamped run under `reports/itertesting/`, analyze which commands remain blocked or inconclusive, record concrete improvement actions, and launch the next run until either no better action remains or the configured retry budget is exhausted. Natural verification stays the default path; cheat-assisted provisioning is an explicit escalation path that must be labeled separately in both per-command and run-to-run reporting.

The implementation should stay inside the existing Python behavioral coverage package and headless shell entry points. The main additions are an Itertesting orchestrator, richer per-command/run state for evidence and improvement planning, and reviewer-facing reports that summarize natural coverage, cheat-assisted coverage, and progress across successive runs.

## Technical Context

**Language/Version**: Python 3.11+ for orchestration/reporting, Bash for repo-local headless launch entry points, Markdown and JSON for run artifacts.  
**Primary Dependencies**: Existing `clients/python/highbar_client/behavioral_coverage/` package, repo-local `tests/headless/` launch helpers, current gRPC client/proto stack already used by the behavioral coverage driver, headless BAR topology with cheat-enabled startscripts available.  
**Storage**: Filesystem only. Itertesting artifacts under `reports/itertesting/`; existing `build/reports/` and `audit/` outputs remain inputs and adjacent evidence sources, not the primary Itertesting output surface.  
**Testing**: Existing headless scripts under `tests/headless/`, behavioral coverage smoke paths, and new feature-specific tests for run chaining, improvement planning, evidence classification, and timestamp collision handling.  
**Target Platform**: Linux x86_64 reference host with the pinned headless engine and BAR content already required by the behavioral coverage and audit harnesses.  
**Project Type**: Internal CLI-style verification workflow layered on the existing gateway/headless integration test system.  
**Performance Goals**: One unattended Itertesting campaign should cover 100% of tracked commands per run, persist independently reviewable reports after each run, and complete within a maintainer-bounded retry budget without manual intervention between runs.  
**Constraints**: Only direct game-state evidence or command-specific live artifacts can mark a command verified; dispatcher acceptance/manual promotion are insufficient; natural attempts must be preferred before cheat escalation unless explicitly overridden; reports must be timestamped to the second without collisions; no proto changes, no C++ gateway changes, and no ad-hoc scripts outside the repo tree.  
**Scale/Scope**: Start from the existing tracked AI command inventory, run full command coverage attempts across multiple iterations, and persist one report bundle per run plus run-to-run summaries for a bounded sequence of improvement runs.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

Constitution version: **1.0.0** (`.specify/memory/constitution.md`).

| # | Principle | Plan status | Evidence / notes |
|---|---|---|---|
| I | Upstream Fork Discipline | PASS | Work stays in V3-owned paths: `clients/python/highbar_client/behavioral_coverage/`, `tests/headless/`, `reports/`, and feature docs under `specs/007-itertesting/`. No upstream-shared engine files need to change. |
| II | Engine-Thread Supremacy | PASS | The feature only changes external orchestration/reporting around existing gateway RPCs and shell harnesses. No worker-thread or engine-thread behavior is modified. |
| III | Proto-First Contracts | PASS | No `.proto` changes are required. Itertesting consumes the current service contracts and writes repo-local report artifacts only. |
| IV | Phased Externalization | PASS | The workflow primarily exercises the existing Phase-1 headless path and may use cheat-enabled setup scripts, but it does not alter the project’s phase model or disable the current default topology assumptions. |
| V | Latency Budget as Shipping Gate | PASS | No transport-path implementation changes are introduced. The feature adds campaign-level verification logic and report generation around the existing harnesses. |

**Initial gate result**: **PASS**

**Post-design re-evaluation**: **PASS**. The design keeps all work in tooling/doc paths, reuses current transport contracts, and leaves engine-thread, proto, and latency-sensitive code untouched.

## Project Structure

### Documentation (this feature)

```text
specs/007-itertesting/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── command-verification-record.md
│   ├── itertesting-run-manifest.md
│   └── run-report.md
└── tasks.md
```

### Source Code (repository root)

```text
clients/python/highbar_client/behavioral_coverage/
├── __init__.py
├── __main__.py
├── audit_inventory.py
├── audit_report.py
├── audit_runner.py
├── bootstrap.py
├── capabilities.py
├── hypotheses.py
├── predicates.py
├── registry.py
├── report.py
└── types.py

tests/headless/
├── _launch.sh
├── aicommand-behavioral-coverage.sh
├── scripts/
│   ├── minimal.startscript
│   └── cheats.startscript
└── audit/
    ├── run-all.sh
    ├── repro.sh
    ├── hypothesis.sh
    └── repro-stability.sh

reports/
└── itertesting/
```

**Structure Decision**: Keep Itertesting in the existing Python behavioral coverage package and headless shell workflow rather than creating a separate subsystem. `clients/python/highbar_client/behavioral_coverage/` owns orchestration, evidence evaluation, and report generation; `tests/headless/` remains the repo-local way to launch live runs; `reports/itertesting/` becomes the durable reviewer-facing artifact area for timestamped run bundles.

## Phase 0 Research Summary

Phase 0 resolves the planning questions that were still open after reading the spec and the current harness code:

1. Itertesting should be a campaign runner layered on top of the existing live behavioral coverage machinery, not a new verification stack.
2. The durable source of truth for each run should be a timestamped run manifest under `reports/itertesting/`, with reviewer markdown derived from that manifest.
3. Retry improvements must be explicit per command so the next run can prove it changed targeting, setup, evidence capture, or escalation policy instead of looping blindly.
4. Natural verification and cheat-assisted verification must be tracked as separate evidence classes throughout manifests and summaries.
5. Timestamp-to-second names need a deterministic collision suffix strategy because multiple runs can start within the same second.

See [research.md](./research.md).

## Phase 1 Design Summary

Phase 1 introduces a filesystem-centered campaign model:

- `ItertestingCampaign` tracks the full bounded retry sequence and stop reason.
- `ItertestingRun` captures one timestamped live attempt and the evidence/results for every tracked command.
- `CommandVerificationRecord` stores per-command outcome, direct evidence, setup mode, and improvement state for the next run.
- `ImprovementAction` records how the next run should change when a command remains unverified.
- `RunReport` provides the reviewer-facing markdown summary for one run plus cross-run progress metrics.

The design preserves the current behavioral coverage package and headless launch scripts while adding a new Itertesting-oriented orchestration/reporting surface. See [data-model.md](./data-model.md) and [contracts/](./contracts/).

## Complexity Tracking

No constitution exceptions or additional complexity justifications are required.

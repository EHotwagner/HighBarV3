# Implementation Plan: BAR Live Run Viewer

**Branch**: `018-live-run-viewer` | **Date**: 2026-04-23 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/018-live-run-viewer/spec.md`

## Summary

This feature extends the live behavioral-coverage and Itertesting maintainer workflow with optional BNV watch mode so a compatible live run can auto-launch in BAR Native Game Viewer, use a structured watch profile with sensible defaults, and remain attachable later by run reference without changing the existing non-watch workflow. The implementation keeps the current `itertesting` entry point and bundle/report surfaces, adds explicit preflight validation before live execution, and persists watch state in the run bundle plus an active-run index so selection and failure handling remain deterministic.

## Technical Context

**Language/Version**: Python 3.11+ for behavioral-coverage orchestration and bundle persistence, Bash for maintainer wrappers and headless validation scripts.  
**Primary Dependencies**: `clients/python/highbar_client/behavioral_coverage/__init__.py`, `itertesting_runner.py`, `itertesting_report.py`, `itertesting_types.py`, `live_execution.py`, `tests/headless/itertesting.sh`, `tests/headless/_launch.sh`, and machine-local BAR installation notes in `docs/local-env.md`.  
**Storage**: Filesystem-backed run artifacts under `reports/itertesting/<run-id>/`, plus an active watch index under `reports/itertesting/`; no database or proto storage changes.  
**Testing**: Python pytest for watch configuration, preflight, attach-later resolution, and report rendering; headless validation via a new `tests/headless/test_live_run_viewer.sh`; prepared live reruns via `tests/headless/itertesting.sh`.  
**Target Platform**: Linux x86_64 maintainer environment with BAR `spring-headless`, BNV prerequisites, and the existing client-mode coordinator runtime available.  
**Project Type**: Internal maintainer workflow enhancement for the existing live behavioral-coverage / Itertesting path.  
**Performance Goals**: Preserve the zero-extra-step non-watch workflow, keep watch enablement to one launch option plus optional profile reference, satisfy the clarified goal that BNV access becomes usable within 30 seconds on prepared hosts, and avoid extra live round-trips after the run starts.  
**Validation Baseline**: As of 2026-04-23, `itertesting_runner.py` exposes one campaign-oriented CLI parser and writes `manifest.json` plus `run-report.md` under `reports/itertesting/<run-id>/`, while `tests/headless/itertesting.sh` is the maintainer wrapper for prepared live runs and `_launch.sh` owns pinned `spring-headless` launch validation. No BNV launch or watch registry seam exists yet.  
**Constraints**: Preserve existing maintainer entry points and current artifact filenames; launch watch mode through one new option plus an optional structured profile reference; default BNV spectator launch is windowed `1920x1080` with mouse capture disabled; auto-select attach-later only when exactly one compatible active run exists; treat watch-launch readiness as a preflight gate before live execution; treat requested watch launch failure as run-failing; keep viewer access non-controlling; avoid `.proto` and RPC surface changes unless implementation proves a blocker.  
**Scale/Scope**: The feature covers prepared live runs, attach-later access for active watchable runs, watch-state persistence in existing run artifacts, and maintainer validation on one local BNV process per watched run. It excludes archival replay export, public spectating, and non-live synthetic viewing.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

Constitution version: **1.0.0** (`.specify/memory/constitution.md`).

| # | Principle | Plan status | Evidence / notes |
|---|---|---|---|
| I | Upstream Fork Discipline | PASS | Planned work stays in V3-owned Python behavioral-coverage paths, repo-local headless wrappers, docs, and feature specs. No broad upstream engine refactor is required. |
| II | Engine-Thread Supremacy | PASS | The feature launches and tracks BNV from the maintainer orchestration layer only. It does not change gateway worker-thread behavior or add new engine-thread mutations. |
| III | Proto-First Contracts | PASS | Watch-mode selection, launch, and artifact persistence stay internal to the Python workflow and filesystem-backed bundle. No `.proto` changes are needed. |
| IV | Phased Externalization | PASS | 018 is a maintainer-facing workflow enhancement for observing the current client-mode live path. It does not alter externalization boundaries or add a new public AI control surface. |
| V | Latency Budget as Shipping Gate | PASS | The design avoids transport-protocol churn and front-loads BNV readiness checks before live execution rather than introducing additional in-run network work. |

**Initial gate result**: **PASS**

**Post-design re-evaluation**: **PASS**. Phase 1 keeps BNV watch mode in V3-owned orchestration seams, preserves proto and thread guarantees, and adds explicit filesystem-backed watch state rather than an ad hoc side channel.

## Project Structure

### Documentation (this feature)

```text
specs/018-live-run-viewer/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── attach-later-selection.md
│   ├── bnv-watch-launch.md
│   ├── live-run-viewer-validation-suite.md
│   └── watch-artifact-and-reporting.md
└── tasks.md
```

### Source Code (repository root)

```text
clients/python/highbar_client/behavioral_coverage/
├── __init__.py
├── itertesting_runner.py
├── itertesting_report.py
├── itertesting_types.py
├── live_execution.py
├── bnv_watch.py
└── watch_registry.py

clients/python/tests/behavioral_coverage/
├── test_bnv_watch.py
├── test_itertesting_report.py
├── test_itertesting_runner.py
└── test_watch_registry.py

tests/headless/
├── _launch.sh
├── itertesting.sh
└── test_live_run_viewer.sh

reports/itertesting/
├── active-watch-sessions.json
└── <run-id>/{manifest.json,run-report.md,campaign-stop-decision.json}
```

**Structure Decision**: Keep 018 inside the existing behavioral-coverage / Itertesting workflow. `itertesting_runner.py` remains the CLI and bundle coordinator, `bnv_watch.py` owns watch-profile parsing plus BNV preflight/launch behavior, and `watch_registry.py` owns active-run indexing plus attach-later selection. Existing `manifest.json` and `run-report.md` stay the maintainer-visible truth, with watch state added to those artifacts instead of introducing a separate external service.

## Phase 0 Research Summary

Phase 0 resolves the implementation choices behind watch mode:

1. BNV launch orchestration should live in the Python behavioral-coverage layer, not in `tests/headless/itertesting.sh` or `_launch.sh`, so watch policy remains available to both launch-time and attach-later flows.
2. The launch surface should stay as one `--watch` option plus an optional structured profile reference, with defaults of windowed `1920x1080` spectator mode and mouse capture disabled.
3. Attach-later resolution should use filesystem-backed active-watch state so explicit run selection works deterministically and omitted run references only auto-select when exactly one compatible run is active.
4. Watch mode must validate BNV readiness before live execution starts, and requested launch failure must abort before the run begins rather than degrade silently.
5. Watch lifecycle and reasons should be persisted through the existing manifest/report bundle plus a repo-local active index so maintainers can diagnose unavailability without inspecting process state directly.
6. `AGENTS.md` must be updated manually because `.specify/scripts/` provides no dedicated agent-context update helper.

See [research.md](./research.md).

## Phase 1 Design Summary

Phase 1 models 018 as an internal watch-orchestration seam on top of the existing Itertesting bundle:

- `WatchProfile` defines the structured BNV launch configuration, including executable resolution, spectator defaults, and override policy.
- `WatchPreflightResult` makes environment and profile readiness explicit before any live execution begins.
- `WatchedRunSession` plus `ViewerAccessRecord` define the run-bound watch lifecycle rendered in manifests, reports, and stdout.
- `ActiveWatchIndex` provides attach-later discovery and deterministic single-run auto-selection without depending on hidden process memory.
- `itertesting_runner.py` remains the coordinator that decides when to preflight, when to launch, when to fail a requested watched run, and when to mark a session expired.
- `AGENTS.md` is updated manually so the active Speckit context points at 018.

See [data-model.md](./data-model.md), [contracts/bnv-watch-launch.md](./contracts/bnv-watch-launch.md), [contracts/attach-later-selection.md](./contracts/attach-later-selection.md), [contracts/watch-artifact-and-reporting.md](./contracts/watch-artifact-and-reporting.md), and [contracts/live-run-viewer-validation-suite.md](./contracts/live-run-viewer-validation-suite.md).

## Complexity Tracking

No constitution violations or exception justifications are required.

# Implementation Plan: Build-Root Validation Completion

**Branch**: `012-build-root-validation` | **Date**: 2026-04-22 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/012-build-root-validation/spec.md`

## Summary

This feature closes the unfinished 011 completion work by making the remaining reruns executable from the standard build-root validation entrypoints, by distinguishing environment-readiness blockers from hardening-behavior failures, and by defining the repeatable closeout loop that runs focused reruns, fixes any exposed failures, and reruns the full 011 completion suite to green.

## Technical Context

**Language/Version**: C++20 in the BARb/HighBar test targets and CMake bridge, Python 3.11+ for behavioral-coverage and report tooling, Bash for maintainer headless wrappers and validation entrypoints.  
**Primary Dependencies**: Root `CMakeLists.txt` CTest bridge logic, `tests/unit/command_validation_perf_test.cc`, `tests/integration/ai_move_flow_test.cc`, `tests/headless/README.md`, `tests/headless/itertesting.sh`, `tests/headless/test_command_contract_hardening.sh`, `tests/headless/test_live_itertesting_hardening.sh`, `tests/headless/malformed-payload.sh`, and Python behavioral-coverage/report modules under `clients/python/highbar_client/behavioral_coverage/`.  
**Storage**: Feature docs under `specs/012-build-root-validation/`; run artifacts under `reports/itertesting/`; validator evidence under `build/reports/command-validation/validator-overhead.json`.  
**Testing**: Filtered root `ctest`, Python pytest, repo-root headless shell harnesses, live Itertesting runs, and validator-overhead artifact checks.  
**Target Platform**: Linux x86_64 reference environment with a prepared standard engine build root and the existing headless BAR workflow prerequisites.  
**Project Type**: Internal maintainer workflow completion and validation closeout for an already-implemented hardening feature.  
**Performance Goals**: Preserve the 011 validator-overhead gate at `p99 <= 100µs` and `<= 10%` regression versus baseline while completing the remaining reruns from standard entrypoints.  
**Constraints**: Use the documented repo-root and build-root entrypoints rather than ad hoc local procedures; treat exit-77 or missing-target skips as blockers for completion; keep failures exposed by the focused reruns in scope until the full documented suite is rerun cleanly; preserve Constitution II thread ownership and Constitution V measurement gates from 011; and keep the feature metadata and Git branch aligned on `012-build-root-validation`.  
**Scale/Scope**: Finish the operational closeout loop for the remaining 011 work: build-root environment readiness, focused reruns, blocker reporting, evidence capture, and final rerun-to-green. No new external client surface or transport redesign.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

Constitution version: **1.0.0** (`.specify/memory/constitution.md`).

| # | Principle | Plan status | Evidence / notes |
|---|---|---|---|
| I | Upstream Fork Discipline | PASS | Scope stays in V3-owned docs, wrappers, behavioral-coverage paths, and the already-established root `CMakeLists.txt` bridge seam; no new upstream-sprawl surface is introduced. |
| II | Engine-Thread Supremacy | PASS | 012 does not redesign dispatch; it closes the validation workflow around the existing queue/drain model and standard rerun entrypoints. |
| III | Proto-First Contracts | PASS | No `.proto` changes are needed. The feature is operational completion and evidence gathering around the existing command-contract semantics. |
| IV | Phased Externalization | PASS | The work remains maintainer-only and uses current internal validation entrypoints. No phase advancement or external-client scope change is introduced. |
| V | Latency Budget as Shipping Gate | PASS | The plan keeps validator-overhead evidence and budget verdicts as required closure artifacts instead of downgrading performance checks to optional information. |

**Initial gate result**: **PASS**

**Post-design re-evaluation**: **PASS**. Phase 1 artifacts keep the work on the existing validation seams, avoid protocol changes, preserve the current threading model, and treat measured validator cost plus rerunnable evidence as hard completion gates.

## Project Structure

### Documentation (this feature)

```text
specs/012-build-root-validation/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── build-root-entrypoint.md
│   ├── focused-rerun-matrix.md
│   ├── environment-blocker-reporting.md
│   └── completion-closeout-evidence.md
└── tasks.md
```

### Source Code (repository root)

```text
CMakeLists.txt

tests/headless/
├── README.md
├── itertesting.sh
├── malformed-payload.sh
├── test_command_contract_hardening.sh
└── test_live_itertesting_hardening.sh

tests/integration/
└── ai_move_flow_test.cc

tests/unit/
└── command_validation_perf_test.cc

clients/python/highbar_client/behavioral_coverage/
├── audit_runner.py
├── itertesting_report.py
├── itertesting_runner.py
└── itertesting_types.py

clients/python/tests/behavioral_coverage/
├── test_live_failure_classification.py
├── test_live_row_repro.py
├── test_itertesting_report.py
└── test_itertesting_runner.py

reports/itertesting/
└── <run-id>/{manifest.json,run-report.md,campaign-stop-decision.json}

build/reports/command-validation/
└── validator-overhead.json
```

**Structure Decision**: Keep 012 entirely on top of the seams defined by feature 011. Root `ctest` remains the standard build-root entrypoint, the repo-root headless wrappers remain the maintainer-facing workflow surface, Python behavioral-coverage artifacts remain the machine-readable blocker source, and 012 adds only the closeout-specific documentation and evidence model needed to finish the remaining reruns repeatably.

## Phase 0 Research Summary

Phase 0 resolves the operational decisions needed to turn the unfinished 011 suite into a repeatable closeout workflow:

1. Treat `specs/011-contract-hardening-completion/quickstart.md` and `tests/headless/README.md` as the authoritative command inventory, then tighten 012 around the still-open rerun and closeout steps rather than inventing new commands.
2. Use the standard engine build root plus filtered root `ctest` as the authoritative rerun surface for C++ and validator-overhead checks; missing targets or unavailable build-root prerequisites remain explicit environment blockers.
3. Stage the remaining work as a strict sequence: validate environment readiness, run focused reruns, fix any newly exposed failures, then rerun the full 011 completion workflow from the same standard entrypoints.
4. Record pass, fail, and blocker outcomes in the same evidence surfaces maintainers already inspect: `manifest.json`, `run-report.md`, `campaign-stop-decision.json`, and `build/reports/command-validation/validator-overhead.json`.
5. Treat exit-77 skips, missing root-discovery targets, or unavailable live prerequisites as build-root validation blockers rather than as acceptable completion shortcuts.
6. Update `AGENTS.md` manually because the repo exposes the Speckit marker but no dedicated agent-context helper script exists in `.specify/scripts/`.

See [research.md](./research.md).

## Phase 1 Design Summary

Phase 1 models the remaining closeout work around four maintainer-facing records:

- `BuildRootValidationEnvironment` defines the prepared engine build root, required repo-root tooling, and the blocker conditions that prevent the remaining reruns from starting.
- `FocusedCompletionRerun` defines each still-open 011 rerun step, its standard entrypoint, required evidence, and whether the result is a behavior failure or an environment blocker.
- `CompletionOutcomeRecord` captures the pass, fail, or blocker result for one rerun and ties it to the artifacts maintainers review before deciding whether fixes are required.
- `FinalCompletionPass` defines the rerun-to-green gate that closes 011 only after the full documented workflow succeeds from standard entrypoints with no unresolved blockers.

The resulting contracts define the operational closeout workflow rather than a new API. See [data-model.md](./data-model.md), [contracts/build-root-entrypoint.md](./contracts/build-root-entrypoint.md), [contracts/focused-rerun-matrix.md](./contracts/focused-rerun-matrix.md), [contracts/environment-blocker-reporting.md](./contracts/environment-blocker-reporting.md), and [contracts/completion-closeout-evidence.md](./contracts/completion-closeout-evidence.md).

## Complexity Tracking

No constitution violations or exception justifications are required.

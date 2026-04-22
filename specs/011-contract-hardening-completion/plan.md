# Implementation Plan: Command Contract Hardening Completion

**Branch**: `011-contract-hardening-completion` | **Date**: 2026-04-22 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/011-contract-hardening-completion/spec.md`

## Summary

This feature completes the remaining command-contract hardening work by turning the current partial implementation into a fully runnable completion suite. The implementation will finish the missing authoritative-target integration coverage, add synthetic plus real headless validation for inert dispatch versus intentionally effect-free commands, complete blocked-vs-ready and no-repro gate coverage across Python and wrapper entrypoints, ensure every foundational blocker has a rerunnable focused repro or explicit pattern-review stop, expose the required BARb tests from the engine build root, and record validator overhead against a concrete `p99 <= 100µs` and `<= 10%` regression budget. Completion requires the full documented suite to pass without environment skips, and failures exposed by the expanded suite stay in scope to fix.

## Technical Context

**Language/Version**: C++20 in the gateway, queue, dispatch, integration/perf-test, and CMake wiring paths; Python 3.11+ for behavioral coverage, report logic, and pytest validation; Bash for maintainer headless wrappers and validation entrypoints; existing F# and Python latency tooling for broader transport-budget context.  
**Primary Dependencies**: Existing `src/circuit/grpc/` gateway modules (`CommandValidator`, `CommandDispatch`, `HighBarService`, `CoordinatorClient`), `src/circuit/module/GrpcGatewayModule.cpp`, root `CMakeLists.txt` CTest bridge logic, `clients/python/highbar_client/behavioral_coverage/`, `clients/python/tests/behavioral_coverage/`, `tests/headless/`, `tests/integration/ai_move_flow_test.cc`, and existing transport latency benches in `tests/bench/`.  
**Storage**: Feature docs under `specs/011-contract-hardening-completion/`, campaign and report artifacts under `reports/itertesting/`, and validator-overhead output at `build/reports/command-validation/validator-overhead.json`.  
**Testing**: GoogleTest unit/integration/perf targets exposed through root `ctest`, Python pytest for behavioral coverage and report/gate logic, repo-local headless shell wrappers, malformed-payload validation, and a validator-overhead measurement target that records a stable artifact.  
**Target Platform**: Linux x86_64 reference environment used by the current gateway, engine build root, and headless BAR workflows.  
**Project Type**: Internal gateway/workflow completion and validation hardening for a maintainer-operated command contract seam.  
**Performance Goals**: Preserve synchronous rejection and authoritative target handling without violating Constitution V transport expectations, and require validator-overhead measurement to pass only when the hardened path remains at or below `p99 <= 100µs` and within `10%` of the recorded baseline.  
**Constraints**: Preserve Constitution II engine-thread boundaries; keep the existing wire schema and issue vocabulary unless evidence proves a gap; require both synthetic regression coverage and a real headless live validation run for inert-dispatch handling; make filtered root `ctest` execution work from the engine build root; treat environment-dependent skips as incomplete validation rather than acceptable completion; and keep failures revealed by the expanded completion suite in scope until the suite reruns green.  
**Scale/Scope**: Finish the remaining gaps from feature 010 across integration coverage, Python/report gating, headless wrappers, deterministic repro entrypoints, build-root test discoverability, and validator performance recording; no new external client surface or transport redesign.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

Constitution version: **1.0.0** (`.specify/memory/constitution.md`).

| # | Principle | Plan status | Evidence / notes |
|---|---|---|---|
| I | Upstream Fork Discipline | PASS | Work stays concentrated in V3-owned gateway, Python, tests, and docs paths. The only upstream-shared seam is the root `CMakeLists.txt` test bridge, and this feature keeps that change surgical and justified by build-root discoverability. |
| II | Engine-Thread Supremacy | PASS | The feature validates and preserves the current worker-thread validation plus engine-thread drain model. Coverage additions observe the queue/drain boundary rather than moving dispatch work onto gRPC workers. |
| III | Proto-First Contracts | PASS | No `.proto` churn is planned. Completion work finishes validation, gating, and documentation around the existing command-contract semantics and report fields. |
| IV | Phased Externalization | PASS | Scope remains the current internal/maintainer workflow. No phase ownership changes or external-client expansion are introduced. |
| V | Latency Budget as Shipping Gate | PASS | The plan adds explicit validator-overhead recording and ties completion to a measured budget verdict rather than assuming the hot path is unaffected. |

**Initial gate result**: **PASS**

**Post-design re-evaluation**: **PASS**. Phase 1 artifacts keep the work in the existing gateway, test, and maintainer-workflow seams; preserve engine-thread dispatch ownership; avoid schema changes; and add explicit measurable validation gates rather than widening the transport surface.

## Project Structure

### Documentation (this feature)

```text
specs/011-contract-hardening-completion/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── validation-suite.md
│   ├── contract-gate-matrix.md
│   ├── foundational-repro-entrypoints.md
│   ├── root-ctest-discovery.md
│   └── validator-performance-record.md
└── tasks.md
```

### Source Code (repository root)

```text
CMakeLists.txt

src/circuit/grpc/
├── CommandValidator.h
├── CommandValidator.cpp
├── CommandDispatch.h
├── CommandDispatch.cpp
├── HighBarService.cpp
└── CoordinatorClient.cpp

src/circuit/module/
└── GrpcGatewayModule.cpp

clients/python/highbar_client/behavioral_coverage/
├── audit_report.py
├── audit_runner.py
├── itertesting_campaign.py
├── itertesting_report.py
├── itertesting_runner.py
├── itertesting_types.py
└── live_failure_classification.py

clients/python/tests/behavioral_coverage/
├── test_live_failure_classification.py
├── test_live_row_repro.py
├── test_itertesting_report.py
└── test_itertesting_runner.py

tests/unit/
├── command_validation_test.cc
└── [new] command_validation_perf_test.cc

tests/integration/
└── ai_move_flow_test.cc

tests/headless/
├── README.md
├── itertesting.sh
├── malformed-payload.sh
├── test_command_contract_hardening.sh
└── test_live_itertesting_hardening.sh

tests/bench/
├── bench_latency.py
├── latency-uds.sh
└── latency-tcp.sh

build/reports/
└── command-validation/
    └── validator-overhead.json
```

**Structure Decision**: Keep completion work in the same seams introduced by feature 010. C++ owns authoritative-target preservation, build-root discoverability, and validator-overhead measurement; Python owns report/gate/repro semantics; headless wrappers remain the public maintainer entrypoints; and feature docs define the finished no-skip completion suite and its pass criteria.

## Phase 0 Research Summary

Phase 0 resolves the practical completion decisions needed before implementation:

1. Finish authoritative-target preservation through `tests/integration/ai_move_flow_test.cc` and keep that test visible from the engine build root rather than treating unit coverage as sufficient.
2. Validate inert dispatch versus intentionally effect-free commands in both synthetic regression coverage and a real headless live run so Python logic and maintainer workflows agree.
3. Cover blocked-vs-ready and pattern-review/no-repro behavior in both pytest and the shell wrapper because the wrapper is part of the maintainer contract, not just a thin launcher.
4. Require one focused rerun path per deterministic foundational issue class and an explicit `needs_pattern_review` stop state when no deterministic repro exists.
5. Use a dedicated validator-overhead record with a concrete `p99 <= 100µs` and `<= 10%` regression gate, stored with build artifacts, rather than relying only on transport round-trip benches.
6. Treat `tests/headless/malformed-payload.sh` as a mandatory suite member and require full-suite completion without environment skips.
7. Update `AGENTS.md` manually because the repo exposes the Speckit marker but no agent-context helper script exists in `.specify/scripts/`.

See [research.md](./research.md).

## Phase 1 Design Summary

Phase 1 models completion around five explicit maintainer-facing records:

- `ValidationSuiteStep` describes each required completion command, whether it must be root-`ctest` discoverable, and the fact that a skip leaves completion incomplete.
- `FoundationalIssueRepro` captures the focused rerun path or explicit pattern-review fallback for a foundational issue class.
- `ContractGateCase` defines the blocked, ready, and needs-pattern-review behaviors that must agree across manifests, reports, and headless wrapper output.
- `RootCTestDiscoveryTarget` records which BARb contract-hardening tests must be discoverable from the engine build root and how maintainers filter them.
- `ValidatorPerformanceRecord` stores the validator-overhead measurement, the absolute and relative budget expectations, and the artifact path used during final validation.

The resulting contracts describe the finished maintainer workflow rather than a new public API. See [data-model.md](./data-model.md), [contracts/validation-suite.md](./contracts/validation-suite.md), [contracts/contract-gate-matrix.md](./contracts/contract-gate-matrix.md), [contracts/foundational-repro-entrypoints.md](./contracts/foundational-repro-entrypoints.md), [contracts/root-ctest-discovery.md](./contracts/root-ctest-discovery.md), and [contracts/validator-performance-record.md](./contracts/validator-performance-record.md).

## Complexity Tracking

No constitution violations or exception justifications are required.

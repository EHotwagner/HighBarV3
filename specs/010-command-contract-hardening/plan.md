# Implementation Plan: Command Contract Hardening

**Branch**: `010-command-contract-hardening` | **Date**: 2026-04-22 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/010-command-contract-hardening/spec.md`

## Summary

This feature hardens foundational command contract semantics before Itertesting is allowed to act as an improvement workflow. The implementation will keep the existing wire schema and maintainer entrypoints, but enforce one coherent batch-target contract across validation and engine-thread dispatch, deepen invalid-command rejection so shallow validator holes stop earlier, classify inert dispatch and other foundational defects separately from ordinary evidence/setup failures, and attach deterministic repro paths so maintainers can fix dispatcher and validator bugs with focused tests instead of another broad campaign.

## Technical Context

**Language/Version**: C++20 in the gateway/dispatch path, Python 3.11+ for behavioral coverage and reporting, Bash for repo-local headless wrappers, Protocol Buffers v3/gRPC for command transport.  
**Primary Dependencies**: Existing `src/circuit/grpc/` gateway modules (`CommandValidator`, `CommandDispatch`, `HighBarService`, `CoordinatorClient`), `src/circuit/module/GrpcGatewayModule.cpp`, generated `proto/highbar/*.proto`, `clients/python/highbar_client/behavioral_coverage/`, and repo-local `tests/headless/` wrappers.  
**Storage**: Filesystem artifacts under `reports/itertesting/` and `build/reports/`, plus feature docs under `specs/010-command-contract-hardening/`.  
**Testing**: Existing C++ unit/integration suite (`tests/unit/command_validation_test.cc`, `tests/integration/ai_move_flow_test.cc`, related transport tests), Python behavioral-coverage pytest suite, `tests/headless/itertesting.sh`, `tests/headless/malformed-payload.sh`, and new targeted headless repro scripts for contract defects.  
**Target Platform**: Linux x86_64 reference host used by the current gateway, coordinator, and headless BAR workflows.  
**Project Type**: Internal transport plus maintainer workflow hardening across gateway, reporting, and deterministic repro tooling.  
**Performance Goals**: Reject malformed or incoherent command batches synchronously without regressing the existing latency budget, surface foundational blockers within one run, and keep maintainers on focused deterministic tests rather than repeated broad Itertesting loops.  
**Constraints**: Preserve Constitution II engine-thread boundaries, prefer existing `CommandBatch` semantics over proto churn, keep improvements backward-compatible with the current maintainer entrypoints, do not hide foundational blockers inside ordinary Itertesting guidance, and keep validation checks bounded and explicit.  
**Scale/Scope**: Command transport covers the current `AICommand` catalog and existing single-session Itertesting campaigns; scope is the command-contract seam and its maintainer-facing classification/repro surfaces, not a new transport or campaign subsystem.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

Constitution version: **1.0.0** (`.specify/memory/constitution.md`).

| # | Principle | Plan status | Evidence / notes |
|---|---|---|---|
| I | Upstream Fork Discipline | PASS | Planned implementation stays in V3-owned paths: `src/circuit/grpc/`, `src/circuit/module/GrpcGatewayModule.cpp`, `proto/highbar/` docs only if needed, `clients/python/`, `tests/`, `reports/`, and `specs/010-command-contract-hardening/`. No upstream-wide engine rewrite is planned. |
| II | Engine-Thread Supremacy | PASS | Validation remains on the gRPC worker thread; dispatch normalization and final command execution remain on the engine-thread drain path. The design explicitly avoids worker-thread command execution or direct CircuitAI mutation. |
| III | Proto-First Contracts | PASS | The working assumption is no `.proto` change: the feature will enforce the existing documented `CommandBatch` single-target contract and expose maintainer-facing workflow/report contracts in repo-local docs. If later evidence proves the wire schema is insufficient, that would require a new constitution re-check before implementation. |
| IV | Phased Externalization | PASS | The feature only hardens the current internal/maintainer workflow. It does not change phase gates or external-client ownership boundaries. |
| V | Latency Budget as Shipping Gate | PASS | The design adds bounded validation and classification, not extra network round-trips. Hot-path work stays limited to synchronous validation and existing queue/dispatch flow, with report gating handled outside the transport critical path. |

**Initial gate result**: **PASS**

**Post-design re-evaluation**: **PASS**. Phase 1 artifacts keep the contract fixes in V3-owned gateway and maintainer-workflow paths, preserve the existing schema-first transport boundary, and keep engine-thread dispatch isolated from worker-thread validation/reporting concerns.

## Project Structure

### Documentation (this feature)

```text
specs/010-command-contract-hardening/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── dispatch-target-invariant.md
│   ├── foundational-issue-classification.md
│   ├── contract-health-decision.md
│   └── deterministic-repro.md
└── tasks.md
```

### Source Code (repository root)

```text
src/circuit/grpc/
├── CommandValidator.h
├── CommandValidator.cpp
├── CommandDispatch.h
├── CommandDispatch.cpp
├── CommandQueue.h
├── HighBarService.cpp
└── CoordinatorClient.cpp

src/circuit/module/
└── GrpcGatewayModule.cpp

proto/highbar/
├── commands.proto
└── service.proto

clients/python/highbar_client/behavioral_coverage/
├── itertesting_types.py
├── live_failure_classification.py
├── itertesting_campaign.py
├── itertesting_runner.py
├── itertesting_report.py
├── audit_runner.py
└── audit_report.py

clients/python/tests/behavioral_coverage/
├── test_live_row_repro.py
├── test_itertesting_runner.py
├── test_itertesting_report.py
└── test_live_failure_classification.py

tests/unit/
└── command_validation_test.cc

tests/integration/
└── ai_move_flow_test.cc

tests/headless/
├── itertesting.sh
├── malformed-payload.sh
├── test_itertesting_campaign.sh
└── [new] test_command_contract_hardening.sh
```

**Structure Decision**: Keep the feature split across the existing V3 gateway seam and the current Python Itertesting/report workflow. C++ owns command-contract enforcement and dispatch invariants; Python owns maintainer-facing issue classification, stop gating, and repro linkage; repo-local tests validate the seam at unit, integration, and headless workflow levels.

## Phase 0 Research Summary

Phase 0 resolves the command-contract choices needed before implementation:

1. Enforce the already-documented single-target `CommandBatch` contract instead of allowing runtime drift between batch-level and per-command unit ids.
2. Deepen validation so malformed or semantically incoherent commands fail synchronously with explicit maintainer-facing reasons, rather than leaking into dispatch-time ambiguity.
3. Classify inert dispatch and similar foundational defects as separate contract blockers, not as ordinary Itertesting evidence or retry candidates.
4. Pair each foundational issue class with a deterministic repro route rooted in existing unit, integration, or headless test entrypoints.
5. Gate Itertesting improvement output behind a run-level contract-health decision so coverage/evidence/setup tuning only happens once foundational blockers are absent.

See [research.md](./research.md).

## Phase 1 Design Summary

Phase 1 introduces a design centered on four explicit contract-hardening entities:

- `CommandContractIssue` records the foundational issue class, affected command, primary cause, and supporting evidence that makes the run non-actionable for ordinary Itertesting.
- `DeterministicRepro` links each contract issue to an independently runnable focused test or headless script.
- `ContractHealthDecision` captures the run-level go/no-go decision for whether improvement-driven Itertesting may proceed.
- `ImprovementEligibility` separates withheld downstream improvement guidance from normal Itertesting output once contract health is acceptable.

The resulting contracts describe the maintainer-facing workflow and enforcement boundaries rather than a new public API. See [data-model.md](./data-model.md), [contracts/dispatch-target-invariant.md](./contracts/dispatch-target-invariant.md), [contracts/foundational-issue-classification.md](./contracts/foundational-issue-classification.md), [contracts/contract-health-decision.md](./contracts/contract-health-decision.md), and [contracts/deterministic-repro.md](./contracts/deterministic-repro.md).

## Complexity Tracking

No constitution violations or exception justifications are required.

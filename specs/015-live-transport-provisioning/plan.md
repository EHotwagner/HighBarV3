# Implementation Plan: Live Transport Provisioning

**Branch**: `015-live-transport-provisioning` | **Date**: 2026-04-22 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/015-live-transport-provisioning/spec.md`

## Summary

This feature closes the last foundational live Itertesting blocker left after 014 by turning `transport_unit` from a discovery-only heuristic into a real provisioning lifecycle. The plan keeps the current Itertesting wrapper and bundle as the maintainer surface, extends the client-mode coordinator so the Python workflow can use the existing `InvokeCallback` contract for runtime unit-def resolution, and teaches the behavioral-coverage bootstrap to discover, provision, validate, refresh, and report supported live transport variants without regressing channel health.

## Technical Context

**Language/Version**: Python 3.11+ for coordinator relay and behavioral-coverage orchestration, Bash for maintainer wrappers, and existing gRPC/protobuf contracts already generated for the Python client.  
**Primary Dependencies**: `specs/002-live-headless-e2e/examples/coordinator.py`, `clients/python/highbar_client/behavioral_coverage/bootstrap.py`, `__init__.py`, `registry.py`, `itertesting_runner.py`, `itertesting_types.py`, `itertesting_report.py`, `live_failure_classification.py`, generated `clients/python/highbar_client/highbar/service_pb2_grpc.py`, and existing proto contracts in `proto/highbar/service.proto`, `callbacks.proto`, and `commands.proto`.  
**Storage**: Feature docs under `specs/015-live-transport-provisioning/`; run artifacts under `reports/itertesting/<run-id>/`; no database changes.  
**Testing**: Python pytest for behavioral-coverage model/report logic; integration validation via `tests/integration/transport_parity_test.cc`; headless validation via `tests/headless/test_live_itertesting_hardening.sh` and `tests/headless/test_itertesting_campaign.sh`; prepared live reruns via `tests/headless/itertesting.sh`; manual audit support through `tests/headless/audit/def-id-resolver.py`.  
**Target Platform**: Linux x86_64 maintainer environment with BAR headless prerequisites, the client-mode coordinator runtime, and prepared live Itertesting available.  
**Project Type**: Internal maintainer reliability hardening for the live Itertesting workflow.  
**Performance Goals**: Eliminate the five commands blocked solely by missing `transport_unit` in the 2026-04-22 baseline run, preserve healthy channel status across three consecutive prepared live reruns, and keep prepared closeout runtime within 10% of the 8-second baseline from `reports/itertesting/itertesting-20260422T195308Z/run-report.md`.  
**Validation Baseline**: Use `itertesting-20260422T195308Z` as the authoritative pre-015 comparison bundle: `transport_unit=missing`, affected commands limited to `cmd-load-onto`, `cmd-load-units`, `cmd-load-units-area`, `cmd-unload-unit`, and `cmd-unload-units-area`, with runtime elapsed seconds `8`.  
**Constraints**: Preserve the existing maintainer wrapper and run bundle, keep `transport_unit` anchored to the authoritative fixture dependency model in `bootstrap.py`, avoid `.proto` schema edits unless a blocker is proven in implementation, reuse the existing `InvokeCallback` and `GiveMeNewUnitCommand` contracts rather than inventing side channels, accept multiple supported transport variants, validate transport-payload compatibility before command evaluation, keep exceptional fallback explicit in reporting, and do not reintroduce channel instability or duplicate blocker semantics. For 015, ordinary live fixture path means coordinator-relayed callback resolution plus normal live command/workflow orchestration; cheat-assisted spawning, if later added, is fallback-only and must be reported distinctly.  
**Scale/Scope**: The client-mode coordinator relay, the Python behavioral-coverage transport bootstrap/reporting path, and the prepared live closeout flow for the five transport-dependent direct commands.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

Constitution version: **1.0.0** (`.specify/memory/constitution.md`).

| # | Principle | Plan status | Evidence / notes |
|---|---|---|---|
| I | Upstream Fork Discipline | PASS | Planned work stays in V3-owned Python client code, specs, reports, and the coordinator example under `specs/002-live-headless-e2e/examples/`. No upstream-shared C++ seam is required by the current plan. |
| II | Engine-Thread Supremacy | PASS | 015 uses the existing `InvokeCallback` RPC surface and command relay. It does not introduce worker-thread mutation of CircuitAI state or bypass the queue/drain model. |
| III | Proto-First Contracts | PASS | The current proto surface already includes `InvokeCallback`, `RequestSnapshot`, and `GiveMeNewUnitCommand`. The plan reuses those contracts and does not require schema changes. |
| IV | Phased Externalization | PASS | The work remains inside the existing maintainer/client-mode workflow and does not change the current externalization phase boundaries. |
| V | Latency Budget as Shipping Gate | PASS | The plan keeps transport changes in the coordinator/Python workflow. If implementation later proves a transport-facing plugin change is necessary, the existing latency gates remain mandatory. |

**Initial gate result**: **PASS**

**Post-design re-evaluation**: **PASS**. Phase 1 keeps 015 inside current V3-owned coordinator and Python behavioral-coverage seams, reuses existing proto contracts, preserves engine-thread rules, and treats transport provisioning as a maintainer workflow concern rather than a new external subsystem.

## Project Structure

### Documentation (this feature)

```text
specs/015-live-transport-provisioning/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── authoritative-transport-fixture-model.md
│   ├── callback-relay-and-def-resolution.md
│   ├── transport-blocker-classification-and-reporting.md
│   └── live-transport-validation-suite.md
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
└── registry.py

clients/python/tests/behavioral_coverage/
├── test_itertesting_report.py
├── test_itertesting_runner.py
└── test_live_failure_classification.py

clients/python/tests/
└── test_behavioral_registry.py

proto/highbar/
├── callbacks.proto
├── commands.proto
└── service.proto

tests/headless/
├── audit/def-id-resolver.py
├── itertesting.sh
├── test_itertesting_campaign.sh
└── test_live_itertesting_hardening.sh

tests/integration/
└── transport_parity_test.cc

reports/itertesting/
└── <run-id>/{manifest.json,run-report.md,campaign-stop-decision.json}
```

**Structure Decision**: Keep 015 inside the existing client-mode and behavioral-coverage workflow. The coordinator remains the relay for the maintainer live endpoint, `bootstrap.py` remains the authoritative fixture dependency source, transport provisioning/reporting stays in the Python live closeout package, and the existing run bundle remains the only review surface.

## Phase 0 Research Summary

Phase 0 resolves the concrete design questions for the remaining transport blocker:

1. The coordinator example already exposes `HighBarProxy` for `Hello`, `StreamState`, and `SubmitCommands`, but it does not relay `InvokeCallback`; 015 should add relay support there instead of changing proto contracts.
2. Runtime unit-def resolution should use the existing `InvokeCallback`/`CallbackId` path so the Python workflow can resolve transport unit defs in the actual client-mode environment instead of hardcoding unit-def ids.
3. `transport_unit` should accept a supported variant set rather than the current `max_health ~= 265.0` `armatlas` heuristic; the validated candidate set starts with `armatlas` and `armhvytrans`.
4. Natural provisioning should remain the default path by reusing or creating a transport through the ordinary live bootstrap path, while any cheat-assisted fallback remains explicit and non-default in the run bundle.
5. The authoritative run bundle from `itertesting-20260422T195308Z` already has the right class/report structure; 015 should enrich the `transport_unit` class status with lifecycle and compatibility details instead of inventing a separate diagnostics artifact.
6. `AGENTS.md` must be updated manually because the repository exposes the Speckit marker but no agent-context update helper exists under `.specify/scripts/`.

See [research.md](./research.md).

## Phase 1 Design Summary

Phase 1 models transport provisioning as a specialization of the 014 fixture framework:

- `SupportedTransportVariant` defines which live unit defs can satisfy `transport_unit` and how they are discovered or created.
- `TransportCandidate` records a preexisting or newly provisioned live unit plus its readiness, provenance, and payload-compatibility state.
- `TransportProvisioningResult` extends the existing `FixtureProvisioningResult` semantics for `transport_unit` with lifecycle events such as discovered, provisioned, refreshed, replaced, fallback-provisioned, missing, and unusable.
- `TransportCompatibilityCheck` ensures a selected transport is alive, usable, and compatible with the pending payload before each load/unload command is judged.
- `TransportLifecycleEvent` gives the report bundle reviewer-facing evidence for discovery, creation, refresh, replacement, loss, fallback use, and failed acquisition.
- `TransportCommandImpact` keeps blocker reporting precise so only the five transport-dependent commands are blocked when coverage is unavailable.

The contracts define the authoritative transport model, callback relay/def-id resolution boundary, blocker/report behavior, and validation loop. See [data-model.md](./data-model.md), [contracts/authoritative-transport-fixture-model.md](./contracts/authoritative-transport-fixture-model.md), [contracts/callback-relay-and-def-resolution.md](./contracts/callback-relay-and-def-resolution.md), [contracts/transport-blocker-classification-and-reporting.md](./contracts/transport-blocker-classification-and-reporting.md), and [contracts/live-transport-validation-suite.md](./contracts/live-transport-validation-suite.md).

## Complexity Tracking

No constitution violations or exception justifications are required.

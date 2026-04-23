# Implementation Plan: Live Bootstrap Hardening

**Branch**: `016-live-bootstrap-hardening` | **Date**: 2026-04-23 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/016-live-bootstrap-hardening/spec.md`

## Summary

This feature hardens prepared live closeout for a callback-limited runtime. Bootstrap still needs explicit readiness handling, but the design can no longer assume that commander, build-option, economy, or map callbacks are broadly available. The implementation keeps runtime prerequisite resolution on the two callback surfaces that the live probe proved work (`CALLBACK_GET_UNIT_DEFS` / 47 and `CALLBACK_UNITDEF_GET_NAME` / 40), treats unsupported callbacks as capability limits rather than generic failures, and uses the session-start `HelloResponse.static_map` payload as the authoritative map source when callback-based map inspection is unavailable.

## Technical Context

**Language/Version**: Python 3.11+ for behavioral-coverage orchestration and reporting, Bash for maintainer wrappers and standalone probes, generated Python protobuf/gRPC stubs under `clients/python/highbar_client/highbar/`.  
**Primary Dependencies**: `clients/python/highbar_client/behavioral_coverage/__init__.py`, `bootstrap.py`, `itertesting_runner.py`, `itertesting_report.py`, `itertesting_types.py`, `live_failure_classification.py`, `specs/002-live-headless-e2e/examples/coordinator.py`, `tests/headless/itertesting.sh`, `tests/headless/behavioral-build.sh`, `tests/headless/test_live_itertesting_hardening.sh`, `tests/headless/test_itertesting_campaign.sh`, and existing contracts in `proto/highbar/{service,callbacks,state}.proto`.  
**Storage**: Feature docs under `specs/016-live-bootstrap-hardening/`; run artifacts under `reports/itertesting/<run-id>/`; no database changes.  
**Testing**: Python pytest for behavioral-coverage/report coverage, integration coverage in `tests/integration/transport_parity_test.cc`, headless validation through `tests/headless/test_live_itertesting_hardening.sh`, `tests/headless/test_itertesting_campaign.sh`, `tests/headless/behavioral-build.sh`, and prepared live reruns via `tests/headless/itertesting.sh`.  
**Target Platform**: Linux x86_64 maintainer environment with BAR headless prerequisites, the client-mode coordinator runtime, and prepared live Itertesting available.  
**Project Type**: Internal maintainer reliability hardening for prepared live bootstrap, diagnostic reporting, and standalone probe parity.  
**Performance Goals**: Keep otherwise healthy prepared live runs inside the existing 90-second fixture-provisioning budget, avoid channel-health regression, and avoid broad callback retries beyond the supported prerequisite-resolution path.  
**Validation Baseline**: The April 23, 2026 callback probe showed only `CALLBACK_GET_UNIT_DEFS (47)` and `CALLBACK_UNITDEF_GET_NAME (40)` as supported; `47` returned 581 unit defs and `40(149)` returned `armmex`. `CALLBACK_UNIT_GET_DEF (23)`, `CALLBACK_UNITDEF_GET_BUILD_OPTIONS (42)`, all economy callbacks, all map callbacks, and the team/mod/cheat/datadir/info groups were explicitly unsupported. `HelloResponse.static_map` still exposed map metal spots despite `CALLBACK_MAP_GET_METAL_SPOTS (58)` being unsupported.  
**Constraints**: Preserve the existing proto/RPC surface unless implementation proves a blocker; keep engine-thread discipline intact; treat unsupported callbacks as capability-limited diagnostics rather than generic workflow or transport failure; use session-start `static_map` when callback map inspection is unavailable; do not regress hosts that expose broader diagnostics.  
**Scale/Scope**: Prepared live closeout bootstrap readiness, capability-aware bundle/report semantics, shared prerequisite and map-source selection for `behavioral-build.sh`, and the coordinator relay boundary already used by the client-mode workflow.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

Constitution version: **1.0.0** (`.specify/memory/constitution.md`).

| # | Principle | Plan status | Evidence / notes |
|---|---|---|---|
| I | Upstream Fork Discipline | PASS | Planned work stays in V3-owned Python client code, maintainer wrappers, feature docs, and the existing coordinator example under `specs/002-live-headless-e2e/examples/`. No broad upstream-shared engine-file refactor is required. |
| II | Engine-Thread Supremacy | PASS | The design reuses the existing `Hello`, `StreamState`, `SubmitCommands`, and `InvokeCallback` boundaries. No worker-thread access to CircuitAI internals is introduced. |
| III | Proto-First Contracts | PASS | The plan explicitly works within the existing `service.proto`, `callbacks.proto`, and `state.proto` surface. The runtime limitation is handled through reporting and source selection, not an ad-hoc side channel. |
| IV | Phased Externalization | PASS | The work remains inside the current maintainer and client-mode workflow. It hardens live closeout and the standalone probe without changing the project’s externalization phase boundary. |
| V | Latency Budget as Shipping Gate | PASS | The design keeps the fix in Python orchestration/reporting, shell wrappers, and the coordinator relay. If implementation later requires plugin-facing changes, the existing latency gate still applies. |

**Initial gate result**: **PASS**

**Post-design re-evaluation**: **PASS**. Phase 1 keeps the feature inside existing V3-owned workflow seams, preserves proto-first behavior, and treats callback-limited runtime handling as reporting and source-selection hardening rather than a new transport or engine subsystem.

## Project Structure

### Documentation (this feature)

```text
specs/016-live-bootstrap-hardening/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── bootstrap-readiness-and-seed-path.md
│   ├── callback-diagnostic-retention.md
│   ├── live-bootstrap-validation-suite.md
│   └── runtime-prerequisite-resolution.md
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
└── live_failure_classification.py

clients/python/tests/
├── behavioral_coverage/
│   ├── test_itertesting_report.py
│   ├── test_itertesting_runner.py
│   └── test_live_failure_classification.py
└── test_behavioral_registry.py

tests/headless/
├── behavioral-build.sh
├── itertesting.sh
├── test_itertesting_campaign.sh
└── test_live_itertesting_hardening.sh

tests/integration/
└── transport_parity_test.cc

proto/highbar/
├── callbacks.proto
├── service.proto
└── state.proto
```

**Structure Decision**: Keep 016 inside the existing client-mode and behavioral-coverage workflow. Bootstrap readiness, capability-aware diagnostics, and supported-source selection stay in the Python client/run-bundle seam; the maintainer wrappers expose and validate those behaviors; the coordinator remains the relay boundary rather than introducing a new service or protocol.

## Phase 0 Research Summary

Phase 0 resolves the key design choices raised by the updated feature spec and the April 23, 2026 live probe:

1. Bootstrap readiness still needs an explicit maintainer-visible outcome because the prepared start can be resource-starved before the first commander build.
2. The live runtime’s capability profile must be made explicit in the bundle because only callback ids `47` and `40` are reliably available on the observed host.
3. Runtime prerequisite resolution should stay on that narrow supported callback path rather than trying to recover commander/build-option diagnostics through unsupported callbacks.
4. Map-derived targeting should treat `HelloResponse.static_map` as the authoritative source when map callbacks are unsupported but session-start map payload data is present.
5. The existing Itertesting manifest/report surface remains the authoritative place to record bootstrap readiness, capability limits, map-source selection, and standalone probe parity.

See [research.md](./research.md).

## Phase 1 Design Summary

Phase 1 models 016 as a capability-aware extension of the existing live-hardening bundle:

- `BootstrapReadinessAssessment` remains the maintainer-visible gate for natural, seeded, or blocked prepared starts.
- `RuntimeCapabilityProfile` captures which callback surfaces are actually supported on the current host and which groups are unavailable.
- `RuntimePrerequisiteResolutionRecord` remains the shared trace for live prerequisite identity, but the contract now explicitly constrains it to the proven `47`/`40` path.
- `MapDataSourceDecision` records whether live closeout and the standalone probe used session-start `static_map`, callback map inspection, or no map data.
- `StandaloneBuildProbeOutcome` extends the maintainer-facing probe evidence with the same supported-source and capability-limit semantics as the main workflow.

The contracts define the bootstrap-readiness boundary, capability-aware diagnostic sourcing, shared prerequisite/map source selection, and the validation suite. See [data-model.md](./data-model.md), [contracts/bootstrap-readiness-and-seed-path.md](./contracts/bootstrap-readiness-and-seed-path.md), [contracts/callback-diagnostic-retention.md](./contracts/callback-diagnostic-retention.md), [contracts/runtime-prerequisite-resolution.md](./contracts/runtime-prerequisite-resolution.md), and [contracts/live-bootstrap-validation-suite.md](./contracts/live-bootstrap-validation-suite.md).

## Complexity Tracking

No constitution violations or exception justifications are required.

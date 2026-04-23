# Implementation Plan: Live Bootstrap Hardening

**Branch**: `016-live-bootstrap-hardening` | **Date**: 2026-04-23 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/016-live-bootstrap-hardening/spec.md`

## Summary

This feature hardens prepared live closeout at the three seams exposed by the April 23, 2026 follow-up evidence: the bootstrap path must stop treating a resource-starved starting state as a viable natural build path, callback-derived diagnostics must survive long bootstrap failures, and `tests/headless/behavioral-build.sh` must resolve prerequisites through the same runtime callback path as the main workflow. The plan keeps the work inside the existing maintainer wrapper, coordinator relay, Python behavioral-coverage package, and Itertesting run bundle rather than introducing new protocol surfaces.

## Technical Context

**Language/Version**: Python 3.11+ for behavioral-coverage orchestration and coordinator relay, Bash for maintainer wrappers and standalone probes, existing generated gRPC/protobuf stubs under `clients/python/highbar_client/highbar/`.  
**Primary Dependencies**: `clients/python/highbar_client/behavioral_coverage/__init__.py`, `bootstrap.py`, `itertesting_runner.py`, `itertesting_report.py`, `live_failure_classification.py`, `itertesting_types.py`, `specs/002-live-headless-e2e/examples/coordinator.py`, `tests/headless/itertesting.sh`, `tests/headless/behavioral-build.sh`, and existing callback contracts in `proto/highbar/callbacks.proto` and `service.proto`.  
**Storage**: Feature docs under `specs/016-live-bootstrap-hardening/`; run artifacts under `reports/itertesting/<run-id>/`; no database changes.  
**Testing**: Python pytest for behavioral-coverage model/report coverage plus headless validation through `tests/headless/test_live_itertesting_hardening.sh`, `tests/headless/test_itertesting_campaign.sh`, `tests/headless/behavioral-build.sh`, and prepared live reruns via `tests/headless/itertesting.sh`.  
**Target Platform**: Linux x86_64 maintainer environment with BAR headless prerequisites, the client-mode coordinator runtime, and prepared live Itertesting available.  
**Project Type**: Internal maintainer reliability hardening for the prepared live closeout workflow and its standalone diagnostic probe.  
**Performance Goals**: Detect resource-starved prepared starts before the first commander-built timeout becomes the primary signal; preserve callback-derived diagnostics through the full closeout window; keep healthy prepared live runs inside the existing 90-second fixture-provisioning budget and without channel-health regression.  
**Validation Baseline**: Use `reports/itertesting/itertesting-20260423T024247Z/run-report.md` as the authoritative failing baseline: `factory_ground/armvp` timed out after bootstrap began, the report recorded `economy=metal:0.1/0.0/1500.0` and later `economy=metal:0.0/0.0/1450.0`, and callback diagnostics degraded to `StatusCode.UNAVAILABLE ... highbar-1.sock ... No such file or directory`. Use the April 23, 2026 `tests/headless/behavioral-build.sh` skip (`HIGHBAR_ARMMEX_DEF_ID not set`) as the baseline for the standalone probe mismatch.  
**Constraints**: Preserve the existing proto contracts unless implementation proves a real blocker; keep engine-thread discipline intact under Constitution II; reuse the Itertesting run bundle as the maintainer review surface; keep non-natural bootstrap-readiness paths explicit in reporting; align standalone prerequisite resolution with the same runtime callback path used by live closeout; do not regress otherwise healthy prepared runs or reclassify unrelated failures as bootstrap/readiness failures.  
**Scale/Scope**: The prepared live bootstrap gate, callback-diagnostic retention path, run-bundle/report semantics, the coordinator-mediated callback path already used by the client-mode workflow, and the standalone `behavioral-build.sh` probe.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

Constitution version: **1.0.0** (`.specify/memory/constitution.md`).

| # | Principle | Plan status | Evidence / notes |
|---|---|---|---|
| I | Upstream Fork Discipline | PASS | Planned work stays in V3-owned Python client code, maintainer wrappers, reports, and the coordinator example under `specs/002-live-headless-e2e/examples/`. No upstream-shared engine-file change is required by the design. |
| II | Engine-Thread Supremacy | PASS | The plan reuses the existing `InvokeCallback` and `SubmitCommands` boundaries and does not propose worker-thread mutation of CircuitAI state. |
| III | Proto-First Contracts | PASS | The design reuses existing callback and service proto contracts; no new side-channel format or schema change is required in planning. |
| IV | Phased Externalization | PASS | The work remains inside the current maintainer/client-mode workflow and does not change the project’s externalization phase boundaries. |
| V | Latency Budget as Shipping Gate | PASS | The plan keeps the changes in the wrapper, coordinator, and Python orchestration/reporting layers. If implementation later requires transport-facing plugin edits, the existing latency gate remains mandatory. |

**Initial gate result**: **PASS**

**Post-design re-evaluation**: **PASS**. Phase 1 keeps the feature inside existing V3-owned workflow seams, preserves proto-first behavior, and treats bootstrap hardening as maintainer workflow reliability rather than a new runtime subsystem.

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
│   ├── runtime-prerequisite-resolution.md
│   └── live-bootstrap-validation-suite.md
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
├── README.md
├── _coordinator.sh
├── behavioral-build.sh
├── itertesting.sh
├── test_itertesting_campaign.sh
└── test_live_itertesting_hardening.sh

reports/itertesting/
└── <run-id>/{manifest.json,run-report.md,campaign-stop-decision.json}
```

**Structure Decision**: Keep 016 inside the existing client-mode and behavioral-coverage workflow. Bootstrap-readiness classification, cached callback diagnostics, and runtime prerequisite resolution stay in the Python client/run-bundle seam; the maintainer wrappers only expose and validate those behaviors; the coordinator remains the relay boundary rather than introducing a new service or protocol.

## Phase 0 Research Summary

Phase 0 resolves the open design choices from the feature prompt and the April 23, 2026 failures:

1. The code already detects an obviously starved economy via `_economy_obviously_starved()` before commander-built bootstrap steps; 016 should turn that into an explicit bootstrap-readiness outcome and pair it with a maintainer-visible seeded-readiness path instead of allowing downstream build timeouts to dominate the diagnosis.
2. Callback-diagnostic stability should rely on preserving an early diagnostic snapshot in the run bundle, with late refresh remaining best-effort, rather than depending solely on the callback relay endpoint staying reachable for the entire failure path.
3. Runtime prerequisite resolution should be generalized from the existing `_resolve_live_def_ids()` helper and the transport resolution trace so both prepared live closeout and `tests/headless/behavioral-build.sh` share the same authoritative callback-based def-name lookup.
4. Reporting should extend the existing manifest/run-report surface with bootstrap-readiness and callback-diagnostic state instead of adding a parallel ad-hoc log artifact.

See [research.md](./research.md).

## Phase 1 Design Summary

Phase 1 models 016 as a targeted extension of the 014/015 live-hardening bundle:

- `BootstrapReadinessAssessment` captures whether prepared live closeout started in a naturally viable state, required an explicit seeded-readiness path, or was blocked before the first commander build.
- `CallbackDiagnosticSnapshot` preserves the commander/build-option/economy evidence needed for late failure analysis even when callback reachability degrades after bootstrap starts.
- `RuntimePrerequisiteResolutionRecord` reuses the callback-based def-resolution model already used for transport traces and makes it a shared contract for both live closeout and the standalone build probe.
- `StandaloneBuildProbeOutcome` ensures the maintainer probe reports runtime-resolution status and build-verification results with the same prerequisite identity the main workflow would use.

The contracts define the bootstrap-readiness boundary, diagnostic-retention behavior, shared runtime prerequisite-resolution trace, and validation suite. See [data-model.md](./data-model.md), [contracts/bootstrap-readiness-and-seed-path.md](./contracts/bootstrap-readiness-and-seed-path.md), [contracts/callback-diagnostic-retention.md](./contracts/callback-diagnostic-retention.md), [contracts/runtime-prerequisite-resolution.md](./contracts/runtime-prerequisite-resolution.md), and [contracts/live-bootstrap-validation-suite.md](./contracts/live-bootstrap-validation-suite.md).

## Complexity Tracking

No constitution violations or exception justifications are required.

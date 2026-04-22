# Implementation Plan: Fixture Bootstrap Simplification

**Branch**: `014-fixture-bootstrap-simplification` | **Date**: 2026-04-22 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/014-fixture-bootstrap-simplification/spec.md`

## Summary

This feature replaces the remaining simplified-bootstrap blocker path with one authoritative fixture dependency and provisioning model for live Itertesting. The implementation keeps the current maintainer wrapper, manifest/report bundle, and Python behavioral-coverage surfaces, but extends them so the six currently missing live fixture classes can be provisioned and refreshed without reintroducing channel instability or ambiguous blocker reporting.

## Technical Context

**Language/Version**: Python 3.11+ for behavioral-coverage orchestration and reporting, Bash for maintainer headless wrappers, and targeted C++20 command-path repairs in the existing gateway/runtime where local helper parity gaps or command-shape handling require them.  
**Primary Dependencies**: `clients/python/highbar_client/behavioral_coverage/bootstrap.py`, `__init__.py`, `itertesting_runner.py`, `itertesting_types.py`, `itertesting_report.py`, `live_failure_classification.py`, `registry.py`, `predicates.py`, `upstream_fixture_intelligence.py`, `clients/python/tests/behavioral_coverage/test_upstream_fixture_intelligence.py`, `clients/python/tests/test_behavioral_registry.py`, `src/circuit/unit/CircuitUnit.cpp`, `src/circuit/unit/CircuitUnit.h`, `src/circuit/grpc/CommandDispatch.cpp`, plus `tests/headless/itertesting.sh`, `tests/headless/test_live_itertesting_hardening.sh`, and the current Itertesting wrapper/report bundle.  
**Storage**: Feature docs under `specs/014-fixture-bootstrap-simplification/`; live run artifacts under `reports/itertesting/<run-id>/`; no database changes.  
**Testing**: Python pytest for fixture modeling, runner behavior, and report rendering; synthetic hardening validation via `tests/headless/test_live_itertesting_hardening.sh`; prepared-environment live reruns through `tests/headless/itertesting.sh`; existing campaign/report validation in `clients/python/tests/behavioral_coverage/`.  
**Target Platform**: Linux x86_64 reference environment with BAR headless prerequisites, coordinator runtime, and the existing live Itertesting workflow available.  
**Project Type**: Internal maintainer reliability and coverage hardening on top of the current live Itertesting workflow.  
**Performance Goals**: Preserve three consecutive prepared live closeout runs with healthy channel status while reducing the baseline direct commands blocked solely by missing fixtures from 11; keep fixture preparation within the workflow's existing live-closeout budget instead of introducing a separate slow path.  
**Validation Baseline**: Use the latest accepted pre-014 prepared closeout bundle as the comparison source. Record its `missing_fixture_blocker_count=11` and total prepared closeout duration in the implementation PR and compare 014 reruns against those values.  
**Constraints**: Keep `tests/headless/itertesting.sh` and the run bundle as the authoritative maintainer interface; remove duplicate simplified-bootstrap blocker rules; keep fixture interpretation anchored to one dependency map; classify only affected commands as fixture-blocked; support refresh/replacement when a provisioned fixture becomes unusable; avoid `.proto` changes; do not regress the stable command-channel behavior hardened in 013; and keep any edits under `src/circuit/unit/*`, `src/circuit/grpc/*`, and `tests/headless/*` surgical and explicitly justified in the implementation PR per Constitution I.  
**Scale/Scope**: The Python behavioral-coverage live bootstrap, Itertesting manifest/report semantics, and headless validation flow for the direct command surface, especially the six currently missing classes `transport_unit`, `payload_unit`, `capturable_target`, `restore_target`, `wreck_target`, and `custom_target`.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

Constitution version: **1.0.0** (`.specify/memory/constitution.md`).

| # | Principle | Plan status | Evidence / notes |
|---|---|---|---|
| I | Upstream Fork Discipline | PASS WITH CONSTRAINT | Planned work stays primarily in V3-owned Python behavioral-coverage paths, specs, and report artifacts, with surgical upstream-shared edits in `src/circuit/unit/*` and surgical maintainer-workflow edits under `tests/headless/*`. Both MUST be justified in the implementation PR per Constitution I. |
| II | Engine-Thread Supremacy | PASS | 014 changes bootstrap provisioning and interpretation in the Python maintainer workflow. It does not move command dispatch or CircuitAI mutation off the engine thread and does not bypass the queue/drain model. |
| III | Proto-First Contracts | PASS | No `.proto` or generated-stub change is needed. The contract change is internal to the Itertesting manifest/report bundle and Python runner types. |
| IV | Phased Externalization | PASS | The feature remains maintainer-facing reliability work for the current live closeout path and does not change externalization phase boundaries. |
| V | Latency Budget as Shipping Gate | PASS | The design keeps the transport path untouched by default and treats healthy live reruns as a guardrail. If transport-facing code is later touched during implementation, the existing latency gates remain mandatory. |

**Initial gate result**: **PASS**

**Post-design re-evaluation**: **PASS**. Phase 1 artifacts keep 014 inside the existing wrapper/report seams, avoid schema changes on external proto contracts, preserve engine-thread rules, and make fixture expansion/reporting an internal workflow concern rather than a new subsystem. Any edits under `tests/headless/*` remain subject to Constitution I's surgical-diff requirement.

## Project Structure

### Documentation (this feature)

```text
specs/014-fixture-bootstrap-simplification/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── authoritative-fixture-model.md
│   ├── fixture-provisioning-and-refresh.md
│   ├── fixture-blocker-classification-and-reporting.md
│   └── live-bootstrap-validation-suite.md
└── tasks.md
```

### Source Code (repository root)

```text
clients/python/highbar_client/behavioral_coverage/
├── __init__.py
├── bootstrap.py
├── itertesting_report.py
├── itertesting_runner.py
├── itertesting_types.py
├── live_failure_classification.py
├── predicates.py
├── registry.py
└── upstream_fixture_intelligence.py

clients/python/tests/behavioral_coverage/
├── test_itertesting_report.py
├── test_itertesting_runner.py
├── test_live_failure_classification.py
└── test_upstream_fixture_intelligence.py

clients/python/tests/
└── test_behavioral_registry.py

src/circuit/grpc/
└── CommandDispatch.cpp

src/circuit/unit/
├── CircuitUnit.cpp
└── CircuitUnit.h

tests/headless/
├── README.md
├── itertesting.sh
├── test_itertesting_campaign.sh
└── test_live_itertesting_hardening.sh

tests/integration/
└── transport_parity_test.cc

reports/itertesting/
└── <run-id>/{manifest.json,run-report.md,campaign-stop-decision.json}
```

**Structure Decision**: Keep 014 inside the existing behavioral-coverage workflow. The static fixture dependency map lives in `bootstrap.py`, live bootstrap/provisioning orchestration stays in the Python behavioral-coverage package, maintainer execution remains on the headless wrapper, and reviewer-facing semantics stay in the existing report bundle rather than a sidecar tool or new transport surface.

## Phase 0 Research Summary

Phase 0 resolves the design questions driving 014:

1. `DEFAULT_LIVE_FIXTURE_CLASS_BY_COMMAND` in `bootstrap.py` should become the only authoritative command-to-fixture dependency map; the duplicate `_SIMPLIFIED_BOOTSTRAP_TARGET_MISSING_ARMS` path in `behavioral_coverage/__init__.py` should be removed.
2. Fixture provisioning and refresh should stay in the Python behavioral-coverage orchestration layer, not in shell glue or new proto contracts, because the runner already owns manifest/report emission and closeout interpretation.
3. The six currently missing classes should be provisioned as reusable shared fixtures, with per-class refresh or replacement when a fixture is consumed, destroyed, or no longer usable before later commands run.
4. The run bundle should remain the authoritative review surface, but it needs richer fixture state so maintainers can see planned, provisioned, refreshed, missing, and affected-command information from one model.
5. Failure classification and contract-health decisions should continue to separate missing fixtures, transport interruption, evidence gaps, and behavioral failure, but now derive fixture blockers only from the authoritative provisioning result.
6. `AGENTS.md` should be updated manually because the repository exposes the Speckit marker but no dedicated agent-context update helper exists in `.specify/scripts/`.

See [research.md](./research.md).

## Phase 1 Design Summary

Phase 1 models 014 around one static dependency source and one dynamic provisioning result:

- `CommandFixtureDependency` formalizes the static fixture classes each direct command requires, with `bootstrap.py` as the single source of truth.
- `FixtureProvisioningResult` expands from aggregate lists into per-class status plus aggregate summaries so the manifest/report can explain what was planned, provisioned, refreshed, missing, and which commands were impacted.
- `SharedFixtureInstance` records the reusable live objects or targets prepared for classes such as transport, payload, capturable target, restore target, wreck target, and custom target, including refresh state when an instance becomes stale.
- `CommandVerificationRecord` and `FailureCauseClassification` continue to drive closeout interpretation, but fixture-blocked outcomes now come solely from the provisioning model instead of a separate simplified-bootstrap exception list.
- `ContractHealthDecision` remains the maintainer gate: a run is not ready for ordinary tuning if missing fixture classes or unusable refreshed fixtures still block intended coverage commands.

The contracts define the authoritative fixture model, provisioning/refresh lifecycle, blocker/report semantics, and validation suite. See [data-model.md](./data-model.md), [contracts/authoritative-fixture-model.md](./contracts/authoritative-fixture-model.md), [contracts/fixture-provisioning-and-refresh.md](./contracts/fixture-provisioning-and-refresh.md), [contracts/fixture-blocker-classification-and-reporting.md](./contracts/fixture-blocker-classification-and-reporting.md), and [contracts/live-bootstrap-validation-suite.md](./contracts/live-bootstrap-validation-suite.md).

## Complexity Tracking

No constitution violations or exception justifications are required.

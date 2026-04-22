# Implementation Plan: Itertesting Channel Stability

**Branch**: `013-itertesting-channel-stability` | **Date**: 2026-04-22 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/013-itertesting-channel-stability/spec.md`

## Summary

This feature hardens the live Itertesting closeout path so maintainers can trust what a run means before they spend time tuning commands. The implementation stays on the existing live wrapper, behavioral-coverage manifest/report model, and headless regression surfaces. It treats command-channel continuity, fixture provisioning coverage, and transport-adjacent failure classification as first-class closeout gates, with `cmd-build-unit` and other specialized-fixture commands remaining blocked until the workflow can prove whether the issue is channel lifecycle, missing setup, or true command behavior.

## Technical Context

**Language/Version**: C++20 for gateway and command-dispatch surfaces, Python 3.11+ for behavioral-coverage orchestration and reporting, Bash for maintainer headless wrappers.  
**Primary Dependencies**: `tests/headless/itertesting.sh`, `tests/headless/test_live_itertesting_hardening.sh`, `tests/headless/README.md`, `clients/python/highbar_client/behavioral_coverage/itertesting_runner.py`, `itertesting_types.py`, `itertesting_report.py`, `live_failure_classification.py`, `bootstrap.py`, and the existing gateway/channel runtime under `src/circuit/grpc/` and `src/circuit/module/GrpcGatewayModule*`.  
**Storage**: Feature docs under `specs/013-itertesting-channel-stability/`; run artifacts under `reports/itertesting/<run-id>/`; transient live attempt logs under the existing wrapper runtime directory.  
**Testing**: Python pytest for behavioral coverage/report classification, synthetic headless hardening validation, prepared-environment live reruns through the documented Itertesting wrapper, integration coverage at the queue/drain seam in `tests/integration/ai_move_flow_test.cc`, and Constitution V latency gates via `tests/bench/latency-uds.sh` and `tests/bench/latency-tcp.sh` when transport-path C++ is touched.  
**Target Platform**: Linux x86_64 reference environment with the existing BAR headless prerequisites, coordinator runtime, and live gateway workflow available.  
**Project Type**: Internal maintainer validation and closeout hardening on top of an existing live verification workflow.  
**Performance Goals**: Achieve three consecutive prepared-environment live closeout reruns without a dispatch-time command-channel disconnect; preserve enough run evidence to identify the first lifecycle break, fixture blockers, and transport-adjacent outcomes on first review.  
**Constraints**: Keep maintainer entrypoints on the documented wrapper and report bundle; do not introduce `.proto` changes for an internal evidence problem; preserve Constitution II engine-thread ownership if transport fixes touch gateway lifecycle code; treat `contract_health_decision` as a hard closeout gate when interruption or fixture blockers remain; classify fixture blockers before behavior; classify transport-adjacent outcomes separately from clean regressions; and use `HIGHBAR_STARTSCRIPT` startscript variants with different `MinSpeed` and `MaxSpeed` values for alternate-speed confirmation.  
**Scale/Scope**: The existing live command surface and evidence model, especially `channel_a_command` rows that depend on fixture coverage or are vulnerable to mid-session channel teardown. No new external API and no transport redesign outside the current gateway/channel seams.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

Constitution version: **1.0.0** (`.specify/memory/constitution.md`).

| # | Principle | Plan status | Evidence / notes |
|---|---|---|---|
| I | Upstream Fork Discipline | PASS | Planned work stays in V3-owned Python behavioral-coverage paths, headless wrappers, specs, and at most the existing V3 gateway seams under `src/circuit/grpc/` and `src/circuit/module/GrpcGatewayModule*`. Any upstream-shared edit remains surgical if root-cause analysis reaches shared bootstrap points. |
| II | Engine-Thread Supremacy | PASS | The feature may diagnose or harden command-channel lifecycle handling, but it does not justify bypassing the queue/drain model. Worker-thread lifecycle reporting remains observational; command dispatch and CircuitAI state mutation stay on the engine thread. |
| III | Proto-First Contracts | PASS | No `.proto` or generated-stub changes are required. The problem is run stability and interpretation inside existing artifact formats and wrappers. |
| IV | Phased Externalization | PASS | The feature is a maintainer-facing reliability pass over the current live validation workflow and does not advance the externalization phase or disable the current baseline. |
| V | Latency Budget as Shipping Gate | PASS | 013 does not relax transport or validator budgets. It makes live closeout evidence trustworthy enough to decide whether follow-up work belongs in transport stability or command behavior. |

**Initial gate result**: **PASS**

**Post-design re-evaluation**: **PASS**. Phase 1 artifacts keep the work inside the existing wrapper/report seams, avoid schema changes, preserve thread-ownership rules, and frame live closeout readiness as an evidence problem rather than a new subsystem.

## Project Structure

### Documentation (this feature)

```text
specs/013-itertesting-channel-stability/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── live-channel-health-record.md
│   ├── fixture-provisioning-and-blockers.md
│   ├── transport-adjacent-failure-classification.md
│   └── live-closeout-validation-suite.md
└── tasks.md
```

### Source Code (repository root)

```text
clients/python/highbar_client/behavioral_coverage/
├── bootstrap.py
├── itertesting_report.py
├── itertesting_runner.py
├── itertesting_types.py
└── live_failure_classification.py

clients/python/tests/behavioral_coverage/
├── test_live_failure_classification.py
├── test_itertesting_report.py
└── test_itertesting_runner.py

tests/headless/
├── README.md
├── itertesting.sh
├── test_live_itertesting_hardening.sh
├── audit/repro.sh
└── scripts/
    ├── minimal.startscript
    └── cheats.startscript

src/circuit/grpc/
├── CommandDispatch.cpp
├── CommandQueue.cpp
└── HighBarService.cpp

src/circuit/module/
└── GrpcGatewayModule.cpp

reports/itertesting/
└── <run-id>/{manifest.json,run-report.md,campaign-stop-decision.json}
```

**Structure Decision**: Keep 013 on the existing Itertesting workflow boundaries. Behavioral classification and artifact semantics live in the Python package, maintainer execution stays in `tests/headless/itertesting.sh`, and any transport-lifecycle fix remains confined to the current V3 gateway/channel implementation paths instead of creating a new orchestration layer.

## Phase 0 Research Summary

Phase 0 resolves the feature’s operational unknowns without adding new interfaces:

1. Keep the documented live wrapper and Python `itertesting` CLI as the authoritative closeout surface instead of adding a new one-shot runner.
2. Treat `channel_health`, `fixture_provisioning`, `failure_classifications`, `contract_health_decision`, and the existing report sections as the canonical evidence model for 013.
3. Use `ChannelHealthOutcome.first_failure_stage`, `failure_signal`, and `commands_attempted_before_failure` as the minimum lifecycle record needed to identify where a live session stopped being trustworthy.
4. Use the bootstrap fixture profile and per-command fixture mapping in `bootstrap.py` as the authoritative source for fixture-blocked classification.
5. Keep transport interruption classification higher priority than command-behavior conclusions whenever the session is unhealthy and the row is not already explained by a required missing fixture.
6. Update `AGENTS.md` manually because the repository exposes the Speckit marker but `.specify/scripts/` has no agent-context update helper.

See [research.md](./research.md).

## Phase 1 Design Summary

Phase 1 models the closeout workflow around five existing records and one derived decision:

- `ItertestingRun` remains the container for one live validation session and is the parent for channel, fixture, classification, and closeout evidence.
- `ChannelHealthOutcome` records the first lifecycle break and whether a dispatch-time interruption invalidated later command outcomes.
- `FixtureProvisioningResult` records which required fixture classes were present, which were missing, and which commands became fixture-blocked as a result.
- `FailureCauseClassification` separates `missing_fixture`, `transport_interruption`, `predicate_or_evidence_gap`, and `behavioral_failure` so transport-adjacent rows do not look like clean regressions.
- `ContractHealthDecision` and the campaign stop decision remain the maintainer-facing closeout gate: interrupted or fixture-blocked runs must not be reported as `ready_for_itertesting`, and normal tuning proceeds only after trustworthy live evidence exists.

The contracts define the required artifact fields, classification precedence, and the prepared-environment validation suite. See [data-model.md](./data-model.md), [contracts/live-channel-health-record.md](./contracts/live-channel-health-record.md), [contracts/fixture-provisioning-and-blockers.md](./contracts/fixture-provisioning-and-blockers.md), [contracts/transport-adjacent-failure-classification.md](./contracts/transport-adjacent-failure-classification.md), and [contracts/live-closeout-validation-suite.md](./contracts/live-closeout-validation-suite.md).

## Complexity Tracking

No constitution violations or exception justifications are required.

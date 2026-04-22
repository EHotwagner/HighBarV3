# Implementation Plan: Live Itertesting Hardening

**Branch**: `009-live-itertest-hardening` | **Date**: 2026-04-22 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/009-live-itertest-hardening/spec.md`

## Summary

This feature hardens the live Itertesting path so default campaigns start from a richer fixture-ready state, keep the plugin command channel healthy for the full run, and judge key live arms with command-specific evidence windows instead of brittle generic timeouts. The implementation will extend the existing bootstrap/startscript assumptions rather than creating a parallel workflow, add explicit run-level channel-health and failure-cause classification, and align live verification rules for `fight`, `move_unit`, and `build_unit` with the evidence already reflected in audit hypotheses and targeted headless repro scripts.

## Technical Context

**Language/Version**: Python 3.11+ for live behavioral orchestration/reporting, Bash for repo-local headless wrappers and startscript launch flow, JSON/Markdown for persisted artifacts.  
**Primary Dependencies**: Existing `clients/python/highbar_client/behavioral_coverage/` package, current bootstrap/predicate/registry model, repo-local `tests/headless/` launch workflow, current gRPC coordinator/plugin integration already used by live coverage and Itertesting.  
**Storage**: Filesystem artifacts under `reports/itertesting/`, existing build/report outputs under `build/reports/`, and feature docs under `specs/009-live-itertest-hardening/`.  
**Testing**: Existing pytest behavioral-coverage suite, `tests/headless/itertesting.sh`, `tests/headless/aicommand-behavioral-coverage.sh`, targeted behavioral scripts (`behavioral-move.sh`, `behavioral-build.sh`, `behavioral-attack.sh`), and audit repro/hypothesis workflows.  
**Target Platform**: Linux x86_64 reference host used by current headless coordinator + engine workflows.  
**Project Type**: Internal CLI-style live verification workflow layered on the current behavioral coverage tooling and headless wrappers.  
**Performance Goals**: Default bounded live campaigns should attempt at least 20 directly verifiable commands from valid prerequisite state, complete without manual restarts in at least 90% of reference runs, and keep key arms (`fight`, `move_unit`, `build_unit`) out of avoidable generic-timeout failure buckets.  
**Constraints**: Preserve current maintainer entrypoints, keep cause classification explicit, separate transport interruption from command failure, avoid proto changes unless evidence shows they are unavoidable, and remain compliant with engine-thread and latency-budget constitution rules.  
**Scale/Scope**: Current 66-command inventory with 47 directly verifiable commands, existing single-session live campaigns, and focused hardening of the default live path rather than a new subsystem.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

Constitution version: **1.0.0** (`.specify/memory/constitution.md`).

| # | Principle | Plan status | Evidence / notes |
|---|---|---|---|
| I | Upstream Fork Discipline | PASS | Planned changes stay in V3-owned paths: `clients/python/highbar_client/behavioral_coverage/`, `clients/python/tests/behavioral_coverage/`, `tests/headless/`, `reports/`, and `specs/009-live-itertest-hardening/`. No upstream-shared C++ engine files are required by the current design. |
| II | Engine-Thread Supremacy | PASS | The feature hardens the client-side live harness, wrapper behavior, and evidence classification. It does not require worker-thread access to CircuitAI state or direct changes to engine-thread dispatch rules. |
| III | Proto-First Contracts | PASS | Current plan assumes no `.proto` changes. Contracts are repo-local workflow/report contracts only. If later research proves the existing wire surface cannot distinguish transport failure from command outcome, that would require a new constitution re-check before implementation. |
| IV | Phased Externalization | PASS | Work is additive to existing live verification workflows and preserves the current maintainer entrypoint rather than changing externalization phase gates. |
| V | Latency Budget as Shipping Gate | PASS | No transport schema or hot-path latency changes are planned. Channel hardening focuses on run survivability and classification in the existing workflow. |

**Initial gate result**: **PASS**

**Post-design re-evaluation**: **PASS**. Phase 1 artifacts keep scope in repo-local live workflow and reporting surfaces, avoid proto changes, and preserve the existing transport/threading boundaries defined by the constitution.

## Project Structure

### Documentation (this feature)

```text
specs/009-live-itertest-hardening/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── live-fixture-profile.md
│   ├── channel-health-outcome.md
│   ├── arm-verification-rule.md
│   └── failure-cause-classification.md
└── tasks.md
```

### Source Code (repository root)

```text
clients/python/highbar_client/behavioral_coverage/
├── __init__.py
├── bootstrap.py
├── predicates.py
├── hypotheses.py
├── audit_runner.py
├── registry.py
├── itertesting_runner.py
├── itertesting_report.py
└── [new] live_failure_classification.py

clients/python/tests/behavioral_coverage/
├── test_itertesting_runner.py
├── test_itertesting_report.py
└── [new] test_live_failure_classification.py

tests/headless/
├── _launch.sh
├── aicommand-behavioral-coverage.sh
├── itertesting.sh
├── behavioral-attack.sh
├── behavioral-build.sh
├── behavioral-move.sh
└── scripts/
    ├── minimal.startscript
    └── cheats.startscript
```

**Structure Decision**: Keep implementation in the existing Python behavioral coverage package and `tests/headless/` wrappers. Extend the current bootstrap/predicate/report surfaces instead of introducing a separate live-verification subsystem, and add a small focused classification helper only if the current modules become too overloaded.

## Phase 0 Research Summary

Phase 0 resolves the live-hardening choices needed before design:

1. Extend the current single live bootstrap path into a richer fixture profile instead of creating ad-hoc manual setup or a separate live harness.
2. Treat plugin command channel health as a run-level outcome with explicit degraded/interrupted classification so transport defects do not pollute per-command results.
3. Use arm-specific verification rules for `fight`, `move_unit`, and `build_unit`, derived from the repo’s existing predicate primitives and live-audit hypothesis vocabulary.
4. Standardize one primary failure-cause category per non-verified direct command so reports cleanly separate fixture gaps, transport interruptions, evidence gaps, and real behavioral failures.
5. Validate the hardened path with both repo-local pytest coverage and live/headless command repro workflows instead of relying on report inspection alone.

See [research.md](./research.md).

## Phase 1 Design Summary

Phase 1 introduces a design centered on four explicit live-hardening entities:

- `LiveFixtureProfile` defines the fixture classes the default live run must provision before command dispatch begins.
- `ChannelHealthOutcome` records whether the plugin command channel stayed healthy, degraded, recovered, or interrupted the run.
- `ArmVerificationRule` formalizes which commands use generic verification behavior and which require tuned live evidence windows or predicates.
- `FailureCauseClassification` guarantees each non-verified direct command gets one primary maintainer-facing cause category.

The resulting contracts define the maintainer-visible workflow/report surface rather than a public API. See [data-model.md](./data-model.md), [contracts/live-fixture-profile.md](./contracts/live-fixture-profile.md), [contracts/channel-health-outcome.md](./contracts/channel-health-outcome.md), [contracts/arm-verification-rule.md](./contracts/arm-verification-rule.md), and [contracts/failure-cause-classification.md](./contracts/failure-cause-classification.md).

## Complexity Tracking

No constitution violations or exception justifications are required.

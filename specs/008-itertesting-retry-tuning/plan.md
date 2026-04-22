# Implementation Plan: Itertesting Retry Tuning

**Branch**: `008-itertesting-retry-tuning` | **Date**: 2026-04-22 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/008-itertesting-retry-tuning/spec.md`

## Summary

This feature tunes Itertesting so campaigns remain bounded, predictable, and outcome-focused. The implementation introduces explicit retry intensity profiles (`quick`, `standard`, `deep`), enforces a non-bypassable global cap of 10 improvement runs, and stops early when direct coverage progress stalls. Campaign outcomes must always report a clear stop reason, keep natural verification primary with cheat-assisted escalation only after natural stalls (or explicit maintainer opt-in), and compute the primary success target against directly verifiable commands while reporting non-observable commands separately.

To satisfy runtime and throughput expectations, the campaign loop will use a target-aware governance policy: stop immediately when at least 20 directly verifiable commands are confirmed, limit wasted retries through stall windows, and keep successful target-reaching campaigns within a 15-minute wall-clock envelope in the reference environment.

## Technical Context

**Language/Version**: Python 3.11+ for campaign orchestration/reporting, Bash for repo-local headless wrappers, JSON/Markdown for persisted artifacts.  
**Primary Dependencies**: Existing `clients/python/highbar_client/behavioral_coverage/` package, current command inventory/evidence model, repo-local `tests/headless/` launch workflow, existing gRPC client/proto integration already used by live coverage runs.  
**Storage**: Filesystem artifacts under `reports/itertesting/` (run manifests, campaign summaries, reusable instruction files, report markdown).  
**Testing**: Existing headless scripts plus new unit/integration coverage for retry profile mapping, hard-cap clamping, stall guardrails, stop-reason emission, natural-vs-cheat accounting, and runtime-governance behavior.  
**Target Platform**: Linux x86_64 reference host used by existing live headless verification workflows.  
**Project Type**: Internal CLI-style verification workflow layered on current behavioral coverage tooling.  
**Performance Goals**: Reach at least 20 directly verifiable commands in reference live campaigns; enforce <=15 minutes for successful target-reaching campaigns; avoid runaway retries through stall-based early stop.  
**Constraints**: Global max 10 improvement runs regardless of configured value; natural-first verification priority; separate accounting for natural vs cheat-assisted and directly verifiable vs non-observable commands; deterministic and explainable stop decisions for every campaign completion.  
**Scale/Scope**: Current tracked command inventory with bounded multi-run campaigns and persisted run-to-run progress evidence.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

Constitution version: **1.0.0** (`.specify/memory/constitution.md`).

| # | Principle | Plan status | Evidence / notes |
|---|---|---|---|
| I | Upstream Fork Discipline | PASS | Changes remain in V3-owned paths (`clients/python/highbar_client/behavioral_coverage/`, `tests/headless/`, `reports/`, and `specs/008-itertesting-retry-tuning/`). No upstream-shared C++ engine files are required. |
| II | Engine-Thread Supremacy | PASS | Retry tuning is orchestration/reporting logic around existing RPC calls; no engine-thread or gateway-thread behavior is changed. |
| III | Proto-First Contracts | PASS | No `.proto` schema changes are needed; feature uses existing contracts and updates repo-local workflow/report contracts only. |
| IV | Phased Externalization | PASS | Feature is additive to existing live verification workflows and does not change phase gating or default externalization posture. |
| V | Latency Budget as Shipping Gate | PASS | No transport-path implementation changes are introduced; tuning focuses on campaign governance and reporting. |

**Initial gate result**: **PASS**

**Post-design re-evaluation**: **PASS**. Phase 1 artifacts keep scope inside tooling/workflow docs, preserve transport and threading constraints, and do not introduce constitution exceptions.

## Project Structure

### Documentation (this feature)

```text
specs/008-itertesting-retry-tuning/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── retry-policy-profile.md
│   ├── campaign-stop-decision.md
│   └── campaign-report-summary.md
└── tasks.md
```

### Source Code (repository root)

```text
clients/python/highbar_client/behavioral_coverage/
├── __main__.py
├── registry.py
├── report.py
├── types.py
├── [new] itertesting_retry_policy.py
├── [new] itertesting_campaign.py
└── [new] itertesting_reporting.py

tests/headless/
├── _launch.sh
├── aicommand-behavioral-coverage.sh
├── [new] itertesting.sh
└── scripts/
    ├── minimal.startscript
    └── cheats.startscript

reports/
└── itertesting/
    ├── <campaign-id>/
    └── instructions/
```

**Structure Decision**: Keep implementation in the existing Python behavioral coverage package and headless launch workflow. Add focused retry-governance modules rather than creating a separate subsystem, and keep reviewer/audit artifacts under `reports/itertesting/`.

## Phase 0 Research Summary

Phase 0 resolves retry-governance design choices and operational thresholds:

1. Define deterministic intensity envelopes that can be reasoned about (`quick`, `standard`, `deep`) while still respecting the global 10-run cap.
2. Use direct-coverage deltas across a short rolling window for stall detection so campaigns stop early when additional runs are no longer productive.
3. Preserve natural-first verification and permit cheat escalation only after natural stalls (unless explicitly overridden).
4. Compute success targets from directly verifiable commands, and report non-observable commands as a separate tracking lane.
5. Add runtime governance tied to the 15-minute target so successful campaigns remain bounded and predictable.
6. Persist and reload reusable per-command improvement instructions across campaigns to avoid relearning prior retry strategy.

See [research.md](./research.md).

## Phase 1 Design Summary

Phase 1 introduces a policy-driven campaign model:

- `CampaignRetryPolicy` centralizes profile selection, hard-cap enforcement, stall guardrails, and runtime governance.
- `RetryIntensityProfile` formalizes quick/standard/deep behavior while allowing configured values to be clamped safely.
- `RunProgressSnapshot` and campaign summaries separate natural/cheat and direct/non-observable progress metrics.
- `CampaignStopDecision` guarantees explicit, machine-readable, reviewer-friendly stop reasons for every campaign.
- `ReusableImprovementInstruction` persists command-level next-step guidance across campaign runs.

Interface contracts define configuration shape, stop-decision output, and report summary requirements. See [data-model.md](./data-model.md), [contracts/retry-policy-profile.md](./contracts/retry-policy-profile.md), [contracts/campaign-stop-decision.md](./contracts/campaign-stop-decision.md), and [contracts/campaign-report-summary.md](./contracts/campaign-report-summary.md).

## Complexity Tracking

No constitution violations or exception justifications are required.

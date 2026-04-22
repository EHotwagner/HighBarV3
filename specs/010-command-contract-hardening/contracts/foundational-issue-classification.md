# Contract: Foundational Issue Classification

**Feature**: [Command Contract Hardening](../plan.md)

## Purpose

Define the maintainer-facing issue classes that count as foundational command-contract blockers and therefore must not be reported as ordinary Itertesting opportunities.

## Required Classes

| Issue class | Meaning | Typical source scope |
|-------------|---------|----------------------|
| `target_drift` | Batch-level and command-level intent disagree about which unit should receive the command. | `validator`, `queue_normalization` |
| `validation_gap` | A malformed or semantically incoherent command reached dispatch or late-stage classification because validation was too shallow. | `validator`, `run_classification` |
| `inert_dispatch` | Dispatch completed or appeared accepted, but the command surface is effectively a no-op or maps to no meaningful engine effect. | `dispatcher`, `repro_followup` |

## Classification Rules

1. Foundational issues outrank ordinary setup, evidence, and retry guidance for the same command in the same run.
2. Every foundational issue must include one primary cause and one supporting evidence summary.
3. Reports may retain downstream findings, but those findings are secondary while a foundational issue remains unresolved.
4. Newly observed patterns that do not fit the current classes may be emitted as `needs_pattern_review` / `needs_new_pattern_review`, but they still block normal improvement guidance until triaged.
5. Intentionally effect-free commands such as `cmd-stop` and `cmd-wait` must not be promoted to `inert_dispatch` solely because the harness lacks a durable state-delta signal.

## Report Expectations

- Run summaries expose foundational blockers in a dedicated section.
- Stop or proceed decisions reference the foundational issue ids.
- Deterministic repro links are attached directly to each foundational issue.

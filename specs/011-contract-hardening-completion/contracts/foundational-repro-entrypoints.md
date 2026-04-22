# Contract: Foundational Repro Entrypoints

**Feature**: [Command Contract Hardening Completion](../plan.md)

## Purpose

Guarantee that each reported foundational issue either has a focused rerun path or is explicitly marked as pattern-review-only.

## Required Mapping

| Issue class | Primary entrypoint | Expected signal |
|-------------|--------------------|-----------------|
| `target_drift` | `ctest --test-dir build --output-on-failure -R command_validation_test` | Validator rejects batch-target drift before enqueue. |
| `validation_gap` | `tests/headless/malformed-payload.sh` | Gateway returns `INVALID_ARGUMENT` and does not forward the bad batch. |
| `inert_dispatch` | `tests/headless/test_command_contract_hardening.sh` | Foundational blocker is reported separately from ordinary improvement guidance. |
| `needs_pattern_review` | No deterministic repro | Manifest/report explicitly state that review is required before ordinary improvement work can continue. |

## Required Behaviors

1. Deterministic repros must be independently runnable from the original campaign.
2. Each deterministic repro must be narrowly scoped enough to confirm one foundational issue class.
3. No deterministic issue class may silently lack a repro entry.
4. The no-repro fallback is valid only when the workflow explicitly reports `needs_pattern_review`.

## Maintainer Workflow

1. Read the foundational blocker section in the latest run artifact.
2. Run the linked focused repro when the issue class is deterministic.
3. Validate the expected signal before returning to broader campaigns.
4. When the blocker is `needs_pattern_review`, follow the review instructions instead of guessing at a repro.

# Contract: Deterministic Repro

**Feature**: [Command Contract Hardening](../plan.md)

## Purpose

Guarantee that each foundational command-contract issue points maintainers to a focused, independently runnable confirmation path.

## Required Properties

1. The repro is tied to exactly one primary foundational issue.
2. The repro can be run independently from a full Itertesting campaign.
3. The repro states the expected signal that confirms the defect or verifies the fix.
4. The repro stays narrowly scoped to the issue class it represents and does not depend on unrelated campaign context.

## Preferred Repro Layers

| Repro kind | When to use |
|------------|-------------|
| `unit` | Validator invariants, normalization rules, and command-shape checks. |
| `integration` | Gateway-to-engine command-path behavior that does not require a full headless BAR match. |
| `headless` | End-to-end contract failures that need the live topology or coordinator/plugin boundary. |
| `pytest` | Python-side report gating and contract-health decision logic. |

## Maintainer Workflow

1. See the foundational issue in the run report.
2. Run the linked repro entrypoint.
   Current implementation:
   - `target_drift` → `ctest --test-dir build --output-on-failure -R command_validation_test`
   - `validation_gap` → `tests/headless/malformed-payload.sh`
   - `inert_dispatch` → `tests/headless/test_command_contract_hardening.sh`
3. Confirm the expected signal for the defect.
4. Fix the validator/dispatcher/report logic.
5. Re-run the same repro before returning to broader Itertesting.

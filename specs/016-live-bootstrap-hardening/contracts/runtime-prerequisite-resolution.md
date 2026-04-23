# Contract: Runtime Prerequisite Resolution

**Feature**: [Live Bootstrap Hardening](../plan.md)

## Purpose

Define the shared runtime lookup model for prerequisite def names used by prepared live closeout and the standalone build verification probe.

## Required Behaviors

1. Runtime prerequisite resolution must use the existing callback-based unit-def lookup path available through the client-mode workflow.
2. `tests/headless/behavioral-build.sh` must use the same runtime lookup model as prepared live closeout for its build prerequisite.
3. Manual def-id environment overrides must not remain the normal path for the standalone build probe.
4. Resolution failure must distinguish `missing` from `relay_unavailable`.
5. Resolution status must be reviewable through a structured trace, not only through shell output.

## Required Record Shape

### Runtime prerequisite resolution record

| Field | Meaning |
|-------|---------|
| `prerequisite_name` | The live prerequisite name being resolved. |
| `consumer` | Whether the lookup served live closeout or the standalone build probe. |
| `callback_path` | The callback route used to resolve the prerequisite. |
| `resolved_def_id` | Runtime def id returned by the environment, if any. |
| `resolution_status` | `resolved`, `missing`, or `relay_unavailable`. |
| `reason` | Reviewer-facing success or failure explanation. |

## Review Expectations

- Reviewers can verify that the standalone probe and the main workflow used the same prerequisite identity.
- Def-id drift across BAR versions remains a runtime concern handled by lookup rather than a manual setup step.
- The design reuses the current proto surface and existing callback helpers instead of inventing a new lookup interface.

## Non-Goals

- This contract does not require a new callback id or proto schema.
- This contract does not require every historical shell script to be retrofitted in this feature; it covers the main live workflow and `behavioral-build.sh`.

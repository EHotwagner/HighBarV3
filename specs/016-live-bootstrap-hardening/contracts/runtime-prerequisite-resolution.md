# Contract: Runtime Prerequisite Resolution And Map Source Selection

**Feature**: [Live Bootstrap Hardening](../plan.md)

## Purpose

Define the shared supported-source model for prerequisite def lookup and map-derived targeting used by prepared live closeout and the standalone build verification probe.

## Required Behaviors

1. Runtime prerequisite resolution must use the proven callback-based unit-def lookup path: `CALLBACK_GET_UNIT_DEFS (47)` plus `CALLBACK_UNITDEF_GET_NAME (40)`.
2. `tests/headless/behavioral-build.sh` must use the same runtime lookup model as prepared live closeout for its build prerequisite.
3. Manual def-id environment overrides must not remain the normal path for the standalone build probe.
4. Resolution failure must distinguish `missing` from `relay_unavailable`.
5. When callback-based map inspection is unsupported but `HelloResponse.static_map` is present, both consumers must use that session-start payload as the authoritative source for metal-spot targeting.
6. Deeper commander/build-option diagnostics that depend on unsupported callbacks must degrade explicitly without invalidating successful prerequisite lookup.
7. Resolution and map-source status must be reviewable through structured bundle data, not only through shell output.

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

### Map data source decision

| Field | Meaning |
|-------|---------|
| `consumer` | Whether the source selection served live closeout or the standalone build probe. |
| `selected_source` | Whether map data came from `hello_static_map`, `callback_map`, or was `missing`. |
| `metal_spot_count` | The number of metal spots available from the selected source. |
| `reason` | Reviewer-facing explanation of why that source was selected. |

## Review Expectations

- Reviewers can verify that the standalone probe and the main workflow used the same prerequisite identity.
- Def-id drift across BAR versions remains a runtime concern handled by lookup rather than a manual setup step.
- Reviewers can also see that map-derived targeting used session-start `static_map` when callback-based map inspection was unavailable.
- The design reuses the current proto surface and existing callback helpers instead of inventing a new lookup interface.

## Non-Goals

- This contract does not require a new callback id or proto schema.
- This contract does not require every historical shell script to be retrofitted in this feature; it covers the main live workflow and `behavioral-build.sh`.

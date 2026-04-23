# Contract: Authoritative Transport Fixture Model

**Feature**: [Live Transport Provisioning](../plan.md)

## Purpose

Define how `transport_unit` is represented as an authoritative live fixture class without drifting away from the existing fixture dependency model introduced in 014.

## Required Record Shape

### `transport_provisioning`

| Field | Meaning |
|-------|---------|
| `supported_variants` | The transport unit types that may satisfy `transport_unit` in the current environment. |
| `active_candidate_id` | The current live transport satisfying the class, if any. |
| `candidates` | Every preexisting or newly provisioned transport candidate observed during the run. |
| `lifecycle_events` | Discovery, provisioning, refresh, replacement, fallback, and failure events. |
| `compatibility_checks` | Per-command transport-payload readiness results. |
| `status` | `preexisting`, `provisioned`, `refreshed`, `replaced`, `fallback_provisioned`, `missing`, or `unusable`. |
| `affected_command_ids` | Only the transport-dependent commands blocked by this result. |

### Relationship to `fixture_provisioning`

| Field | Meaning |
|-------|---------|
| `class_statuses[transport_unit]` | The class-level summary row that must agree with `transport_provisioning.status`. |
| `affected_command_ids` | Aggregate blocked commands that must include transport-blocked commands and no unrelated commands. |
| `missing_fixture_classes` | Includes `transport_unit` only when transport provisioning remains `missing` or `unusable`. |

## Required Behaviors

1. `bootstrap.py` remains the only authoritative static source mapping commands to `transport_unit`.
2. `transport_unit` may be satisfied by more than one supported live variant when the environment provides them.
3. A preexisting usable transport must satisfy the class before the workflow attempts new provisioning.
4. A selected candidate must remain alive, usable, and payload-compatible for the pending command.
5. Loss of the current transport must cause either refresh/replacement or an explicit transition to `missing`/`unusable`.

## Review Expectations

- Maintainers can tell which transport variant satisfied coverage for the run.
- Maintainers can see whether the coverage came from discovery, natural provisioning, refresh, replacement, or fallback.
- Reviewers do not need to inspect hidden heuristics or shell state to understand why a transport-dependent command was allowed or blocked.

## Non-Goals

- This contract does not require a new external schema or sidecar artifact.
- This contract does not declare every air unit a valid transport candidate.

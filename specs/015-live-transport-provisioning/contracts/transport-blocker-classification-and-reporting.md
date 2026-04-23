# Contract: Transport Blocker Classification And Reporting

**Feature**: [Live Transport Provisioning](../plan.md)

## Purpose

Define how transport provisioning outcomes flow into failure classification, run reporting, and closeout gating without hiding real remaining blockers.

## Required Behaviors

1. When no usable transport can be obtained, only `cmd-load-onto`, `cmd-load-units`, `cmd-load-units-area`, `cmd-unload-unit`, and `cmd-unload-units-area` may be blocked by transport fixture status.
2. A transport candidate that exists but cannot carry the selected payload must produce transport-specific compatibility detail rather than collapsing into payload-missing or generic behavior-failure text.
3. `transport_interruption` remains distinct from `missing_fixture`; unhealthy-session failures do not get relabeled as successful transport provisioning.
4. Any exceptional fallback used to obtain transport coverage must be visible in `run-report.md` and `manifest.json`.
5. `campaign-stop-decision.json` must continue to block normal tuning while transport remains a foundational blocker.

## Required Record Shape

### `run-report.md`

| Section | Required transport detail |
|---------|---------------------------|
| `## Fixture Provisioning` | Current `transport_unit` status, affected commands, and whether coverage was preexisting, provisioned, refreshed, replaced, fallback-provisioned, missing, or unusable. |
| `### Fixture Class Statuses` | A `transport_unit` row with precise reason text and affected commands. |
| `### Shared Fixture Instances` or equivalent transport detail | The live transport instance(s) or replacement chain used during the run. |
| `## Failure Cause Summary` | Separation between `missing_fixture`, `transport_interruption`, evidence gaps, and behavioral failures. |

### `manifest.json`

| Field | Required transport detail |
|-------|---------------------------|
| `fixture_provisioning` | Class-level status consistent with the report. |
| `transport_provisioning` | Detailed transport lifecycle and compatibility record for the run. |

## Review Expectations

- Maintainers can determine from one run bundle whether the remaining blocker is real transport unavailability, transport-payload incompatibility, or a separate unhealthy-session problem.
- Reviewers can see exactly which commands regained coverage and which ones remain blocked.
- The reporting surface stays compatible with the existing closeout workflow.

## Non-Goals

- This contract does not require report consumers to parse a second artifact to understand transport state.
- This contract does not redefine non-transport fixture reporting.

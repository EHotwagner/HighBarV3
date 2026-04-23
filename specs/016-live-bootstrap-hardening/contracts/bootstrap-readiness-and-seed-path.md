# Contract: Bootstrap Readiness And Seed Path

**Feature**: [Live Bootstrap Hardening](../plan.md)

## Purpose

Define the boundary for deciding whether prepared live closeout can start commander-driven bootstrap naturally or must stop with an explicit readiness outcome.

## Required Behaviors

1. Prepared live closeout must assess bootstrap readiness before the first commander-built bootstrap step becomes a long timeout path.
2. A resource-starved prepared state must be reported explicitly as a bootstrap-readiness outcome rather than collapsing into a later generic build timeout.
3. If the workflow uses a non-natural readiness path to make bootstrap viable, that path must be maintainer-visible and reported distinctly from ordinary prepared-state readiness.
4. Bootstrap-readiness reporting must remain inside the existing run bundle and must not require a separate ad-hoc artifact.
5. A seeded-readiness path must not hide unsupported runtime inspection limits, unrelated command-behavior failures, or fixture failures once bootstrap proceeds.

## Required Record Shape

### Bootstrap readiness assessment

| Field | Meaning |
|-------|---------|
| `readiness_status` | Whether the run was `natural_ready`, `seeded_ready`, `resource_starved`, or `unknown`. |
| `readiness_path` | Whether readiness came from the ordinary prepared state, an explicit seed path, or was unavailable. |
| `first_required_step` | The first commander-built bootstrap requirement being validated. |
| `economy_summary` | Reviewer-facing snapshot of the opening economy state. |
| `reason` | Why the run proceeded, required seeding, or stopped. |

## Review Expectations

- Reviewers can tell from one bundle whether bootstrap was naturally viable.
- Resource starvation is distinguishable from later fixture, capability-limit, or behavior failures.
- Any explicit readiness seed remains visible rather than masquerading as normal natural bootstrap.

## Non-Goals

- This contract does not require a specific implementation mechanism for the seeded-readiness path.
- This contract does not redefine the downstream fixture-provisioning model once bootstrap is viable.

# Contract: Callback Diagnostic Retention

**Feature**: [Live Bootstrap Hardening](../plan.md)

## Purpose

Define how callback-derived diagnostics remain reviewable when bootstrap failures outlive live callback reachability.

## Required Behaviors

1. The workflow must capture the critical callback-derived diagnostics needed for bootstrap failure analysis early enough that late relay loss does not erase them.
2. Late callback refresh is best-effort; failure to refresh must not discard diagnostics already captured successfully.
3. The run bundle must distinguish diagnostics that are still live, diagnostics preserved from earlier capture, and diagnostics that were genuinely unavailable.
4. Callback-retention reporting must separate relay loss from the underlying bootstrap or capability failure being analyzed.
5. The standalone probe and the main workflow may reuse the same diagnostic source, but the authoritative preserved evidence lives in the Itertesting bundle.

## Required Record Shape

### Callback diagnostic snapshot

| Field | Meaning |
|-------|---------|
| `capture_stage` | When the diagnostic was captured or preserved. |
| `availability_status` | Whether the diagnostic is `live`, `cached`, or `missing`. |
| `source` | Whether the evidence came from a live callback, preserved earlier capture, or was not available. |
| `diagnostic_scope` | The diagnostic areas covered, such as commander def/build options/economy. |
| `summary` | Reviewer-facing explanation of what was captured or lost. |

## Review Expectations

- Maintainers can still inspect callback-derived commander/bootstrap evidence in long failure paths.
- A `relay_unavailable` late path does not automatically imply the diagnostic evidence is gone.
- Diagnostic retention remains visible in the same bundle as fixture, transport, and contract-health reporting.

## Non-Goals

- This contract does not require the callback relay to remain reachable forever.
- This contract does not introduce a separate diagnostics store outside the existing bundle.

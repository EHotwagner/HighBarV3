# Contract: Runtime Capability And Diagnostic Sourcing

**Feature**: [Live Bootstrap Hardening](../plan.md)

## Purpose

Define how the workflow records supported callback surfaces, distinguishes unsupported inspection from relay loss, and preserves usable diagnostics in a callback-limited runtime.

## Required Behaviors

1. The workflow must record which callback surfaces are supported on the current host and which groups are explicitly unsupported.
2. Diagnostics that depend on unsupported callbacks must be reported as capability-limited rather than as generic relay or workflow failures.
3. Successful early prerequisite-resolution evidence must remain reviewable even if later deeper diagnostics are unavailable on the host.
4. Late transport or relay loss must remain distinct from “unsupported on this host.”
5. The authoritative maintained evidence for capability-aware diagnostics lives in the Itertesting bundle, even when the standalone probe reuses the same supported-source model.

## Required Record Shape

### Runtime capability profile

| Field | Meaning |
|-------|---------|
| `supported_callbacks` | Callback ids proven usable on the current host. |
| `supported_scopes` | Human-readable scopes available on the host, such as prerequisite lookup or session-start map data. |
| `unsupported_callback_groups` | Reviewer-facing groups that are unavailable on the host. |
| `map_data_source_status` | Whether map data is available from session-start `static_map`, callback inspection, or not at all. |
| `notes` | Summary of what the host can and cannot do. |

### Callback diagnostic snapshot

| Field | Meaning |
|-------|---------|
| `capture_stage` | When the diagnostic was captured or preserved. |
| `availability_status` | Whether the diagnostic is `live`, `cached`, or `missing`. |
| `source` | Whether the evidence came from a live callback, preserved earlier capture, or was not available. |
| `diagnostic_scope` | The diagnostic areas covered, such as commander def/build options/economy. |
| `summary` | Reviewer-facing explanation of what was captured, what was unsupported, and what was lost. |

## Review Expectations

- Maintainers can see why prerequisite lookup worked even when deeper commander/build-option diagnostics were unavailable.
- A `relay_unavailable` late path does not automatically imply the diagnostic evidence is gone.
- Capability-aware diagnostic reporting remains visible in the same bundle as fixture, transport, and contract-health reporting.

## Non-Goals

- This contract does not require the callback relay to remain reachable forever.
- This contract does not introduce a separate diagnostics store outside the existing bundle.

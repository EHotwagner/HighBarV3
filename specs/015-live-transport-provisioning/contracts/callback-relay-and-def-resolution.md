# Contract: Callback Relay And Def Resolution

**Feature**: [Live Transport Provisioning](../plan.md)

## Purpose

Define the implementation boundary for runtime transport unit-def resolution in the client-mode workflow.

## Required Behaviors

1. The maintainer-facing coordinator endpoint must relay `InvokeCallback` on the existing `HighBarProxy` service used by live Itertesting.
2. Runtime unit-def resolution for supported transport variants must use the existing callback contract rather than hardcoded unit-def ids.
3. The Python behavioral-coverage workflow may populate `BootstrapContext.def_id_by_name` from callback results and then reuse that map throughout transport provisioning.
4. Failure to resolve a transport def at runtime must remain explicit in provisioning/reporting and must not silently degrade into unrelated behavior failure.
5. No `.proto` schema change is required unless implementation proves the existing callback contract is insufficient.

## Required Record Shape

### Transport resolution trace

| Field | Meaning |
|-------|---------|
| `variant_id` | Transport unit name being resolved. |
| `callback_path` | Callback id or lookup path used to resolve the variant. |
| `resolved_def_id` | Runtime unit-def id returned by the live environment, if successful. |
| `resolution_status` | `resolved`, `missing`, or `relay_unavailable`. |
| `reason` | Reviewer-facing explanation when resolution fails or falls back. |

## Review Expectations

- Reviewers can see that the workflow used the real client-mode endpoint rather than an out-of-band local assumption.
- The plan preserves reuse of the current proto contracts and generated client stubs.
- Relay gaps remain isolated to the coordinator/Python workflow rather than leaking into report semantics as fake fixture blockers.

## Non-Goals

- This contract does not require a transport-specific callback id.
- This contract does not require implementation to move provisioning policy into the plugin.

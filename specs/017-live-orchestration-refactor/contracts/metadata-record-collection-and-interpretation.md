# Contract: Metadata Record Collection And Interpretation

## Purpose

Define the single collection seam and single interpretation seam for live orchestration metadata so new record types do not depend on raw row filtering, marker strings, or incidental ordering.

## Requirements

1. Live execution must emit direct command outcomes separately from metadata records; metadata collection must not rely on `arm_name` marker values embedded in command rows.
2. Each metadata record type must have exactly one authoritative collection definition and exactly one authoritative interpretation rule.
3. Interpretation must consume typed metadata records and explicit run-mode policy, not repeated rescans of raw live rows.
4. Existing bundle concerns such as bootstrap readiness, runtime capability profile, prerequisite resolution, map-source selection, and standalone probe parity must continue to be represented through the same maintainer-visible bundle surface.
5. Adding a new metadata record type must require changes only in the declared collection owner and interpretation owner for that type.

## Authoritative record map

| Record type | Collection owner | Interpretation owner | Primary bundle concern |
|-------------|------------------|----------------------|------------------------|
| `bootstrap_readiness` | Live execution seam | Interpretation seam | Bootstrap readiness summary |
| `runtime_capability_profile` | Live execution seam | Interpretation seam | Capability-aware diagnostics |
| `callback_diagnostic` | Live execution seam | Interpretation seam | Preserved callback diagnostics |
| `prerequisite_resolution` | Live execution seam or standalone probe | Interpretation seam | Runtime prerequisite identity |
| `map_source_decision` | Live execution seam or standalone probe | Interpretation seam | Map-derived targeting source |
| `standalone_build_probe` | Standalone probe adapter | Interpretation seam | Probe parity and capability limits |

## Invariants

1. The maintainer workflow may continue to serialize metadata into the bundle, but interpretation is no longer allowed to depend on raw marker-row ordering.
2. `itertesting_runner.py` must not become a second collection owner for metadata types that originate during live execution.
3. Record interpretation must be deterministic for a given ordered metadata list and run-mode policy.

## Expected outcomes

- Maintainers can add or modify a metadata type without editing unrelated fixture or report code paths.
- The bundle remains stable even when internal collection ownership changes.
- Future refactors stop growing `behavioral_coverage/__init__.py` and `itertesting_runner.py` as catch-all modules for unrelated metadata behavior.

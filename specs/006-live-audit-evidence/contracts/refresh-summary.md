# Contract — Refresh Summary

**Applies to**: run-end stdout summaries and the high-level summary content mirrored into `audit/README.md`.  
**Referenced from**: [data-model.md](../data-model.md) (`RefreshSummary`).

## Required summary statements

Every completed live refresh must surface:

1. The selected run identifier
2. Whether each deliverable is `refreshed`, `partial`, or `not refreshed live`
3. Counts for verified, blocked, broken, drifted, and not-refreshed rows
4. The most important failure reasons when the run is partial or incomplete

## Output constraints

- The summary must be derivable from the persisted manifest.
- The summary must not claim a fully refreshed audit if any deliverable or row remains not refreshed live.
- The summary should remain short enough for shell output, but rich enough for a reviewer to decide whether to trust the checked-in artifacts.

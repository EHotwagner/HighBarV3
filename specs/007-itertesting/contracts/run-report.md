# Contract — Run Report

**Feature**: [Itertesting](../spec.md)  
**Plan**: [plan.md](../plan.md)

The run report is the reviewer-facing markdown artifact for one Itertesting run. It is written under `reports/itertesting/<run-id>/run-report.md`.

## Required sections

1. Run metadata
2. Coverage summary
3. Comparison with previous run, when available
4. Newly verified commands
5. Still unverified commands with reasons
6. Improvement actions for the next run or stop reason

## Minimum content requirements

- Run metadata must include `run_id`, timestamps, sequence index, and setup mode.
- Coverage summary must show:
  - total tracked commands
  - total verified
  - naturally verified
  - cheat-assisted verified
  - inconclusive
  - blocked
  - failed
- Previous-run comparison must state whether coverage improved, regressed, or stalled.
- Every unverified command must include a blocking, failure, or inconclusive reason.
- Every cheat-assisted verified command must be labeled as such.
- The report must be understandable without reading raw engine output.

## Example outline

```md
# Itertesting Run Report

> Run: `itertesting-20260422T101530Z`
> Sequence: 1
> Setup mode: mixed

## Coverage Summary

- Tracked commands: 66
- Verified total: 24
- Verified naturally: 19
- Verified cheat-assisted: 5
- Inconclusive: 18
- Blocked: 20
- Failed: 4

## Compared With Previous Run

- Coverage delta: +3 verified
- Natural delta: +1
- Cheat-assisted delta: +2
- Overall result: improved

## Newly Verified Commands

- `cmd-build-unit` — cheat-assisted — new unit observed under construction.

## Still Unverified

- `cmd-patrol` — inconclusive — movement diff still masked by AI reissuance.
- `cmd-capture` — blocked — prerequisite target state unavailable in natural setup.

## Next Improvements

- Escalate `cmd-capture` to cheat-assisted unit provisioning.
- Add stronger target preparation for `cmd-patrol`.
```

## Rules

- The report is derived from the run manifest, not hand-maintained.
- The report should remain concise enough for reviewers to scan quickly, while still covering every unverified command somewhere in the artifact bundle.

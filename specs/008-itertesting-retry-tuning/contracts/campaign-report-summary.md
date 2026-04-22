# Contract — Campaign Report Summary

**Feature**: [Itertesting Retry Tuning](../spec.md)  
**Plan**: [plan.md](../plan.md)

This contract defines minimum required summary content for each run report and campaign-level summary artifact.

## Required summary metrics

| Metric | Semantics |
|-------|-----------|
| `tracked_commands_total` | Total commands in inventory for the run. |
| `directly_verifiable_total` | Commands included in primary coverage target set. |
| `direct_verified_natural` | Directly verifiable commands verified naturally. |
| `direct_verified_cheat_assisted` | Directly verifiable commands verified with cheat-assisted setup. |
| `direct_verified_total` | Sum of natural + cheat-assisted direct verified. |
| `direct_unverified_total` | Direct subset not verified (blocked/inconclusive/failed). |
| `non_observable_tracked_total` | Separate tracking lane for non-direct commands. |
| `runtime_elapsed_seconds` | Campaign wall-clock elapsed at report point. |
| `configured_improvement_runs` | Requested retry budget. |
| `effective_improvement_runs` | Budget after hard-cap clamping. |
| `stop_reason` | Canonical stop reason from stop decision contract. |

## Required report sections

1. `Run Metadata` (run id, sequence index, setup mode, timestamps)
2. `Coverage Summary` (direct/non-observable split + natural/cheat split)
3. `Compared With Previous Run` (improved/regressed/stalled) when prior run exists
4. `Intensity and Governance` (configured vs effective retries, warnings)
5. `Stop Reason` (when campaign completes)
6. `Unverified Direct Commands` (blocking reason and next action)
7. `Instruction Updates` (command id, revision, status, and guidance text)

## Rules

- `direct_verified_total = direct_verified_natural + direct_verified_cheat_assisted`.
- Primary success target evaluation (`>=20`) must use `direct_verified_total` only.
- Non-observable command counts must be shown but excluded from target pass/fail logic.
- Any disproportionate-intensity warning must appear in the governance section with a concrete trigger statement.

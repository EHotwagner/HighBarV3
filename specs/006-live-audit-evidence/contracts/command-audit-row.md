# Contract — Refreshed Command Audit Row

**Applies to**: each rendered row or row-block in `audit/command-audit.md`.  
**Referenced from**: [plan.md](../plan.md), [data-model.md](../data-model.md).

## Required row content

Every row must still identify the underlying command or RPC and retain the 004 row vocabulary, but the refreshed version must also expose freshness explicitly.

## Mandatory fields

| Field | Requirement |
|-------|-------------|
| Row identifier | Stable 004 `row_id` such as `cmd-build-unit` or `rpc-hello`. |
| Outcome bucket | Current row classification from the latest completed live run. |
| Freshness state | Must state whether the row was refreshed live, drifted, or not refreshed live. |
| Dispatch citation | Existing source citation remains required. |
| Evidence or failure reason | Refreshed rows show current evidence; non-refreshed rows show why current evidence is missing. |
| Reproduction or hypothesis command | Existing row-level workflow path remains visible. |

## Rendering rules

- A row with fresh evidence must cite evidence from the latest completed live run only.
- A row marked `not refreshed live` must not include seed wording as if it were current evidence.
- A drifted row must make the change from the prior completed run visible in reviewer-facing text.

## Compatibility rule

The refreshed row format may add freshness metadata, but it must preserve stable row ids and retain reviewer-facing linkage to `hypothesis-plan.md` and `v2-v3-ledger.md`.

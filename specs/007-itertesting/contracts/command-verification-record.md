# Contract — Command Verification Record

**Feature**: [Itertesting](../spec.md)  
**Plan**: [plan.md](../plan.md)

Each command verification record describes the outcome for exactly one tracked command within one Itertesting run.

## Required fields

| Field | Type | Allowed values / semantics |
|-------|------|----------------------------|
| `command_id` | string | Stable command row id, consistent across runs. |
| `command_name` | string | Human-readable arm or command name. |
| `category` | string | Existing registry category. |
| `attempt_status` | enum | `verified`, `inconclusive`, `blocked`, `failed`. |
| `verification_mode` | enum | `natural`, `cheat-assisted`, `not-attempted`. |
| `evidence_kind` | enum | `game-state`, `live-artifact`, `dispatch-only`, `none`. |
| `verified` | boolean | True only for direct evidence-backed verification. |
| `improvement_state` | enum | `none`, `candidate`, `applied`, `exhausted`. |
| `source_run_id` | string | Parent run id. |

## Conditional fields

| Field | Required when | Semantics |
|-------|----------------|-----------|
| `evidence_summary` | `verified=true` | Reviewer-readable proof summary. |
| `evidence_artifact_path` | row-specific artifact exists | Relative or absolute path to detailed live evidence. |
| `blocking_reason` | `verified=false` | Why the command was not verified. |
| `setup_actions` | non-empty setup manipulation occurred | Natural setup prep or cheat-backed provisioning steps used for this command. |
| `improvement_note` | `improvement_state != none` | What changed for this command or why no better next step exists. |

## Rules

- `dispatch-only` evidence can never produce `verified=true`.
- `verification_mode=cheat-assisted` must be visibly distinguishable in reports and summaries.
- A command that remains unverified after a run must either have a candidate/applied improvement note or be marked exhausted with a clear reason.
- Records should be stable enough to compare across runs by `command_id`.

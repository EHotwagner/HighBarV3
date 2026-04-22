# Contract — Itertesting Run Manifest

**Feature**: [Itertesting](../spec.md)  
**Plan**: [plan.md](../plan.md)

The run manifest is the machine-readable source of truth for one Itertesting run. It is written under `reports/itertesting/<run-id>/manifest.json` and must be sufficient to regenerate the reviewer markdown for that run.

## Shape

```json
{
  "run_id": "itertesting-20260422T101530Z",
  "campaign_id": "itertesting-20260422T101500Z",
  "started_at": "2026-04-22T10:15:30Z",
  "completed_at": "2026-04-22T10:19:42Z",
  "sequence_index": 1,
  "engine_pin": "recoil_2025.06.19",
  "gametype_pin": "test-29926",
  "setup_mode": "mixed",
  "summary": { "...": "see run-report contract summary fields" },
  "previous_run_comparison": { "...": "optional comparison block" },
  "improvement_actions": [
    {
      "action_id": "cmd-build-unit-02",
      "command_id": "cmd-build-unit",
      "action_type": "cheat-escalation",
      "trigger_reason": "natural attempts stalled",
      "applies_to_run_id": "itertesting-20260422T101530Z",
      "status": "applied",
      "details": "Switch setup to cheats.startscript and provision prerequisite units."
    }
  ],
  "command_records": [
    {
      "command_id": "cmd-build-unit",
      "command_name": "build_unit",
      "category": "channel_a_command",
      "attempt_status": "verified",
      "verification_mode": "cheat-assisted",
      "evidence_kind": "game-state",
      "verified": true,
      "evidence_summary": "New armmex appeared under construction after dispatch.",
      "evidence_artifact_path": "reports/itertesting/itertesting-20260422T101530Z/rows/cmd-build-unit.md",
      "blocking_reason": null,
      "setup_actions": [
        "enabled cheats",
        "spawned prerequisite builder"
      ],
      "improvement_state": "applied",
      "improvement_note": "Escalated after two natural attempts produced no targetable builder path.",
      "source_run_id": "itertesting-20260422T101530Z"
    }
  ]
}
```

## Rules

- `run_id` must be unique within `reports/itertesting/`.
- The manifest must contain one `command_records[]` entry for every tracked command.
- `verified=true` is only valid when `evidence_kind` is `game-state` or `live-artifact`.
- `verification_mode=cheat-assisted` requires at least one cheat-backed `setup_actions` entry.
- `previous_run_comparison` is omitted on the first run in a campaign.

## Compatibility

- New fields may be added, but existing field names and semantics should remain stable across minor iterations of the feature.
- Reports should consume the manifest rather than re-deriving command outcomes from raw logs.

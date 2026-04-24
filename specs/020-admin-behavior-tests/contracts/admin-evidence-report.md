# Contract: Admin Evidence Report

## Artifact Layout

The suite writes artifacts under:

```text
build/reports/admin-behavior/
├── run-report.md
├── evidence.jsonl
├── summary.csv
├── logs/
│   ├── engine.log
│   └── coordinator.log
└── repeats/
    ├── repeat-1.json
    ├── repeat-2.json
    └── repeat-3.json
```

`run-report.md` is the human-readable summary. `evidence.jsonl` is the durable per-scenario record stream. `summary.csv` is a compact CI-friendly table.

## Evidence JSONL Record

Each line is one `AdminEvidenceRecord`:

```json
{
  "scenario_id": "pause_match",
  "action_name": "pause",
  "caller": {"client_id": "admin-suite", "role": "operator"},
  "request": {"action_seq": 1, "client_action_id": 1001, "action": "pause"},
  "result": {"status": "ADMIN_ACTION_EXECUTED", "issues": [], "frame": 123, "state_seq": 456},
  "expected_observation": "frame progression stops within 10s",
  "actual_observation": "frame 124 remained stable for 2 observation windows",
  "passed": true,
  "diagnostics": [],
  "log_location": "build/reports/admin-behavior/logs/engine.log"
}
```

Request and result values may be rendered from proto JSON, but the report contract is the field meaning, not a separate command protocol.

## Summary CSV

Columns:

- `scenario_id`
- `action_name`
- `category`
- `result_status`
- `observed`
- `passed`
- `failure_class`
- `log_location`

Allowed `category` values:

- `success`
- `rejection`
- `capability`
- `cleanup`
- `prerequisite`

Allowed `failure_class` values:

- empty string for passing rows
- `prerequisite_missing`
- `permission_not_rejected`
- `invalid_value_not_rejected`
- `lease_conflict_not_rejected`
- `effect_not_observed`
- `unexpected_mutation`
- `capability_mismatch`
- `cleanup_failed`
- `internal_error`

## Human Report Requirements

`run-report.md` must include:

- run id, fixture id, repeat index, start and end timestamps
- prerequisite status and clear prerequisite failure text when applicable
- capability profile used for scenario selection
- one row per admin action category with request, expected observation, actual observation, and pass status
- failure details with action name, expected state transition, actual state observed, and log location
- cleanup status
- final exit classification

## Repeatability Evidence

For SC-006, a repeat command runs the suite three times in the same prepared environment. Each repeat writes a compact JSON summary containing final status, cleanup status, leftover pause/speed/lease indicators, and counts of spawned/transferred/resource-mutated entities that could affect later runs.

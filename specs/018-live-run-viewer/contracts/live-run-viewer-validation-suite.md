# Contract: Live Run Viewer Validation Suite

## Purpose

Define the validation loop for proving that BNV watch mode integrates with the live Itertesting workflow without breaking existing non-watch behavior.

## Validation matrix

| Validation target | Command | Evidence |
|-------------------|---------|----------|
| Watch profile parsing and preflight | `uv run --project clients/python pytest clients/python/tests/behavioral_coverage/test_bnv_watch.py clients/python/tests/behavioral_coverage/test_watch_registry.py` | Default profile behavior, profile overrides, BNV path resolution, and attach-later selection remain deterministic. |
| Runner integration and failure policy | `uv run --project clients/python pytest clients/python/tests/behavioral_coverage/test_itertesting_runner.py` | Requested watch readiness failures abort correctly, non-watch runs remain unchanged, and attach-later selection obeys the active-index rules. |
| Bundle and report rendering | `uv run --project clients/python pytest clients/python/tests/behavioral_coverage/test_itertesting_report.py` | Manifest/report surfaces render watch lifecycle state and reasons coherently. |
| Headless watch validation | `tests/headless/test_live_run_viewer.sh` | Prepared live runs can launch BNV on a viewer-capable host, and watch-unavailable conditions stay explicit. |
| Prepared maintainer rerun | `HIGHBAR_ITERTESTING_WATCH=true HIGHBAR_ITERTESTING_MAX_IMPROVEMENT_RUNS=0 tests/headless/itertesting.sh` | The normal maintainer wrapper can enable watch mode without changing the non-watch workflow. |

## Acceptance rules

1. A requested watched run that fails BNV readiness must fail before live execution begins and emit a user-readable reason.
2. A non-watch run must still require no additional operator steps.
3. Attach-later without an explicit run id may auto-select only when exactly one compatible active run exists.
4. Manifest, report, stdout, and active-index state must agree on watch lifecycle and reason.
5. Viewer disconnect after launch must remain diagnosable without rewriting the original run identity.

## Artifact inspection

Inspect the latest:

- `reports/itertesting/active-watch-sessions.json`
- `reports/itertesting/<run-id>/manifest.json`
- `reports/itertesting/<run-id>/run-report.md`

Expected behavior:

- The active index reflects current attachability without silently guessing a target.
- The manifest/report record watch request, preflight result, and viewer access state with consistent wording.
- Watched-run failures and later disconnects remain distinguishable in the persisted artifacts.

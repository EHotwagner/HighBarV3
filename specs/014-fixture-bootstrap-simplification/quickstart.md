# Quickstart — Fixture Bootstrap Simplification

**Branch**: `014-fixture-bootstrap-simplification`  
**Plan**: [plan.md](./plan.md)

This quickstart defines the minimum validation loop for proving that richer fixture provisioning improves live command coverage without reintroducing channel instability or duplicate blocker semantics.

## Preconditions

1. Use the normal Linux reference environment for BAR headless workflows, the coordinator runtime, and the Python behavioral-coverage tooling.
2. Ensure `uv` is available and the existing live wrapper prerequisites used by `tests/headless/itertesting.sh` are satisfied.
3. Keep `reports/itertesting/` writable so each rerun emits a manifest, report, and stop-decision artifact.
4. Run from the repository root on branch `014-fixture-bootstrap-simplification`.

## 1. Validate fixture model and report semantics

```bash
uv run --project clients/python pytest \
  clients/python/tests/behavioral_coverage/test_live_failure_classification.py \
  clients/python/tests/behavioral_coverage/test_itertesting_runner.py \
  clients/python/tests/behavioral_coverage/test_itertesting_report.py
```

Expected behavior:

- One authoritative fixture dependency path drives classification and reporting.
- Fixture provisioning output exposes planned, provisioned, missing, and affected-command information.
- No report path relies on a separate simplified-bootstrap blocker list.

## 2. Run the synthetic hardening check

```bash
tests/headless/test_live_itertesting_hardening.sh
```

Expected behavior:

- The generated bundle still contains `fixture_profile`, `fixture_provisioning`, `channel_health`, and `failure_classifications`.
- Fixture-dependent commands are blocked only through the authoritative provisioning result.
- The report still renders `## Fixture Provisioning`, `## Channel Health`, and `## Failure Cause Summary`.
- The report and wrapper also expose `## Command Semantic Inventory`, `## Semantic Gates`, and terminal `semantic_inventory` / `semantic_gates` summaries for exact BAR command ids and non-fixture blockers.

## 3. Run campaign/report coverage checks

```bash
uv run --project clients/python pytest \
  clients/python/tests/behavioral_coverage/test_itertesting_runner.py \
  clients/python/tests/behavioral_coverage/test_itertesting_report.py
tests/headless/test_itertesting_campaign.sh
```

Expected behavior:

- Chained runs still emit manifest, report, and stop-decision artifacts.
- Contract-health decisions continue to block normal tuning while missing fixtures remain.

## 4. Run three prepared live closeout reruns

```bash
for i in 1 2 3; do
  HIGHBAR_ITERTESTING_MAX_IMPROVEMENT_RUNS=0 tests/headless/itertesting.sh
done
```

Expected behavior:

- Each run keeps healthy channel status while the richer fixture workflow is enabled.
- The number of commands blocked solely by missing fixtures decreases from the current baseline.
- Commands still lacking a valid class stay explicitly fixture-blocked by named class instead of falling back to generic simplified-bootstrap text.

## 5. Inspect the latest bundle

Review the newest:

- `reports/itertesting/<run-id>/manifest.json`
- `reports/itertesting/<run-id>/run-report.md`
- `reports/itertesting/<run-id>/campaign-stop-decision.json`

Expected behavior:

- The bundle shows the planned fixture classes, current class statuses, missing classes, and affected commands from one model.
- Shared or refreshed fixtures are visible enough to explain why later dependent commands were allowed or blocked.
- Exact BAR command ids `32102`, `34571`, `34922`, `34923`, `34924`, `34925`, and `37382` appear in the semantic inventory when reviewing custom-command surfaces.
- Semantic-gate outcomes distinguish helper-parity, Lua rewrite, unit-shape, and mod-option blockers from true missing fixtures.
- `channel_health` remains healthy on successful closeout runs.

## 6. Optional stale-fixture confirmation

If the environment can force a prepared fixture to become unusable mid-run, rerun the same workflow and confirm the replacement path:

```bash
HIGHBAR_ITERTESTING_MAX_IMPROVEMENT_RUNS=0 tests/headless/itertesting.sh
```

Expected behavior:

- The affected class becomes `refreshed` when replacement succeeds or stays explicitly `unusable`/`missing` when refresh fails.
- Only commands depending on that class are blocked.

## 7. Closeout gate

Treat 014 as ready for normal Itertesting tuning only when all of the following hold:

1. The targeted pytest suite and headless hardening checks pass.
2. Three consecutive prepared live closeout runs complete with healthy channel status.
3. The six currently missing fixture classes are either provisioned/refreshed successfully or reported explicitly by class name.
4. The run bundle no longer depends on duplicate simplified-bootstrap blocker logic.
5. Commands still lacking a valid setup remain clearly fixture-blocked rather than appearing as transport or behavior failures.

# Quickstart — Live Orchestration Refactor

**Branch**: `017-live-orchestration-refactor`  
**Plan**: [plan.md](./plan.md)

This quickstart defines the validation loop for proving that live behavioral-coverage orchestration is split cleanly between execution, metadata collection, and interpretation without changing the maintainer-facing workflow.

## Preconditions

1. Use the normal Linux reference environment for BAR headless workflows, the client-mode coordinator runtime, and the Python behavioral-coverage tooling.
2. Ensure `uv` is available and the existing prerequisites for `tests/headless/itertesting.sh` are satisfied.
3. Keep `reports/itertesting/` writable so each validation run emits a manifest, report, and stop-decision bundle.
4. Run from the repository root on branch `017-live-orchestration-refactor`.

## 1. Validate the metadata collection seam

```bash
uv run --project clients/python pytest \
  clients/python/tests/behavioral_coverage/test_live_execution.py \
  clients/python/tests/behavioral_coverage/test_metadata_records.py
```

Expected behavior:

- Live execution emits command rows and metadata records through separate structures.
- Each known metadata type has one typed collection definition.
- Unknown metadata records are preserved rather than silently dropped.

## 2. Validate fixture and transport interpretation

```bash
uv run --project clients/python pytest \
  clients/python/tests/behavioral_coverage/test_itertesting_runner.py \
  clients/python/tests/behavioral_coverage/test_live_failure_classification.py
```

Expected behavior:

- Fixture availability is derived from explicit transitions and run-mode policy rather than marker-row ordering.
- The latest explicit fixture state is authoritative for final availability while earlier states remain visible as history.
- Live runs without explicit transport evidence remain `unknown` or `unproven`, and synthetic or skipped-live runs stay mode-qualified non-live.
- Unknown metadata interpretation emits warnings and blocks fully interpreted or successful classification.

## 3. Validate bundle and report rendering

```bash
uv run --project clients/python pytest \
  clients/python/tests/behavioral_coverage/test_itertesting_report.py \
  clients/python/tests/test_behavioral_registry.py
```

Expected behavior:

- `manifest.json` and `run-report.md` remain stable as the maintainer review surface.
- Interpretation warnings and layer-trace detail, when present, render without contradicting fixture, transport, or blocker summaries.
- `fully_interpreted`, `interpretation_warnings`, and `decision_trace` stay aligned between the manifest and report.
- Existing bootstrap, capability-profile, prerequisite-resolution, and map-source sections still agree with the underlying manifest data.

## 4. Run the synthetic hardening and campaign validation suites

```bash
tests/headless/test_live_itertesting_hardening.sh
tests/headless/test_itertesting_campaign.sh
```

Expected behavior:

- Synthetic and skipped-live modes still produce valid bundles without being misclassified as established live evidence.
- Bundle/report generation remains coherent when bootstrap metadata exists but fixture or transport proof does not.
- No contradictory fixture-availability claims appear in the regression suite.

## 5. Run prepared live closeout reruns

```bash
for i in 1 2 3; do
  HIGHBAR_ITERTESTING_MAX_IMPROVEMENT_RUNS=0 tests/headless/itertesting.sh
done
```

Expected behavior:

- Prepared live reruns keep healthy channel behavior and remain inside the established bootstrap and fixture budget.
- The resulting bundle identifies whether a blocker came from execution, metadata interpretation, or existing failure classification logic.
- A run that records bootstrap metadata but no downstream fixture proof does not claim unproven fixture or transport availability.

## 6. Inspect the latest bundle

Review the newest:

- `reports/itertesting/<run-id>/manifest.json`
- `reports/itertesting/<run-id>/run-report.md`
- `reports/itertesting/<run-id>/campaign-stop-decision.json`

Expected behavior:

- Major decisions can be traced back to execution, metadata, or interpretation ownership without reverse-engineering oversized modules.
- Any unhandled metadata record is preserved in the manifest and surfaced as a maintainer-visible warning.
- Fixture and transport summaries agree with the latest explicit evidence and the selected run-mode policy.
- Review `fully_interpreted`, `interpretation_warnings`, and `decision_trace` before treating the run as ready for normal Itertesting tuning.

## 7. Closeout gate

Treat 017 as ready for `/speckit.tasks` only when all of the following hold:

1. The metadata collection seam, interpretation seam, and report rendering tests pass independently.
2. Synthetic and skipped-live bundles remain valid but clearly marked as non-live-qualified where required.
3. Prepared live reruns show no contradictory fixture or transport claims in the bundle.
4. Adding a metadata record requires updates only in the declared collection and interpretation seams.
5. Maintainers can inspect a representative live failure and identify the responsible layer within the bundle and targeted tests.

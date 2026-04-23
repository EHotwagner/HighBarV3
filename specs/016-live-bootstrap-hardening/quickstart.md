# Quickstart — Live Bootstrap Hardening

**Branch**: `016-live-bootstrap-hardening`  
**Plan**: [plan.md](./plan.md)

This quickstart defines the minimum validation loop for proving that prepared live closeout now handles resource-starved starts explicitly, preserves callback-derived diagnostics through long bootstrap failures, and keeps `tests/headless/behavioral-build.sh` aligned with runtime callback-based prerequisite resolution.

## Preconditions

1. Use the normal Linux reference environment for BAR headless workflows, the client-mode coordinator runtime, and the Python behavioral-coverage tooling.
2. Ensure `uv` is available and the same live prerequisites used by `tests/headless/itertesting.sh` are satisfied.
3. Keep `reports/itertesting/` writable so each rerun emits a manifest, report, and stop-decision artifact.
4. Run from the repository root on branch `016-live-bootstrap-hardening`.

## 1. Validate the behavioral model and report semantics

```bash
uv run --project clients/python pytest \
  clients/python/tests/behavioral_coverage/test_live_failure_classification.py \
  clients/python/tests/behavioral_coverage/test_itertesting_runner.py \
  clients/python/tests/behavioral_coverage/test_itertesting_report.py \
  clients/python/tests/test_behavioral_registry.py
```

Expected behavior:

- Bootstrap-readiness outcomes are represented explicitly in the behavioral-coverage model.
- Callback-diagnostic retention and prerequisite-resolution traces render through the existing bundle/report surface.
- The standalone-probe prerequisite path no longer depends on a manual def-id override in the model.

## 2. Run the synthetic hardening and campaign validation suites

```bash
tests/headless/test_live_itertesting_hardening.sh
tests/headless/test_itertesting_campaign.sh
```

Expected behavior:

- The generated bundle still contains coherent fixture, channel-health, and failure-cause sections.
- Added readiness and diagnostic-retention state agrees across `manifest.json` and `run-report.md`.
- Campaign/report generation remains stable after the new reporting detail is added.

## 3. Validate the standalone build probe

```bash
tests/headless/behavioral-build.sh
```

Expected behavior:

- The probe resolves its prerequisite from the live runtime instead of requiring `HIGHBAR_ARMMEX_DEF_ID` as the normal path.
- If callback resolution is unavailable, the probe fails with an explicit runtime-resolution reason rather than a stale env-var setup message.
- The probe’s resolved prerequisite identity matches the one the main workflow would use in the same environment.
- The probe emits `behavioral-build-outcome.json` under the active runtime directory so maintainers can inspect the resolved prerequisite identity and dispatch result directly.

## 4. Run prepared live closeout reruns

```bash
for i in 1 2 3; do
  HIGHBAR_ITERTESTING_MAX_IMPROVEMENT_RUNS=0 tests/headless/itertesting.sh
done
```

Expected behavior:

- Each run either starts from a naturally viable prepared state or reports an explicit bootstrap-readiness outcome before the first commander-build timeout dominates the failure detail.
- Long bootstrap failures still leave callback-derived diagnostics reviewable in the final bundle.
- Otherwise healthy runs do not regress channel-health or the existing fixture-provisioning budget because of the hardening changes.

## 5. Inspect the latest bundle

Review the newest:

- `reports/itertesting/<run-id>/manifest.json`
- `reports/itertesting/<run-id>/run-report.md`
- `reports/itertesting/<run-id>/campaign-stop-decision.json`
- terminal summary lines from `tests/headless/itertesting.sh`

Expected behavior:

- The bundle makes clear whether the run was `natural_ready`, `seeded_ready`, or `resource_starved`.
- Callback-derived diagnostics are visibly `live`, preserved from earlier capture, or genuinely unavailable.
- Runtime prerequisite resolution is recorded with explicit `resolved`, `missing`, or `relay_unavailable` status.

## 6. Closeout gate

Treat 016 as ready for `/speckit.tasks` only when all of the following hold:

1. The targeted pytest suite and headless hardening/campaign checks pass.
2. `tests/headless/behavioral-build.sh` no longer relies on the old manual def-id injection path for its normal run path.
3. Three consecutive prepared live closeout reruns either complete without the old bootstrap-readiness ambiguity or report an explicit readiness blocker before the first commander-build timeout becomes the primary signal.
4. Long bootstrap failures still retain callback-derived diagnostic evidence in the final run bundle.

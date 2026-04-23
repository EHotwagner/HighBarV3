# Quickstart — Live Bootstrap Hardening

**Branch**: `016-live-bootstrap-hardening`  
**Plan**: [plan.md](./plan.md)

This quickstart defines the minimum validation loop for proving that prepared live closeout handles resource-starved starts explicitly, reports callback capability limits correctly, keeps runtime prerequisite resolution on the supported `47`/`40` path, and uses the session-start map payload when callback-based map inspection is unavailable.

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
- Capability-limited diagnostics render through the existing bundle/report surface without collapsing into generic relay failures.
- Runtime prerequisite-resolution traces still render through the existing bundle/report surface.
- Session-start map sourcing is preserved in report logic when callback map inspection is unavailable.

## 2. Run the synthetic hardening and campaign validation suites

```bash
tests/headless/test_live_itertesting_hardening.sh
tests/headless/test_itertesting_campaign.sh
```

Expected behavior:

- The generated bundle still contains coherent fixture, channel-health, and failure-cause sections.
- Added readiness, capability-profile, and source-selection state agrees across `manifest.json` and `run-report.md`.
- Campaign/report generation remains stable after the new capability-aware reporting detail is added.

## 3. Validate the standalone build probe

```bash
tests/headless/behavioral-build.sh
```

Expected behavior:

- The probe resolves `armmex` from the live runtime through the supported bulk unit-def plus name-resolution callback path instead of requiring `HIGHBAR_ARMMEX_DEF_ID` as the normal path.
- The probe uses the session-start map payload for metal-spot targeting when callback-based map inspection is unavailable.
- If deeper commander or build-option diagnostics are unsupported, the probe reports an explicit capability limitation rather than a stale env-var setup message.
- The probe emits `behavioral-build-outcome.json` under the active runtime directory so maintainers can inspect the resolved prerequisite identity, map source, capability-limit summary, and dispatch result directly.

## 4. Run prepared live closeout reruns

```bash
for i in 1 2 3; do
  HIGHBAR_ITERTESTING_MAX_IMPROVEMENT_RUNS=0 tests/headless/itertesting.sh
done
```

Expected behavior:

- Each run either starts from a naturally viable prepared state or reports an explicit bootstrap-readiness outcome before the first commander-build timeout dominates the failure detail.
- The final bundle shows that prerequisite resolution stayed on the supported callback surface even if deeper diagnostics were capability-limited.
- Map-derived targeting and diagnostics use session-start `static_map` data when callback-based map inspection is unsupported.
- If session-start map payload data is missing, the bundle reports that condition explicitly rather than conflating it with unsupported callback inspection.
- Otherwise healthy runs do not regress channel-health or the existing fixture-provisioning budget because of the hardening changes.
- On a broader-capability host, richer callback diagnostics remain available and no new capability-reporting or map-data regression is introduced.

## 5. Inspect the latest bundle

Review the newest:

- `reports/itertesting/<run-id>/manifest.json`
- `reports/itertesting/<run-id>/run-report.md`
- `reports/itertesting/<run-id>/campaign-stop-decision.json`
- `behavioral-build-outcome.json` from the active runtime directory when step 3 was run
- terminal summary lines from `tests/headless/itertesting.sh`

Expected behavior:

- The bundle makes clear whether the run was `natural_ready`, `seeded_ready`, or `resource_starved`.
- The bundle distinguishes supported runtime inspection, unsupported callback groups, and late transport loss.
- Runtime prerequisite resolution is recorded with explicit `resolved`, `missing`, or `relay_unavailable` status.
- Map sourcing is visibly attributed to session-start `static_map`, callback inspection, or missing data.
- The standalone probe outcome records the same map-source and capability-limit interpretation as the main live bundle.

## 6. Closeout gate

Treat 016 as ready for `/speckit.tasks` only when all of the following hold:

1. The targeted pytest suite and headless hardening/campaign checks pass.
2. `tests/headless/behavioral-build.sh` no longer relies on the old manual def-id injection path for its normal run path.
3. Three consecutive prepared live closeout reruns either complete without the old bootstrap-readiness ambiguity or report an explicit readiness blocker before the first commander-build timeout becomes the primary signal.
4. The final bundle distinguishes unsupported runtime inspection from relay loss and command-behavior failure.
5. Session-start map data remains usable for metal-spot targeting whenever callback-based map inspection is unsupported.

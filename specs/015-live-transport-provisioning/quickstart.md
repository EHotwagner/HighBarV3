# Quickstart — Live Transport Provisioning

**Branch**: `015-live-transport-provisioning`  
**Plan**: [plan.md](./plan.md)

This quickstart defines the minimum validation loop for proving that `transport_unit` is provisioned through the real client-mode workflow, that transport-dependent commands stop failing on a missing foundational fixture when coverage is achievable, and that the existing run bundle remains trustworthy.

## Preconditions

1. Use the normal Linux reference environment for BAR headless workflows, the client-mode coordinator runtime, and the Python behavioral-coverage tooling.
2. Ensure `uv` is available and the same live prerequisites used by `tests/headless/itertesting.sh` are satisfied.
3. Keep `reports/itertesting/` writable so each rerun emits a manifest, report, and stop-decision artifact.
4. Run from the repository root on branch `015-live-transport-provisioning`.

## 1. Validate transport model and report semantics

```bash
uv run --project clients/python pytest \
  clients/python/tests/behavioral_coverage/test_live_failure_classification.py \
  clients/python/tests/behavioral_coverage/test_itertesting_runner.py \
  clients/python/tests/behavioral_coverage/test_itertesting_report.py \
  clients/python/tests/test_behavioral_registry.py
```

Expected behavior:

- `transport_unit` remains in the authoritative fixture dependency model.
- Transport lifecycle and compatibility details render through the existing bundle/report surface.
- Only transport-dependent commands are fixture-blocked when transport coverage is unavailable.

## 2. Run synthetic hardening and campaign validation

```bash
tests/headless/test_live_itertesting_hardening.sh
tests/headless/test_itertesting_campaign.sh
```

Expected behavior:

- The generated bundle still contains fixture, channel-health, and failure-cause sections.
- `transport_unit` status agrees across `fixture_provisioning`, transport lifecycle detail, and failure classifications.
- Campaign/report generation remains stable after transport-specific changes.

## 3. Optional audit of supported transport variants

```bash
tests/headless/audit/def-id-resolver.py cmd-load-units --all
```

Expected behavior:

- The audit helper shows the curated transport prerequisites used for live review.
- The implementation still resolves the actual `def_id` values at runtime rather than depending on the helper for execution.

## 4. Run three prepared live closeout reruns

```bash
for i in 1 2 3; do
  HIGHBAR_ITERTESTING_MAX_IMPROVEMENT_RUNS=0 tests/headless/itertesting.sh
done
```

Expected behavior:

- Each run keeps healthy channel status while transport provisioning is enabled.
- When the environment can supply a supported transport, the five transport-dependent commands are no longer blocked solely by missing `transport_unit`.
- When transport coverage still cannot be achieved, only those five commands remain explicitly blocked by transport-specific fixture reasoning.

## 5. Inspect the latest bundle

Review the newest:

- `reports/itertesting/<run-id>/manifest.json`
- `reports/itertesting/<run-id>/run-report.md`
- `reports/itertesting/<run-id>/campaign-stop-decision.json`
- terminal summary lines from `tests/headless/itertesting.sh` such as
  `itertesting: transport_status=...` and
  `itertesting: transport_affected_commands=...`

Expected behavior:

- The bundle shows whether transport coverage was preexisting, newly provisioned, refreshed, replaced, fallback-provisioned, or still missing.
- `manifest.json` includes a `transport_provisioning` object with supported variants, candidate chain, lifecycle events, compatibility checks, and resolution trace.
- The bundle identifies the exact commands affected by missing or unusable transport coverage.
- Transport-specific reasoning remains separated from payload availability, evidence gaps, and unrelated behavioral failures.

## 6. Compatibility and refresh confirmation

If the environment can force a transport to become unusable or swap the payload pairing mid-run, rerun the same workflow and confirm transport refresh logic:

```bash
HIGHBAR_ITERTESTING_MAX_IMPROVEMENT_RUNS=0 tests/headless/itertesting.sh
```

Expected behavior:

- The workflow rechecks transport-payload compatibility before later load/unload commands.
- A successful replacement or refresh is visible in the bundle as `refreshed` or `replaced`.
- A failed refresh keeps only transport-dependent commands blocked and reports the exact reason.

## 7. Closeout gate

Treat 015 as ready for normal Itertesting tuning only when all of the following hold:

1. The targeted pytest suite and headless hardening/campaign checks pass.
2. Three consecutive prepared live closeout runs complete with healthy channel status.
3. Supported environments report `transport_unit` as preexisting, provisioned, refreshed, or replaced rather than missing.
4. The five transport-dependent commands from 2026-04-22 are no longer blocked solely by missing `transport_unit` where transport coverage is achievable.
5. Any exceptional fallback used to obtain transport coverage is explicitly visible in the run bundle.

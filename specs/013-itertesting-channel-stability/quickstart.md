# Quickstart — Itertesting Channel Stability

**Branch**: `013-itertesting-channel-stability`  
**Plan**: [plan.md](./plan.md)

This quickstart defines the minimum validation loop for proving that the live Itertesting closeout path stays trustworthy long enough to judge command behavior.

## Preconditions

1. Use the normal Linux reference environment for BAR headless workflows, the coordinator runtime, and the Python behavioral-coverage tooling.
2. Ensure `uv` is available and the existing live wrapper prerequisites used by `tests/headless/itertesting.sh` are satisfied.
3. Prepare the live validation environment expected by the current headless wrapper.
4. Keep `reports/itertesting/` writable so each rerun emits a manifest, report, and stop-decision artifact.

## 1. Confirm classification and report semantics

```bash
uv run --project clients/python pytest \
  clients/python/tests/behavioral_coverage/test_live_failure_classification.py \
  clients/python/tests/behavioral_coverage/test_itertesting_runner.py \
  clients/python/tests/behavioral_coverage/test_itertesting_report.py
```

Expected behavior:

- Channel interruption remains distinct from missing fixtures and clean behavioral failure.
- The run bundle still renders fixture, channel-health, and failure-cause sections.
- Commands such as `cmd-build-unit` stay transport-adjacent or fixture-blocked until the evidence proves otherwise.

## 2. Run the synthetic hardening check

```bash
tests/headless/test_live_itertesting_hardening.sh
```

Expected behavior:

- The generated bundle contains `fixture_profile`, `fixture_provisioning`, `channel_health`, and `failure_classifications`.
- The report renders `## Fixture Provisioning`, `## Channel Health`, and `## Failure Cause Summary`.
- The tuned verification rules for `cmd-move-unit`, `cmd-fight`, and `cmd-build-unit` remain intact.

## 3. Run transport latency gates when transport-facing C++ code changes

```bash
tests/bench/latency-uds.sh
tests/bench/latency-tcp.sh
```

Expected behavior:

- The touched transport path stays within Constitution V latency budgets.
- A latency-bench failure blocks closure for transport-facing gateway or queue/drain changes.

## 4. Run three prepared live closeout reruns

```bash
for i in 1 2 3; do
  HIGHBAR_ITERTESTING_MAX_IMPROVEMENT_RUNS=0 tests/headless/itertesting.sh
done
```

Expected behavior:

- Each run completes without a dispatch-time command-channel disconnect collapsing the session.
- The wrapper does not leave the maintainer with only a partial run and no new artifact bundle.
- If the session still degrades, the resulting artifact makes the lifecycle failure explicit instead of reporting a generic command failure.

## 5. Inspect the latest bundle

Review the newest:

- `reports/itertesting/<run-id>/manifest.json`
- `reports/itertesting/<run-id>/run-report.md`
- `reports/itertesting/<run-id>/campaign-stop-decision.json`

Expected behavior:

- `channel_health` identifies the first failure point, if any.
- `fixture_provisioning` lists the missing classes and affected commands.
- `failure_classifications` separate `transport_interruption`, `missing_fixture`, `predicate_or_evidence_gap`, and `behavioral_failure`.
- Commands affected by session collapse are not summarized as clean behavioral regressions.

## 6. Optional alternate-speed confirmation

Create or use `tests/headless/scripts/minimal-slow.startscript` with different
`MinSpeed` and `MaxSpeed` values than
`tests/headless/scripts/minimal.startscript`, then rerun the same workflow:

```bash
HIGHBAR_STARTSCRIPT=tests/headless/scripts/minimal-slow.startscript \
HIGHBAR_ITERTESTING_MAX_IMPROVEMENT_RUNS=0 \
tests/headless/itertesting.sh
```

Expected behavior:

- The blocker interpretation stays the same when the underlying command-channel interruption is unchanged.
- A speed change does not convert a transport-adjacent or fixture-blocked run into a clean semantic regression.

## 7. Closeout gate

Treat 013 as ready for normal Itertesting tuning only when all of the following hold:

1. The regression checks and synthetic hardening check pass.
2. Transport latency gates pass when transport-facing C++ code changed.
3. Three consecutive prepared live reruns complete without dispatch-time channel collapse.
4. Commands that still cannot be judged are explicitly classified as fixture-blocked or transport-adjacent.
5. Interrupted or fixture-blocked runs are not reported as ready for normal Itertesting tuning.
6. The artifact bundle is sufficient to tell whether the next fix belongs in channel lifecycle handling, fixture bootstrap, or command behavior.

# Live Rerun Status Report

Date: 2026-04-23
Feature: `017-live-orchestration-refactor`
Command executed:

```bash
for i in 1 2 3; do
  HIGHBAR_ITERTESTING_MAX_IMPROVEMENT_RUNS=0 tests/headless/itertesting.sh
done
```

## Executive Summary

The prepared live rerun loop completed, but no run reached trustworthy live closeout. All three requested reruns stopped with `foundational_blocked`. One of the three reruns triggered an internal wrapper retry, so the artifact set contains four run bundles total.

The important result for 017 is that the refactored orchestration classified the failures coherently:

- The two resource-starved runs preserved live bootstrap metadata, callback diagnostics, prerequisite resolution, and map-source evidence, then stopped on authoritative missing-fixture coverage.
- The channel/relay failure path stopped on transport interruption or missing-fixture authority without contradictory fixture or transport claims.
- Every live failure bundle remained `fully_interpreted=true` with `interpretation_warnings=[]`, so the current blocker is the live environment/bootstrap path, not missing interpretation support in the new seams.

## Overall Outcome

Status: `validation executed, live closeout still blocked`

Observed failure modes:

1. Bootstrap resource starvation before `armap` could be established.
2. Plugin command channel disconnection during bootstrap.
3. Retry-path prerequisite resolution failure with relay unavailable and a stale socket path reference.

Net result:

- `0/20` direct verified commands in every live campaign.
- No run reached command evaluation beyond bootstrap in a way that could validate the prepared live closeout path.
- The new execution/metadata/interpretation seams did surface distinct layer ownership for the different failure modes.

## Run Matrix

| Requested rerun | Final run id | Campaign | Runtime | Stop reason | Primary blocker |
|---|---|---|---:|---|---|
| 1 | `itertesting-20260423T104356Z` | `itertesting-campaign-20260423T104352Z` | 4s | `foundational_blocked` | `bootstrap_readiness=resource_starved` at `armap` |
| 2 attempt 1 | `itertesting-20260423T104430Z` | `itertesting-campaign-20260423T104416Z` | 14s | `foundational_blocked` | plugin command channel disconnected |
| 2 retry | `itertesting-20260423T104453Z` | `itertesting-campaign-20260423T104450Z` | 3s | `foundational_blocked` | prerequisite resolution relay unavailable |
| 3 | `itertesting-20260423T104517Z` | `itertesting-campaign-20260423T104512Z` | 5s | `foundational_blocked` | `bootstrap_readiness=resource_starved` at `armap` |

## Per-Run Detail

### Run 1: Resource-starved bootstrap

Artifacts:

- [manifest.json](../reports/itertesting/itertesting-20260423T104356Z/manifest.json)
- [run-report.md](../reports/itertesting/itertesting-20260423T104356Z/run-report.md)
- [campaign-stop-decision.json](../reports/itertesting/itertesting-campaign-20260423T104352Z/campaign-stop-decision.json)

Key facts:

- `bootstrap_readiness.readiness_status = resource_starved`
- `bootstrap_readiness.first_required_step = armap`
- Economy at failure: `metal:0.0/0.0/2250.0`, `energy:6017.6/0.0/8318.0`
- Runtime capability profile was populated from live execution:
  - callbacks `23, 40, 42, 47`
  - map source `hello_static_map`
- `armmex` prerequisite resolution succeeded with `resolved_def_id = 149`
- Callback diagnostics were live and captured at `bootstrap_start`
- Fixture authority correctly collapsed to baseline-only:
  - provisioned: `commander`, `movement_lane`, `resource_baseline`
  - missing: every fixture that depends on successful bootstrap provisioning, including `builder`, `cloakable`, `hostile_target`, `payload_unit`, `transport_unit`
- `transport_provisioning.status = missing`
- `transport_decision.availability_status = unproven`
- `blocking_issue_ids = ["live-closeout:missing-fixture"]`

Assessment:

- This is the cleanest failure mode in the set.
- The refactor preserved all expected bootstrap-layer metadata and produced a consistent missing-fixture closeout.

### Run 2 attempt 1: Channel disconnect during bootstrap

Artifacts:

- [manifest.json](../reports/itertesting/itertesting-20260423T104430Z/manifest.json)
- [run-report.md](../reports/itertesting/itertesting-20260423T104430Z/run-report.md)
- [campaign-stop-decision.json](../reports/itertesting/itertesting-campaign-20260423T104416Z/campaign-stop-decision.json)

Key facts:

- Wrapper output recorded:
  - optional bootstrap skip around `solar/armsolar`
  - gRPC `UNAVAILABLE`
  - `"plugin command channel is not connected"`
- `bootstrap_readiness = unknown`
- No live prerequisite-resolution metadata survived into the bundle
- No live callback diagnostics survived; report fell back to `bootstrap_failure / missing / not_available`
- `runtime_capability_profile` fell back to implicit empty capability state
- `map_source_decisions` fell back to `missing`
- `transport_provisioning.status = missing`
- `transport_decision.availability_status = unproven`
- `blocking_issue_ids = ["live-closeout:transport-interruption"]`
- Summary totals classified all 47 direct commands under `transport_interruption_total`

Assessment:

- This run demonstrates the transport/channel failure path clearly.
- The bundle did not claim resource starvation or fixture absence as the primary cause.
- The wrapper correctly retried after detecting degraded live session state.

### Run 2 retry: Relay unavailable during prerequisite resolution

Artifacts:

- [manifest.json](../reports/itertesting/itertesting-20260423T104453Z/manifest.json)
- [run-report.md](../reports/itertesting/itertesting-20260423T104453Z/run-report.md)
- [campaign-stop-decision.json](../reports/itertesting/itertesting-campaign-20260423T104450Z/campaign-stop-decision.json)

Key facts:

- Wrapper output recorded bootstrap def resolution failure with relay unavailable.
- `prerequisite_resolution` contains `armmex: relay_unavailable`
- `runtime_capability_profile` preserved partial evidence:
  - callbacks `40, 47`
  - map source `missing`
- `bootstrap_readiness = unknown`
- `callback_diagnostics` again fell back to missing bootstrap-failure state
- `transport_provisioning.status = missing`
- `transport_decision.availability_status = unproven`
- `blocking_issue_ids = ["live-closeout:missing-fixture"]`
- Summary totals were mixed:
  - `missing_fixture_total = 22`
  - `predicate_or_evidence_gap_total = 2`
  - `behavioral_failure_total = 23`

Important inference:

- The retry ran on `attempt-2`, but the reported socket failure referenced `attempt-1/highbar-1.sock`.
- That strongly suggests some retry-path state still referenced the previous attempt’s relay/socket location instead of the freshly launched session.

Assessment:

- This is the most suspicious infrastructure result in the set.
- The refactor kept the failure visible through typed prerequisite metadata instead of flattening it into a generic bootstrap failure.
- The likely next debugging target is retry-session cleanup or path rebinding, not the interpretation seam.

### Run 3: Resource-starved bootstrap again

Artifacts:

- [manifest.json](../reports/itertesting/itertesting-20260423T104517Z/manifest.json)
- [run-report.md](../reports/itertesting/itertesting-20260423T104517Z/run-report.md)
- [campaign-stop-decision.json](../reports/itertesting/itertesting-campaign-20260423T104512Z/campaign-stop-decision.json)

Key facts:

- Same dominant signature as Run 1:
  - `bootstrap_readiness = resource_starved`
  - first required step `armap`
  - live callback diagnostics present
  - prerequisite resolution for `armmex` succeeded
  - map source `hello_static_map`
- Energy differed slightly from Run 1, but the failure class was identical.
- `blocking_issue_ids = ["live-closeout:missing-fixture"]`
- `transport_decision.availability_status = unproven`

Assessment:

- This repeat strongly suggests the main prepared-live blocker is stable and environmental, not a one-off orchestration regression.

## Cross-Run Findings

### What 017 validated successfully

1. Distinct responsibility layers are visible in the artifacts.
   - Resource-starved runs include explicit `bootstrap_readiness`, capability, prerequisite, map-source, and callback metadata from `live_execution`.
   - The relay/channel failures show thinner metadata and correspondingly shorter decision traces.

2. Fixture and transport authority stayed internally consistent.
   - Resource-starved runs did not claim builder/hostile/transport availability.
   - Channel/relay runs did not silently upgrade transport to available.
   - Transport remained `unproven` rather than being inferred from setup mode or baseline assumptions.

3. The refactor did not introduce interpretation gaps.
   - All four live bundles reported:
     - `fully_interpreted = true`
     - `interpretation_warnings = []`

4. Decision trace data is useful in practice.
   - Resource-starved runs show a full chain from metadata records into fixture transitions.
   - The retry relay failure shows only the smaller evidence set that actually survived collection.

### What remains blocked

1. Prepared live bootstrap is not reliable enough to reach closeout.
   - Two runs starved on `armap`.
   - One run lost the plugin command channel.
   - One retry failed prerequisite resolution with relay unavailable.

2. No run exercised downstream transport establishment.
   - Every run ended with `transport_provisioning.status = missing`
   - Every live run ended with `transport_decision.availability_status = unproven`

3. No run verified even one direct command.
   - The live rerun loop is still blocked before command-level confidence can be assessed.

## Interpretation of the Current State

The 017 refactor appears to be doing the right thing under failure:

- It is not hiding missing evidence.
- It is not producing contradictory fixture or transport claims.
- It is preserving enough layer-specific metadata to separate bootstrap starvation from channel loss from relay/prerequisite failure.

The evidence now points away from the new interpretation seam as the primary blocker and toward the live environment/bootstrap path itself.

## Recommended Next Steps

1. Investigate why `armap` is the first commander-built step that repeatedly starves despite large stored metal/energy values.
   - Focus on whether the issue is build placement, effective income availability, commander state, or an engine-side prerequisite not represented in the current economy summary.

2. Investigate retry cleanup around relay/socket rebinding.
   - The retry path referencing `attempt-1/highbar-1.sock` during `attempt-2` is the strongest sign of stale session state.

3. Capture coordinator and engine logs for the failing live attempts alongside these bundles.
   - The bundles now narrow the failure class enough that the next missing evidence is outside the manifest layer.

4. Re-run the prepared live loop only after the retry-path socket issue and the `armap` bootstrap starvation have been examined.
   - Right now a rerun is likely to reproduce the same blocked states rather than provide new closeout evidence.

## Final Status

Prepared live rerun validation was executed and documented.

Result: `completed but not passed`

Reason:

- The loop itself ran.
- The refactored reporting behaved correctly.
- The prepared live environment did not produce a single trustworthy closeout run.

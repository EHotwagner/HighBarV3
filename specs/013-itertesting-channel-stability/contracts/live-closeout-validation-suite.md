# Contract: Live Closeout Validation Suite

**Feature**: [Itertesting Channel Stability](../plan.md)

## Purpose

Define the validation steps maintainers use to declare the live Itertesting closeout path stable enough for normal tuning work.

## Required Steps

| Step | Entrypoint | Required outcome |
|------|------------|------------------|
| Python classification regressions | `uv run --project clients/python pytest clients/python/tests/behavioral_coverage/test_live_failure_classification.py clients/python/tests/behavioral_coverage/test_itertesting_runner.py clients/python/tests/behavioral_coverage/test_itertesting_report.py` | Fixture, channel-health, transport-adjacent, and report semantics stay consistent. |
| Synthetic live-hardening validation | `tests/headless/test_live_itertesting_hardening.sh` | The generated run bundle contains fixture, channel-health, and failure-cause sections with the expected tuned-rule coverage. |
| Prepared live closeout reruns | `for i in 1 2 3; do HIGHBAR_ITERTESTING_MAX_IMPROVEMENT_RUNS=0 tests/headless/itertesting.sh; done` | Three consecutive prepared-environment runs complete without a dispatch-time command-channel disconnect blocking evaluation. |
| Artifact inspection | Review the latest `reports/itertesting/<run-id>/{manifest.json,run-report.md,campaign-stop-decision.json}` | The bundle clearly shows whether the run was stable, fixture-blocked, transport-adjacent, or behavior-failing. |
| Optional alternate-speed confirmation | Rerun the same prepared workflow with only the local simulation-speed setting changed, if that control is available in the environment | The blocker interpretation remains transport- or fixture-focused when the underlying lifecycle problem is unchanged. |

## Required Behaviors

1. A live rerun that exits through a command-channel interruption is not acceptable closure evidence, even if some batches were forwarded successfully.
2. A run with unresolved fixture blockers may still be diagnostically useful, but it is not ready for normal tuning of the affected commands.
3. The report, manifest, and shell wrapper output must agree on whether the run is transport-degraded, fixture-blocked, or ready for ordinary improvement guidance.
4. Reviewers must be able to identify the first lifecycle failure point and the list of affected commands from the artifact bundle alone.
5. Repeated reruns must preserve the same blocker interpretation when the same underlying transport problem recurs.

## Output Expectations

- The latest run report includes `## Fixture Provisioning`, `## Channel Health`, and `## Failure Cause Summary`.
- The manifest records the machine-readable `channel_health`, `fixture_provisioning`, and `failure_classifications` blocks.
- Commands that are transport-adjacent or fixture-blocked are not summarized as clean semantic regressions.

# Contract: Live Bootstrap Validation Suite

**Feature**: [Fixture Bootstrap Simplification](../plan.md)

## Purpose

Define the validation steps maintainers use to confirm that richer fixture provisioning improves live coverage without regressing channel health or report trustworthiness.

## Required Steps

| Step | Entrypoint | Required outcome |
|------|------------|------------------|
| Fixture/classification regressions | `uv run --project clients/python pytest clients/python/tests/behavioral_coverage/test_live_failure_classification.py clients/python/tests/behavioral_coverage/test_itertesting_runner.py clients/python/tests/behavioral_coverage/test_itertesting_report.py` | The authoritative fixture model, provisioning result, and report output stay aligned. |
| Synthetic live-hardening validation | `tests/headless/test_live_itertesting_hardening.sh` | The run bundle still contains fixture, channel-health, and failure-cause sections, and fixture blockers come from the authoritative provisioning result. |
| Campaign artifact validation | `tests/headless/test_itertesting_campaign.sh` | Chained runs still emit manifest, report, and stop-decision artifacts correctly. |
| Prepared live closeout reruns | `for i in 1 2 3; do HIGHBAR_ITERTESTING_MAX_IMPROVEMENT_RUNS=0 tests/headless/itertesting.sh; done` | Three consecutive prepared runs complete with healthy channel status while richer fixture provisioning is enabled. |
| Artifact inspection | Review the latest `reports/itertesting/<run-id>/{manifest.json,run-report.md,campaign-stop-decision.json}` | The bundle shows fixture class status, missing classes, affected commands, and closeout readiness from one model. |

## Required Behaviors

1. A run that reintroduces channel instability is not acceptable closure evidence even if more fixtures were provisioned.
2. The number of direct commands blocked solely by missing fixtures must decrease materially from the current baseline of 11.
3. Commands still blocked by setup must be blocked by named fixture class, not by a duplicate simplified-bootstrap explanation.
4. Reviewers must be able to identify whether a class was provisioned, refreshed, missing, or unusable from the artifact bundle alone.
5. Transport-facing latency benches remain required if implementation touches transport C++ paths while delivering 014.

## Output Expectations

- `run-report.md` includes fixture provisioning detail that matches `manifest.json`.
- The latest stop decision remains `blocked_foundational` until missing or unusable classes stop blocking intended coverage commands.
- Healthy live reruns remain the final closeout gate for the feature.

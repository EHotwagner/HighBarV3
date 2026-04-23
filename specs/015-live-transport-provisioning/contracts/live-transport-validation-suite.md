# Contract: Live Transport Validation Suite

**Feature**: [Live Transport Provisioning](../plan.md)

## Purpose

Define the validation steps maintainers use to confirm that transport provisioning closes the last real foundational fixture blocker without regressing run stability or bundle trustworthiness.

## Required Steps

| Step | Entrypoint | Required outcome |
|------|------------|------------------|
| Behavioral model/report regressions | `uv run --project clients/python pytest clients/python/tests/behavioral_coverage/test_live_failure_classification.py clients/python/tests/behavioral_coverage/test_itertesting_runner.py clients/python/tests/behavioral_coverage/test_itertesting_report.py clients/python/tests/test_behavioral_registry.py` | Transport lifecycle, fixture status, registry inputs, and reporting remain aligned. |
| Synthetic live-hardening validation | `tests/headless/test_live_itertesting_hardening.sh` | The run bundle still contains coherent fixture, channel-health, and failure-cause sections after transport provisioning changes. |
| Campaign artifact validation | `tests/headless/test_itertesting_campaign.sh` | Chained runs still emit manifest, report, and stop-decision artifacts correctly. |
| Prepared live closeout reruns | `for i in 1 2 3; do HIGHBAR_ITERTESTING_MAX_IMPROVEMENT_RUNS=0 tests/headless/itertesting.sh; done` | Three consecutive prepared runs complete with healthy channel status while transport provisioning is enabled. |
| Artifact inspection | Review the latest `reports/itertesting/<run-id>/{manifest.json,run-report.md,campaign-stop-decision.json}` | The bundle shows transport lifecycle, affected commands, and closeout readiness from one model. |

## Required Behaviors

1. A run that reintroduces channel instability is not acceptable closure evidence even if transport coverage improves.
2. The five transport-dependent commands blocked in `itertesting-20260422T195308Z` must stop being blocked solely by missing `transport_unit` when the environment can supply supported transport coverage.
3. When coverage is not achievable, 100% of transport-blocked commands must carry explicit transport detail and no unrelated commands may join that blocker set.
4. Prepared live closeout runtime must remain within 10% of the 8-second baseline from the 2026-04-22 authoritative run unless a justified variance is recorded during implementation.
5. If implementation touches transport-facing plugin code after planning, latency-budget validation remains mandatory under Constitution V.

## Output Expectations

- `run-report.md` shows transport lifecycle detail consistent with `manifest.json`.
- `campaign-stop-decision.json` remains `blocked_foundational` until missing or unusable transport coverage stops blocking intended commands.
- Healthy live reruns remain the final closeout gate for the feature.

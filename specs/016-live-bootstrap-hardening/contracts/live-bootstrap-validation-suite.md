# Contract: Live Bootstrap Validation Suite

**Feature**: [Live Bootstrap Hardening](../plan.md)

## Purpose

Define the validation loop maintainers use to confirm that prepared live closeout now classifies resource-starved starts correctly, preserves callback diagnostics through long failures, and keeps the standalone build probe aligned with runtime prerequisite resolution.

## Required Steps

| Step | Entrypoint | Required outcome |
|------|------------|------------------|
| Behavioral model/report regressions | `uv run --project clients/python pytest clients/python/tests/behavioral_coverage/test_live_failure_classification.py clients/python/tests/behavioral_coverage/test_itertesting_runner.py clients/python/tests/behavioral_coverage/test_itertesting_report.py clients/python/tests/test_behavioral_registry.py` | Bootstrap-readiness, diagnostic-retention, and prerequisite-resolution model/report behavior remain aligned. |
| Synthetic live-hardening validation | `tests/headless/test_live_itertesting_hardening.sh` | Fixture, channel-health, and failure-cause reporting remain coherent after bootstrap-hardening changes. |
| Campaign artifact validation | `tests/headless/test_itertesting_campaign.sh` | Manifest/report/stop-decision artifacts remain stable after adding readiness and diagnostic-retention detail. |
| Standalone build probe validation | `tests/headless/behavioral-build.sh` | The probe resolves its build prerequisite at runtime without requiring `HIGHBAR_ARMMEX_DEF_ID` as the normal path. |
| Prepared live reruns | `for i in 1 2 3; do HIGHBAR_ITERTESTING_MAX_IMPROVEMENT_RUNS=0 tests/headless/itertesting.sh; done` | Three consecutive prepared runs either complete without the old bootstrap-readiness ambiguity or report an explicit readiness blocker before the first commander-build timeout becomes the primary signal. |
| Artifact inspection | Review the latest `reports/itertesting/<run-id>/{manifest.json,run-report.md,campaign-stop-decision.json}` | The bundle shows bootstrap readiness, callback-diagnostic retention, and prerequisite-resolution status in one place. |

## Required Behaviors

1. A run that still starts from a resource-starved state without explicit readiness classification is not acceptable closure evidence.
2. A run that loses callback reachability late must still retain earlier callback-derived diagnostics if they were captured successfully.
3. The standalone build probe must stop using the old env-var def-id injection path as its normal prerequisite mechanism.
4. Otherwise healthy prepared live runs must not regress channel-health or the existing 90-second fixture-provisioning budget because of this feature.
5. If implementation later touches plugin-facing code beyond the current coordinator/Python/workflow seam, Constitution V latency validation remains mandatory.

## Output Expectations

- `run-report.md` shows bootstrap-readiness and callback-diagnostic state consistent with `manifest.json`.
- The standalone build probe produces runtime-resolution-driven evidence instead of an env-var skip message.
- Prepared live reruns remain the final closeout gate for the feature.

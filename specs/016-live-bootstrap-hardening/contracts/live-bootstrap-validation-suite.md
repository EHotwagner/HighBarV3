# Contract: Live Bootstrap Validation Suite

**Feature**: [Live Bootstrap Hardening](../plan.md)

## Purpose

Define the validation loop maintainers use to confirm that prepared live closeout now classifies resource-starved starts correctly, records callback capability limits coherently, and keeps the standalone build probe aligned with supported runtime sources.

## Required Steps

| Step | Entrypoint | Required outcome |
|------|------------|------------------|
| Behavioral model/report regressions | `uv run --project clients/python pytest clients/python/tests/behavioral_coverage/test_live_failure_classification.py clients/python/tests/behavioral_coverage/test_itertesting_runner.py clients/python/tests/behavioral_coverage/test_itertesting_report.py clients/python/tests/test_behavioral_registry.py` | Bootstrap-readiness, capability-aware reporting, and prerequisite/map-source model behavior remain aligned. |
| Synthetic live-hardening validation | `tests/headless/test_live_itertesting_hardening.sh` | Fixture, channel-health, capability-profile, and failure-cause reporting remain coherent after bootstrap-hardening changes. |
| Campaign artifact validation | `tests/headless/test_itertesting_campaign.sh` | Manifest/report/stop-decision artifacts remain stable after adding readiness, capability, and map-source detail. |
| Standalone build probe validation | `tests/headless/behavioral-build.sh` | The probe resolves its build prerequisite at runtime without requiring `HIGHBAR_ARMMEX_DEF_ID` as the normal path and uses session-start map data when callback map inspection is unavailable. |
| Prepared live reruns | `for i in 1 2 3; do HIGHBAR_ITERTESTING_MAX_IMPROVEMENT_RUNS=0 tests/headless/itertesting.sh; done` | Three consecutive prepared runs either complete without the old bootstrap-readiness ambiguity or report an explicit readiness blocker before the first commander-build timeout becomes the primary signal. |
| Artifact inspection | Review the latest `reports/itertesting/<run-id>/{manifest.json,run-report.md,campaign-stop-decision.json}` and the active `behavioral-build-outcome.json` when the standalone probe ran | The bundle shows bootstrap readiness, callback capability status, prerequisite-resolution status, and map-source selection in one place. |

## Required Behaviors

1. A run that still starts from a resource-starved state without explicit readiness classification is not acceptable closure evidence.
2. A run on a callback-limited host must distinguish unsupported inspection capability from relay loss and from command-behavior failure.
3. The standalone build probe must stop using the old env-var def-id injection path as its normal prerequisite mechanism.
4. Session-start map data must remain a valid map source when callback-based map inspection is unsupported.
5. Otherwise healthy prepared live runs must not regress channel-health or the existing 90-second fixture-provisioning budget because of this feature.
6. If implementation later touches plugin-facing code beyond the current coordinator/Python/workflow seam, Constitution V latency validation remains mandatory.

## Output Expectations

- `run-report.md` shows bootstrap-readiness, capability-aware diagnostics, and map-source state consistent with `manifest.json`.
- The standalone build probe produces runtime-resolution-driven evidence instead of an env-var skip message.
- Prepared live reruns remain the final closeout gate for the feature.

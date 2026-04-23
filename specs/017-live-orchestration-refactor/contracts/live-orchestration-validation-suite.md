# Contract: Live Orchestration Validation Suite

## Purpose

Define the validation loop maintainers use to confirm that the live orchestration refactor preserves workflow behavior while improving responsibility isolation and bundle trustworthiness.

## Validation matrix

| Validation target | Command | Evidence |
|-------------------|---------|----------|
| Metadata collection seam | `uv run --project clients/python pytest clients/python/tests/behavioral_coverage/test_live_execution.py clients/python/tests/behavioral_coverage/test_metadata_records.py` | Live execution and typed metadata collection remain isolated and deterministic. |
| Interpretation seam | `uv run --project clients/python pytest clients/python/tests/behavioral_coverage/test_itertesting_runner.py clients/python/tests/behavioral_coverage/test_live_failure_classification.py` | Fixture, transport, blocker, and warning synthesis remain coherent. |
| Bundle/report rendering | `uv run --project clients/python pytest clients/python/tests/behavioral_coverage/test_itertesting_report.py clients/python/tests/test_behavioral_registry.py` | Manifest and report rendering stay aligned with interpreted run state. |
| Synthetic hardening validation | `tests/headless/test_live_itertesting_hardening.sh` | Synthetic and partial-live bundles remain valid and non-contradictory. |
| Campaign artifact validation | `tests/headless/test_itertesting_campaign.sh` | Campaign-level bundle generation and stop-decision semantics remain stable. |
| Prepared live reruns | `for i in 1 2 3; do HIGHBAR_ITERTESTING_MAX_IMPROVEMENT_RUNS=0 tests/headless/itertesting.sh; done` | Three consecutive prepared reruns remain healthy and produce trustworthy bundles. |

## Acceptance rules

1. No regression suite run may claim unproven fixture or transport availability after bootstrap-blocked or evidence-poor live scenarios.
2. A preserved but unhandled metadata record must produce a visible warning and block fully interpreted success in both manifest and report surfaces.
3. The targeted validation commands must allow maintainers to change metadata collection, interpretation, and reporting independently.
4. Prepared live reruns must not regress the existing channel-health and bootstrap budget guardrails because of the refactor.
5. Representative failure bundles must show which responsibility layer produced the decisive result.

## Artifact inspection

Inspect the latest:

- `reports/itertesting/<run-id>/manifest.json`
- `reports/itertesting/<run-id>/run-report.md`
- `reports/itertesting/<run-id>/campaign-stop-decision.json`

Expected behavior:

- Fixture and transport summaries agree with authoritative transitions and run-mode policy.
- Interpretation warnings and decision trace data, when present, are preserved in the manifest and reflected coherently in the report.
- `fully_interpreted` must stay false whenever blocking interpretation warnings remain.
- Existing bootstrap, capability-profile, prerequisite-resolution, and map-source detail remains intact after the refactor.

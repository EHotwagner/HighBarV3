# Gateway Command Audit Harness

This directory contains the checked-in live audit entry points.

- `run-all.sh`: regenerate the checked-in audit markdown from a new manifest-backed refresh.
- `repro.sh`: reproduce one audit row from the latest completed manifest and write a row report.
- `hypothesis.sh`: run the distinguishing command for one hypothesis class and persist the verdict report.
- `repro-stability.sh`: compare the latest completed manifest with the immediately previous one and write a drift report.
- `phase2-macro-chain.sh`: Phase-2 dispatcher-only smoke wrapper that persists attribution evidence.

Row-specific prerequisites:

- `tests/headless/audit/def-id-resolver.py <row-id>` prints the primary unit name associated with that row.
- `tests/headless/audit/def-id-resolver.py <row-id> --all` prints every curated prerequisite unit for transport/save-load rows.
- Partial refreshes can be simulated with `HIGHBAR_AUDIT_FAIL_ROWS`, `HIGHBAR_AUDIT_FAIL_RPCS`, `HIGHBAR_AUDIT_TOPOLOGY_FAILURE`, or `HIGHBAR_AUDIT_SESSION_FAILURE` when validating reviewer-facing failure markers.

Operational notes:

- `run-all.sh` remains unattended and repo-local; it writes manifests and row reports under `build/reports/`.
- The Python refresh command supports partial-failure simulation without editing checked-in scripts:
  `python -m highbar_client.behavioral_coverage audit refresh --fail-rows cmd-move-unit --topology-failure "launcher degraded"`

These scripts are intentionally repo-local and write evidence under `build/reports/`.

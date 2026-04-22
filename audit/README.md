# Gateway Command Audit

This directory holds the checked-in live-refresh audit deliverables derived from the latest completed manifest.

- Latest completed run: `live-audit-20260422T064705Z`
- Total audit rows: 74
- Verified rows: 10
- Hypothesis entries: 43
- Blocked rows: 39
- Broken rows: 1
- Drifted rows: 0
- Not refreshed rows: 0

Primary reviewer commands:

```bash
tests/headless/audit/run-all.sh
tests/headless/audit/repro.sh cmd-build-unit --phase=1
tests/headless/audit/hypothesis.sh cmd-move-unit phase1_reissuance
tests/headless/audit/repro-stability.sh
tests/headless/audit/phase2-macro-chain.sh
```

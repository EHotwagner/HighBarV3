# Gateway Command Audit

This directory holds the checked-in 004 audit deliverables generated from the 003 behavioral-coverage registry, the current gRPC service/dispatcher source, and the 004 hypothesis vocabulary.

- Total audit rows: 74
- Verified rows: 10
- Hypothesis entries: 43
- Blocked rows: 39

Primary reviewer commands:

```bash
tests/headless/audit/run-all.sh
tests/headless/audit/repro.sh cmd-build-unit --phase=1
tests/headless/audit/hypothesis.sh cmd-move-unit phase1_reissuance
tests/headless/audit/phase2-macro-chain.sh
```

Validation run recorded in this branch:

- `build/reports/004-repro-cmd-build-unit.md`
- `build/reports/004-repro-rpc-submit-commands.md`
- `build/reports/004-repro-rpc-save.md`
- `build/reports/004-repro-rpc-load.md`
- `build/reports/004-hypothesis-cmd-move-unit-phase1_reissuance.md`
- `build/reports/004-phase2-smoke.md`
- `build/reports/004-stability-run-1.md`
- `build/reports/004-stability-run-2.md`

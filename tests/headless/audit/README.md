# Gateway Command Audit Harness

This directory contains the checked-in 004 audit entry points.

- `repro.sh`: reproduce one audit row or regenerate the checked-in markdown artifacts.
- `hypothesis.sh`: run the distinguishing command for one hypothesis class.
- `repro-stability.sh`: regenerate the audit twice and compare the markdown outputs.
- `phase2-macro-chain.sh`: Phase-2 dispatcher-only smoke wrapper.
- `run-all.sh`: convenience wrapper that refreshes the checked-in audit markdown and runs the lightweight shell checks.

These scripts are intentionally repo-local and write evidence under `build/reports/`.

# Quickstart — Command Contract Hardening

**Branch**: `010-command-contract-hardening`  
**Plan**: [plan.md](./plan.md)

This quickstart validates the contract-first workflow: coherent batch targeting, deeper validator rejection, foundational issue classification, deterministic repro links, and Itertesting gating that stays closed while contract blockers exist.

## Preconditions

1. Use the same Linux reference environment required by the current gateway, integration, and headless workflows.
2. Have the normal C++ build tree available for `ctest`-driven unit/integration checks.
3. Ensure Python client dependencies and `uv` are available for behavioral-coverage and headless scripts.

## 1. Run focused validator and dispatch regressions

```bash
ctest --test-dir build --output-on-failure -R 'command_validation_test|ai_move_flow_test'
```

Expected behavior:

- Target drift and malformed command shapes fail deterministically.
- Valid commands still reach the existing dispatch path.
- No change is required to the public wire schema to enforce the contract.

## 2. Run end-to-end malformed and contract-blocker checks

```bash
tests/headless/malformed-payload.sh
tests/headless/test_command_contract_hardening.sh
```

Expected behavior:

- The gateway rejects invalid or incoherent command batches synchronously.
- The headless contract-hardening script classifies foundational blockers separately from ordinary Itertesting findings.
- Repro output points maintainers at the specific focused confirmation path for each blocker.

## 3. Run an Itertesting campaign through the contract-health gate

```bash
HIGHBAR_ITERTESTING_MAX_IMPROVEMENT_RUNS=0 \
tests/headless/itertesting.sh
```

Expected behavior:

- If foundational contract blockers are present, the run records a contract-health stop decision and withholds normal improvement guidance.
- If no foundational blockers are present, ordinary coverage/evidence/setup/learning output continues as before.
- The wrapper prints the latest run report path plus any blocking issue ids and deterministic repro commands when contract health is not ready.

## 4. Inspect run artifacts

```bash
latest_run="$(find reports/itertesting -maxdepth 1 -type d -name 'itertesting-*' ! -name 'itertesting-campaign-*' | sort | tail -n 1)"
sed -n '1,260p' "$latest_run/run-report.md"
sed -n '1,260p' "$latest_run/manifest.json"
```

Expected behavior:

- Foundational issues are listed in a dedicated section with issue class and supporting evidence.
- The manifest includes contract-health state and deterministic repro references.
- Downstream Itertesting findings are clearly marked secondary when the gate is closed.

## 5. Follow the deterministic repro path

Run the repo-local repro command linked from the foundational issue entry and confirm its expected signal before returning to broader Itertesting.

Expected behavior:

- The repro can be run independently from the original campaign.
- Fixes are validated against the focused repro first, then against the broader campaign workflow.

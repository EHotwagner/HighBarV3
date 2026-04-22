# Headless Workflow Notes

`tests/headless/itertesting.sh` is the maintainer entrypoint for the Itertesting CLI from the repo root.
The live wrappers prefer a Unix-socket coordinator endpoint and fall back to
loopback TCP when the local gRPC runtime cannot bind `unix:` endpoints.

The command-contract completion suite also depends on the standard
build-root CTest entrypoints:

```bash
ctest --test-dir build -N -R 'command_validation_test|ai_move_flow_test|command_validation_perf_test'
ctest --test-dir build --output-on-failure -R 'command_validation_test|ai_move_flow_test'
ctest --test-dir build --output-on-failure -R 'command_validation_perf_test'
```

Every command in that suite is required for feature completion; a skipped
required step leaves validation incomplete.

Use the default single-run path:

```bash
tests/headless/itertesting.sh
```

Run a bounded campaign with one follow-up retry:

```bash
HIGHBAR_ITERTESTING_MAX_IMPROVEMENT_RUNS=1 tests/headless/itertesting.sh
```

Allow cheat escalation after natural progress stalls:

```bash
HIGHBAR_ITERTESTING_MAX_IMPROVEMENT_RUNS=2 \
HIGHBAR_ITERTESTING_ALLOW_CHEAT_ESCALATION=true \
tests/headless/itertesting.sh
```

Expected bundle per run:

- `reports/itertesting/<run-id>/manifest.json`
- `reports/itertesting/<run-id>/run-report.md`
- `reports/itertesting/instructions/index.json`
- `reports/itertesting/instructions/cmd-*.json`

When command-contract blockers are detected, `tests/headless/itertesting.sh`
prints the contract-health status, the latest run report path, each blocking
issue id/class, and any linked deterministic repro commands before returning
control to the maintainer.

Live-hardening validation now has a dedicated entrypoint:

```bash
tests/headless/test_live_itertesting_hardening.sh
```

The script validates fixture provisioning, channel-health reporting, failure-cause summaries, and tuned repro coverage for `cmd-move-unit`, `cmd-fight`, and `cmd-build-unit`.

Use `tests/headless/test_itertesting_campaign.sh` to validate that chained runs emit both artifacts.

Malformed payload resilience can be checked directly with:

```bash
tests/headless/malformed-payload.sh
```

Expected result: `INVALID_ARGUMENT` for the bad batch, no gateway disable, continued heartbeats.

Command-contract blocker separation can be checked directly with:

```bash
tests/headless/test_command_contract_hardening.sh
```

Expected result: a manifest and report containing `Contract Health` and
`Foundational Blockers` sections, with ordinary improvement guidance withheld.

The validator-overhead target writes its machine-readable artifact to:

- `build/reports/command-validation/validator-overhead.json`

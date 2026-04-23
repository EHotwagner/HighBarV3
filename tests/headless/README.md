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

The script validates bootstrap-readiness reporting, callback-diagnostic retention, runtime prerequisite resolution, fixture provisioning, channel-health reporting, failure-cause summaries, and tuned repro coverage for `cmd-move-unit`, `cmd-fight`, and `cmd-build-unit`.

For 015, maintainers should also review the semantic surfaces emitted by
the run bundle:

- `## Command Semantic Inventory` in `run-report.md` for exact BAR ids such as
  `32102`, `34571`, `34922`-`34925`, and `37382`
- `## Semantic Gates` in `run-report.md` for helper-parity, Lua rewrite,
  unit-shape, and mod-option blockers that are not missing-fixture outcomes
- `### Transport Provisioning` in `run-report.md` for transport lifecycle,
  compatibility checks, and runtime def-resolution trace
- `## Bootstrap Readiness` in `run-report.md` for `natural_ready`,
  `seeded_ready`, or `resource_starved` prepared-live starts
- `## Callback Diagnostics` in `run-report.md` for live vs cached
  callback-derived commander/bootstrap evidence
- `## Runtime Capability Profile` in `run-report.md` for supported callback
  ids, supported scopes, unsupported callback groups, and active map-source
  status
- `## Runtime Prerequisite Resolution` in `run-report.md` for shared
  callback-based prerequisite lookup status
- `## Map Source Decisions` in `run-report.md` for live closeout and
  standalone-probe source selection when callback map inspection is unavailable
- `transport_provisioning` in `manifest.json` for supported variants,
  candidate chain, and affected transport commands
- `bootstrap_readiness`, `runtime_capability_profile`,
  `callback_diagnostics`, `prerequisite_resolution`, and
  `map_source_decisions` in `manifest.json` for the top-level 016 hardening
  evidence
- `itertesting: semantic_inventory=...` and `itertesting: semantic_gates=...`
  lines from `tests/headless/itertesting.sh` for quick terminal review
- `itertesting: transport_status=...` and `itertesting: transport_affected_commands=...`
  lines from `tests/headless/itertesting.sh` for quick terminal review
- `itertesting: bootstrap_readiness=...`,
  `itertesting: runtime_capability_profile=...`,
  `itertesting: callback_diagnostics=...`,
  `itertesting: prerequisite_resolution=...`, and
  `itertesting: map_source_decisions=...` lines from
  `tests/headless/itertesting.sh` for quick terminal review

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

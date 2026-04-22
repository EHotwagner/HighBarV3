# Quickstart — Live Itertesting Hardening

**Branch**: `009-live-itertest-hardening`  
**Plan**: [plan.md](./plan.md)

This quickstart validates the hardened live path: richer fixture provisioning, explicit channel-health outcomes, and tuned verification for `fight`, `move_unit`, and `build_unit`.

## Preconditions

1. Use the same Linux reference environment required by the current headless behavioral coverage workflow.
2. Start in repo root with Python client dependencies available.
3. Confirm the maintainer entrypoint and startscripts exist:
   - `tests/headless/itertesting.sh`
   - `tests/headless/scripts/minimal.startscript`
   - `tests/headless/scripts/cheats.startscript`

## 1. Run the default hardened live campaign

```bash
HIGHBAR_ITERTESTING_MAX_IMPROVEMENT_RUNS=0 \
tests/headless/itertesting.sh
```

Expected behavior:

- The live run starts from the hardened default fixture profile.
- At least 20 directly verifiable commands reach a real attempt state in the reference environment.
- The run completes without manual coordinator or engine restart.
- The final report distinguishes missing fixture, transport interruption, predicate/evidence gap, and behavioral failure.

For a repo-local validation pass that exercises the new manifest/report contract without requiring a live topology, run:

```bash
tests/headless/test_live_itertesting_hardening.sh
```

## 2. Inspect the live run artifacts

```bash
latest_run="$(find reports/itertesting -maxdepth 1 -type d -name 'itertesting-*' ! -name 'itertesting-campaign-*' | sort | tail -n 1)"
sed -n '1,260p' "$latest_run/run-report.md"
sed -n '1,220p' "$latest_run/manifest.json"
```

Expected behavior:

- The report includes channel-health and failure-cause visibility in maintainer-facing language.
- Commands blocked by prerequisites are reported as fixture issues rather than generic timeouts.
- Commands affected by transport instability are not misclassified as ordinary behavioral failures.

## 3. Re-run targeted movement/build/combat regressions

```bash
tests/headless/behavioral-move.sh
tests/headless/behavioral-build.sh
tests/headless/behavioral-attack.sh
```

Expected behavior:

- Movement and build regressions stay green under the same live topology assumptions.
- Combat-related live verification remains reachable and consistent with the hardened report semantics.

## 4. Validate tuned arm evidence paths

```bash
tests/headless/audit/repro.sh cmd-move-unit --phase=1
tests/headless/audit/repro.sh cmd-fight --phase=1
tests/headless/audit/repro.sh cmd-build-unit --phase=1
```

Expected behavior:

- `cmd-move-unit`, `cmd-fight`, and `cmd-build-unit` produce outcomes that align with their tuned live verification rules.
- Avoidable generic timeout failures for these arms are materially reduced.

## 5. Confirm disconnect handling remains explicit

Inspect the latest run for channel-health reporting after any degraded session or wrapper retry.

```bash
latest_campaign="$(find reports/itertesting -maxdepth 1 -type d -name 'itertesting-campaign-*' | sort | tail -n 1)"
sed -n '1,220p' "$latest_campaign/campaign-stop-decision.json"
```

Expected behavior:

- If the command channel stayed healthy, the run finishes without degraded-session messaging.
- If the channel degraded, the workflow records an explicit transport-level outcome instead of hiding the issue inside generic per-command failures.

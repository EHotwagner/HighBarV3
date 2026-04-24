# Quickstart: Comprehensive Admin Channel Behavioral Control

## Prerequisites

- Prepared local BAR/Spring runtime matching the repository headless test setup.
- `uv` available for the Python client test driver.
- Generated proto stubs refreshed after any `proto/highbar/*.proto` changes.
- A startscript/fixture with known teams, resources, unit definitions, valid spawn positions, and an existing transferable unit.

Missing runtime prerequisites must make the headless wrapper exit 77.

## Generate Proto Stubs After Contract Changes

```bash
buf lint proto
cd proto && buf generate
```

Then run the generated-client checks that are relevant to changed stubs:

```bash
uv run --project clients/python pytest clients/python/tests/test_admin.py
dotnet build clients/fsharp/HighBar.Client.fsproj
```

## Run Unit and Integration Coverage

```bash
cmake --build build --target admin_control_test
ctest --test-dir build --output-on-failure -R 'admin_control|command_capabilities'
uv run --project clients/python pytest clients/python/tests/behavioral_coverage/test_admin_actions.py
```

## Run the Live Admin Behavioral Suite

```bash
tests/headless/admin-behavioral-control.sh \
  --startscript tests/headless/scripts/admin-behavior.startscript \
  --output-dir build/reports/admin-behavior \
  --timeout-seconds 10
```

Expected exit codes:

- `0`: all required behavior passed
- `1`: behavioral failure; inspect `build/reports/admin-behavior/run-report.md`
- `2`: harness/report internal error
- `77`: local runtime prerequisite missing or gateway disabled

## Repeatability Check

```bash
for i in 1 2 3; do
  tests/headless/admin-behavioral-control.sh \
    --startscript tests/headless/scripts/admin-behavior.startscript \
    --output-dir "build/reports/admin-behavior/repeat-$i" \
    --timeout-seconds 10 \
    --repeat-index "$i" || exit $?
done
```

Each run must resume play, restore normal speed, and leave no active admin lease that changes the next run's outcome.

## Review Evidence

Start with:

```bash
sed -n '1,220p' build/reports/admin-behavior/run-report.md
```

For each failed row, the report must show the action, expected observation, actual observation, and engine/coordinator log location.

For fail-closed report validation without launching Spring, run:

```bash
tests/headless/admin-behavioral-control.sh --skip-launch
```

That path still renders `evidence.jsonl`, `summary.csv`, and `run-report.md`, but it must exit `1` because no before/after state-stream evidence was collected. A passing run requires live or replayed behavioral evidence for every required scenario.

For deterministic CI of the evaluator itself, run the replay fixture:

```bash
tests/headless/admin-behavioral-control.sh \
  --skip-launch \
  --evidence-replay tests/fixtures/admin_behavior/evidence-replay.json \
  --output-dir build/reports/admin-behavior-replay
```

Replay mode is accepted only because every row contains explicit before/after behavioral state and an allowed evidence source.

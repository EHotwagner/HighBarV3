# Quickstart — BAR Live Run Viewer

**Branch**: `018-live-run-viewer`  
**Plan**: [plan.md](./plan.md)

This quickstart defines the validation loop for proving that watch mode runs Itertesting inside BAR's normal graphical client, preserves the current non-watch workflow, and supports attach-later selection from durable run context.

## Preconditions

1. Use the normal Linux maintainer environment for live behavioral-coverage workflows.
2. Ensure `uv`, `SPRING_HEADLESS`, and the existing `tests/headless/itertesting.sh` prerequisites are available.
3. Ensure the BAR graphical `spring` client is installed locally with the pinned engine release. `HIGHBAR_BAR_CLIENT_BINARY` can override the resolved client path when needed.
4. Run from the repository root on branch `018-live-run-viewer`.

## 1. Validate watch profile parsing and attach-later selection

```bash
uv run --project clients/python pytest \
  clients/python/tests/behavioral_coverage/test_bnv_watch.py \
  clients/python/tests/behavioral_coverage/test_watch_registry.py
```

Expected behavior:

- The default watch profile resolves to windowed `1920x1080` spectator launch with mouse capture disabled and a default watch speed target of `3x`.
- Explicit profile references override defaults without adding many CLI flags.
- Attach-later selection uses explicit run ids or single-active auto-selection only when unambiguous.

## 2. Validate runner integration and failure policy

```bash
uv run --project clients/python pytest \
  clients/python/tests/behavioral_coverage/test_itertesting_runner.py \
  clients/python/tests/behavioral_coverage/test_itertesting_report.py
```

Expected behavior:

- Requested watch readiness failures abort before live execution begins.
- Non-watch campaigns still use the existing launch flow unchanged.
- Manifest/report surfaces render explicit watch reasons and lifecycle state.

## 3. Run the dedicated headless watch validation

```bash
tests/headless/test_live_run_viewer.sh
```

Expected behavior:

- The scripted validation creates a fake graphical `spring` binary, simulates a live watched launch, and verifies the persisted watch bundle and active index.
- An unavailable graphical BAR client environment returns an explicit failure reason within 10 seconds.
- Explicit attach-later succeeds for the selected run, while multi-run auto-selection is rejected as ambiguous.

## 4. Run a prepared live watched campaign through the maintainer wrapper

```bash
HIGHBAR_BAR_CLIENT_BINARY=/path/to/spring \
HIGHBAR_ITERTESTING_WATCH=true \
HIGHBAR_ITERTESTING_WATCH_PROFILE=default \
HIGHBAR_ITERTESTING_MAX_IMPROVEMENT_RUNS=0 \
tests/headless/itertesting.sh
```

Expected behavior:

- The wrapper still starts the existing live topology, but a watched run now uses BAR's normal graphical client instead of a separate viewer sidecar.
- The default watched viewer speed target is `3x`. Watched launches rewrite the BAR startscript bounds to `MinSpeed=0` and `MaxSpeed=10`, while pause remains a separate control.
- If `HIGHBAR_ITERTESTING_WATCH_SPEED` is set, it overrides the default target after launch through the local AI Bridge.
- On success, stdout reports the run id, campaign id, reports directory, and watch availability.
- On failure, the run stops with a watch-specific reason before consuming live execution time.

## 5. Verify attach-later against an active run

```bash
uv run --project clients/python python -m highbar_client.behavioral_coverage itertesting \
  --watch-run <run-id> \
  --watch-profile default \
  --reports-dir reports/itertesting
```

Expected behavior:

- An explicit run id reuses the intended active graphical BAR run.
- Omitting the run id by invoking `--watch-run` without a value is only allowed when the active watch index contains exactly one compatible active run.
- Ambiguous or expired requests return a user-readable reason instead of guessing.

## 6. Inspect the watch artifacts

Review the newest:

- `reports/itertesting/active-watch-sessions.json`
- `reports/itertesting/<run-id>/manifest.json`
- `reports/itertesting/<run-id>/run-report.md`

Expected behavior:

- Watch request, profile, preflight result, and viewer access state all appear in durable artifacts.
- Manifest and report use the same state and reason text.
- Viewer disconnect after launch is distinguishable from readiness failure before launch.

## 7. Closeout gate

Treat 018 as ready for `/speckit.tasks` only when all of the following hold:

1. Watch profile parsing, attach-later selection, runner integration, and report rendering tests pass.
2. The dedicated headless watch validation proves both success and explicit failure cases.
3. Non-watch live runs still require no extra operator steps.
4. Attach-later selection never guesses when multiple compatible active runs exist.
5. Watch state is visible in stdout, manifest, report, and the active watch index.

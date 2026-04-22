# Quickstart — Itertesting

**Branch**: `007-itertesting`  
**Plan**: [plan.md](./plan.md)

Itertesting runs a bounded sequence of live command-verification passes and writes one timestamped report bundle per run under `reports/itertesting/`.

## Preconditions

1. Use the reference Linux host with the pinned headless engine and BAR content already required by the existing headless scripts.
2. Start from the repo root with the normal prerequisites for `tests/headless/_launch.sh` and the Python client workspace available.
3. Ensure the default natural run can launch from `tests/headless/scripts/minimal.startscript`; keep `tests/headless/scripts/cheats.startscript` available for cheat-assisted escalation.

## Start one bounded Itertesting campaign

Run Itertesting with a retry budget of three improvement runs:

```bash
uv run --project clients/python python -m highbar_client.behavioral_coverage itertesting \
  --reports-dir reports/itertesting \
  --max-improvement-runs 3
```

Expected outcome:

- A new timestamped run directory is created under `reports/itertesting/`.
- Reusable per-command instruction files are updated under `reports/itertesting/instructions/`.
- The run manifest records all tracked commands with verified, inconclusive, blocked, or failed outcomes.
- The report separates naturally verified commands from cheat-assisted verified commands.
- If unverified commands still have better next steps, Itertesting records improvement actions and starts the next run automatically until the budget or stop rule is reached.

## Allow explicit cheat escalation

Run with cheat-backed setup available once natural progress stalls:

```bash
uv run --project clients/python python -m highbar_client.behavioral_coverage itertesting \
  --reports-dir reports/itertesting \
  --max-improvement-runs 3 \
  --allow-cheat-escalation \
  --cheat-startscript tests/headless/scripts/cheats.startscript
```

Expected outcome:

- Commands that could not be verified naturally may escalate to cheat-assisted setup in later runs.
- The report labels those commands and counts them separately from natural verification.

## Review one run

Inspect the latest run bundle:

```bash
ls -1 reports/itertesting
sed -n '1,220p' reports/itertesting/<run-id>/run-report.md
```

Expected outcome:

- The report can be reviewed without consulting raw engine output.
- Each unverified command includes a blocking, failure, or inconclusive reason.
- The report states whether verified coverage improved, regressed, or stalled versus the previous run.
- The `instructions/` directory captures reusable per-command guidance that later campaigns can load and refine.

## Force a short diagnostic campaign

Limit the workflow to the initial run only:

```bash
uv run --project clients/python python -m highbar_client.behavioral_coverage itertesting \
  --reports-dir reports/itertesting \
  --max-improvement-runs 0
```

Expected outcome:

- Exactly one run bundle is created.
- The campaign stops immediately after the first run and records that the retry budget was exhausted.

## Naming and collision behavior

- Run ids are based on UTC date/time to the second.
- If two runs start within the same second, Itertesting appends a deterministic suffix so reports do not collide.
- Older run bundles remain in place for comparison; Itertesting must not overwrite them.

## Repo-local wrapper

Use the wrapper when you want the repo defaults without retyping the Python invocation:

```bash
tests/headless/itertesting.sh
HIGHBAR_ITERTESTING_MAX_IMPROVEMENT_RUNS=1 tests/headless/itertesting.sh
HIGHBAR_ITERTESTING_MAX_IMPROVEMENT_RUNS=2 \
HIGHBAR_ITERTESTING_ALLOW_CHEAT_ESCALATION=true \
tests/headless/itertesting.sh
```

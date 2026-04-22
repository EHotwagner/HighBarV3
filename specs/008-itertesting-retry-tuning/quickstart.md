# Quickstart — Itertesting Retry Tuning

**Branch**: `008-itertesting-retry-tuning`  
**Plan**: [plan.md](./plan.md)

This quickstart validates the retry-tuning behavior: profile intent mapping, 10-run hard cap, early stall stop, natural-first ordering, and direct-target/runtime reporting.

## Preconditions

1. Use the same Linux reference environment required by existing headless behavioral coverage workflows.
2. Start in repo root with Python client dependencies available.
3. Confirm both startscripts exist:
   - `tests/headless/scripts/minimal.startscript`
   - `tests/headless/scripts/cheats.startscript`

## 1. Run a standard campaign

```bash
uv run --project clients/python python -m highbar_client.behavioral_coverage itertesting \
  --reports-dir reports/itertesting \
  --retry-intensity standard \
  --max-improvement-runs 5 \
  --runtime-target-minutes 15
```

Expected behavior:

- Campaign uses `standard` retry envelope.
- Effective improvement-run budget is <= 10.
- Run reports include direct/non-observable split and configured-vs-effective retries.
- Campaign emits `reports/itertesting/<campaign-id>/campaign-stop-decision.json`.

## 2. Verify hard cap clamping

```bash
uv run --project clients/python python -m highbar_client.behavioral_coverage itertesting \
  --reports-dir reports/itertesting \
  --retry-intensity deep \
  --max-improvement-runs 100
```

Expected behavior:

- Requested budget is logged as 100.
- Effective budget is clamped to 10.
- Campaign never executes more than 10 improvement runs.

## 3. Validate quick diagnostic mode

```bash
uv run --project clients/python python -m highbar_client.behavioral_coverage itertesting \
  --reports-dir reports/itertesting \
  --retry-intensity quick \
  --max-improvement-runs 100
```

Expected behavior:

- Campaign finishes with a small bounded retry envelope.
- Early-stop behavior triggers quickly if direct progress stalls.
- Stop decision reason is `stalled` and run count is far below the configured budget.

## 4. Validate natural-first with optional cheat escalation

```bash
uv run --project clients/python python -m highbar_client.behavioral_coverage itertesting \
  --reports-dir reports/itertesting \
  --retry-intensity standard \
  --allow-cheat-escalation \
  --cheat-startscript tests/headless/scripts/cheats.startscript
```

Expected behavior:

- Natural verification attempts happen first.
- Cheat-assisted verification appears only after natural stalls (unless explicit override mode is configured via `--no-natural-first`).
- Reports split natural and cheat-assisted direct counts.

## 5. Reuse improvement guidance across campaigns

Run two consecutive campaigns over the same command inventory.

```bash
uv run --project clients/python python -m highbar_client.behavioral_coverage itertesting \
  --reports-dir reports/itertesting \
  --retry-intensity standard

uv run --project clients/python python -m highbar_client.behavioral_coverage itertesting \
  --reports-dir reports/itertesting \
  --retry-intensity standard
```

Expected behavior:

- `reports/itertesting/instructions/` is loaded on campaign start.
- Updated guidance revisions are written when new evidence changes recommendations.

## 6. Confirm target and runtime signaling

Inspect the latest campaign summary/report.

```bash
ls -1 reports/itertesting
sed -n '1,260p' reports/itertesting/<campaign-or-run-id>/run-report.md
sed -n '1,200p' reports/itertesting/<campaign-id>/campaign-stop-decision.json
```

Expected behavior:

- Report states whether directly verifiable target (`>=20`) was met.
- Report includes runtime elapsed and whether run completed within the 15-minute target envelope.
- Stop reason is explicit (`target_reached`, `stalled`, `budget_exhausted`, `runtime_guardrail`, or `interrupted`).

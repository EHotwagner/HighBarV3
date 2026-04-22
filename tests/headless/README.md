# Headless Workflow Notes

`tests/headless/itertesting.sh` is the maintainer entrypoint for the Itertesting CLI from the repo root.

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

Use `tests/headless/test_itertesting_campaign.sh` to validate that chained runs emit both artifacts.

Malformed payload resilience can be checked directly with:

```bash
tests/headless/malformed-payload.sh
```

Expected result: `INVALID_ARGUMENT` for the bad batch, no gateway disable, continued heartbeats.

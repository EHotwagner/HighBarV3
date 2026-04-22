# Quickstart — Live Audit Evidence Refresh

**Branch**: `006-live-audit-evidence`  
**Plan**: [plan.md](./plan.md)

This feature keeps the existing 004 entry points but changes them from seeded synthesis to live refresh commands.

## Preconditions

1. Use the reference host with the pinned headless engine and BAR content already required by the existing headless tests.
2. Start from the repo root on branch `006-live-audit-evidence`.
3. Ensure the normal headless launch prerequisites used by `tests/headless/_launch.sh` are available.

## Full refresh

Run the complete live refresh workflow:

```bash
tests/headless/audit/run-all.sh
```

Expected outcome:

- The latest live-run manifest is written under `build/reports/`.
- `audit/command-audit.md`, `audit/hypothesis-plan.md`, and `audit/v2-v3-ledger.md` are regenerated from that run.
- Any incomplete rows or deliverables are marked `not refreshed live` or `partial`.
- Shell stdout includes the selected run id plus refreshed, drifted, and not-refreshed counts.

## Row-level reproduction

Reproduce one refreshed row against the live topology:

```bash
tests/headless/audit/repro.sh cmd-build-unit --phase=1
tests/headless/audit/repro.sh rpc-submit-commands --phase=1
```

Expected outcome:

- A row-specific report lands in `build/reports/`.
- The command exits with a reviewer-readable PASS/FAIL summary.
- Use `tests/headless/audit/def-id-resolver.py <row-id>` to print the primary unit prerequisite for row-specific setup.

## Hypothesis recheck

Re-run one blocked or broken row’s distinguishing test:

```bash
tests/headless/audit/hypothesis.sh cmd-move-unit phase1_reissuance
```

Expected outcome:

- The script records a hypothesis result under `build/reports/`.
- The verdict is explicit (`CONFIRMED` or `FALSIFIED`) and can be linked back into the refreshed markdown.

## Drift check

Compare repeated live refreshes:

```bash
tests/headless/audit/repro-stability.sh
```

Expected outcome:

- Two completed manifests are compared.
- Rows whose latest outcome differs are surfaced as drift instead of being silently overwritten.

## Partial refresh validation

Simulate a degraded environment without editing the scripts:

```bash
PYTHONPATH=clients/python python -m highbar_client.behavioral_coverage audit refresh \
  --summary-only \
  --fail-rows cmd-move-unit,cmd-fight \
  --topology-failure "launcher degraded"
```

Expected outcome:

- The generated manifest records `topology_status=partial`.
- The affected rows are marked `not refreshed live` with explicit failure reasons.
- Deliverable states move to `partial` and the summary surfaces the failure reasons.

## Phase-2 attribution

Run the dispatcher-only smoke path:

```bash
tests/headless/audit/phase2-macro-chain.sh
```

Expected outcome:

- Phase-2 attribution evidence lands under `build/reports/`.
- Rows that depend on Phase-2 confirmation can link to current smoke evidence instead of the existing static seed report.

## Timing and unattended-run notes

- `tests/headless/audit/run-all.sh` is intended to run unattended from the repo root and writes all outputs under `build/reports/`.
- The refresh flow is deterministic enough for repeated manifest comparison, but no hard wall-clock SLA is enforced by this feature.
- Reviewers should treat the shell summary as the first gate: if any deliverable is `partial` or `not refreshed live`, inspect the listed failure reasons before trusting the checked-in markdown.

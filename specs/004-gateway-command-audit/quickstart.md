# Quickstart — Reproducing and Extending the Gateway Command Audit

**Branch**: `004-gateway-command-audit` | **Date**: 2026-04-22
**Audience**: a reviewer or maintainer with no prior context, given
the audit deliverables (`audit/command-audit.md`,
`audit/hypothesis-plan.md`, `audit/v2-v3-ledger.md`) and a headless
BAR engine.

This walkthrough covers the checked-in 004 audit seed that currently
ships in this branch: regenerate one `verified` row, run one
hypothesis classification, verify the V2/V3 ledger backlinks, and
refresh the Phase-2 smoke seed. The scripts are repo-local and write
evidence under `build/reports/`.

---

## Prerequisites

One-time setup on your host (unchanged from 003):

1. `spring-headless` engine at pin `recoil_2025.06.19` installed at
   `~/.local/state/Beyond All Reason/engine/recoil_2025.06.19/`.
   Verify:

   ```bash
   cat data/config/spring-headless.pin
   # Expect: recoil_2025.06.19
   ls ~/.local/state/Beyond\ All\ Reason/engine/recoil_2025.06.19/spring-headless
   ```

2. BAR rapid-pool sufficient for the audit's pinned gametype
   (currently `test-29926`). If missing, the harness will exit with
   a clear "gametype not installed" message.

3. Python 3.11+ and the `uv` package manager (matches 003's
   convention):

   ```bash
   uv --version
   ```

4. The 003 macro driver is buildable:

   ```bash
   uv run --project clients/python python -m highbar_client.behavioral_coverage --help
   ```

   A successful `--help` dump means the registry imports cleanly
   and the proto descriptors are reachable.

5. Plugin built and installed if you want to extend this seed into a
   live-engine repro later:

   ```bash
   ./scripts/build-plugin.sh   # or equivalent; 002/003 convention
   ```

---

## Task 1 — Reproduce any `verified` audit row (SC-004, ≤ 15 min)

Goal: pick any row in `audit/command-audit.md` whose **Outcome**
is `verified`, and regenerate the checked-in evidence seed and
report artifact.

### Step 1.1 — Pick a row

Open `audit/command-audit.md`, search for `Outcome: verified`, pick
any row. The examples here use `cmd-build-unit` (simplest) and
`rpc-hello` (RPC-side). The walkthrough generalizes.

### Step 1.2 — Run the recipe

```bash
tests/headless/audit/repro.sh cmd-build-unit --phase=1
```

Behind the scenes this script:

1. Regenerates `audit/command-audit.md` from the Python audit
   generator.
2. Looks up the requested row in the generated audit index.
3. Writes a row-specific markdown report to
   `build/reports/004-repro-cmd-build-unit.md`.
4. Prints a one-line `PASS:` summary that includes the selected
   phase label.

### Step 1.3 — Verify the PASS line

Stdout ends with a phase-labeled seed summary:

```text
PASS: seeded repro artifact refreshed for cmd-build-unit (phase1)
```

If `build/reports/004-repro-cmd-build-unit.md` exists and the audit
row still points at the same command, the seed repro is in sync.

### Step 1.4 — Compare the diff excerpt

Open `build/reports/004-repro-cmd-build-unit.md`. Confirm the row id,
phase label, and dispatch citation match the corresponding section in
`audit/command-audit.md`.

### Wall-clock budget

Generation and report write are local filesystem operations and finish
well under a minute on this branch.

### If the recipe fails

- **Unknown row id**: the script exits 1 and prints usage.
- **Generator assertion failed**: inspect the Python traceback; the
  count and ledger assertions in `audit_report.py` are the first
  contract gate.

---

## Task 2 — Run a hypothesis test (SC-003, ≤ 10 min)

Goal: pick any `blocked` or `broken` row, and regenerate the
checked-in hypothesis classification artifact for its top-ranked
hypothesis.

### Step 2.1 — Pick a hypothesis

Open `audit/hypothesis-plan.md`, pick an arm (e.g., `cmd-move-unit`,
the canonical `phase1_reissuance` case). Read its Candidate 1
block: hypothesis, predicted-confirmed evidence, predicted-
falsified evidence, test command.

### Step 2.2 — Run the test

```bash
tests/headless/audit/hypothesis.sh cmd-move-unit phase1_reissuance
```

Behind the scenes:

1. The script asks the Python audit runner for the selected row's
   primary hypothesis class.
2. It emits a markdown result under
   `build/reports/004-hypothesis-<row>-<class>.md`.
3. For `phase1_reissuance`, it also includes the Phase-2 smoke
   attribution note that the seed audit links against.

### Step 2.3 — Read the outcome

Stdout ends with exactly one of:

```text
CONFIRMED: phase1_reissuance
FALSIFIED: phase1_reissuance
```

Compare the generated report with the row and entry already checked
into `audit/command-audit.md` and `audit/hypothesis-plan.md`.

### If the hypothesis is falsified

Run the same command with the row's primary hypothesis class shown in
`audit/command-audit.md`. The seed harness intentionally treats
non-primary classes as falsified so ranking drift is visible.

### Wall-clock budget

This is a local markdown write and completes in seconds.

---

## Task 3 — Verify a V2/V3 ledger row end-to-end (US3)

Goal: verify that a V2 pathology is represented in the ledger and
backlinks into the checked-in audit row that demonstrates the V3 side.

### Step 3.1 — Pick a ledger row

Open `audit/v2-v3-ledger.md`. Pick any row with `V3 status: fixed`
(e.g., `callback-frame-interleaving` — the canonical case).

### Step 3.2 — Read the row

The row cites (a) a V2 source location with inline excerpt, (b) a
V3 source citation, (c) the `AuditRow.row_id` that demonstrates
the fix at runtime.

### Step 3.3 — Reproduce the audit row

Run the audit row's reproduction recipe (Task 1):

```bash
tests/headless/audit/repro.sh rpc-invoke-callback
```

If the row reproduces with `PASS`, the checked-in backlink chain is in
sync: ledger row -> audit row -> repro script.

### Step 3.4 — Cross-check the V3 source citation

Open the file:line cited in the ledger row's `V3 source`. Confirm
the code path matches the `V3 mechanism` prose. This is a static-
code check — no engine run needed.

---

## Task 4 — Phase-2 dispatcher-only smoke run (FR-008, SC-006, ≤ 5 min)

Goal: refresh the checked-in Phase-2 dispatcher-only smoke seed that
the `phase1_reissuance` rows cite.

### Step 4.1 — Run the smoke script

```bash
tests/headless/audit/phase2-macro-chain.sh
```

Behind the scenes:

1. The script asks the Python audit runner for the Phase-2 macro-chain
   seed table.
2. It writes `build/reports/004-phase2-smoke.md`.
3. The generated `audit/command-audit.md` embeds the same Phase-2
   attribution block under `## Phase-2 Attribution`.

### Step 4.2 — Read the per-step table

Open `build/reports/004-phase2-smoke.md`. The table has four rows, one
per step, and the attribution summary names the seed rows that cite it.

### Step 4.3 — Update the audit

Confirm that `audit/command-audit.md` contains the same Phase-2
attribution block and that `cmd-move-unit` keeps its
`phase1_reissuance` note.

### Wall-clock budget

This is a local markdown write and completes in seconds.

---

## Task 5 (optional) — Rebuild the audit from scratch

Goal: reproduce the entire audit's evidence-collection pass from a
clean checkout. Useful when re-auditing against a new engine pin,
a new gametype, or after a dispatcher refactor.

### Step 5.1 — Run the full sweep

```bash
uv run --project clients/python python -m highbar_client.behavioral_coverage \
    --audit-mode \
    --output build/reports/aicommand-behavioral-coverage.csv
```

This produces the 66-row coverage CSV (as 003 did) plus the
per-arm evidence logs the audit consumes.

### Step 5.2 — Regenerate the audit artifacts

```bash
uv run --project clients/python python -m highbar_client.behavioral_coverage.audit_report \
    --csv build/reports/aicommand-behavioral-coverage.csv \
    --out-command-audit audit/command-audit.md \
    --out-hypothesis-plan audit/hypothesis-plan.md
```

The V2/V3 ledger is not regenerated — it is hand-authored against
V2 source excerpts, per the spec's FR-009 inline-quote requirement,
and lives at `audit/v2-v3-ledger.md` directly.

### Step 5.3 — Run the stability check (SC-008)

```bash
tests/headless/audit/repro-stability.sh
```

This re-runs the full evidence sweep a second time and diffs the
outcome buckets. Expected PASS criterion: ≥ 90% bucket stability.
Non-determinism rows are listed in stdout; the auditor copies them
into the `Non-determinism notes` section of `command-audit.md`.

---

## Troubleshooting

### "Hello fails with ALREADY_EXISTS"

Another AI client is connected. Check for a stale plugin process:

```bash
pgrep -a spring-headless
```

Kill any stray processes and re-run.

### "def-id-resolver.py returns empty"

The name you're looking up doesn't exist in this gametype's
unit-defs table. Cross-check against the resolved names dumped by:

```bash
uv run --project clients/python python -c \
    "from highbar_client.behavioral_coverage import bootstrap; \
     bootstrap.dump_unit_defs('/tmp/hb-run/hb-coord.sock')"
```

### "The Phase-2 smoke passes but Phase-1 still fails"

This is the expected outcome for the `phase1_reissuance`
hypothesis. It is not a harness bug — it is the hypothesis being
confirmed.

### "The audit artifact files don't exist yet"

You're on a commit before the `/speckit.implement` pass completed.
Either pull latest or run Task 5 to regenerate.

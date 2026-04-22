# Contract — Reproduction Recipe format

**Applies to**: every `reproduction_recipe` field on a
`verified` `AuditRow` and every `test_command` field on a
`HypothesisCandidate`.

**Referenced from**: data-model.md (`ReproductionRecipe`),
audit-row.md, hypothesis-entry.md.

## Shell command shape

Recipes are shell one-liners. Two canonical forms:

### Form A — audit row reproduction

```bash
tests/headless/audit/repro.sh <row_id> [gametype_pin]
```

- `<row_id>` is the kebab-case AuditRow identifier (e.g.,
  `cmd-build-unit`, `rpc-hello`).
- `[gametype_pin]` is optional. When absent, the script reads
  `tests/headless/scripts/minimal.startscript`'s pinned gametype.
- The script writes full evidence to
  `build/reports/004-repro-<row_id>.md` (path MUST be under
  `build/reports/`, gitignored, per SC-007).
- The script's stdout MUST contain a one-line `PASS:` or `FAIL:`
  summary. The audit row's `expected_stdout_excerpt` captures the
  `PASS:` line.

### Form B — hypothesis test

```bash
tests/headless/audit/hypothesis.sh <row_id> <hypothesis_class>
```

- `<row_id>` is the kebab-case AuditRow identifier of the
  related audit row.
- `<hypothesis_class>` is a value from the closed vocabulary
  (data-model §HypothesisClass).
- The script writes a structured result to
  `build/reports/004-hypothesis-<row_id>-<hypothesis_class>.md`
  (gitignored).
- Stdout contains either `CONFIRMED: <hypothesis_class>` or
  `FALSIFIED: <hypothesis_class>`, exactly one of the two.
- Exit code 0 regardless of confirmed/falsified (both are valid
  outcomes); exit code 1 only for harness errors (engine boot
  failure, RPC not reachable, def-id resolution failure).

## Parameter-table form (optional)

When a recipe needs extra parameters beyond `<row_id>` and
`[gametype_pin]`, it extends the form with `--key=value` flags:

```bash
tests/headless/audit/repro.sh cmd-give-me --cheats=on
tests/headless/audit/hypothesis.sh cmd-move-unit phase1_reissuance --phase=2
```

The parameter vocabulary is restricted to the following keys
(extensible only via a contract update):

| Key | Values | Purpose |
|-----|--------|---------|
| `--cheats` | `on` \| `off` | Select cheats startscript variant (research §4). Default: `off`. |
| `--phase` | `1` \| `2` | Select Phase-1 (enable_builtin=true) or Phase-2 (enable_builtin=false). Default: `1` per FR-013. |
| `--seed` | integer | Fix game seed for determinism investigation. Default: startscript pin. |
| `--repro-timeout` | integer (seconds) | Override wall-clock budget (SC-003 / SC-004). Default from the recipe's `wall_clock_budget_seconds`. |

## Constraints

1. **No `/tmp/*.py` or other ad-hoc paths** (FR-012, SC-007). The
   `repro.sh` / `hypothesis.sh` scripts live under
   `tests/headless/audit/` and are checked in.
2. **No hardcoded integer def-ids** (FR-006). Recipes resolve
   def-ids at run time via `tests/headless/audit/def-id-resolver.py`
   or — when the arm's proto accepts an integer payload — record
   the gametype pin in the recipe's `[gametype_pin]` argument.
3. **Phase-1 default** (FR-013). Phase-2 recipes MUST pass
   `--phase=2` explicitly.
4. **Wall-clock budget** (SC-003, SC-004): hypothesis tests ≤ 10
   minutes (600 seconds); reproduction recipes ≤ 15 minutes (900
   seconds). Scripts enforce via `timeout` wrapper; on budget
   expiry they emit `FAIL: budget exceeded` and exit 1.

## Output artifacts

All recipe artifacts land under `build/reports/` (gitignored,
SC-007):

```text
build/reports/
├── 004-repro-<row_id>.md                 # per-arm repro full output
├── 004-hypothesis-<row_id>-<class>.md    # per-hypothesis full output
├── 004-phase2-smoke.log                  # raw stdout of the Phase-2 smoke run
└── 004-stability-run-{1,2}.md            # per-run output of repro-stability.sh
```

The checked-in `reports/004-phase2-smoke.md` is the *narrative*
Phase-2 smoke report written by hand after
`phase2-macro-chain.sh` runs — the raw log in `build/reports/` is
the evidence it cites.

## Recipe lifecycle

- **Written**: during `/speckit.implement`, one recipe per
  `verified` audit row and one per hypothesis candidate.
- **Run**: by `/speckit.implement` to produce evidence; by any
  reviewer reproducing an audit row (SC-004).
- **Updated**: whenever the dispatcher code or snapshot wire
  format changes. The recipe is stable against gametype drift
  because of FR-006's name-based def-id resolution.
- **Deprecated**: if the row's outcome bucket changes to
  `broken` or `dispatched-only`, the recipe is removed and
  replaced with a hypothesis test or a channel citation.

## Example recipes (for reference)

### Example 1 — cmd-build-unit (verified)

```bash
tests/headless/audit/repro.sh cmd-build-unit
```

Expected stdout:

```text
[004-repro] engine=recoil_2025.06.19 gametype=test-29926
[004-repro] resolved def_id(armlab) via HelloResponse.unit_defs
[004-repro] dispatched BuildUnit commander=<cid> def_id=<did>
[004-repro] sampled snapshot at T+2.0s: own_units[lab]
            .under_construction=true .build_progress=0.08
PASS: build_progress diff > 0, under_construction=true observed
```

### Example 2 — cmd-move-unit (blocked, phase1_reissuance hypothesis)

```bash
tests/headless/audit/hypothesis.sh cmd-move-unit phase1_reissuance
```

Expected stdout (on confirmation):

```text
[004-hyp] Phase-1 run: no position diff after MoveUnit (as predicted)
[004-hyp] Phase-2 run (--phase=2): position diff observed
[004-hyp] hypothesis: phase1_reissuance → ambient BARb re-issued prior order
CONFIRMED: phase1_reissuance
```

### Example 3 — cmd-give-me (cheats-gated, dual-outcome)

```bash
tests/headless/audit/repro.sh cmd-give-me --cheats=on
tests/headless/audit/repro.sh cmd-give-me --cheats=off
```

Both recipes produce evidence; the audit row records the outcome
of both runs per spec edge case "Cheats-gated arms when cheats are
off".

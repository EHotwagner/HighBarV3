# Phase 0 Research — Gateway Command Audit

**Branch**: `004-gateway-command-audit` | **Date**: 2026-04-22
**Plan**: [plan.md](./plan.md) | **Spec**: [spec.md](./spec.md)

The spec explicitly enumerates its requirements (74 rows, ≥43
hypothesis entries, ≥6 ledger rows). The open questions that need
resolution before Phase 1 artifact design are:

1. **Authoritative V2-pathology source**: where does the ledger cite
   from? (Spec references a path that doesn't exist.)
2. **Outcome bucket semantics**: how does the audit encode the
   FR-011 "dispatcher correct ≠ engine outcome" rule so `broken` is
   reserved for genuine dispatcher defects?
3. **Hypothesis class vocabulary**: what's the closed enumeration of
   hypothesis families the plan should use? Open-ended free-text
   hypotheses make cross-row analysis impossible.
4. **Cheats-mode variant**: how does the audit exercise `give_me` /
   `give_me_new_unit` against both cheats-enabled and cheats-disabled
   match configurations without forking the startscript system?
5. **Def-id stability policy**: FR-006 allows either run-time
   resolution OR gametype-pinning. Which does the harness default to,
   and when is the fallback invoked?
6. **Audit deliverable directory**: the spec names `audit/command-audit.md`
   but the directory doesn't exist yet. Where should it live to avoid
   colliding with existing conventions (`docs/`, `reports/`)?
7. **Reproducibility window**: SC-008 mandates ≥90% outcome bucket
   stability across runs. Which non-determinism sources does this
   bound, and how does the stability script bucket flipping?
8. **Phase-2 smoke-run integration**: does `tests/headless/audit/phase2-macro-chain.sh`
   extend the existing 003 `phase2-smoke.sh`, or is it an independent
   driver?

Each decision below follows the Decision / Rationale / Alternatives
Considered format mandated by the speckit research-phase template.

---

## 1. Authoritative V2-pathology source

**Decision**: The V2 pathology ledger cites from two authoritative
V2 files:

- `/home/developer/projects/HighBarV2/docs/known-issues.md`
  (primary — enumerates the callback-frame interleaving race, the
  8 MB max-message limit, single-connection lockout with no
  auto-reconnect, frame-budget timeout, Save/Load TODOs).
- `/home/developer/projects/HighBarV2/reports/017-fix-client-socket-hang.md`
  (secondary — documents the `recvBytes` infinite loop at
  `clients/fsharp/src/Client.fs` lines 33-40, cited by FR-010).

Both files are quoted inline in `audit/v2-v3-ledger.md` so the
ledger is self-contained per FR-009's "if the V2 directory is
unavailable on a reviewer's host, the V2 ledger MUST quote the
relevant V2 source excerpts inline."

**Rationale**: The spec at FR-009 and User Story 3 acceptance scenario
1 cites `/home/developer/projects/HighBarV2/reports/known-issues.md`.
That file does not exist. Surveying the V2 tree on 2026-04-22 located
the file at `docs/known-issues.md` (105 lines, content matches FR-010's
named pathologies). The spec has a path typo. The research phase
corrects the citation so the plan is implementable; the spec itself
is not re-opened because the *content* it wants is unambiguous (the
V2 pathology enumeration) and only the filename differs.

**Alternatives considered**:

- *Reopen the spec to edit FR-009*: rejected. The spec's intent is
  unambiguous and the typo doesn't affect any other requirement. Re-
  opening would force a re-clarify cycle for a cosmetic correction.
- *Cite only `017-fix-client-socket-hang.md` and omit the other
  pathologies*: rejected. FR-010 names six pathologies explicitly by
  content, five of which live only in `docs/known-issues.md`. Omitting
  them would fail FR-010.
- *Re-derive the pathology list from V2 git-log commit messages*:
  rejected. Commit messages are less stable evidence than the
  already-curated `known-issues.md` digest. The V2 team already did
  the curation work.

---

## 2. Outcome-bucket semantics

**Decision**: The audit uses exactly four outcome buckets, defined in
FR-001, with the following concrete decision procedure applied per
row in the order listed:

1. **`verified`** — the dispatcher returned success AND the expected
   post-effect is visible on the wire (snapshot diff OR engine log
   line OR delta event). The row cites the specific evidence excerpt.
2. **`dispatched-only`** — the dispatcher returned success AND the
   effect is **not wire-observable by design** (channel-C Lua,
   channel-B query, team-global state, drawer-only). The row cites
   the specific channel per FR-014, using the vocabulary already
   present in `clients/python/highbar_client/behavioral_coverage/registry.py`
   (`_CHANNEL_C_LUA_ARMS`, `_CHANNEL_B_QUERY_ARMS`, `_CHEATS_ARMS`).
3. **`blocked`** — the dispatcher returned success AND the expected
   effect is *in principle* wire-observable, but a **documented
   external condition** prevented it on this run (Phase-1 ambient AI
   re-issuance, cheats off, cross-team def-id, team-global singleton
   held elsewhere). The row states the hypothesis in one sentence
   and names the test that would distinguish "dispatcher correct,
   external blocker" from "dispatcher actually broken."
4. **`broken`** — the dispatcher returned success but the engine
   performed no effect AND no documented external condition explains
   it. This is the defect-backlog bucket. Rows here MUST name a
   falsifiable dispatcher hypothesis (e.g., "CommandDispatch.cpp's
   `kFoo` handler calls the wrong `CCircuitUnit::Cmd*` method") and
   the test that confirms or falsifies the dispatcher defect.

The decision procedure ensures no row is `broken` purely for
"dispatched-but-effect-not-observed" reasons (FR-011).

**Rationale**: FR-011 is the single most important rule in this
feature — it keeps `broken` narrow enough that the defect backlog is
actionable. A 4-bucket taxonomy with an ordered decision procedure
makes the classification reproducible across reviewers (SC-008 90%
stability); a fuzzier taxonomy (or an unordered one) would produce
bucket drift between audit runs and invalidate SC-008.

The `dispatched-only` label (rather than `na` as the 003 registry
uses) is a deliberate rename: `na` is ambiguous between "not
applicable to our coverage" and "no evidence collected"; the audit
replaces it with a positive statement of what the arm *does* (its
dispatch succeeded) and why it is not wire-observable (the channel).
The cross-walk is one-to-one: every 003 `verified="na"` row becomes
an audit `dispatched-only` row; no rows are re-classified.

**Alternatives considered**:

- *Three buckets (verified / not-verified / broken)*: rejected. This
  collapses `dispatched-only` and `blocked` into "not-verified,"
  which destroys the hypothesis-plan's ability to distinguish
  "arm is dispatcher-correct and engineering won't pursue further
  verification" from "arm is dispatcher-correct but blocked on a
  testable external condition."
- *Five buckets (add `unknown` as a fifth)*: rejected. `unknown` is
  equivalent to "the auditor didn't reach this row" and would leak
  into the final artifact. The audit is not complete unless every
  row has evidence; a missing-evidence row is itself a finding
  (bucket `broken` with hypothesis "audit did not collect evidence
  because X").
- *Keep the 003 `verified="true"/"false"/"na"` ternary*: rejected.
  It lacks a `blocked` distinction, which is the thing the audit is
  *for*.

---

## 3. Hypothesis class vocabulary

**Decision**: The hypothesis-plan uses a closed enumeration of
hypothesis classes. Each unverified arm's hypothesis list is a
ranked selection from this vocabulary. New rows MAY add a class to
the vocabulary via a one-line edit to
`clients/python/highbar_client/behavioral_coverage/audit_report.py`'s
`HYPOTHESIS_CLASSES` dict, but ad-hoc free-text hypotheses are not
allowed at the row level (cross-row analysis requires a closed set).

Initial vocabulary (ordered by expected frequency in the 39-arm
denominator):

- **`phase1_reissuance`** — Phase-1 BARb ambient AI overrides the
  external command on the next frame by re-issuing its own decision.
  Predicted-confirmed shape: Phase-1 observes no snapshot diff,
  Phase-2 (enable_builtin=false) observes the expected diff.
  Falsifier: US4 smoke run. Known precedent: report 1 §4 step 4
  MoveUnit-on-factory-produce.
- **`effect_not_snapshotable`** — the engine performs the effect but
  it does not surface in `own_units[]` / `enemy_units[]` /
  `StateSnapshot` (e.g., attack posture flags, movement-state flags,
  repeat-mode flags, stockpile counters). Predicted-confirmed shape:
  no snapshot diff but an `engine.infolog` line like "unit %d set
  fire_state=%s" confirms. Falsifier: engine log inspection.
- **`target_missing`** — the dispatcher requires a target that the
  harness didn't provision (e.g., `capture` needs an enemy unit in
  range; `repair` needs a damaged friendly; `reclaim_feature` needs
  a feature to reclaim). Predicted-confirmed shape: gateway ack
  returns success but engine log shows "target not found" or the
  pre-effect unit state is not a valid precondition.
  Falsifier: provision the precondition in the bootstrap plan and re-
  run; if effect now manifests, hypothesis confirmed.
- **`cross_team_rejection`** — dispatcher ack succeeds but engine
  silently rejects because the def-id belongs to a faction the actor
  can't build (report 1 §4.3 step 2 — Cortex def issued by Armada
  commander). Predicted-confirmed shape: no `own_units[]` diff. No
  engine log line. Falsifier: resolve the def-id via
  `def-id-resolver.py` with the actor's faction and re-run; if
  effect manifests, hypothesis confirmed.
- **`cheats_required`** — the arm requires `cheats=1` in the match
  configuration (`give_me`, `give_me_new_unit`). Predicted-confirmed
  shape: cheats-off run produces no diff; cheats-on run produces
  the expected diff. Falsifier: cheats.startscript variant per spec
  Assumptions.
- **`dispatcher_defect`** — the dispatcher's handler for this arm
  calls the wrong engine method, returns success without invoking
  any method, or invokes the right method with malformed arguments.
  Predicted-confirmed shape: Phase-2 smoke run also produces no
  diff AND no engine log line for the dispatched arm. Falsifier:
  Phase-2 smoke run with a bespoke assertion on
  `src/circuit/grpc/CommandDispatch.cpp`'s arm-handler log output.
- **`intended_noop`** — the dispatcher intentionally does nothing
  (e.g., `set_figure_position` per `src/circuit/grpc/CommandDispatch.cpp`
  lines 595-603: "Engine has no Figure::SetPosition"). Predicted-
  confirmed shape: no effect is expected on any channel; the
  dispatcher comment is cited as the positive proof of intent.
  Falsifier: none needed — this is itself a design decision the
  audit records as `dispatched-only` with the dispatcher comment
  as evidence.
- **`engine_version_drift`** — the engine version under audit
  (`recoil_2025.06.19`) doesn't expose the callback or engine-side
  API the dispatcher attempts to call (e.g., a future BAR
  widget-bound command). Predicted-confirmed shape: dispatcher log
  line shows "drawer not available" or "callback returned nullptr".
  Falsifier: retry against a newer engine pin (out of scope for 004;
  logged as a follow-up).

**Rationale**: A closed vocabulary makes the hypothesis plan a
first-class data structure rather than a prose document. It enables
SC-008's 90% stability check (bucket flipping is detected by class
flipping) and lets the audit's follow-up planning aggregate
"hypothesis classes by frequency" rather than re-reading each row.
The eight classes above cover every example the spec names plus the
patterns visible in the 003 registry lines 320-352 enumeration.

**Alternatives considered**:

- *Free-text hypotheses*: rejected. The spec's success criteria
  (SC-008) require stability across runs; free-text hypotheses drift
  between auditor passes even when the underlying finding is stable.
- *Enumerate exactly one hypothesis per arm*: rejected. US2
  acceptance scenario 1 requires "ranked hypothesis list" for
  ambiguous cases. A 2-3-long ranked list is cheap to produce and
  avoids premature commitment.
- *Larger vocabulary with 12+ classes*: rejected. Adding classes
  that fewer than ~3 arms would map to produces sparse, unusable
  buckets. The eight-class vocabulary is extensible via the registry
  edit path noted above.

---

## 4. Cheats-mode variant handling

**Decision**: Add one new startscript variant
(`tests/headless/scripts/cheats.startscript`) that is a byte-for-
byte copy of `minimal.startscript` with exactly two overrides:
(a) `Cheats=1` under `[GAME]`, (b) `GameType=test-29926` pinned to
the same gametype the Phase-1 audit runs against (so def-ids are
comparable). The cheats-gated audit rows (`give_me`, `give_me_new_unit`)
run their reproduction recipe twice — once against each startscript
— and the row records both outcomes:

- Cheats-on run expected outcome: `verified` with the spawned unit
  in `own_units[]`.
- Cheats-off run expected outcome: `blocked` with hypothesis class
  `cheats_required`.

**Rationale**: Spec edge case "Cheats-gated arms when cheats are off"
is explicit that the audit MUST run both outcomes and record both.
The existing 003 `minimal.startscript` is used by every other arm's
reproduction; forking it to a cheats variant is cheaper than
parameterising the existing one (which the existing 002/003 scripts
don't expect). Two separate startscripts also make it trivially clear
at the script-file level which mode a given reproduction recipe is
using — no invisible runtime flags.

**Alternatives considered**:

- *Parameterise `minimal.startscript` with environment-variable
  substitution*: rejected. Every existing 003 script treats that
  file as a static input; adding parameterisation would require
  auditing every caller. Two files is simpler.
- *Only run cheats-off and record `give_me` as permanently
  `blocked`*: rejected. Fails the spec edge case's "record both
  outcomes" rule and loses the positive-proof-of-dispatch evidence
  for cheats-on.
- *Enable cheats at runtime via the `CheatInterface` callback*:
  rejected. That's an out-of-spec path (not how BAR competitive
  matches are configured), produces evidence whose engine-side
  semantics diverge from a real cheats match, and requires code
  changes the audit-only feature is forbidden from making.

---

## 5. Def-id stability policy

**Decision**: The audit's primary def-id resolution path is
**run-time name resolution** via
`tests/headless/audit/def-id-resolver.py`, which:

1. Opens a `Hello` against the running engine.
2. Parses `HelloResponse.unit_defs[]`.
3. Returns the `def_id` matching a `(name, faction)` tuple.
4. Fails hard (non-zero exit, stderr message) if the name is not
   present in the response.

Reproduction recipes pass names (e.g., `armcom`, `armlab`,
`armflash`, `corcom`, `corrad`), never integer def-ids. Names are
stable across BAR-rapid gametypes within the same major BAR version;
def-ids are not (report 2 §3, `def_id=36 → def_id=370` between
`test-29979` and `test-29926`).

**Fallback**: if a reproduction recipe must use an integer def-id
(e.g., because the name is ambiguous or the arm's proto input takes
the integer), the row records the gametype it was run against and
notes the def-id is gametype-specific. The audit's row schema has a
`gametype_pin` column for this.

**Rationale**: FR-006 allows either strategy. Run-time resolution is
more robust across BAR-rapid drift (addresses the spec edge case
"BAR rapid-pool drift"). It also matches the `def-id-resolver.py`
helper's single-file deployment — one script, every recipe uses it.
The fallback exists because some proto arms (`build_unit` is the
main one) take the def-id as the payload; if the name resolution
fails we don't paper over it, we record the gametype.

**Alternatives considered**:

- *Hard-code def-ids in every recipe*: rejected. Breaks
  reproducibility across gametypes (spec edge case) and fails FR-006.
- *Commit a static def-id table to `data/config/`*: rejected.
  Gametypes ship on BAR-rapid at a cadence the V3 repo can't track.
  The table would rot between commits. Run-time resolution is free
  (one Hello RPC, <1 second).
- *Resolve def-ids only once per audit run and cache*: deferred —
  profiling of the initial audit run will reveal whether resolution
  cost dominates recipe runtime. If so, add a one-session cache in
  `def-id-resolver.py`; if not, keep the cache out.

---

## 6. Audit deliverable directory

**Decision**: Create a new top-level `audit/` directory housing
`command-audit.md`, `hypothesis-plan.md`, `v2-v3-ledger.md`, and
`README.md`. The directory is first-class (on par with `docs/` and
`reports/`), tracked in git, and the spec's acceptance scenarios
(US1, US2, US3 — "a reviewer can open `audit/command-audit.md`")
reference the path directly.

**Rationale**: The spec names the paths unambiguously:
`audit/command-audit.md` (US1 independent test), `audit/v2-v3-ledger.md`
(US3 acceptance). Co-locating the three deliverables in one
directory makes the "open any row, follow the citations" workflow
(US1 #2, US3 #2) single-directory. `docs/` is reserved for
design/architecture docs; `reports/` is reserved for live-run
narrative reports. `audit/` is the third — an evidence + findings
tree. The directory is committed (unlike `build/reports/`) because
the deliverables are the feature; the build outputs they cite are
the gitignored reproduction products.

**Alternatives considered**:

- *Put the audit under `docs/audit/`*: rejected. `docs/` is for
  design-intent documents, and reviewers looking for architecture
  guidance shouldn't trip over a 74-row table. Separate tree
  matches reader-intent separation.
- *Put the audit under `reports/004/`*: rejected. Reports are
  point-in-time narrative artifacts; the audit is a durable
  classification artifact that will be updated as verifiers are
  added. It deserves its own subtree.
- *Keep the audit entirely in `specs/004-gateway-command-audit/`*:
  rejected. The audit is not a spec artifact — `spec.md`, `plan.md`,
  `tasks.md`, and the Phase-0/1 outputs are. The audit is the
  *product* the feature ships, and products don't live under `specs/`.

---

## 7. Reproducibility window + stability bucketing

**Decision**: `tests/headless/audit/repro-stability.sh` runs the full
74-row evidence collection twice against the same engine pin and the
same gametype pin, with the same game seed if the startscript pins
it. Between runs it does a hard engine restart (kill + restart,
clean session dir). It then compares each row's outcome bucket
across the two runs. A row is **stable** if both runs produced the
same bucket. A row is **flipping** if buckets differ across the two
runs.

The script asserts:
- **≥ 90% bucket stability** across all 74 rows (SC-008's explicit
  threshold).
- The flipping rows are named in the script's stdout, so the audit
  can cite them in a "non-determinism notes" section of
  `command-audit.md` with hypothesis class (likely
  `phase1_reissuance` — ambient AI choices differ between seeds).

**Rationale**: SC-008 says "Re-running the audit's evidence-collection
step against the same engine pin and gametype produces the same
outcome bucket for at least 90% of rows." Two runs is the minimum
statistically honest evaluation — one-run "stability" is not a
measure. Two runs bounds the stability measurement cost (SC-003's
10-minute-per-test budget means two full audit runs fit within a
half-day slot on the self-hosted runner). Five runs (matching
003's reproducibility check) is not justified by SC-008 and would
blow the wall-clock budget; the 90% threshold is a per-pair
property, not a population-variance one.

**Alternatives considered**:

- *Five-run reproducibility like 003*: rejected. SC-008 asks for
  pair stability, not digest equality, so five runs is
  over-provisioned and wall-clock-expensive. If a future audit
  expansion wants digest-level stability it can add a separate
  script.
- *Single-run with engine-seed pinning and assume determinism*:
  rejected. BARb ambient AI RNG is not 100% seed-determinate
  (micro-decisions vary with wall-clock timing), so single-run
  would falsely claim stability the spec doesn't have.
- *Run the stability check in CI on every PR*: deferred. Gating
  PR merges on a 2× audit run is too expensive; the stability
  check runs as a weekly post-merge job (or manually) and its
  findings update `audit/command-audit.md`'s non-determinism
  notes.

---

## 8. Phase-2 smoke-run integration

**Decision**: `tests/headless/audit/phase2-macro-chain.sh` is a new
script that **does not replace** the existing
`tests/headless/phase2-smoke.sh`. The existing script validates that
the gateway boots cleanly with `enable_builtin=false` (a lifecycle
test). The new script validates that the 4-step macro chain from
report 1 §4 produces the same or different outcomes under Phase-2
vs Phase-1 (a behavioral test).

The new script:
1. Sources the same engine/gateway launch helpers as
   `phase2-smoke.sh` (via `tests/headless/_launch.sh`).
2. Overrides the `grpc.json` with `enable_builtin=false` (passed
   through config, not a source edit).
3. Dispatches the exact 4-step chain documented in
   `reports/003-macro-build-live-run.md` §4 (commander builds lab,
   lab builds mobile, mobile moves, mobile attacks).
4. Emits a per-step PASS/FAIL table to
   `reports/004-phase2-smoke.md` (FR-008, SC-006).
5. Records the outcome of step 4 (MoveUnit-on-factory-produce —
   the currently-failing case in Phase 1). If Phase-2 step 4 passes,
   hypothesis `phase1_reissuance` is confirmed for `move_unit`; if
   it fails, the dispatcher is itself suspect and a follow-up
   investigation is triggered.

**Rationale**: The existing `phase2-smoke.sh` proves plumbing; the
new script proves behavior. Keeping them separate means a future
plumbing regression is diagnosable independently from a behavioral
regression. Extending (rather than replacing) `phase2-smoke.sh`
also preserves its role as a fast pre-flight check.

**Alternatives considered**:

- *Overload `phase2-smoke.sh` with the 4-step chain*: rejected. The
  existing script is a short lifecycle test (boots in ~15s); adding
  a 4-step chain runs it >2 minutes and breaks its fast-feedback
  role.
- *Produce the Phase-2 report as part of the Python macro driver*:
  rejected. The driver targets the 66-row coverage sweep; adding
  an optional "one chain" mode mixes concerns. A dedicated Bash
  script matches 003's convention (e.g., `behavioral-move.sh`,
  `behavioral-build.sh` are per-arm anchors, not macro-driver
  modes).

---

## Carry-forward (not re-researched here)

The following were settled in 001/002/003 research.md artifacts and
continue to hold. They are re-asserted here as known inputs to the
Phase 1 artifact design:

- **Engine pin**: `recoil_2025.06.19` (003 research §1, spec
  Assumptions).
- **Gametype pin**: `test-29926` from
  `tests/headless/scripts/minimal.startscript` (commit `d18b4c34`
  bumped from `test-29979`; per report 2 §3 the pin change
  shifted def-ids — reinforces §5's name-based resolution decision).
- **Registry contract**: reuse 003's `BehavioralTestCase`,
  `VerifyPredicate`, `VerificationOutcome` (spec Assumptions). New
  fields added to `BehavioralTestCase` in 004 (`audit_row_id`,
  `audit_bucket_hint`, `hypothesis_ids`) are additive and do not
  affect 003's validation (registry import-time validation still
  passes).
- **Snapshot builder**: 003 shipped the `under_construction` +
  `build_progress` wire fix (`reports/003-macro-build-live-run.md`
  §2). The audit consumes this already-working surface.
- **Authentication + token file**: 001's `x-highbar-ai-token`
  mechanism at `$writeDir/highbar.token` mode 0600. The Hello-RPC
  audit row exercises the token-file race (spec edge case) as a
  cold-start test; no implementation changes needed.

---

## Phase-0 exit criteria

All NEEDS CLARIFICATION tags from the plan's Technical Context are
resolved:

- ✓ V2 source-of-truth path (§1)
- ✓ Outcome-bucket semantics (§2)
- ✓ Hypothesis-class vocabulary (§3)
- ✓ Cheats-mode variant (§4)
- ✓ Def-id resolution policy (§5)
- ✓ Audit deliverable directory (§6)
- ✓ Reproducibility window (§7)
- ✓ Phase-2 smoke-run integration (§8)

Proceed to Phase 1 artifact design (data-model, contracts, quickstart).

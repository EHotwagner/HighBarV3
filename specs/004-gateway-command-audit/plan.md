# Implementation Plan: Gateway Command Audit

**Branch**: `004-gateway-command-audit` | **Date**: 2026-04-22 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/004-gateway-command-audit/spec.md`

## Summary

003 shipped the snapshot-tick + macro-driver framework and landed four
wired verifiers (`build_unit`, `move_unit`, `attack`, `self_destruct`).
Live-run reports 1 and 2 proved end-to-end dispatch for two additional
construction arms but exposed that **39 unit arms** remain registered
as `verified="false" / error="effect_not_observed"` (see
`clients/python/highbar_client/behavioral_coverage/registry.py`
lines 320-352) and **~21 arms** are classified `verified="na"`
(channel-C Lua, channel-B queries, team-global, cheats-gated) without
any positive proof of end-to-end behavior.

This feature is a **documentation + evidence-collection** feature, not a
transport or protocol feature. It produces three authoritative
artifacts plus the harness scripts that reproduce them:

1. **`audit/command-audit.md`** — one row per AICommand arm (66) and
   per RPC (8), each row carrying an outcome bucket, V3 dispatcher
   citation, evidence excerpt, and — for `blocked`/`broken` rows — a
   falsifiable hypothesis with a named test.
2. **`audit/hypothesis-plan.md`** — one entry per unverified arm,
   each entry naming ranked candidate hypotheses and the test that
   distinguishes them.
3. **`audit/v2-v3-ledger.md`** — one row per V2 pathology (drawn from
   `/home/developer/projects/HighBarV2/docs/known-issues.md` and
   `/home/developer/projects/HighBarV2/reports/017-fix-client-socket-hang.md`,
   per FR-009 — the spec text cites `reports/known-issues.md` but
   the file actually lives at `docs/known-issues.md`; see research.md
   §1), each row citing the V3 fix's source location and the
   audit-table row that demonstrates the fix at runtime.

The audit extends the 003 registry rather than replacing it, reusing
the existing `BehavioralTestCase` / `VerifyPredicate` /
`VerificationOutcome` types under
`clients/python/highbar_client/behavioral_coverage/` (spec
Assumptions). Evidence collection runs through the existing macro
driver plus a small `tests/headless/audit/` harness that invokes it
with per-arm or per-RPC configurations.

The feature is deliberately narrow on code changes: **no new proto
fields, no new RPCs, no new C++ modules, no wiring of additional
snapshot-diff verifiers beyond what the audit itself needs to classify
a row.** Expanding verifier coverage and fixing any defects the audit
identifies are explicit out-of-scope items (spec Assumptions) and
become their own follow-up features informed by this audit's
hypothesis plan.

Technical approach continues to track
[`docs/architecture.md`](../../docs/architecture.md). The four
behavioral sections consulted are:

- **§Context** (V2 pathology enumeration — enumerates "lifecycle
  hangs, event loss, framing bugs" that the V2/V3 ledger cross-walks
  with cited V2 source).
- **§Module fate (phased)** (Phase-1 vs Phase-2 definition — the
  audit's dispatcher-only smoke run exercises `enable_builtin=false`
  per User Story 4).
- **§State model / §Threading** (confirms why the separate
  `InvokeCallback` unary RPC and separate `StreamState` server-stream
  eliminate V2's multiplexing race by construction — see V2/V3 ledger
  row for "callback/frame interleaving").
- **§Critical pitfalls** (single-AI lockout, token-file race — each
  becomes an audit row on the RPC side per spec edge cases).

## Technical Context

**Language/Version**: **Python 3.11+** (extends
`clients/python/highbar_client/behavioral_coverage/`). **Markdown**
for the three audit artifacts. **Bash** for the reproduction
harness scripts (existing `tests/headless/` convention). No C++ or
F# changes in this feature. No proto changes.

**Primary Dependencies**: inherited from 003 — `grpcio` /
`grpcio-tools` for the Python macro driver, `spring-headless` pin
`recoil_2025.06.19` (`data/config/spring-headless.pin`) for the
live engine, the 003-landed
`clients/python/highbar_client/behavioral_coverage/` package for
`BehavioralTestCase`, `VerifyPredicate`, `VerificationOutcome`,
`BootstrapPlan`, and the canonical CSV + digest serialiser. One new
optional dependency possibility: if any new verify-predicate needs
log-line parsing from `engine.infolog`, it uses Python `re` (stdlib).
No new pip deps expected.

**Storage**: **filesystem only**. Audit artifacts land in two
tracked locations and one build-output location:

- **Tracked**: `audit/command-audit.md`, `audit/hypothesis-plan.md`,
  `audit/v2-v3-ledger.md` (new top-level `audit/` directory, checked
  in — these are the audit deliverables).
- **Tracked**: `tests/headless/audit/` harness scripts (checked in
  per FR-012 — reproduction MUST NOT depend on ad-hoc `/tmp/*.py`).
- **Build output**: `build/reports/004-*.{md,csv,log}` — reproduced
  evidence files cited by the audit rows. Gitignored per the 003
  convention (`reports/003-macro-build-live-run.md` §7 and SC-007).

No persistent state on the plugin side — the feature is audit-only.

**Testing**: no unit tests, no new integration tests. The audit is
validated by its own reproduction harness:

- Every `verified` audit row runs through `tests/headless/audit/repro.sh
  <arm>` and re-produces the cited evidence against a live engine
  (acceptance scenario US1 #2, FR-005, SC-004).
- Every `blocked`/`broken` row's hypothesis test runs through
  `tests/headless/audit/hypothesis.sh <arm> <hypothesis-id>` and
  produces a binary confirmed/falsified outcome (acceptance scenario
  US2 #2, FR-003, SC-003).
- The Phase-2 smoke run (US4) runs through
  `tests/headless/audit/phase2-macro-chain.sh` and produces a
  4-step PASS/FAIL table (FR-008, SC-006). This extends the existing
  `tests/headless/phase2-smoke.sh` from 003 rather than replacing
  it.
- The audit's 90% reproducibility criterion (SC-008) is exercised by
  `tests/headless/audit/repro-stability.sh`, which re-runs the audit
  twice against the same engine pin + gametype and diffs outcome
  buckets; the non-determinism budget (10%) matches the spec.

**Target Platform**: unchanged — Linux x86_64 Ubuntu 22.04 reference
host, `bar-engine` self-hosted runner for headless stages, engine pin
`recoil_2025.06.19` (spec Assumptions). Reviewers reproducing the
audit need the same engine and BAR rapid pool sufficient to resolve
the gametype the evidence was collected against.

**Project Type**: unchanged — forked C++ game plugin plus two client
libraries. This feature adds one top-level documentation tree
(`audit/`) and one new headless subtree (`tests/headless/audit/`).
No source-code project structure shifts.

**Performance Goals**:

- **SC-003** — each hypothesis test completes in **≤ 10 minutes** of
  wall-clock against a live headless engine (bounds the rate of
  follow-up iteration).
- **SC-004** — a reviewer picking any `verified` row reproduces its
  evidence in **≤ 15 minutes** (includes engine boot time).
- **SC-006** — the Phase-2 smoke run completes the report-1 §4
  4-step chain within the existing 5-minute Phase-1 macro-driver
  budget (no regression vs Phase 1).

All existing 001/002/003 latency budgets continue to hold: p99
round-trip ≤ 500µs UDS, ≤ 1.5ms loopback TCP, ≤ 5% framerate
regression with four observers, FR-001 snapshot cadence ≥ 25
snapshots/30s. This feature measures, it does not alter.

**Constraints**: the audit inherits all 001/002/003 constraints —
engine-thread supremacy for all mutations, bounded queues,
schema-version strict equality. The feature-specific constraints are:

- **Reproducibility of recorded evidence.** Every `verified` row
  cites specific evidence (snapshot diff excerpt, log line). FR-006
  forbids hard-coded def-ids in reproduction recipes unless the
  recipe also records the gametype it was run against — because
  BAR-rapid def-ids drift between gametypes (report 2 §3,
  `def_id=36` vs `def_id=370` for the same commander class between
  `test-29979` and `test-29926`). The audit resolves this either by
  parsing `HelloResponse.unit_defs` at run time and name-matching
  (preferred) or by committing the gametype pin inline with the row.
- **Scripts live under the repo tree.** FR-012 and SC-007 both
  forbid ad-hoc `/tmp/*.py` harnesses. Every reproduction recipe
  points at a checked-in `tests/headless/audit/*.sh` or
  `clients/python/highbar_client/behavioral_coverage/` entry point.
- **Phase-1 default.** FR-013 requires every reproduction recipe to
  run in Phase-1 mode (built-in BARb AI active) by default, matching
  003's design constraint. Phase-2 recipes (US4) are explicitly
  flagged.
- **Dispatcher correctness ≠ engine outcome.** FR-011 is the single
  most important rule in this feature: a row whose dispatcher is
  correct but whose engine outcome is "no observable effect" is
  `blocked` or `dispatched-only`, not `broken`. `broken` is reserved
  for genuine dispatcher defects (e.g., the arm handler returns
  success without invoking the right `CCircuitUnit::Cmd*` method).
  This discipline is the whole point of the audit — it keeps the
  hypothesis plan focused on actionable follow-ups.
- **Cross-team def-id silent rejection.** Spec edge case: the
  gateway acks `BuildUnit` for a Cortex def issued by an Armada
  commander, but no `own_units[]` entry appears because the engine
  silently rejects cross-team defs. The audit records this as
  "dispatcher correct, engine silently rejects" — distinct from a
  dispatcher bug. Every build/unit-targeting row's reproduction
  recipe resolves the def-id from the *actor's* faction table.

**Scale/Scope**: scope is finite and bounded by the spec's
deliverable list:

- **74 audit rows** (66 AICommand arms in
  `proto/highbar/commands.proto` per FR-001 / SC-001 + 8 RPCs in
  `proto/highbar/service.proto` — Hello, StreamState,
  SubmitCommands, InvokeCallback, Save, Load, GetRuntimeCounters,
  RequestSnapshot).
- **≥ 43 hypothesis-plan entries** (39 unverified unit arms per
  registry lines 320-352 + the 4 verified-but-Phase-1-fragile arms
  identified in report 1 §4).
- **≥ 6 V2/V3 ledger rows** (the specific pathologies named in
  FR-010, each cross-walked to the V3 source location or a
  hypothesis-plan entry).
- **1 Phase-2 smoke-run report** (`build/reports/004-phase2-smoke.md`,
  per FR-008).
- **One new `tests/headless/audit/` directory** with a small number
  of harness scripts (reproduction, hypothesis, stability,
  phase-2 chain). No other top-level structural growth.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

Constitution version: **1.0.0** (`.specify/memory/constitution.md`).

| # | Principle | Plan status | Evidence / notes |
|---|---|---|---|
| I | Upstream Fork Discipline | **PASS** | Zero edits to upstream-shared CircuitAI files. All new files land under V3-reserved subtrees: `audit/` (new top-level documentation tree, unambiguously V3), `tests/headless/audit/` (extends the existing 002/003 test subtree), and the existing `clients/python/highbar_client/behavioral_coverage/` Python package (inherited from 003's FR-013 — extend, don't fork). No C++ code changes. No CMake or build-script edits. Upstream merge cost for this feature is **zero** (all new files are in paths upstream never touches). |
| II | Engine-Thread Supremacy (NON-NEGOTIABLE) | **PASS** | Vacuously satisfied — the feature adds no engine-thread code. All new code runs on the Python driver side or as Bash wrappers around the 003-era macro driver. All plugin-side interactions go through the existing `SubmitCommands` → `DrainCommandQueue` engine-thread path and the existing `RequestSnapshot` RPC (both landed in 003 and already engine-thread-correct). The audit's Phase-2 smoke run exercises `enable_builtin=false` but that flag's only effect is upstream-shared `CCircuitAI::Init()` behavior — already audited by 001/002 and not touched here. |
| III | Proto-First Contracts | **PASS** | **Zero proto changes.** The audit is a documentation + evidence feature — it classifies the *existing* schema's arms, it does not add fields or methods. Every audit row's dispatcher citation points at existing `src/circuit/grpc/CommandDispatch.cpp` code; every RPC row points at existing `src/circuit/grpc/HighBarService.cpp` handlers. Schema version stays `1.0.0`. No regenerated stubs. |
| IV | Phased Externalization | **PASS** | The audit respects the existing phase boundaries: FR-013 mandates Phase-1 default for all reproduction recipes (matching 003), and Phase-2 is only exercised for the dispatcher-only smoke run (US4) per the architecture doc §Module fate. The smoke run does **not** require Phase-2 economy/tech-progression logic — it exercises the same 4-step chain with `enable_builtin=false` and measures whether step 4 (the currently-failing MoveUnit-on-factory-produce case from report 1 §4) resolves when the ambient BARb AI is absent. Phase 3 remains out of scope. The audit's findings may inform the Phase-1 → Phase-2 gating criterion in future, but this feature does not change the gate. |
| V | Latency Budget as Shipping Gate | **PASS** | The audit measures but does not modify transport or serialisation code. All 001/002/003 latency benches remain the authoritative gate. The feature does impose *its own* wall-clock budgets (SC-003, SC-004, SC-006) for reproduction and hypothesis-test iteration, but those are *audit ergonomic* budgets — they bound how long a reviewer spends reproducing evidence, not the engine's latency envelope. The Phase-2 smoke run (FR-008) re-uses the existing report-1 §4 4-step chain, which was already produced within a 5-minute budget in Phase 1; running it with `enable_builtin=false` does not add any new wire traffic or serialisation cost. No microbench changes. |

**License & Compliance**: PASS. No new third-party dependencies. The
audit artifacts are Markdown text and the harness is Bash + Python
stdlib — all GPL-2.0-compatible.

**Complexity Tracking**: *none expected*. This is a documentation +
evidence-collection feature riding on top of already-landed plumbing.
The only non-trivial complexity is the enumerative scale (74 rows + 43
hypothesis entries + ≥6 ledger rows), and that is a labor cost, not
an architectural one. No design deviates from the architecture doc or
a principle at plan-authoring time. If the repro-stability criterion
(SC-008) turns out to exceed its 90% floor — i.e., non-determinism in
BARb ambient AI produces more than 10% bucket-flipping — that becomes
an audit finding in its own right (spec SC-008 rationale), not a
plan-level complexity deviation.

**Initial gate result**: **PROCEED TO PHASE 0.**

**Post-design re-evaluation (to be filled after Phase 1 artifacts
land)**: deferred — the plan command completes with artifacts on
disk; the re-evaluation sentence is written by the tasks/implement
commands as the phase boundary is actually crossed. At plan-authoring
time no post-design delta is known.

## Project Structure

### Documentation (this feature)

```text
specs/004-gateway-command-audit/
├── plan.md              # This file (/speckit.plan output)
├── research.md          # Phase 0 output — outcome-bucket taxonomy, V2 source-of-truth path correction, hypothesis-class inventory, cheats-mode variant decision, def-id stability policy, V3 deliverable directory choice
├── data-model.md        # Phase 1 output — AuditRow, HypothesisPlanEntry, V2V3LedgerRow, ReproductionRecipe, OutcomeBucket (formalized)
├── quickstart.md        # Phase 1 output — how a reviewer reproduces (a) any verified row, (b) any hypothesis test, (c) the Phase-2 smoke run, against the reference host
├── contracts/           # Phase 1 output — audit-row markdown schema, hypothesis-entry schema, V2/V3-ledger schema, repro-recipe format
├── checklists/          # Existing (spec-time output)
└── tasks.md             # Phase 2 output (/speckit.tasks — not created here)
```

### Source Code (repository root)

This feature creates **one new top-level documentation directory**
(`audit/`) and **one new `tests/headless/` subdirectory**
(`tests/headless/audit/`). Every other change extends an existing
file or adds inside an already-existing subtree. No code-generation
changes, no proto edits, no CMake edits.

The list below names every file this feature edits or creates; lines
are from the 003-landed tree as surveyed on 2026-04-22 (commit
`d18b4c34`).

```text
# Audit deliverables (new top-level tree — the feature's primary artifact)
audit/command-audit.md                           # NEW — 74 rows: 66 AICommand arms (FR-001)
                                                 #        + 8 RPCs (Hello, StreamState,
                                                 #        SubmitCommands, InvokeCallback, Save,
                                                 #        Load, GetRuntimeCounters,
                                                 #        RequestSnapshot). Per contracts/
                                                 #        audit-row.md row schema. Each row
                                                 #        cites V3 source file:line, cites
                                                 #        evidence, names hypothesis + test
                                                 #        for blocked/broken (FR-002, FR-003,
                                                 #        FR-004, FR-014).
audit/hypothesis-plan.md                         # NEW — ≥ 43 entries: one per arm currently
                                                 #        registered verified="false" or
                                                 #        verified="true" only-by-ack, per
                                                 #        contracts/hypothesis-entry.md. Each
                                                 #        entry lists ranked candidate
                                                 #        hypotheses with predicted-confirmed
                                                 #        and predicted-falsified evidence
                                                 #        shapes, and the test that
                                                 #        distinguishes them (FR-007, US2).
audit/v2-v3-ledger.md                            # NEW — ≥ 6 rows covering FR-010 pathologies
                                                 #        explicitly, plus any additional
                                                 #        pathology rows from V2's
                                                 #        docs/known-issues.md (see research.md
                                                 #        §1 for the path correction) and
                                                 #        017-fix-client-socket-hang.md.
                                                 #        Per contracts/v2-v3-ledger.md.
audit/README.md                                  # NEW — one-paragraph index; points at the
                                                 #        three artifacts above, the harness,
                                                 #        and the Phase-2 smoke-run report.

# Reproduction + hypothesis + Phase-2 harness (FR-005, FR-012, SC-007)
tests/headless/audit/repro.sh                    # NEW — reproduces one verified row's
                                                 #        evidence. Usage:
                                                 #          repro.sh <arm_name> [gametype_pin]
                                                 #        Wraps the 003 macro driver with the
                                                 #        registry filter set to one arm,
                                                 #        writes evidence to build/reports/
                                                 #        004-repro-<arm>.md.
tests/headless/audit/hypothesis.sh               # NEW — runs one hypothesis test for one
                                                 #        unverified arm. Usage:
                                                 #          hypothesis.sh <arm> <hyp-id>
                                                 #        Produces a binary confirmed/
                                                 #        falsified PASS/FAIL and a diff
                                                 #        excerpt matching the entry's
                                                 #        predicted-confirmed evidence shape.
tests/headless/audit/phase2-macro-chain.sh       # NEW — Phase-2 dispatcher-only smoke run
                                                 #        (FR-008, US4). Re-executes the
                                                 #        report-1 §4 4-step chain with
                                                 #        enable_builtin=false; produces a
                                                 #        per-step PASS/FAIL table. Extends
                                                 #        the existing Phase-2 smoke script
                                                 #        rather than replacing it.
tests/headless/audit/repro-stability.sh          # NEW — SC-008 check: runs the full audit's
                                                 #        evidence collection twice against
                                                 #        the same engine pin + gametype and
                                                 #        diffs outcome buckets; asserts
                                                 #        ≥ 90% bucket stability.
tests/headless/audit/def-id-resolver.py          # NEW — shared helper: reads HelloResponse
                                                 #        unit_defs from a live Hello and
                                                 #        returns the def_id for a name+
                                                 #        faction tuple (FR-006). Imported by
                                                 #        repro.sh / hypothesis.sh to avoid
                                                 #        hardcoded def-ids.

# Python behavioral-coverage extensions (reuse, not rewrite — spec Assumptions)
clients/python/highbar_client/behavioral_coverage/registry.py           # EDIT — per-row light touch only:
                                                                       #        add `audit_row_id`,
                                                                       #        `audit_bucket_hint`, and
                                                                       #        `hypothesis_ids` optional
                                                                       #        attributes on each
                                                                       #        BehavioralTestCase. No
                                                                       #        change to the 66-row
                                                                       #        enumeration or the existing
                                                                       #        verify_predicate wiring —
                                                                       #        data only.
clients/python/highbar_client/behavioral_coverage/audit_report.py       # NEW — generator: reads the 003
                                                                       #        coverage CSV + the
                                                                       #        registry metadata and
                                                                       #        emits the command-audit.md
                                                                       #        row block. Not a replacement
                                                                       #        for report.py; it consumes
                                                                       #        report.py output.

# Cheats-enabled startscript variant (spec Assumptions — for give_me / give_me_new_unit)
tests/headless/scripts/cheats.startscript         # NEW — copy of minimal.startscript with
                                                 #        `Cheats=1` and team configured to
                                                 #        allow the dispatcher to issue
                                                 #        `give_me` against a valid target.
                                                 #        Documented in docs/architecture.md
                                                 #        pin as a test-only variant.

# Phase-2 smoke-run report (FR-008 artifact)
build/reports/004-phase2-smoke.md                # NEW — companion to reports/003-macro-
                                                 #        build-live-run.md and
                                                 #        003-macro-build-live-run-2.md.
                                                 #        Records the enable_builtin=false
                                                 #        Phase-2 run of the report-1 §4
                                                 #        4-step chain with per-step
                                                 #        PASS/FAIL. Written under the
                                                 #        build-output convention used by
                                                 #        the rest of the audit artifacts.

# Docs updates
docs/architecture.md                             # EDIT (light) — one paragraph in §Context
                                                 #        linking to audit/v2-v3-ledger.md
                                                 #        as the authoritative V2→V3 problem
                                                 #        map. One sentence in §Module fate
                                                 #        referencing build/reports/
                                                 #        004-phase2-smoke.md as the
                                                 #        dispatcher-only Phase-2 evidence.
                                                 #        No design changes.
CLAUDE.md                                        # EDIT — update the active-feature-plan
                                                 #        pointer inside the
                                                 #        <!-- SPECKIT START/END --> block
                                                 #        to specs/004-gateway-command-audit/
                                                 #        plan.md.
.gitignore                                       # EDIT — add /build/reports/004-*.md and
                                                 #        /build/reports/004-*.log to the
                                                 #        gitignored artifact conventions
                                                 #        (SC-007 build-output rule).
```

**Structure Decision**: This feature creates one new top-level
documentation tree (`audit/`) — this is intentional, audit
deliverables are first-class project artifacts on par with `docs/`
and `reports/`, and the spec names them explicitly (`audit/command-audit.md`,
`audit/v2-v3-ledger.md`). One new test subdirectory
(`tests/headless/audit/`) houses the reproduction + hypothesis +
Phase-2 harness scripts, keeping them adjacent to the existing
headless suite and satisfying FR-012's "live under the repo tree" rule
(and SC-007's "not in /tmp" rule). Every other change extends an
existing file or adds to an already-existing subtree, preserving
001/002/003's fork-discipline shape (Constitution I).

## Complexity Tracking

*No Constitution Check violations at plan-authoring time.*

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| *(none)*  | *(n/a)*    | *(n/a)*                             |

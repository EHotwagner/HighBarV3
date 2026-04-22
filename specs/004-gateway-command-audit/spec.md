# Feature Specification: Gateway Command Audit

**Feature Branch**: `004-gateway-command-audit`
**Created**: 2026-04-22
**Status**: Draft
**Input**: User description: "@reports/ read those reports. develop a plan to test all commands. develop and test hypothesis what works and why. refer to https://github.com/rlcevg/CircuitAI/tree/0ef36267633d6c1b2f6408a8d8a59fff38745dc3 for research. what were the problems with highbarv2 and can/did we fix them?"

## Overview

The 003 feature established that the gateway's snapshot pipeline carries
build-state correctly and that ~4 of 66 AICommand arms have wired
verifiers (`build_unit`, `move_unit`, `attack`, `self_destruct`). Live-run
report 1 (2026-04-21) further proved end-to-end dispatch for two more
construction arms via a bespoke macro driver, but exposed that 39 unit
arms remain in a `verified="false" / error="effect_not_observed"` state —
dispatched with no snapshot verifier wired — and that ~21 arms are
classified `verified="na"` (channel-C Lua, channel-B queries,
team-global, cheats-gated) without any positive proof of
end-to-end behavior.

This feature audits **every** RPC and AICommand arm against a live
engine, classifies each into a small evidence-based outcome bucket
(verified / unobservable-but-proven-dispatched / blocked-by-known-cause /
broken), and pairs every "broken" or "blocked" finding to a specific,
testable hypothesis. The audit's secondary deliverable is a
side-by-side V2 → V3 problem ledger that closes the loop on the V2
pathologies enumerated in `docs/architecture.md` Context section
(lifecycle hangs, event loss, framing bugs).

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Audit table covering all 66 AICommand arms (Priority: P1)

A maintainer needs a single authoritative document that, for every AICommand
arm in `commands.proto`, states (a) the current verification status, (b)
the concrete evidence the audit collected (snapshot-diff excerpt, ack
return code, engine log line, or the explicit "not wire-observable"
marker), (c) the hypothesis explaining the result, and (d) what test
would falsify the hypothesis.

**Why this priority**: Without this artifact, all downstream work
(closing dispatch gaps, expanding verifiers, deciding what to ship in
Phase 2) is opinion-driven. The audit table is the foundational
evidence base. It is also the only deliverable that directly answers
the user's stated question ("what works and why").

**Independent Test**: A reviewer can open `audit/command-audit.md`,
pick any AICommand row at random, and reproduce the cited evidence by
running the linked reproduction recipe (a shell command that invokes
the macro driver or a bespoke harness against a fresh headless run)
and confirming the recorded outcome matches.

**Acceptance Scenarios**:

1. **Given** the audit table exists, **When** a reviewer counts rows,
   **Then** there is exactly one row per AICommand arm enumerated in
   `proto/highbar/commands.proto` (currently 66) plus one row per
   service RPC (Hello, StreamState, SubmitCommands, InvokeCallback,
   Save, Load, GetRuntimeCounters, RequestSnapshot).
2. **Given** any audit row classified `verified`, **When** the
   reviewer runs the row's reproduction recipe against a fresh
   headless engine, **Then** the recipe completes and the recorded
   evidence (snapshot-diff excerpt or engine log line) is produced.
3. **Given** any audit row classified `dispatched-only`, **When**
   the reviewer reads the row, **Then** the row cites the specific
   not-wire-observable reason the effect is not visible in the
   snapshot wire format (channel-C Lua, channel-B query, team-global
   state, drawer-only).
4. **Given** any audit row classified `blocked` or `broken`, **When**
   the reviewer reads the row, **Then** the row states a falsifiable
   hypothesis (e.g., "Phase-1 BARb re-issuance loop overrides our
   command on the next frame") and names a specific follow-up test
   that would either confirm the hypothesis or prove the dispatch
   itself broken.

---

### User Story 2 — Hypothesis-driven test plan for unverified arms (Priority: P1)

For each of the ~39 unit arms currently registered as
`error="effect_not_observed"` and the 4 verified-but-Phase-1-fragile
arms identified in live-run report 1 (notably `move_unit` on a
factory-produced unit), the audit produces a short, ranked hypothesis
list and a test that distinguishes them. The plan is the test, not the
prose: each hypothesis maps to a concrete invocation against a live
engine.

**Why this priority**: The user explicitly asked for hypothesis
testing, not just a snapshot of current state. The 003 macro driver
landed the verification framework but only wired four verifiers; a
maintainer staring at 39 untested arms cannot tell which of them are
trivially verifiable vs. genuinely Phase-1-blocked vs. dispatcher
bugs. Without this plan, the next iteration of verifier-wiring work
is uninformed.

**Independent Test**: A maintainer picks any unverified arm from the
plan, runs the test that the plan prescribes for the top-ranked
hypothesis, and the test produces a binary outcome (hypothesis
confirmed / falsified) with the predicted evidence shape.

**Acceptance Scenarios**:

1. **Given** the hypothesis plan exists, **When** a maintainer counts
   entries, **Then** every arm currently classified `verified="false"`
   or `verified="true"` (where "true" came only from dispatch ack,
   not snapshot-diff) has at least one hypothesis row.
2. **Given** any hypothesis row, **When** the maintainer reads it,
   **Then** it names: the hypothesis in one sentence; the test
   command that would distinguish it; the predicted snapshot-diff
   shape if confirmed; the predicted shape if falsified.
3. **Given** the plan's "Phase-1 ambient AI overrides external
   command" hypothesis class, **When** the maintainer reads it,
   **Then** it lists a specific reproducible test (e.g., the report-1
   §4 §Step 4 MoveUnit-on-factory-produce pattern) and the
   expected Phase-2 fallback test that confirms the dispatcher is
   correct even when Phase 1 hides it.

---

### User Story 3 — V2-vs-V3 problem ledger (Priority: P2)

A small ledger lists every concrete V2 transport/protocol/dispatch
pathology surfaced in V2's `reports/` and `CLAUDE.md`, and for each:
(a) names the V3 design or code change that addresses it, with file
citations; (b) states the audit evidence (from User Story 1) that
shows the V3 fix actually holds at runtime; (c) flags any V2 problem
that V3 has *not* yet addressed and recommends whether to add it to
the audit's hypothesis plan.

**Why this priority**: The user asked the question directly. It is
also the only deliverable that retroactively justifies the cost of the
V3 fork — without this ledger, V3's existence is asserted, not
demonstrated. P2 because it is a smaller artifact and depends on User
Story 1's evidence base.

**Independent Test**: A reviewer can open `audit/v2-v3-ledger.md`,
pick any V2 problem row, and confirm both the V3 source-code citation
(file:line) and the audit-table row that demonstrates the fix at
runtime.

**Acceptance Scenarios**:

1. **Given** the V2 ledger exists, **When** the reviewer counts rows,
   **Then** every concrete V2 problem documented in
   `/home/developer/projects/HighBarV2/docs/known-issues.md` and
   `/home/developer/projects/HighBarV2/reports/017-fix-client-socket-hang.md`
   has a row.
2. **Given** any "fixed in V3" row, **When** the reviewer reads it,
   **Then** it cites a V3 file:line (typically in
   `src/circuit/grpc/`) and references a specific audit-table row
   whose evidence demonstrates the runtime behavior is correct.
3. **Given** any "still open in V3" row, **When** the reviewer reads
   it, **Then** it either points at an existing audit-table
   hypothesis row, or recommends a new one with a one-sentence test.
4. **Given** the V2 problem "callback frame interleaving"
   (`/home/developer/projects/HighBarV2/docs/known-issues.md`
   lines 40-62), **When** the reviewer reads the corresponding
   V3 row, **Then** the row demonstrates that V3's separate
   `InvokeCallback` unary RPC and separate `StreamState` server-stream
   eliminate the multiplexing race by construction (cite
   `proto/highbar/service.proto` and the audit-table InvokeCallback
   row's evidence).

---

### User Story 4 — Phase-2 dispatcher-only smoke run (Priority: P3)

The audit produces one short live-run report (companion to the
existing reports 1 and 2) executed with `enable_builtin=false`
(Phase-2 mode per `docs/architecture.md` §"Module fate"). The smoke
run exercises the same 4-step macro chain from report 1 §4 plus an
arbitrary arm chosen from the unverified bucket, and confirms whether
removing the BARb ambient AI changes the outcome bucket for any arm.

**Why this priority**: Phase-2 is gated by `docs/architecture.md` as
out of scope for 003 because it requires the external client to
replace BARb's economy and tech-progression logic. But a *smoke* run
that just confirms "dispatcher works without internal AI" does not
require that — it just requires bringing up the gateway with the flag
flipped. The result is the cleanest possible attribution test for the
hypothesis "Phase-1 ambient AI re-issuance is what masks the
dispatcher."

**Independent Test**: A maintainer with the headless engine installed
runs `tests/headless/audit/phase2-macro-chain.sh`,
the harness reports per-step PASS/FAIL, and the report records
whether the previously-failing Step 4 MoveUnit now passes.

**Acceptance Scenarios**:

1. **Given** Phase-2 mode is enabled, **When** the macro driver runs
   the report-1 §4 4-step chain, **Then** the report records the
   per-step outcome.
2. **Given** the report records Step 4 PASS in Phase 2 (and Step 4
   FAIL in Phase 1 from report 1), **When** the audit cites this
   pair, **Then** the hypothesis "Phase-1 ambient AI overrides
   external MoveUnit" is confirmed; otherwise, the hypothesis is
   falsified and dispatcher correctness for `move_unit` becomes a
   live audit finding requiring its own follow-up.

---

### Edge Cases

- **Cross-team def-id rejection** (report 1 §4.3 Step 2): the gateway
  acks `BuildUnit` for a Cortex def issued by an Armada commander, but
  no `own_units[]` entry appears. The audit must record this as
  *dispatcher correct, engine silently rejects* — distinct from a
  dispatcher bug — and the audit's reproduction recipe must be robust
  to BAR's def-id table shifting between gametypes (per report 2 §3,
  `def_id=36 → def_id=370` between `test-29979` and `test-29926`).
- **Snapshot sampler races at high MaxSpeed** (report 2 §4):
  `behavioral-build.sh`'s `snap_at` returns the latest buffered
  snapshot when the engine outruns the sampler, producing trivially
  monotonic-equal sequences. Audit reproduction recipes must either
  use wall-clock-paced sampling or oldest-first iteration, and must
  document whichever choice they make.
- **BAR rapid-pool drift** (report 2 setup §2): the start-script's
  pinned gametype may not be in rapid at audit time; the audit's
  reproduction recipes must record the gametype they ran against and
  not require a specific pin to reproduce.
- **`set_figure_position` no-op** (CommandDispatch.cpp lines 595-603):
  the engine has no `Figure::SetPosition`; the dispatcher logs and
  returns success. The audit row for this arm must record the
  no-op as the *intended* behavior and cite the dispatcher comment.
- **Cheats-gated arms when cheats are off** (`give_me`,
  `give_me_new_unit`): the audit must run these against both
  cheats-enabled and cheats-disabled match configs and record both
  outcomes, since the registry's current "cheats_required" outcome
  is the cheats-disabled path only.
- **Save / Load**: the V2 ledger flags these as proxy-side TODOs
  (V2 `proxy/src/proxy.c:382, 391`). The audit row must determine
  whether V3's `Save`/`Load` are wired, stubbed, or proxied — and if
  stubbed, that is itself an audit finding rather than a fix.
- **Single-AI lockout**: per architecture, a second concurrent AI
  `SubmitCommands` returns `ALREADY_EXISTS`. The audit's RPC rows
  for `SubmitCommands` and `Hello` must include a deliberate
  duplicate-AI test that confirms the lockout fires.
- **Token-file race**: per architecture pitfall #4, AI clients poll
  the token file on startup. The audit's `Hello` row must include a
  cold-start test that proves the AI client's first `Hello` succeeds
  without manual coordination.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The audit MUST classify every AICommand arm enumerated
  in `proto/highbar/commands.proto` and every RPC enumerated in
  `proto/highbar/service.proto` into exactly one of these outcome
  buckets: `verified` (snapshot-diff or engine-log evidence proves
  the post-effect occurred); `dispatched-only` (gateway ack received,
  effect intentionally not wire-observable, with cited reason);
  `blocked` (dispatch correct but a documented external condition —
  Phase-1 ambient AI, cheats off, cross-team def — prevents the
  effect); `broken` (dispatch returns success but the engine does not
  perform the effect for an unexplained reason that the audit
  identifies as a defect).
- **FR-002**: Every audit row MUST cite the file path(s) and (where
  the citation is to a specific behavior, not a whole file) line
  number(s) of the V3 dispatch code that handles the arm. Rows for
  AICommand arms MUST cite a line range in `src/circuit/grpc/CommandDispatch.cpp`.
- **FR-003**: Every audit row classified `blocked` or `broken` MUST
  state the hypothesis explaining the outcome and name the
  reproducible test that would falsify the hypothesis. Hypotheses MUST
  be ranked when more than one applies.
- **FR-004**: Every audit row classified `verified` MUST cite either
  (a) a snapshot-diff excerpt of the same shape used in
  `reports/003-macro-build-live-run.md` §4.3, or (b) an engine log
  line excerpt with the engine pin recorded.
- **FR-005**: The audit MUST include reproduction recipes — runnable
  shell command lines — for every `verified` row, sufficient that a
  reviewer with `spring-headless recoil_2025.06.19` installed can
  re-execute the recipe and obtain the recorded evidence.
- **FR-006**: The audit's reproduction recipes MUST resolve def-ids
  at run time rather than hard-coding them, OR record the gametype
  they were run against and note the def-id values are not
  cross-gametype-stable (per report 2 §3, §5).
- **FR-007**: The hypothesis test plan MUST cover every arm currently
  registered as `verified="false" / error="effect_not_observed"` (per
  `clients/python/highbar_client/behavioral_coverage/registry.py`
  lines 320-352, currently 39 arms) and every arm currently
  registered with non-empty `error` other than `not_wire_observable`.
- **FR-008**: The audit MUST produce a Phase-2 smoke-run report that
  re-executes the report 1 §4 4-step macro chain with
  `enable_builtin=false` and records per-step outcomes.
- **FR-009**: The V2-vs-V3 ledger MUST contain one row per concrete
  V2 problem documented in `/home/developer/projects/HighBarV2/docs/known-issues.md`
  and `/home/developer/projects/HighBarV2/reports/017-fix-client-socket-hang.md`.
  Each row MUST cite the V2 source location, the V3 source location
  of the fix (or "not addressed"), and the audit-table row whose
  evidence demonstrates the fix at runtime.
- **FR-010**: The V2 ledger MUST address each of these specific V2
  pathologies by name:
  - Callback / Frame interleaving race.
  - Client `recvBytes` infinite loop on engine death (V2
    `Client.fs` lines 33-40).
  - Default 8 MB max message size insufficient for large maps.
  - Single-connection lockout with no auto-reconnect.
  - Frame-budget timeout and AI removal.
  - `Save` / `Load` proxy-side TODO stubs (V2
    `proxy/src/proxy.c:382, 391`).
- **FR-011**: The audit MUST distinguish *dispatcher correctness*
  from *engine outcome* for every arm. A row whose dispatcher is
  correct but whose engine outcome is "no observable effect" MUST
  NOT be classified `broken`; it MUST be classified `blocked` or
  `dispatched-only` with the reason cited.
- **FR-012**: The audit MUST be reproducible from a clean git
  checkout: a `tests/headless/audit/` directory (or equivalent) MUST
  contain the harness scripts the audit calls, and the audit's
  evidence-collection step MUST run from those scripts, not from
  `/tmp/*.py` ad-hoc files.
- **FR-013**: Reproduction recipes MUST run in Phase-1 mode by
  default (matching the design requirement of 003 — snapshot diffs
  must work with built-in AI active per `reports/003-macro-build-live-run.md`
  §1). Phase-2 recipes MUST be explicitly flagged.
- **FR-014**: For every arm classified `dispatched-only` because the
  effect is not wire-observable, the audit MUST cite the specific
  channel (channel-C Lua, channel-B query, team-global state,
  drawer-only) using the same vocabulary as
  `clients/python/highbar_client/behavioral_coverage/registry.py`.

### Key Entities

- **Audit Row**: one entry covering one RPC or one AICommand arm.
  Attributes: arm name; outcome bucket; dispatch-code citation
  (file:line); evidence (snapshot-diff excerpt / log line / "not
  wire-observable" marker); hypothesis (for `blocked`/`broken`);
  falsification test (for `blocked`/`broken`); reproduction recipe
  (for `verified`); engine-pin and gametype the evidence was
  collected against.
- **Hypothesis Plan Entry**: one entry per unverified arm.
  Attributes: arm name; ranked list of candidate hypotheses (each
  with predicted-confirmed and predicted-falsified evidence shapes);
  the specific test command that distinguishes them.
- **V2/V3 Ledger Row**: one entry per V2 pathology. Attributes: V2
  problem description; V2 source citation (file:line in
  `/home/developer/projects/HighBarV2/`); V3 status
  (fixed/partial/not-addressed); V3 source citation (when fixed);
  audit-row reference (which audit row demonstrates the runtime
  evidence for the fix); residual risk note.
- **Reproduction Recipe**: a shell command line plus its expected
  output excerpt, parameterized by engine pin and gametype, runnable
  on any host with `spring-headless recoil_2025.06.19` installed.
- **Outcome Bucket**: enumerated value, one of `verified`,
  `dispatched-only`, `blocked`, `broken`. Definitions in FR-001.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of AICommand arms in `commands.proto` and 100%
  of RPCs in `service.proto` have an audit row.
- **SC-002**: At least 50% of AICommand arms have an outcome bucket
  better than `broken` — i.e., are `verified`, `dispatched-only` (with
  a cited not-wire-observable reason), or `blocked` (with a named,
  falsifiable hypothesis). The remaining `broken` rows are the
  defect backlog produced by the audit.
- **SC-003**: Every `blocked` and `broken` row has a hypothesis test
  whose execution time is bounded — a single hypothesis test
  completes in under 10 minutes of wall-clock against a live
  headless engine.
- **SC-004**: A reviewer with no prior context, given the audit and
  a headless engine, can pick any `verified` row and reproduce its
  cited evidence within 15 minutes of wall-clock time.
- **SC-005**: The V2 ledger covers 100% of named V2 pathologies in
  FR-010 and links each to either a V3 fix-with-evidence or a
  hypothesis-plan entry.
- **SC-006**: The Phase-2 smoke run completes the report-1 §4
  4-step chain and produces a per-step PASS/FAIL table within the
  same 5-minute budget as the Phase-1 macro driver.
- **SC-007**: The audit's reproduction harness lives under the
  repository tree (not in `/tmp`), is invoked by checked-in shell
  scripts, and produces evidence files into `build/reports/`
  (gitignored) — matching the established convention of
  `reports/003-macro-build-live-run.md` §7.
- **SC-008**: Re-running the audit's evidence-collection step
  against the same engine pin and gametype produces the same
  outcome bucket for at least 90% of rows (the non-determinism
  budget covers BAR's ambient AI making different choices on
  different seeds; arms whose outcome is sensitive to that variance
  are themselves an audit finding).

## Assumptions

- **Engine pin is `recoil_2025.06.19`** (the pin the existing reports
  used). The audit may be re-executed against later pins, but the
  delivered evidence is collected against this pin.
- **Phase-1 default**: The audit runs Phase-1 (built-in BARb AI
  active) by default, matching 003's design constraint and the
  existing reports. Phase-2 is exercised only for the User Story 4
  smoke run; full Phase-2 verifier wiring is out of scope.
- **The 003 macro driver and its registry are the foundation**: the
  audit extends the registry rather than replacing it, and reuses
  the existing `BehavioralTestCase` / `VerifyPredicate` /
  `VerificationOutcome` types in
  `clients/python/highbar_client/behavioral_coverage/`.
- **Cheats-gated arms** (`give_me`, `give_me_new_unit`) require a
  separate cheats-enabled startscript variant; the audit may add
  one under `tests/headless/scripts/`.
- **Save/Load**: V3's wire definition exists in `service.proto`. The
  audit's discovery of whether the engine-side handlers are
  implemented, stubbed, or proxied is a finding, not a precondition.
- **Out of scope**:
  - Wiring new snapshot-diff verifiers for the 39
    currently-unverified arms beyond what the audit needs to
    classify them. (Verifier expansion is a follow-up feature
    informed by this audit's hypothesis plan.)
  - Implementing Phase 2's external-AI economy/tech-progression
    logic.
  - Fixing any defects the audit discovers — the audit's deliverable
    is the classification and the falsification tests, not the
    bug-fix patches.
  - Cross-version BAR-rapid def-id stabilization. The audit
    documents the instability (per report 2 §3) but does not solve
    it.
- **Reference**: `https://github.com/rlcevg/CircuitAI/tree/0ef36267633d6c1b2f6408a8d8a59fff38745dc3`
  is the upstream from which BARb is forked. The audit may consult
  it to resolve questions about CircuitAI manager semantics
  (`CCircuitUnit::Cmd*` API contracts, `IModule` event ordering).

## Dependencies

- **003-snapshot-arm-coverage** (squash-merged 2026-04-22, commit
  `7578ce29`): provides the `BehavioralTestCase` / `VerifyPredicate`
  framework, the macro driver, the snapshot-tick + RequestSnapshot
  mechanism, and the SnapshotBuilder fix that makes
  `under_construction` / `build_progress` observable on the wire.
- **Existing live-run reports**:
  `reports/003-macro-build-live-run.md` and
  `reports/003-macro-build-live-run-2.md` are the baseline evidence
  the audit extends.
- **HighBarV2 reports tree** at
  `/home/developer/projects/HighBarV2/reports/` is the source of
  V2 pathology citations; if the V2 directory is unavailable on a
  reviewer's host, the V2 ledger MUST quote the relevant V2 source
  excerpts inline so the ledger is self-contained.

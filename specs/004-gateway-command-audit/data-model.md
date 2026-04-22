# Phase 1 Data Model — Gateway Command Audit

**Branch**: `004-gateway-command-audit` | **Date**: 2026-04-22
**Plan**: [plan.md](./plan.md) | **Research**: [research.md](./research.md)

The audit is a documentation + evidence feature, so its "data model"
is the shape of each row in its three Markdown deliverables, plus the
lightweight Python metadata the macro driver reads and writes to
produce them. No database, no protobuf schema changes.

The five entities formalized here correspond one-to-one with the
spec's Key Entities section. Each has: field list, validation rules,
and relationship to sibling entities.

---

## Entity: `OutcomeBucket`

A closed enumeration. Definitions in spec FR-001 and plan
research.md §2.

| Value | Definition |
|-------|------------|
| `verified` | Dispatcher returned success AND expected post-effect is visible on the wire (snapshot diff, engine log line, or delta event). |
| `dispatched-only` | Dispatcher returned success AND effect is not wire-observable by design (channel-C Lua, channel-B query, team-global state, drawer-only). |
| `blocked` | Dispatcher returned success AND expected effect is in principle wire-observable, but a documented external condition prevented it on this run (Phase-1 ambient AI, cheats off, cross-team def, team-global singleton). |
| `broken` | Dispatcher returned success but engine performed no effect AND no documented external condition explains it. This is the defect-backlog bucket. |

**Validation**:
- Exactly one value per `AuditRow`.
- Decision procedure is **ordered**: a row is evaluated against
  `verified` → `dispatched-only` → `blocked` → `broken` in that
  order and lands in the first bucket it matches (research §2).
- `broken` rows MUST have a non-empty `hypothesis` field naming a
  falsifiable dispatcher-level hypothesis from the
  `HypothesisClass` enumeration (see below).

---

## Entity: `HypothesisClass`

A closed enumeration used by both `AuditRow.hypothesis_class` (for
`blocked`/`broken` rows) and `HypothesisPlanEntry.candidates[]`
(for ranked hypothesis lists). Research §3 defines the initial
eight values.

| Value | Applies when | Predicted-confirmed evidence | Falsifier test |
|-------|--------------|------------------------------|----------------|
| `phase1_reissuance` | Phase-1 ambient BARb AI re-issues its own decision on the frame after the external command lands. | Phase-1 snapshot diff empty; Phase-2 snapshot diff matches expected. | Phase-2 smoke run (FR-008). |
| `effect_not_snapshotable` | Engine performs effect but it doesn't surface in `own_units[]` / `enemy_units[]` / `StateSnapshot`. | No snapshot diff; `engine.infolog` line confirms arm-specific state change. | Engine-log inspection. |
| `target_missing` | Dispatcher needs a precondition target (damaged friendly, in-range enemy, reclaimable feature) that the bootstrap plan didn't provision. | Gateway ack success; no snapshot diff; optional engine-log line "target not found". | Provision precondition in bootstrap; re-run. |
| `cross_team_rejection` | def-id belongs to a faction the actor cannot build (report 1 §4.3 step 2). | Gateway ack success; no `own_units[]` entry; no engine-log error. | Resolve def-id with actor faction via `def-id-resolver.py`; re-run. |
| `cheats_required` | Arm requires `Cheats=1` in match config. | Cheats-off: no diff. Cheats-on: expected diff. | Run `cheats.startscript` variant (research §4). |
| `dispatcher_defect` | Handler calls wrong engine method, returns success without calling any method, or passes malformed arguments. | Phase-2 ALSO produces no diff and no arm-specific engine-log entry. | Phase-2 smoke + bespoke log assertion on `CommandDispatch.cpp` arm handler. |
| `intended_noop` | Dispatcher intentionally does nothing (e.g., `set_figure_position` at `src/circuit/grpc/CommandDispatch.cpp:595-603`). | No effect on any channel; dispatcher comment cited. | None — recorded as `dispatched-only` with source-comment evidence. |
| `engine_version_drift` | Engine pin lacks the callback the dispatcher attempts to call. | `engine.infolog` line "drawer not available" or "callback returned nullptr". | Retry against newer engine pin (out of 004 scope). |

**Validation**:
- Values are extensible via a one-line edit to
  `clients/python/highbar_client/behavioral_coverage/audit_report.py`'s
  `HYPOTHESIS_CLASSES` dict (research §3).
- Free-text hypotheses are forbidden at the row level — every
  hypothesis MUST pick a class.

---

## Entity: `AuditRow`

One entry in `audit/command-audit.md`. Corresponds to exactly one
AICommand arm (from `proto/highbar/commands.proto` AICommand oneof)
OR one RPC (from `proto/highbar/service.proto` HighBarProxy service).

**Fields**:

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `row_id` | string | yes | Kebab-case unique identifier. AICommand arms: `cmd-<arm_name>` (e.g., `cmd-build-unit`). RPCs: `rpc-<method>` (e.g., `rpc-hello`). |
| `kind` | enum | yes | `aicommand` \| `rpc`. |
| `arm_or_rpc_name` | string | yes | For `aicommand`: the snake_case arm name from the AICommand oneof. For `rpc`: the PascalCase RPC name. |
| `outcome` | `OutcomeBucket` | yes | Per §OutcomeBucket decision procedure. |
| `dispatch_citation` | string | yes | `file:line_start-line_end`. AICommand arms cite `src/circuit/grpc/CommandDispatch.cpp` line ranges (FR-002). RPCs cite `src/circuit/grpc/HighBarService.cpp`. |
| `evidence_shape` | enum | yes | `snapshot_diff` \| `engine_log` \| `not_wire_observable` \| `dispatch_ack_only`. |
| `evidence_excerpt` | markdown block | required for `verified`; optional otherwise | For `snapshot_diff`: the same shape as `reports/003-macro-build-live-run.md` §4.3. For `engine_log`: excerpt with engine pin. For `not_wire_observable`: a one-line reason referencing a channel name. |
| `channel` | enum | required when `outcome=dispatched-only` | `channel_a_command` \| `channel_b_query` \| `channel_c_lua` \| `team_global` \| `drawer_only`. Vocabulary matches `clients/python/highbar_client/behavioral_coverage/registry.py` (FR-014). |
| `hypothesis_class` | `HypothesisClass` | required when `outcome ∈ {blocked, broken}` | Per §HypothesisClass. |
| `hypothesis_summary` | one-sentence string | required when `outcome ∈ {blocked, broken}` | Instantiates the hypothesis for this specific arm (e.g., "Phase-1 BARb re-issues move command to factory-produced unit on the next frame, overriding the external MoveUnit"). |
| `falsification_test` | string | required when `outcome ∈ {blocked, broken}` | Shell command pointing at `tests/headless/audit/hypothesis.sh <arm> <hyp-id>`. |
| `reproduction_recipe` | string | required when `outcome=verified` | Shell command line pointing at `tests/headless/audit/repro.sh <arm>`. Produces the row's `evidence_excerpt`. |
| `gametype_pin` | string | required | The gametype the evidence was collected against (e.g., `test-29926`). |
| `engine_pin` | string | required | `recoil_2025.06.19` at feature-authoring time. |
| `notes` | markdown | optional | Free-text nuance (e.g., "non-deterministic; bucket flipped in 1 of 2 stability runs"). |

**Validation**:
- `row_id` is unique across all rows.
- For `outcome=verified`, `evidence_excerpt` is non-empty AND
  `reproduction_recipe` is runnable (FR-004, FR-005).
- For `outcome ∈ {blocked, broken}`, `hypothesis_class`,
  `hypothesis_summary`, and `falsification_test` are all non-empty
  (FR-003).
- For `outcome=dispatched-only`, `channel` is non-empty (FR-014).
- `dispatch_citation` must point at an existing file:line range in
  the current commit.
- The set of row_ids MUST equal exactly:
  `{cmd-<arm> for each arm in AICommand.oneof.command} ∪
   {rpc-hello, rpc-stream-state, rpc-submit-commands,
    rpc-invoke-callback, rpc-save, rpc-load,
    rpc-get-runtime-counters, rpc-request-snapshot}` (SC-001).

---

## Entity: `HypothesisPlanEntry`

One entry in `audit/hypothesis-plan.md`. One entry per unverified
AICommand arm (spec US2, FR-007 — covering the 39 unit arms at
`clients/python/highbar_client/behavioral_coverage/registry.py`
lines 320-352 and the 4 dispatch-ack-only arms identified in report
1 §4).

**Fields**:

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `arm_name` | string | yes | Must match exactly one AICommand arm. |
| `related_audit_row_id` | string | yes | Links to `AuditRow.row_id`. |
| `candidates` | array of `HypothesisCandidate` | yes, 1-3 entries | Ranked; first is highest-priority. |

Where `HypothesisCandidate` is:

| Field | Type | Notes |
|-------|------|-------|
| `rank` | int | 1-indexed; unique within the candidates list. |
| `hypothesis_class` | `HypothesisClass` | From the closed vocabulary. |
| `hypothesis_summary` | one-sentence string | Arm-specific instantiation. |
| `predicted_confirmed_evidence` | markdown block | What the evidence looks like if this hypothesis holds (US2 acceptance #2). |
| `predicted_falsified_evidence` | markdown block | What the evidence looks like if this hypothesis is falsified (US2 acceptance #2). |
| `test_command` | string | Shell command that runs the distinguishing test (US2 acceptance #2). |

**Validation**:
- `candidates[0].rank == 1`; ranks are dense from 1.
- Every `arm_name` appears in the underlying registry as
  `verified="false"` or as a 003-era `verified="true"` that was
  ack-only (no snapshot diff).
- For every `HypothesisClass` in the candidates list, the
  `predicted_confirmed_evidence` and `predicted_falsified_evidence`
  are consistent with the class's decision row in §HypothesisClass.

---

## Entity: `V2V3LedgerRow`

One entry in `audit/v2-v3-ledger.md`. One row per V2 pathology drawn
from the V2 authoritative sources (research §1:
`HighBarV2/docs/known-issues.md` and
`HighBarV2/reports/017-fix-client-socket-hang.md`). Per FR-010, six
pathologies are named explicitly; the ledger MAY include others from
those two files.

**Fields**:

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `pathology_id` | string | yes | Kebab-case; e.g., `callback-frame-interleaving`. |
| `pathology_name` | short string | yes | Human-readable (matches FR-010 where named). |
| `v2_source_citation` | string | yes | `file:line_start-line_end` under `/home/developer/projects/HighBarV2/`. |
| `v2_excerpt` | markdown block | yes | Quoted inline per FR-009 (self-contained). |
| `v3_status` | enum | yes | `fixed` \| `partial` \| `not-addressed`. |
| `v3_source_citation` | string | required when `v3_status ∈ {fixed, partial}` | `file:line_start-line_end` under `/home/developer/projects/HighBarV3/`. |
| `v3_mechanism` | one-paragraph string | required when `v3_status ∈ {fixed, partial}` | How the V3 fix works, explained in prose (not just code quote). |
| `audit_row_reference` | string | required when `v3_status=fixed` | The `AuditRow.row_id` whose evidence demonstrates the fix holds at runtime (US3 acceptance #2). |
| `hypothesis_plan_reference` | string | required when `v3_status=not-addressed` | The `HypothesisPlanEntry.arm_name` (if an existing hypothesis covers it) OR the text `RECOMMEND_ADD` plus a one-sentence test proposal (US3 acceptance #3). |
| `residual_risk` | markdown | optional | Note on what's still exposed or what the fix doesn't cover. |

**Validation**:
- `pathology_id` is unique across all rows.
- The ledger MUST contain at least the six pathologies FR-010 names
  by content:
  1. Callback / frame interleaving race.
  2. Client `recvBytes` infinite loop on engine death.
  3. Default 8 MB max-message-size insufficient for large maps.
  4. Single-connection lockout with no auto-reconnect.
  5. Frame-budget timeout and AI removal.
  6. `Save` / `Load` proxy-side TODO stubs.
- For every `v3_status=fixed` row, the referenced `AuditRow` MUST
  have `outcome=verified` (the fix is demonstrated at runtime, not
  asserted).

---

## Entity: `ReproductionRecipe`

Not a separate file — one occurrence per `AuditRow` with
`outcome=verified` and one occurrence per `HypothesisPlanEntry`
candidate's `test_command`. Formalized here because the spec's Key
Entities section names it.

**Fields**:

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `shell_command` | string | yes | Full command line, including flags. MUST point at a checked-in script under `tests/headless/audit/` or `clients/python/highbar_client/behavioral_coverage/` (FR-012, SC-007). |
| `parameters` | map (string → string) | optional | Per-recipe parameter table. |
| `expected_stdout_excerpt` | markdown block | yes (for `verified` recipes) | What the recipe prints when the evidence is produced. |
| `expected_artifact_path` | string | optional | Path under `build/reports/` where the recipe writes full evidence (SC-007). |
| `wall_clock_budget_seconds` | int | yes | Must be ≤ 600 for hypothesis tests (SC-003); ≤ 900 for reproduction (SC-004). |

**Validation**:
- `shell_command` MUST NOT reference `/tmp/*.py` or any ad-hoc file
  (FR-012).
- `wall_clock_budget_seconds` is bounded by spec success criteria.
- When `expected_artifact_path` is set, the path MUST be under
  `build/reports/` (SC-007) and MUST be gitignored.

---

## Relationships

```text
AuditRow (1) ───── related_audit_row_id (1) ───── HypothesisPlanEntry
   │                                                   │
   │                                                   │ candidates[]
   │                                                   ▼
   │                                             HypothesisCandidate
   │                                                   │
   │                                                   │ hypothesis_class
   ▼                                                   ▼
hypothesis_class ──────────────────────────────── HypothesisClass
   │
   │ audit_row_reference (from V2V3LedgerRow)
   ▼
V2V3LedgerRow
```

**Cardinality**:
- Each `AuditRow` may be referenced by zero or more `V2V3LedgerRow`s
  (one V3 fix may be demonstrated by one audit row; one audit row
  may demonstrate multiple V2 pathology fixes — rare but allowed).
- Each `AuditRow` with `outcome ∈ {blocked, broken}` has exactly
  one `HypothesisPlanEntry` (FR-007 requires one-to-one for
  unverified arms).
- Each `HypothesisPlanEntry` has 1-3 `HypothesisCandidate`s.

---

## File layouts on disk

```text
audit/
├── README.md                 # one-paragraph index
├── command-audit.md          # § per kind (RPC / AICommand by category), rows as Markdown tables
├── hypothesis-plan.md        # § per arm, candidates as nested lists
└── v2-v3-ledger.md           # single Markdown table
```

Each artifact is a single Markdown file. Rows are Markdown table
rows (for `command-audit.md` and `v2-v3-ledger.md`) or heading-
anchored sections (for `hypothesis-plan.md`'s per-arm per-candidate
structure). Concrete row-level schemas are in `contracts/`.

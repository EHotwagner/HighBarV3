# Contract — Hypothesis Plan Entry (`audit/hypothesis-plan.md`)

**Applies to**: every entry in `audit/hypothesis-plan.md`.
**Referenced from**: plan.md (Structure), data-model.md (`HypothesisPlanEntry`).

## Entry Markdown schema

Each entry in `audit/hypothesis-plan.md` is rendered as a level-3-
heading-anchored section per arm. Candidates are nested level-4
sections under the arm.

Document skeleton:

```markdown
# Hypothesis Plan for Unverified Arms

> Companion to audit/command-audit.md. Contains ≥ 43 entries:
> one per arm currently registered `verified="false"` (registry
> lines 320-352) or `verified="true"` via dispatch ack only
> (report 1 §4). Each entry names ranked candidate hypotheses
> from the closed vocabulary in `plan/research.md §3` and the
> test that distinguishes them.

## channel_a_command unit arms (ranked by frequency)

### cmd-stop

Related audit row: [`cmd-stop`](command-audit.md#cmd-stop)

#### Candidate 1 — `effect_not_snapshotable`

- **Hypothesis**: Stop command clears the unit's command queue but
  does not alter position, health, build_progress, or any
  `own_units[]` field that StateSnapshot currently carries.

- **Predicted-confirmed evidence** (if `effect_not_snapshotable` is true):

  ```text
  [engine.infolog]  unit 4201 command_queue: []
  ```

  …and no `own_units[]` diff in the snapshot pair.

- **Predicted-falsified evidence** (if the unit instead keeps
  executing its prior order):

  ```text
  [engine.infolog]  unit 4201 command_queue: [MoveTo(...)]
  ```

  …or a continued `own_units[].position` delta after the Stop
  dispatch timestamp.

- **Test command**:

  ```bash
  tests/headless/audit/hypothesis.sh cmd-stop effect_not_snapshotable
  ```

#### Candidate 2 — `phase1_reissuance`
… (same shape)

### cmd-move-unit
…

## channel_b_query arms

### cmd-init-path
…

## Phase-1-fragile arms (ack-only verified in 003)

### cmd-build-unit
… (the 003-verified build_unit has a MoveUnit-follow-up issue
   per report 1 §4 step 4; this entry lists the hypothesis under
   that specific Phase-1 pattern)

## Summary — hypothesis classes by frequency

| Hypothesis class | Arm count |
|---|---|
| phase1_reissuance | NN |
| effect_not_snapshotable | NN |
| target_missing | NN |
| cross_team_rejection | NN |
| cheats_required | 2 |
| dispatcher_defect | NN |
| intended_noop | NN |
| engine_version_drift | NN |
| **TOTAL** | **≥ 43** |
```

## Field-by-field rules

For each field defined in `data-model.md` §HypothesisPlanEntry and
§HypothesisCandidate:

| Field | Markdown placement | Validation |
|-------|-------------------|------------|
| `arm_name` | Level-3 heading (`### cmd-stop`). Derive arm_name by stripping `cmd-` prefix and reverse-kebab-casing. | Must exist as a row in `command-audit.md`. |
| `related_audit_row_id` | First paragraph: `Related audit row: [cmd-stop](command-audit.md#cmd-stop)` | Link target resolves in the rendered Markdown. |
| `candidates[i].rank` | Implicit in ordering — candidates are numbered `Candidate 1`, `Candidate 2`, `Candidate 3` in level-4 headings. | Ranks dense from 1. |
| `candidates[i].hypothesis_class` | Appears in the level-4 heading (`#### Candidate 1 — phase1_reissuance`). | Value from closed vocabulary. |
| `candidates[i].hypothesis_summary` | First bullet (`- **Hypothesis**: …`). | One sentence; arm-specific. |
| `candidates[i].predicted_confirmed_evidence` | Second bullet + fenced block. | Evidence shape consistent with the hypothesis class (per data-model §HypothesisClass). |
| `candidates[i].predicted_falsified_evidence` | Third bullet + fenced block. | Same class-consistency rule. |
| `candidates[i].test_command` | Fourth bullet + fenced `bash` block. | Must point at `tests/headless/audit/hypothesis.sh` with correct args. |

## Completeness rule

The hypothesis-plan generator MUST assert the entry count is ≥ 43
(FR-007):

```python
# 39 from registry lines 320-352 (_UNVERIFIED_UNIT_ARMS)
# + 4 from report 1 §4 (cmd-build-unit, cmd-move-unit, plus two
#   ack-only cases from report 1 §4.3)
assert len(entries) >= 43, f"hypothesis-plan entries: got {len(entries)}, expected ≥ 43"
```

## Ordering

- Level-2 sections in this order:
  1. `channel_a_command unit arms`
  2. `channel_b_query arms`
  3. `channel_c_lua arms` (usually empty of unverified — channel-C
     is `dispatched-only` by design, not `blocked`)
  4. `Phase-1-fragile arms`
  5. `Summary`
- Within each level-2 section, entries sorted by
  `related_audit_row_id` ascending.
- Within each entry, candidates sorted by rank ascending.

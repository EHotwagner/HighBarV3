# Contract — Audit Row (`audit/command-audit.md`)

**Applies to**: every row in `audit/command-audit.md`.
**Referenced from**: plan.md (Structure), data-model.md (`AuditRow`).

## Row-block Markdown schema

Each row in `audit/command-audit.md` is rendered as a
level-3-heading-anchored section with a four-line metadata block,
then body. Rows are grouped into level-2 sections by kind and
category.

Document skeleton:

```markdown
# Gateway Command Audit

> Engine pin: `recoil_2025.06.19` | Gametype pin: `test-29926`
> | Collected: 2026-04-22 | Commit: <commit-sha>

## RPCs (8)

### rpc-hello

- **Outcome**: verified
- **Dispatch citation**: `src/circuit/grpc/HighBarService.cpp:NNN-MMM`
- **Evidence shape**: engine_log
- **Channel** / **Hypothesis class**: —
- **Gametype**: test-29926 | **Engine**: recoil_2025.06.19

**Evidence**:

```text
[hb-gateway] Hello accepted: client_id=... ai_role=... schema=1.0.0
```

**Reproduction recipe**:

```bash
tests/headless/audit/repro.sh rpc-hello
# Expected stdout excerpt:
#   PASS: Hello returned schema=1.0.0
```

### rpc-submit-commands
... (same shape)

## AICommand arms — channel_a_command (unit commands)

### cmd-build-unit

- **Outcome**: verified
- **Dispatch citation**: `src/circuit/grpc/CommandDispatch.cpp:NNN-MMM`
- **Evidence shape**: snapshot_diff
- **Channel** / **Hypothesis class**: —
- **Gametype**: test-29926 | **Engine**: recoil_2025.06.19

**Evidence** (snapshot diff excerpt):

```diff
  own_units:
+   - unit_id: 4201
+     def_id: <resolved-at-runtime>
+     under_construction: true
+     build_progress: 0.08
```

**Reproduction recipe**:

```bash
tests/headless/audit/repro.sh cmd-build-unit
```

### cmd-move-unit

- **Outcome**: blocked
- **Dispatch citation**: `src/circuit/grpc/CommandDispatch.cpp:NNN-MMM`
- **Evidence shape**: snapshot_diff
- **Channel**: —
- **Hypothesis class**: phase1_reissuance
- **Gametype**: test-29926 | **Engine**: recoil_2025.06.19

**Hypothesis**: Phase-1 BARb re-issues move command to factory-
produced unit on the next frame, overriding the external MoveUnit.

**Falsification test**:

```bash
tests/headless/audit/hypothesis.sh cmd-move-unit phase1_reissuance
# Runs Phase-2 (enable_builtin=false); expected PASS confirms hypothesis.
```

## AICommand arms — channel_b_query
... (channel-B arms: init_path, get_approx_length, ...)

## AICommand arms — channel_c_lua
... (channel-C Lua arms: draw_add_point, send_text_message, ...)

## AICommand arms — cheats-gated
... (give_me, give_me_new_unit; each has two evidence blocks —
     cheats-on and cheats-off)

## Non-determinism notes

> Rows whose outcome bucket flipped across two runs of
> `tests/headless/audit/repro-stability.sh` (SC-008 per-pair check).
> Current flip rate: X / 74 rows (target ≤ 10%).
```

## Field-by-field rules

For each field defined in `data-model.md` §AuditRow:

| Field | Markdown placement | Validation |
|-------|-------------------|------------|
| `row_id` | Level-3 heading (`### cmd-build-unit`) | Unique across all rows. |
| `kind` | Implicit in parent `## AICommand arms …` or `## RPCs` | Level-2 section determines kind. |
| `arm_or_rpc_name` | Implicit — derived from `row_id` (strip `cmd-`/`rpc-` prefix, reverse kebab-case → snake_case for arms, kebab-case → PascalCase for RPCs). | `row_id` round-trips to arm/rpc name. |
| `outcome` | First metadata bullet (`- **Outcome**: …`) | One of `verified`, `dispatched-only`, `blocked`, `broken`. |
| `dispatch_citation` | Second metadata bullet | `file:line_start-line_end`. For AICommand arms, file MUST be `src/circuit/grpc/CommandDispatch.cpp` (FR-002). |
| `evidence_shape` | Third metadata bullet | One of `snapshot_diff`, `engine_log`, `not_wire_observable`, `dispatch_ack_only`. |
| `channel` / `hypothesis_class` | Fourth metadata bullet (one of the two, not both; em-dash for irrelevant field) | Per outcome bucket (data-model §AuditRow). |
| `gametype_pin` / `engine_pin` | Fifth metadata bullet | Required always. |
| `evidence_excerpt` | First fenced block under `**Evidence**:` heading | Required for `verified`. Format: `diff` for snapshot-diff, `text` for engine-log. |
| `hypothesis_summary` | Sentence under `**Hypothesis**:` heading | Required for `blocked`/`broken`. |
| `falsification_test` | Fenced `bash` block under `**Falsification test**:` heading | Required for `blocked`/`broken`. |
| `reproduction_recipe` | Fenced `bash` block under `**Reproduction recipe**:` heading | Required for `verified`. |
| `notes` | Italic paragraph after the fenced blocks, prefixed `_Note:_`. | Optional. |

## Completeness rule

The generator (`clients/python/highbar_client/behavioral_coverage/audit_report.py`)
MUST assert at emission time that the row count equals 74:

```python
assert n_rpc_rows == 8 and n_aicommand_rows == 66, (
    f"audit row count: expected 8+66, got {n_rpc_rows}+{n_aicommand_rows}"
)
```

SC-001 failure at generation time is louder and cheaper than failure
at review time.

## Ordering

- Level-2 sections appear in this order: `RPCs`, `channel_a_command`,
  `channel_b_query`, `channel_c_lua`, `cheats-gated`.
- Within each level-2 section, rows are sorted by `row_id` ascending.
- The `Non-determinism notes` section is the final level-2 section.

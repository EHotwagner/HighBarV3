# Contract: `AICommand` coverage report CSV

**Addresses**: FR-013.

A CMake custom target `aicommand-arm-coverage` writes
`build/reports/aicommand-arm-coverage.csv` on every build. The file
is uploaded as a CI artifact and grep'd by acceptance tests.

## File format

UTF-8 CSV, `\n` line terminator, comma-delimited, header row
present. Fields that contain commas are double-quoted. No other
escaping.

## Columns

```
arm_name,arm_field_number,dispatcher_wired,observability_channel,covering_scripts,assertion_count
```

| Column | Type | Example |
|---|---|---|
| `arm_name` | snake_case | `move_unit` |
| `arm_field_number` | positive integer | `1` |
| `dispatcher_wired` | `true` \| `false` | `true` |
| `observability_channel` | `state-stream` \| `engine-log` \| `lua-widget` | `state-stream` |
| `covering_scripts` | double-quoted, comma-separated bash script basenames | `"us2-ai-coexist.sh,us3-external-only.sh"` |
| `assertion_count` | non-negative integer | `3` |

## Derivation

- `arm_name` and `arm_field_number` come from parsing
  `proto/highbar/commands.proto` with `buf`'s JSON descriptor
  (`buf build -o -`).
- `dispatcher_wired` is `true` iff a `case` with a matching
  `kind_case` label exists in
  `src/circuit/grpc/CommandDispatch.cpp` AND that case's body calls
  an identifier matching `^(unit->Cmd|springai::|ai->Cheats\(\))`.
  The match is syntactic (grep-based); no preprocessor or template
  expansion is required.
- `observability_channel` comes from
  `contracts/aicommand-arm-map.md` — a pre-build step parses the
  three tables in that file to build the arm→channel map.
- `covering_scripts` is the set of `tests/headless/*.sh` files whose
  first 30 lines contain a `# arm-covered: <arm_name>` comment.
  Multiple arms per script permitted; one `# arm-covered:` line per
  arm.
- `assertion_count` is the number of lines in the covering scripts
  that match the regex `(assert|expect|fail)_` and appear textually
  after the first `# arm-covered: <arm_name>` line, until the next
  `# arm-covered:` comment (or EOF). This is intentionally crude —
  the signal is "test does *some* work for this arm", not a deep
  static analysis.

## Build failure rules

The target exits non-zero (and the build fails) on any of:

- `dispatcher_wired = false` for any arm (FR-012).
- `covering_scripts` is empty for any arm (FR-013).
- `observability_channel = lua-widget` but the arm's widget file
  listed in `aicommand-arm-map.md` does not exist.
- `arm_field_number` missing or duplicated across arms (proto sanity).

Warnings (build continues, but CI surfaces them):

- `assertion_count = 0` (script declares coverage but has no
  matching assertions).
- `covering_scripts` list exceeds 4 entries (likely over-coupled).

## Example

```
arm_name,arm_field_number,dispatcher_wired,observability_channel,covering_scripts,assertion_count
move_unit,1,true,state-stream,"us1-observer.sh,us2-ai-coexist.sh",4
patrol,2,true,state-stream,"us2-ai-coexist.sh",2
send_chat_message,34,true,engine-log,"aicommand-arm-coverage.sh",1
draw_line,42,true,lua-widget,"aicommand-arm-coverage.sh",3
cheat_kill_unit,55,true,engine-log,"aicommand-arm-coverage.sh",1
```

## Consumers

- CI uploads the CSV as a pipeline artifact (`actions/upload-artifact`).
- `tests/headless/aicommand-arm-coverage.sh` reads the CSV at the
  start of its run and uses it to iterate arms.
- Future drift tooling (e.g. a PR comment bot) consumes the CSV
  diff between base and head to flag newly-uncovered arms.

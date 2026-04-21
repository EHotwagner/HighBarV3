# Contract: `AICommand` per-arm wiring and observability

**Addresses**: FR-012, FR-013, SC-004, spec Clarification Q1.

Every arm in the `AICommand` oneof maps to (a) a concrete engine
entry point the dispatcher calls, and (b) exactly one observability
channel a test can assert on. This file is the authoritative map;
the CMake `aicommand-arm-coverage` target consumes it (via the
`# arm-covered:` headers on acceptance scripts — see
`aicommand-coverage-report.md`) and fails the build if any arm is
unmapped or unwired.

**Scope**: all 66 oneof arms declared in
`proto/highbar/commands.proto`. The feature's FR-012/FR-013/SC-004
gates are measured against this set of 66. The earlier "97" figure
is retired — see research.md §R3 for the reconciliation.

The map is organized by **observability channel** because that's
what determines test shape.

## Channel A: state-stream-observable (40 arms)

An arm is in this channel when its effect appears as a standard
`DeltaEvent` in the outgoing stream within 3 engine frames of
dispatch. Acceptance tests assert by reading the stream and matching
a predicate on the delta.

| Arm (oneof field) | Engine entry point | Predicate the test asserts |
|---|---|---|
| `build_unit` | `CCircuitUnit::CmdBuild` | New `UnitCreated` delta on completion OR build-start marker. |
| `stop` | `CCircuitUnit::CmdStop` | Unit's command queue empties. |
| `wait` | `CCircuitUnit::CmdWait` | Unit's wait flag set. |
| `timed_wait` | `CCircuitUnit::CmdWait` (timed variant) | Wait-until-frame flag on unit. |
| `squad_wait` | `CCircuitUnit::CmdWait` (squad variant) | Squad-count wait tag on unit. |
| `death_wait` | `CCircuitUnit::CmdWait` (death variant) | Death-trigger tag on unit referencing target. |
| `gather_wait` | `CCircuitUnit::CmdWait` (gather variant) | Gather-count tag on unit. |
| `move_unit` | `CCircuitUnit::CmdMoveTo` | Unit's `position` changes. |
| `patrol` | `CCircuitUnit::CmdPatrolTo` | Next delta carries a patrol-order diff. |
| `fight` | `CCircuitUnit::CmdFightTo` | Unit's command queue reflects fight order. |
| `attack` | `CCircuitUnit::CmdAttackUnit` | Engagement marker on target within 3 frames. |
| `attack_area` | `CCircuitUnit::CmdAttackGround` | Attack marker on area. |
| `guard` | `CCircuitUnit::CmdGuard` | Unit assigned to guard target. |
| `repair` | `CCircuitUnit::CmdRepair` | Target unit's health increases. |
| `reclaim_unit` | `CCircuitUnit::CmdReclaimUnit` | Target `UnitDestroyed` delta. |
| `reclaim_area` | `CCircuitUnit::CmdReclaimArea` | Features removed from stream within radius. |
| `reclaim_in_area` | `CCircuitUnit::CmdReclaimInArea` | Features removed from stream. |
| `reclaim_feature` | `CCircuitUnit::CmdReclaimFeature` | Single feature disappears from stream. |
| `restore_area` | `CCircuitUnit::CmdRestoreArea` | Terrain restoration tag on unit. |
| `resurrect` | `CCircuitUnit::CmdResurrect` | Target feature → new `UnitCreated` delta. |
| `resurrect_in_area` | `CCircuitUnit::CmdResurrectInArea` | New `UnitCreated` delta from feature. |
| `capture` | `CCircuitUnit::CmdCapture` | Target ownership changes. |
| `capture_area` | `CCircuitUnit::CmdCaptureInArea` | Ownership changes for units in radius. |
| `set_base` | `CCircuitUnit::CmdSetBase` | Base-position tag on unit. |
| `self_destruct` | `CCircuitUnit::CmdSelfD(true)` | `UnitDestroyed` delta for own unit. |
| `load_units` | `CCircuitUnit::CmdLoadUnits` | Carrier's `loadedUnits` list changes. |
| `load_units_area` | `CCircuitUnit::CmdLoadUnitsArea` | Carrier's `loadedUnits` list changes. |
| `load_onto` | `CCircuitUnit::CmdLoadOnto` | Unit's carrier-id field set. |
| `unload_unit` | `CCircuitUnit::CmdUnloadUnit` | Carrier's `loadedUnits` list shrinks. |
| `unload_units_area` | `CCircuitUnit::CmdUnloadUnitsArea` | Carrier's `loadedUnits` list shrinks. |
| `set_wanted_max_speed` | `CCircuitUnit::CmdWantedSpeed` | Unit's `maxSpeed` field changes. |
| `stockpile` | `CCircuitUnit::CmdStockpile` | Unit's `stockpileSize` increments. |
| `dgun` | `CCircuitUnit::CmdDGun` | Projectile event + commander's `dgun` cooldown. |
| `set_on_off` | `CCircuitUnit::CmdOnOff` | Unit's `active` flag toggles. |
| `set_repeat` | `CCircuitUnit::CmdRepeat` | Unit's `repeatLoop` flag. |
| `set_move_state` | `CCircuitUnit::CmdSetMoveState` | Unit's `moveState` changes. |
| `set_fire_state` | `CCircuitUnit::CmdSetFireState` | Unit's `fireState` changes. |
| `set_trajectory` | `CCircuitUnit::CmdTrajectory` | Trajectory flag on unit. |
| `set_auto_repair_level` | `CCircuitUnit::CmdAutoRepairLevel` | Auto-repair tag on unit. |
| `set_idle_mode` | `CCircuitUnit::CmdIdleMode` | Idle-mode tag on unit. |

**Count in this channel: 40 arms.**

## Channel B: engine-log side-channel (15 arms)

An arm is in this channel when its effect is visible in the engine's
stdout but not in the `DeltaEvent` stream. The acceptance test
greps the engine log for a specific line.

| Arm | Engine entry point | Log line substring |
|---|---|---|
| `send_text_message` | `springai::Game::SendTextMessage` | `[AI→chat]` |
| `set_last_pos_message` | `springai::Game::SetLastMessagePosition` | `[AI→last-pos]` |
| `send_resources` | `springai::Economy::SendResources` | `[resource-xfer]` |
| `set_my_income_share_direct` | `springai::Economy::SetShare` | `[share-direct]` |
| `set_share_level` | `springai::Economy::SetShareLevel` | `[share-level]` |
| `pause_team` | `springai::Game::PauseTeam` | `[team-pause]` |
| `give_me` | `springai::Cheats::GiveMe` (cheat-on matches) | `[cheat][give]` |
| `give_me_new_unit` | `springai::Cheats::GiveMeNew` (cheat-on matches) | `[cheat][give-new]` |
| `init_path` | `springai::Pathing::InitPath` | `[pathing][init]` with path_id |
| `get_approx_length` | `springai::Pathing::GetApproxLength` | `[pathing][len]` with numeric result |
| `get_next_waypoint` | `springai::Pathing::GetNextWaypoint` | `[pathing][waypoint]` |
| `free_path` | `springai::Pathing::FreePath` | `[pathing][free]` |
| `custom` | `CCircuitUnit::CmdCustom` (passthrough) | `[custom-cmd]` with opcode |
| `call_lua_rules` | `springai::Lua::CallRules` | Test-chosen unique payload string. |
| `call_lua_ui` | `springai::Lua::CallUI` | Test-chosen unique payload string. |

**Count in this channel: 15 arms.** BAR's engine log is
line-oriented with stable prefixes, so a substring match is safe.

Note: `call_lua_rules` and `call_lua_ui` are placed in Channel B
because the test sends a unique Lua payload that echoes to the
engine log. If a Lua widget test is needed instead (rare), these
two can be promoted to Channel C via a widget — the map entry
stays but the widget file gets listed in `tests/headless/widgets/README.md`.

## Channel C: Lua-widget / in-memory hook (11 arms)

An arm is in this channel when its effect is visible neither in the
stream nor in the engine log, but a BAR Lua widget attached by the
test can observe it via a BAR callin. The widget exports its
record via `InvokeCallback` under a well-known name.

| Arm | Engine entry point | Lua callin the widget hooks |
|---|---|---|
| `draw_add_point` | `springai::Drawer::AddPoint` | `MapDrawCmd` |
| `draw_add_line` | `springai::Drawer::AddLine` | `DrawInMinimap` |
| `draw_remove_point` | `springai::Drawer::DeletePoint` | `MapDrawCmd` diff |
| `create_spline_figure` | `springai::Drawer::CreateSplineFigure` | `DrawInMinimap` figure record |
| `create_line_figure` | `springai::Drawer::CreateLineFigure` | `DrawInMinimap` figure record |
| `set_figure_position` | `springai::Drawer::SetFigurePosition` | `DrawInMinimap` figure.position field |
| `set_figure_color` | `springai::Drawer::SetFigureColor` | `DrawInMinimap` figure.color field |
| `remove_figure` | `springai::Drawer::RemoveFigure` | `DrawInMinimap` diff |
| `draw_unit` | `springai::Drawer::DrawUnit` | `DrawWorldPreUnit` |
| `group_add_unit` | `springai::Group::AddUnit` | `GroupChanged` call-record |
| `group_remove_unit` | `springai::Group::RemoveUnit` | `GroupChanged` call-record |

**Count in this channel: 11 arms.** The test widgets live at
`tests/headless/widgets/`; the coverage-report target checks that
each Channel-C arm names a widget file that actually exists.

## Totals

Channel A (40) + Channel B (15) + Channel C (11) = **66 arms**,
matching the `AICommand.command` oneof declaration count in
`proto/highbar/commands.proto`.

## Dispatcher contract (FR-012)

The dispatcher's `default:` branch at
`src/circuit/grpc/CommandDispatch.cpp` lines 175–183 (the
"command arm not yet wired" log-and-skip path) is removed. Every
oneof arm has an explicit `case`. Hitting the `default:` branch
becomes an unreachable assertion because the `case` labels cover
every `AICommand::kind_case` enumerator.

Malformed payloads inside a wired arm (missing required sub-field,
out-of-range value) return `grpc::Status::INVALID_ARGUMENT` with a
field path; they do *not* silently succeed. This is the distinction
spec Clarification Q1 drew between "deferred" (forbidden) and
"malformed-payload-rejection" (normal RPC validation).

## Coverage contract (FR-013)

Every arm appears in at least one acceptance script's `# arm-covered:`
header. The coverage-report target fails the build when this is
violated. See `aicommand-coverage-report.md` for the CSV schema.

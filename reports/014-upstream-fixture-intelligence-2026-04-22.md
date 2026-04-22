# Upstream Fixture Intelligence Report

Date: 2026-04-22
Repo: `HighBarV3`
Scope: upstream BARb/CircuitAI and Beyond All Reason game-side Lua fixture analysis for command verification and Itertesting

## Executive Summary

Yes, there is important fixture and command-semantic information in the upstream BARb/CircuitAI and Beyond All Reason sources.

The main finding is that many "missing fixture" or "command did nothing" cases are not explained by the gateway alone. They fall into three distinct buckets:

1. The command is implemented upstream in CircuitAI, but this fork has partially stubbed or altered that helper.
2. The command exists in BAR only when Lua inserts, rewrites, or gates it for specific units.
3. The command exists, but BAR game-side Lua changes its accepted target shape or the evidence channel needed to prove success.

The practical consequence is that Itertesting should not keep treating every weak command result as a generic "need better fixture" problem. Some are fixture gaps, some are fork-vs-upstream parity gaps, and some are command-shape mismatches driven by BAR Lua.

As part of this work, a repo-local intelligence module was added at [upstream_fixture_intelligence.py](/home/developer/projects/HighBarV3/clients/python/highbar_client/behavioral_coverage/upstream_fixture_intelligence.py:1) together with tests at [test_upstream_fixture_intelligence.py](/home/developer/projects/HighBarV3/clients/python/tests/behavioral_coverage/test_upstream_fixture_intelligence.py:1).

## Method

I searched:

- the local HighBarV3 fork
- a fresh upstream clone of `rlcevg/CircuitAI`
- a sparse checkout of `beyond-all-reason/Beyond-All-Reason` focused on `luarules`, `luaui`, `gamedata`, `units`, `weapons`, and `unitdefs`

The goal was to identify:

- whether the command exists upstream
- whether BAR Lua inserts or rewrites the command
- what unit or mod-option preconditions apply
- what observable signal should exist if the command works
- whether the local fork has diverged from the upstream helper

## High-Value Findings

### 1. `set_wanted_max_speed` is not a plain engine command in practice

This is one of the clearest examples of why upstream source mining matters.

Upstream CircuitAI still issues `CMD_WANTED_SPEED` directly in [upstream `CircuitUnit.cpp`](/tmp/CircuitAI-upstream/src/circuit/unit/CircuitUnit.cpp:248). The local fork, however, has `CCircuitUnit::CmdWantedSpeed` commented out in [local `CircuitUnit.cpp`](/home/developer/projects/HighBarV3/src/circuit/unit/CircuitUnit.cpp:317).

BAR game-side behavior is also conditional:

- `unit_wanted_speed.lua` exits immediately unless the `emprework` mod option is enabled in [unit_wanted_speed.lua](/tmp/BAR-game-sparse/luarules/gadgets/unit_wanted_speed.lua:2).
- It only handles gunships and ground/sea movers, not fixed-wing aircraft, in [unit_wanted_speed.lua](/tmp/BAR-game-sparse/luarules/gadgets/unit_wanted_speed.lua:37).
- The effect is applied through `MoveCtrl.SetGunshipMoveTypeData` or `MoveCtrl.SetGroundMoveTypeData`, not through a simple unit-state flag in [unit_wanted_speed.lua](/tmp/BAR-game-sparse/luarules/gadgets/unit_wanted_speed.lua:134).
- The Lua gadget intercepts the command in `AllowCommand` in [unit_wanted_speed.lua](/tmp/BAR-game-sparse/luarules/gadgets/unit_wanted_speed.lua:173).

Implication:

- A failed `set_wanted_max_speed` run can mean:
  - the local fork never issued the command
  - `emprework` was off
  - the selected unit was an unhandled movetype
  - the test looked in the wrong evidence channel

This is not a generic fixture miss. It is a mix of local parity drift and BAR mod-option gating.

### 2. `attack` semantics can be rewritten by BAR Lua

The gateway currently treats `attack.target_unit_id` as a simple raw command dispatch in [CommandDispatch.cpp](/home/developer/projects/HighBarV3/src/circuit/grpc/CommandDispatch.cpp:192).

But BAR can alter attack semantics:

- `cmd_place_target_on_ground.lua` marks units whose weapons have `customParams.place_target_on_ground` in [cmd_place_target_on_ground.lua](/tmp/BAR-game-sparse/luarules/gadgets/cmd_place_target_on_ground.lua:19).
- For those units, the command descriptor is edited so attack becomes `CMDTYPE_ICON_MAP` in [cmd_place_target_on_ground.lua](/tmp/BAR-game-sparse/luarules/gadgets/cmd_place_target_on_ground.lua:53).
- If a unit-target command still arrives, the gadget rewrites it to ground coordinates in [cmd_place_target_on_ground.lua](/tmp/BAR-game-sparse/luarules/gadgets/cmd_place_target_on_ground.lua:96).

Implication:

- Testing unit-target attack semantics with the wrong unit can make a healthy gateway look broken.
- Attack fixtures should explicitly choose a non-rewritten direct-fire unit when the test expects unit-id targeting.

### 3. `dgun` and manual fire are not uniform across units

BAR has a manual-launch gadget:

- It defines a distinct `MANUAL_LAUNCH` command in [cmd_manual_launch.lua](/tmp/BAR-game-sparse/luarules/gadgets/cmd_manual_launch.lua:17).
- It applies to manual-fire units except commanders in [cmd_manual_launch.lua](/tmp/BAR-game-sparse/luarules/gadgets/cmd_manual_launch.lua:21).
- On unit creation, it removes `CMD.MANUALFIRE` and inserts the replacement command in [cmd_manual_launch.lua](/tmp/BAR-game-sparse/luarules/gadgets/cmd_manual_launch.lua:43).

Implication:

- DGun verification should stay commander-only.
- Non-commander manual-fire behavior cannot be treated as the same surface.

### 4. `custom` is not a single behaviorally meaningful command

The gateway supports arbitrary custom command ids via `cmd-custom` in [CommandDispatch.cpp](/home/developer/projects/HighBarV3/src/circuit/grpc/CommandDispatch.cpp:496).

That is too generic for Itertesting to verify meaningfully without upstream command-id metadata. BAR adds or edits many custom commands in Lua:

- `unit_target_on_the_move.lua` inserts custom set-target commands in [unit_target_on_the_move.lua](/tmp/BAR-game-sparse/luarules/gadgets/unit_target_on_the_move.lua:392).
- `unit_builder_priority.lua` inserts the builder priority command in [unit_builder_priority.lua](/tmp/BAR-game-sparse/luarules/gadgets/unit_builder_priority.lua:149).
- `unit_cloak.lua` inserts the `want cloak` command in [unit_cloak.lua](/tmp/BAR-game-sparse/luarules/gadgets/unit_cloak.lua:215).

Implication:

- A generic `custom_target` fixture class is too weak.
- `cmd-custom` should be split by actual command id or owning gadget family before serious coverage work continues.

### 5. BAR exposes real commands that this fork currently stubs or changes

There are local parity gaps that should not be misclassified as fixture problems.

#### `CMD_PRIORITY`

Upstream CircuitAI emits `CMD_PRIORITY` in [upstream `CircuitUnit.cpp`](/tmp/CircuitAI-upstream/src/circuit/unit/CircuitUnit.cpp:280).
The local fork leaves `CmdPriority` commented out in [local `CircuitUnit.cpp`](/home/developer/projects/HighBarV3/src/circuit/unit/CircuitUnit.cpp:362).
BAR Lua exposes builder priority as a real unit command for qualifying builders in [unit_builder_priority.lua](/tmp/BAR-game-sparse/luarules/gadgets/unit_builder_priority.lua:54) and handles it in [unit_builder_priority.lua](/tmp/BAR-game-sparse/luarules/gadgets/unit_builder_priority.lua:206).

#### Cloak support

Upstream CircuitAI emits both `CMD_WANT_CLOAK` and `CMD_CLOAK_SHIELD` in [upstream `CircuitUnit.cpp`](/tmp/CircuitAI-upstream/src/circuit/unit/CircuitUnit.cpp:258).
The local fork only emits `CMD_WANT_CLOAK` in [local `CircuitUnit.cpp`](/home/developer/projects/HighBarV3/src/circuit/unit/CircuitUnit.cpp:334).
BAR replaces the stock cloak command with a Lua-managed `want cloak` command and enforces energy/stun checks in [unit_cloak.lua](/tmp/BAR-game-sparse/luarules/gadgets/unit_cloak.lua:24) and [unit_cloak.lua](/tmp/BAR-game-sparse/luarules/gadgets/unit_cloak.lua:127).

#### `CMD_FIND_PAD`, `CMD_ONECLICK_WEAPON`, `CMD_MISC_PRIORITY`, `CMD_AIR_STRAFE`, `CMD_DONT_FIRE_AT_RADAR`

Upstream CircuitAI still emits these commands in [upstream `CircuitUnit.cpp`](/tmp/CircuitAI-upstream/src/circuit/unit/CircuitUnit.cpp:265).
The local fork leaves several of them stubbed or substitutes a different command in [local `CircuitUnit.cpp`](/home/developer/projects/HighBarV3/src/circuit/unit/CircuitUnit.cpp:341).

Implication:

- Some missing behavior is due to local fork drift, not missing fixtures.

## What This Means For Itertesting

Itertesting is still useful, but it needs a more precise notion of "fixture" and "upstream semantic gate".

The current fixture model in [bootstrap.py](/home/developer/projects/HighBarV3/clients/python/highbar_client/behavioral_coverage/bootstrap.py:159) is a good start, but it is too coarse for commands whose semantics depend on:

- unit class
- mod options
- BAR Lua command insertion
- BAR Lua command rewriting
- command-descriptor type
- rules params or MoveCtrl state rather than plain snapshot diffs

The most important conceptual shift is:

- "missing fixture" should mean "the world state needed for the command is absent"
- it should not absorb:
  - local helper stubs
  - command-id family ambiguity
  - BAR Lua command rewrites
  - mod-option gates

## Recommended Next Steps

### Immediate

1. Keep using Itertesting for coverage growth, but stop treating every weak command as a fixture-only issue.
2. For high-risk commands, consult the new metadata module before classifying the failure cause.
3. Lower sim speed during live verification runs when the goal is diagnosis rather than throughput.

### Short-term code work

1. Repair local helper parity for obviously stubbed surfaces that upstream still supports:
   - `CmdWantedSpeed`
   - `CmdPriority`
   - `CmdFireAtRadar`
   - `CmdManualFire`
   - `CmdMiscPriority`
   - `CmdAirStrafe`
2. Add an Itertesting-side concept of:
   - mod-option gates
   - unit-shape constraints
   - Lua-rewritten command shape
3. Split `cmd-custom` into command-id-specific subcases before trying to "improve" it behaviorally.

### Medium-term

1. Build a mined inventory of BAR custom command ids and owning gadgets.
2. Add a verifier-side notion of expected evidence channel:
   - snapshot diff
   - rules param
   - command-desc mutation
   - MoveCtrl or engine-specific side effect
3. For fixture-sensitive commands, emit richer failure causes:
   - `modoption_gate`
   - `lua_command_not_inserted_for_unit`
   - `lua_rewrites_target_shape`
   - `local_helper_stubbed`

## Deliverables Added

- [upstream_fixture_intelligence.py](/home/developer/projects/HighBarV3/clients/python/highbar_client/behavioral_coverage/upstream_fixture_intelligence.py:1)
- [test_upstream_fixture_intelligence.py](/home/developer/projects/HighBarV3/clients/python/tests/behavioral_coverage/test_upstream_fixture_intelligence.py:1)

These artifacts are deliberately non-invasive. They preserve the upstream findings in a repo-local form that Itertesting can consume later without changing current runtime behavior in this patch.

## Bottom Line

The upstream sources do contain the missing context.

The most useful BAR/Circuit lesson is that "fixture availability" and "command availability" are not the same thing. A command can fail because:

- the world fixture is missing
- the unit never gets that command in BAR
- the command exists only under a mod option
- Lua rewrites the command's parameter shape
- the local fork never emits the upstream command at all

Without separating those causes, Itertesting will keep spending retries on problems that are not actually improvable by better setup.

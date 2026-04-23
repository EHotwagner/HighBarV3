# 017 NullAI enemy-spawner status report

**Date**: 2026-04-23  
**Branch/landing**: `master`, commit `ad875fab "Add NullAI enemy fixture spawner"`  
**Engine**: spring-headless pin `recoil_2025.06.19` (sha `e4f63c1a391f`)  
**Primary workflow**: `tests/headless/itertesting.sh` using `tests/headless/scripts/cheats.startscript`

## 1. Executive summary

The hostile-opponent portion of live Itertesting has been moved from an active enemy BARb AI to a passive `NullAI` setup, with hostile fixtures now provisioned explicitly through a LuaRules-backed enemy spawner.

The change is partially successful:

1. The previous dependence on live hostile AI behavior is removed at the scenario-design level.
2. The Python live bootstrap/reset pipeline can now request a passive enemy fixture explicitly through `call_lua_rules`.
3. The live system has already proven the key control path:
   - coordinator ownership is restored to the correct BARb slot
   - bootstrap completes
   - a bootstrap manifest is emitted
   - `call_lua_rules` batches are forwarded live

The current blocker is no longer hostile interference. The current blocker is a shutdown-time hang inside the plugin/gateway teardown path:

- `circuit::grpc::HighBarService::Shutdown(...)`

That hang appeared in the first successful post-fix NullAI rerun and prevented the run wrapper from finishing cleanly and writing a normal completed report bundle.

## 2. Goal of the change

The user request was to stop running long live workflows against an active hostile AI so that coverage progress would not be distorted by real enemy behavior.

The design chosen was:

1. Switch the opposing side from `BARb` to `NullAI`.
2. Preserve hostile-dependent command coverage by spawning passive enemy units on demand.
3. Keep the hostile fixture surface inside the existing command transport by using `call_lua_rules`, not a new RPC.

This was necessary because:

- `GiveMeNewUnitCommand` does not expose `team_id` in [commands.proto](/home/developer/projects/HighBarV3/proto/highbar/commands.proto:190).
- The C++ cheat path ultimately calls `GiveMeUnit` / `CreateUnit` without a team parameter.
- Engine Lua can create units for an arbitrary team, so LuaRules is the clean targetable spawn surface.

## 3. What landed

### 3.1 LuaRules enemy spawner

A new synced gadget was added at [highbar_enemy_spawner.lua](/home/developer/projects/HighBarV3/tests/headless/LuaRules/Gadgets/highbar_enemy_spawner.lua:1).

Behavior:

- listens for `RecvSkirmishAIMessage`
- accepts messages prefixed with `highbar_spawn_enemy:`
- parses `unitName:x:z[:facing]`
- finds the first non-allied enemy team relative to the sender AI team
- destroys any previously tracked spawned fixture for that AI team
- creates the unit on the enemy team with `Spring.CreateUnit`
- immediately issues `CMD.STOP`
- tracks the spawned unit until destruction

This gives the live Python layer a deterministic way to create a passive visible enemy without depending on enemy AI behavior.

### 3.2 Headless launcher installation

The shared headless launcher now copies repo-local LuaRules gadgets into the write dir before engine launch:

- [_launch.sh](/home/developer/projects/HighBarV3/tests/headless/_launch.sh:57)
- gadget install hook at [_launch.sh](/home/developer/projects/HighBarV3/tests/headless/_launch.sh:142)

This ensures the spawner is available in live headless runs without a separate manual install step.

### 3.3 Python fixture provisioning

The behavioral coverage driver gained a dedicated enemy fixture provisioning path in [__init__.py](/home/developer/projects/HighBarV3/clients/python/highbar_client/behavioral_coverage/__init__.py:675):

- `_call_lua_rules_batch(...)`
- `_wait_for_visible_enemy(...)`
- `_attempt_enemy_fixture_provisioning(...)`

The provisioning logic:

1. refreshes the current bootstrap context
2. returns immediately if `visible_enemies` already yielded a hostile target
3. otherwise computes a spawn position offset from the commander
4. dispatches `call_lua_rules` with `highbar_spawn_enemy:corck:<x>:<z>:west`
5. requests snapshots while waiting for a new visible enemy
6. refreshes the live context once the enemy appears

This path is now integrated into both major live seams:

- after bootstrap completion at [__init__.py](/home/developer/projects/HighBarV3/clients/python/highbar_client/behavioral_coverage/__init__.py:2463)
- after manifest reset at [__init__.py](/home/developer/projects/HighBarV3/clients/python/highbar_client/behavioral_coverage/__init__.py:2624)

The reset integration matters because attack/capture/dgun coverage can legitimately remove the currently tracked hostile fixture.

### 3.4 Startscript changes

All three headless startscripts were converted to use `NullAI` on the opposing team:

- [cheats.startscript](/home/developer/projects/HighBarV3/tests/headless/scripts/cheats.startscript:34)
- [minimal.startscript](/home/developer/projects/HighBarV3/tests/headless/scripts/minimal.startscript:37)
- [minimal-slow.startscript](/home/developer/projects/HighBarV3/tests/headless/scripts/minimal-slow.startscript:37)

Final slot arrangement:

- `AI0` = `NullAI`, team 1
- `AI1` = `BARb`, team 0

That slot order is intentional because `tests/headless/itertesting.sh` exports:

- `HIGHBAR_COORDINATOR_OWNER_SKIRMISH_AI_ID=1`

The coordinator owner therefore must remain skirmish AI id `1`, which now maps to BARb controlling team 0.

## 4. Tests and validation

### 4.1 Focused Python tests

The behavioral registry suite was extended with direct coverage for the new helper:

- spawn-when-missing at [test_behavioral_registry.py](/home/developer/projects/HighBarV3/clients/python/tests/test_behavioral_registry.py:336)
- skip-when-visible at [test_behavioral_registry.py](/home/developer/projects/HighBarV3/clients/python/tests/test_behavioral_registry.py:414)
- bootstrap integration check at [test_behavioral_registry.py](/home/developer/projects/HighBarV3/clients/python/tests/test_behavioral_registry.py:1664)

Validation result:

```bash
uv run --project clients/python pytest -q clients/python/tests/test_behavioral_registry.py -q
```

Passed locally before push.

### 4.2 First live NullAI rerun: owner-slot regression

The first live rerun after the startscript swap failed early:

- report: [itertesting-20260423T090130Z/run-report.md](/home/developer/projects/HighBarV3/reports/itertesting/itertesting-20260423T090130Z/run-report.md:1)
- summary failure: `bootstrap_failed: no commander within 30s`

Root cause:

- `itertesting.sh` pins coordinator ownership to skirmish AI id `1`
- the initial NullAI swap had put `NullAI` in slot `AI1`
- BARb on team 0 became a non-owner client
- gateway log showed:
  - `skipping coordinator client-mode for non-owner skirmishAIId=0 owner=1`

This was a real regression introduced by the first version of the NullAI startscript change.

It was fixed by reversing the AI slot order while keeping `NullAI` on the enemy team.

### 4.3 Second live NullAI rerun: ownership fixed, spawner path active

After the slot fix, a second live rerun proved the new architecture is live:

- BARb owner slot confirmed in [highbar-launch.log](/tmp/hb-run-itertesting/attempt-1/highbar-launch.log:1514)
- NullAI non-owner enemy slot confirmed in [highbar-launch.log](/tmp/hb-run-itertesting/attempt-1/highbar-launch.log:1513)
- gateway endpoint attached on `highbar-1.sock` in [highbar-launch.log](/tmp/hb-run-itertesting/attempt-1/highbar-launch.log:1474)
- coordinator callback traffic hit `highbar-1.sock` in [coord.log](/tmp/hb-run-itertesting/attempt-1/coord.log:31)
- bootstrap emitted a manifest in [itertesting.out](/tmp/hb-run-itertesting/attempt-1/itertesting.out:2)
- `call_lua_rules` batches were forwarded live in [coord.log](/tmp/hb-run-itertesting/attempt-1/coord.log:1228)

This means the following claims are now backed by live evidence:

1. coordinator ownership is correctly aligned with the BARb controller again
2. bootstrap can complete under the NullAI arrangement
3. the new LuaRules enemy-spawner transport path is actually exercised in a real run

## 5. Current blocker

The current blocker is a shutdown-time hang in the engine/plugin teardown path, not hostile AI behavior and not the original bootstrap-reset issue.

Observed evidence:

- repeated watchdog warnings in [highbar-launch.log](/tmp/hb-run-itertesting/attempt-1/highbar-launch.log:12039)
- repeated stack traces pinned at:
  - `circuit::grpc::HighBarService::Shutdown(...)`
  - `circuit::CGrpcGatewayModule::~CGrpcGatewayModule()`
  - `circuit::CCircuitAI::~CCircuitAI()`

Representative lines:

- [highbar-launch.log](/tmp/hb-run-itertesting/attempt-1/highbar-launch.log:12055)
- [highbar-launch.log](/tmp/hb-run-itertesting/attempt-1/highbar-launch.log:12107)
- [highbar-launch.log](/tmp/hb-run-itertesting/attempt-1/highbar-launch.log:12211)

The same active log also flowed into the current engine `infolog.txt`:

- [infolog.txt](/home/developer/.local/state/Beyond%20All%20Reason/engine/recoil_2025.06.19/infolog.txt:12053)

Operational consequence:

- the wrapper never completed normally
- I killed the stuck processes after capturing logs
- no completed second post-fix `run-report.md` bundle exists for that rerun

## 6. Is the current blocker a regression?

Yes, with an important split.

### 6.1 Fixed regression

The first `no commander within 30s` failure was a direct regression from the first NullAI slot arrangement. That regression is already fixed.

### 6.2 Current blocker

The current shutdown hang also appears to be a new regression or at minimum a new blocker introduced by this change boundary.

Reasoning:

1. Earlier April 23 runs completed normally enough to write standard Itertesting bundles and report downstream bootstrap/reset failures such as:
   - [itertesting-20260423T081731Z/run-report.md](/home/developer/projects/HighBarV3/reports/itertesting/itertesting-20260423T081731Z/run-report.md:46)
   - [itertesting-20260423T083911Z/run-report.md](/home/developer/projects/HighBarV3/reports/itertesting/itertesting-20260423T083911Z/run-report.md:40)

2. In the post-fix NullAI rerun, bootstrap and command dispatch progressed further than the earlier owner-slot regression, but the engine then wedged during teardown instead of returning a final bundle.

So the old live blocker remained in bootstrap/reset semantics, while the current live blocker is different and newly visible in shutdown.

## 7. What is no longer blocked

The following points should now be treated as solved or materially improved:

1. Running against an active hostile AI is no longer required by the design.
2. Enemy fixture generation no longer depends on BARb-vs-BARb combat behavior.
3. The proto limitation around `GiveMeNewUnitCommand` team targeting is worked around cleanly through LuaRules.
4. Coordinator ownership under the NullAI arrangement is now correctly restored.
5. The hostile fixture path can be re-established explicitly after bootstrap/reset through `call_lua_rules`.

## 8. What remains uncertain

These points are not yet fully resolved:

1. Whether `capturable_target` / `custom_target` remain consistently populated across long runs after the spawned passive enemy is interacted with repeatedly.
2. Whether the current shutdown hang is caused by:
   - the new LuaRules spawn path itself
   - a new interaction between NullAI lifecycle and gateway teardown
   - a pre-existing teardown bug only exposed once the run got farther under the new setup
3. Whether the hang occurs only on run shutdown or can also distort command verification before teardown.

## 9. Recommended next investigation

The highest-signal next task is not more fixture work. It is shutdown-path diagnosis.

Recommended next steps:

1. Reproduce the shutdown hang with the smallest possible live scenario after one successful `call_lua_rules` enemy spawn.
2. Instrument `HighBarService::Shutdown()` and `CGrpcGatewayModule::~CGrpcGatewayModule()` to identify the joining/waiting thread boundary.
3. Determine whether the service is hanging on:
   - command-stream worker join
   - state-stream worker join
   - coordinator client shutdown
   - service bind/accept loop teardown
4. Only after shutdown is stable, rerun the full NullAI Itertesting workflow and evaluate whether hostile fixtures remain durable enough for `capture`, `custom`, and `dgun`.

## 10. Current status statement

Current status on 2026-04-23:

- NullAI plus explicit enemy spawner is implemented and pushed.
- The temporary owner-slot regression is fixed.
- Live evidence proves the new architecture is active.
- The primary blocker has moved to shutdown hang behavior in `HighBarService::Shutdown()`.

That is the current state of the system.

## 11. Follow-up investigation and local fix

Further code investigation after the report above identified a concrete shutdown-risk path inside the server-side observer stream implementation:

1. `HighBarService::Shutdown()` previously shut down the server and completion queue without first evicting active `StreamState` subscriber slots.
2. `StreamStateCallData` owns a pump thread that can block indefinitely in `SubscriberSlot::BlockingPop()` while idle.
3. `StreamStateCallData::~StreamStateCallData()` previously joined that pump thread before unsubscribing/evicting the slot.

That combination gives a credible explanation for the observed main-thread wedge:

- shutdown begins
- a CQ worker reaches `StreamStateCallData` teardown
- teardown joins the pump
- the pump is still asleep in `BlockingPop()` because no final eviction/wakeup was issued
- `HighBarService::Shutdown()` then blocks forever waiting on `cq_workers_.join()`

Local code changes now in place:

- `DeltaBus::EvictAll(EvictionReason)` was added so service shutdown can evict every subscriber slot up front
- `HighBarService::Shutdown()` now calls `delta_bus_->EvictAll(kCanceled)` before server/CQ shutdown
- `HighBarService::FaultCloseAllStreams()` now calls `delta_bus_->EvictAll(kFault)` so disabled-state teardown wakes the same path
- `StreamStateCallData::~StreamStateCallData()` now unsubscribes/evicts the slot before joining the pump thread
- `StreamState` now maps `kFault` eviction to `UNAVAILABLE` instead of silently finishing `OK`

Focused regression coverage:

```bash
g++ -std=c++20 -pthread -Isrc/circuit tests/unit/delta_bus_test.cc \
  src/circuit/grpc/DeltaBus.cpp \
  src/circuit/grpc/SubscriberSlot.cpp \
  src/circuit/grpc/Counters.cpp \
  -lgtest -lgtest_main \
  -o build/manual-tests/delta_bus_test

./build/manual-tests/delta_bus_test
```

Result:

- all 3 `DeltaBus` tests passed
- the new `EvictAllWakesBlockedConsumers` regression check passed

Important limit:

- this is a code-level root-cause fix plus focused unit coverage
- a fresh live `tests/headless/itertesting.sh` rerun is still required to confirm the original shutdown hang is actually gone in the full NullAI workflow

## 12. Rebuilt-plugin rerun result

After landing the shutdown wakeup patch, I rebuilt the actual BARb plugin used by headless runs:

```bash
cmake --build /home/developer/recoil-engine/build --target BARb -j 8
cp /home/developer/recoil-engine/build/AI/Skirmish/BARb/data/libSkirmishAI.so \
   "$HOME/.local/state/Beyond All Reason/engine/recoil_2025.06.19/AI/Skirmish/BARb/stable/libSkirmishAI.so"
```

The rebuilt runtime `libSkirmishAI.so` was then used for another live `tests/headless/itertesting.sh` attempt.

Result:

- the same shutdown-time watchdog hang still reproduced
- the main-thread stack still pinned at `HighBarService::Shutdown()` waiting in `std::thread::join()`
- therefore the `StreamState`/subscriber wakeup fix is not sufficient to clear the live client-mode teardown wedge

New evidence from the rebuilt rerun:

- the gateway definitely loaded the rebuilt plugin because the shutdown-frame symbol offsets changed from the earlier run
- client-mode is active (`client-mode`, `client-mode-push-stream`, `client-mode-cmd-channel`)
- the engine log shows a very large number of short-lived gateway `role=ai` connections during the run
- there is still no evidence from this workflow that a server-side `StreamState` observer is the critical long-lived shutdown participant

Updated diagnosis:

- the first fix is still worth keeping because it closes a real shutdown hole for server-side observer streams
- however, the live Itertesting blocker has moved to a different gRPC lifecycle path, most likely one of:
  - repeated AI-role unary/session churn (`Hello` / `InvokeCallback`)
  - the long-lived `SubmitCommands` stream
  - another CQ worker/CallData teardown path that remains active in client-mode even when `StreamState` is irrelevant

Next investigation target after this report revision:

1. instrument `HighBarService::Shutdown()` and `CqWorker()` with maintainer-visible logs naming the last active `CallData` type before join
2. add per-RPC teardown logging for `SubmitCommandsCallData` and `InvokeCallbackCallData`
3. rerun the live workflow once those logs are in place so the hanging CQ worker can be tied to a specific RPC class instead of a generic `join()` wait

## 13. Actual shutdown root cause and validation

Temporary CQ-worker instrumentation exposed the real issue:

- every async handler registered its replacement `CallData` **before** checking `ok`
- during CQ shutdown, `ok=false` still caused a fresh pending listener to be created on the already-shutting-down completion queue
- that left the worker with a newly registered request listener that never completed, so `HighBarService::Shutdown()` blocked forever on `cq_workers_.join()`

This affected the async handler families uniformly:

- `Hello`
- `GetRuntimeCounters`
- `StreamState`
- `SubmitCommands`
- `InvokeCallback`
- `Save`
- `Load`
- `RequestSnapshot`

The fix that is now in the codebase:

- every handler now checks `if (!ok) { delete this; return; }` **before** creating its replacement listener
- the earlier `DeltaBus::EvictAll(...)` / `StreamState` teardown fix remains in place as a valid hardening improvement, but it was not the full explanation for the client-mode shutdown wedge

Post-fix validation:

1. Rebuilt BARb and reinstalled the runtime plugin.
2. Reran `tests/headless/itertesting.sh`.
3. Ran direct client-mode shutdown repros with the coordinator relay active.

Most important confirming repro:

- launched `minimal.startscript` through `_launch.sh`
- exported `HIGHBAR_CALLBACK_PROXY_ENDPOINT=unix:/tmp/.../highbar-1.sock` **before** starting the coordinator
- hammered the coordinator `HighBarProxy` surface with repeated `Hello` + `InvokeCallback(40, 149)` calls while the match ran
- observed `count=317` successful/attempted callback-loop iterations and `322` proxied `InvokeCallback` log lines in the coordinator log
- the engine exited naturally (`engine_alive=0`)
- the engine log contained:
  - `Skirmish AI <BARbarIAn-stable>: [hb-gateway] shutdown frames_since_bind=45194`
- the engine log did **not** contain watchdog or hang-detection lines

Updated status:

- the NullAI enemy-spawner change remains landed
- the owner-slot regression is fixed
- the shutdown wedge in `HighBarService::Shutdown()` was traced to async listener replacement during `ok=false` CQ teardown and is now fixed
- direct client-mode shutdown now completes cleanly even under active callback relay pressure

What still remains separate from shutdown:

- live Itertesting can still block early for foundational reasons such as `bootstrap_readiness=resource_starved`
- that is a bootstrap/readiness problem, not the old teardown hang

## 14. Follow-up on the current bootstrap blocker

The next live blocker is confirmed to be bootstrap/readiness, not transport teardown:

- latest live bundle: [itertesting-20260423T093232Z/run-report.md](/home/developer/projects/HighBarV3/reports/itertesting/itertesting-20260423T093232Z/run-report.md:1)
- live client output: [itertesting.out](/tmp/hb-run-itertesting/attempt-1/itertesting.out:1)

Observed live result:

- `bootstrap_failed: bootstrap_readiness=resource_starved`
- `first_required_step=armap`
- economy at failure: `metal:0.0/0.0/1950.0 energy:7788.6/0.0/7861.5`

During follow-up investigation I found a separate report-synthesis bug in Itertesting:

- when live bootstrap aborted early, the run bundle still started fixture inference from a default assumption that several planned live fixtures were already provisioned
- that could incorrectly mark fixtures such as `builder`, `cloakable`, or `hostile_target` as available even though the live session had never established them
- the raw live artifact did **not** support that claim; the session exited immediately after the bootstrap-readiness gate

The reporting fix now in code:

- bootstrap-blocked runs are detected from the preserved `__bootstrap_readiness__` metadata
- fixture inference no longer strips that metadata before deciding baseline availability
- when bootstrap is blocked, only the true baseline fixtures (`commander`, `movement_lane`, `resource_baseline`) are assumed available up front
- other fixture classes stay blocked until live command evidence proves them

Validation for the reporting fix:

```bash
uv run --project clients/python pytest -q \
  clients/python/tests/behavioral_coverage/test_itertesting_runner.py \
  clients/python/tests/behavioral_coverage/test_itertesting_report.py
```

Result:

- `51 passed`

Updated diagnosis after this pass:

- the shutdown regression is fixed
- the current live blocker is a real bootstrap economy/readiness gate
- the Itertesting bundle now reports that blocker more honestly instead of over-claiming fixture availability after an aborted bootstrap

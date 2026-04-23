# 018 Watch Attach Investigation

**Date**: 2026-04-23  
**Repo**: `HighBarV3`  
**Branch**: `master`  
**HEAD at investigation time**: `ee668b75832a` (`Implement 018 live run viewer`)  
**Engine**: `recoil_2025.06.19`  
**Primary workflows**: `tests/headless/itertesting.sh`, `tests/headless/_launch.sh`, watched BAR Native viewer attach

## 1. Executive summary

The original watched-run failure was not one bug. It was two separate failures that happened to present as the same symptom: the graphical spectator client timing out while trying to join the headless host.

Confirmed findings:

1. There was a real plugin bug in `highBar`: the native plugin still bound the local in-process `HighBarService` even when running in coordinator client-mode.
2. That bug is now fixed in the working tree by making client-mode runs skip `HighBarService::Bind()` entirely.
3. After that fix, spectator attach succeeds in controlled repros as long as `highBar` is not also the active coordinator owner.
4. A second bug remained: when `highBar` is the active coordinator owner, the spectator attach still timed out.
5. Follow-up fixes applied:
   - coordinator `PushState` writes now run on a bounded background queue instead of the Spring engine thread
   - active coordinator client construction is deferred until the first live frame, keeping gRPC client channel setup out of Spring's pregame spectator join window
6. Graphical watched attach has now been validated end-to-end: the host accepted `HighBarV3Watch` and logged the spectator as ingame.

This means the watched-run failure was narrowed to the active coordinator client-mode path, not to:

- BNV itself
- watch speed `3`
- the watch viewer startscript format
- the watch widget/gadget patching
- the `highBar` rename as a literal string change

## 2. Question investigated

The user-facing question was effectively:

1. Why does the BNV spectator client fail to attach?
2. Why did this start showing up after moving from the old BARb-named slot to the `highBar` slot?

The key distinction established during the investigation is:

- the viewer attach failure is not the Python/proxy/gRPC connection failing
- it is the separate graphical spectator client failing to join the existing headless game host

## 3. Topology clarified

For watched runs, the repo launches three relevant pieces:

1. A headless Spring host running the actual match.
2. The native `highBar` skirmish AI inside that host.
3. A second graphical Spring client in spectator mode.

Those are separate from the coordinator relay.

The watch client startscript contains only:

- `HostIP`
- `HostPort`
- `SourcePort`
- `MyPlayerName`
- `IsHost=0`

Reference:

- [tests/headless/itertesting.sh](/home/developer/projects/HighBarV3/tests/headless/itertesting.sh:1258)

So the viewer attach failure specifically means:

- the graphical spectator client could not complete its network join to the headless host

It does **not** mean:

- the native plugin could not talk to Python
- the coordinator socket was down
- BNV failed to launch at all

## 4. What changed with the rename

The attach failure correlates with the runtime path that became active after moving to a distinct `highBar` slot, not with the literal string rename by itself.

Relevant changes in topology:

1. The launcher now installs the plugin into a separate `highBar` AI directory instead of only relying on the BARb slot.
   - [tests/headless/_launch.sh](/home/developer/projects/HighBarV3/tests/headless/_launch.sh:122)
2. Startscripts now use `ShortName=highBar`.
   - [tests/headless/scripts/minimal.startscript](/home/developer/projects/HighBarV3/tests/headless/scripts/minimal.startscript:50)
3. The live wrapper explicitly makes skirmish AI id `1` the coordinator owner.
   - [tests/headless/itertesting.sh](/home/developer/projects/HighBarV3/tests/headless/itertesting.sh:1345)
4. Native owner selection is by skirmish AI id, not by AI name.
   - [src/circuit/module/GrpcGatewayModule.cpp](/home/developer/projects/HighBarV3/src/circuit/module/GrpcGatewayModule.cpp:94)

The practical consequence is that the rename caused the `highBar` plugin's own client-mode codepath to become the active path under watched live runs. That exposed bugs that were previously masked by BARb-seeded assumptions and slot ownership history.

## 5. Repro matrix

I ran a sequence of controlled repros to isolate where the attach failure actually lives.

### 5.1 Clean Spring control

Host:

- `spring-headless`
- two `NullAI` skirmish AIs
- spectator player declared in host startscript

Viewer:

- separate graphical `spring`
- plain client startscript with `HostIP/HostPort`

Result:

- attach succeeds
- host logs spectator connection
- viewer receives local player number

Evidence:

- host: [/tmp/hb-attach-wrapper/host.log](/tmp/hb-attach-wrapper/host.log:12882)
- viewer: [/tmp/hb-attach-wrapper/viewer.log](/tmp/hb-attach-wrapper/viewer.log:366)

Conclusion:

- generic Spring host/viewer attach is fine in this environment

### 5.2 `highBar` loaded before native fix

Variants tested:

1. `enable_builtin=false`
2. builtin default profile
3. builtin `macro` profile

Result in all three cases:

- viewer times out after 10s
- host socket remains bound
- `highBar` initializes
- host never logs remote spectator connection

Representative evidence:

- viewer timeout: [/tmp/hb-attach-variants/plugin_only/viewer.log](/tmp/hb-attach-variants/plugin_only/viewer.log:353)
- plugin startup: [/tmp/hb-attach-variants/plugin_only/host.log](/tmp/hb-attach-variants/plugin_only/host.log:1448)
- plugin initialized: [/tmp/hb-attach-variants/plugin_only/host.log](/tmp/hb-attach-variants/plugin_only/host.log:1451)

Conclusion:

- the problem reproduced as soon as `highBar` was loaded, even with builtin logic disabled
- therefore the problem was not specific to the macro profile or AngelScript profile selection

## 6. First confirmed root cause

The first confirmed native issue was in `CGrpcGatewayModule`.

Before the current working-tree patch, the plugin always did this sequence:

1. construct `HighBarService`
2. call `service_->Bind(...)`
3. only afterwards decide whether client-mode coordinator dialing is enabled

The relevant code path is:

- [src/circuit/module/GrpcGatewayModule.cpp](/home/developer/projects/HighBarV3/src/circuit/module/GrpcGatewayModule.cpp:238)

This mattered because the repo already documents that the in-process Spring-side server bind is a known bad interaction:

- [BUILD.md](/home/developer/projects/HighBarV3/BUILD.md:10)

### 6.1 Fix applied

I changed the constructor so that when `HIGHBAR_COORDINATOR` is set:

1. the plugin does **not** call `HighBarService::Bind()`
2. startup is logged as `transport=client-mode`
3. `bind=client-mode-only`

Current working-tree implementation:

- [src/circuit/module/GrpcGatewayModule.cpp](/home/developer/projects/HighBarV3/src/circuit/module/GrpcGatewayModule.cpp:238)

## 7. Validation after the native bind fix

After rebuilding the plugin and making sure `_launch.sh` was using the rebuilt artifact, I reran the minimal attach repro.

### 7.1 `highBar` loaded, no active coordinator owner

Result:

- spectator attach succeeds
- host logs remote spectator connection
- viewer receives local player number

Evidence:

- host startup: [/tmp/hb-attach-verify2/host.log](/tmp/hb-attach-verify2/host.log:1448)
- host spectator connection: [/tmp/hb-attach-verify2/host.log](/tmp/hb-attach-verify2/host.log:26816)
- viewer accepted into match: [/tmp/hb-attach-verify2/viewer.log](/tmp/hb-attach-verify2/viewer.log:368)

Conclusion:

- the native bind fix is real and necessary
- the original all-`highBar` attach failure is no longer universal

## 8. Remaining failure isolated

After the bind fix, I replayed the same watched macro host/client setup under two different environments.

### 8.1 Case A: no active coordinator owner

Result:

- attach succeeds

Evidence:

- host: [/tmp/hb-macro-manual-patched-profile/host.log](/tmp/hb-macro-manual-patched-profile/host.log:42174)
- viewer: [/tmp/hb-macro-manual-patched-profile/viewer.log](/tmp/hb-macro-manual-patched-profile/viewer.log:366)

### 8.2 Case B: active coordinator owner enabled

This case used the same host/client startscripts but also applied `configure_live_attempt_env()`, which exports:

- `HIGHBAR_COORDINATOR_OWNER_SKIRMISH_AI_ID=1`

Reference:

- [tests/headless/itertesting.sh](/home/developer/projects/HighBarV3/tests/headless/itertesting.sh:1342)

Result:

- spectator attach fails again
- host still starts in `client-mode-only`
- viewer times out

Evidence:

- host startup in client-mode-only: [/tmp/hb-macro-manual-configenv/host.log](/tmp/hb-macro-manual-configenv/host.log:1448)
- coordinator client connect banner: [/tmp/hb-macro-manual-configenv/host.log](/tmp/hb-macro-manual-configenv/host.log:1449)
- viewer timeout: [/tmp/hb-macro-manual-configenv/viewer.log](/tmp/hb-macro-manual-configenv/viewer.log:351)

Conclusion:

- the remaining attach failure only appears once `highBar` is the active coordinator owner
- therefore the remaining bug is in the active coordinator client-mode path, not in the watch scripts themselves

## 9. Things ruled out

The following explanations were tested and ruled out:

1. **Watch speed `3`**
   - watched host starts with `MinSpeed=0.0` and `MaxSpeed=10.0`
   - watch speed is applied later through AI Bridge, not as the host's initial attach setting
2. **Viewer-only flag or `_launch.sh` in general**
   - the control repro works through `_launch.sh`
3. **The watch widget/gadget patching**
   - manual attach with the same watch patches succeeds when coordinator ownership is not active
4. **Viewer window profile / 1920x1080 vs smaller**
   - manual attach succeeds with the default watch-profile dimensions too
5. **The literal rename string**
   - owner selection is by skirmish AI id, not by `highBar` text

## 10. Why the rename seemed to cause it

The rename changed more than a string:

1. `highBar` became its own installed skirmish AI slot.
2. The live wrapper explicitly pointed coordinator ownership at skirmish AI id `1`.
3. Startscripts now place `highBar` in that live owner slot.

That meant the renamed `highBar` slot became the one actually running:

- the native plugin constructor path
- the client-mode coordinator connection
- the owner-side relay responsibilities

So the rename exposed bugs in that path. It did not create a failure simply because the AI was called `highBar`.

## 11. Current code and workspace state

Confirmed working-tree code change from this investigation:

- client-mode now skips local `HighBarService::Bind()`
  - [src/circuit/module/GrpcGatewayModule.cpp](/home/developer/projects/HighBarV3/src/circuit/module/GrpcGatewayModule.cpp:238)

Other relevant uncommitted work already present in the tree from the earlier macro-AI task:

- [data/AIOptions.lua](/home/developer/projects/HighBarV3/data/AIOptions.lua:1)
- [tests/headless/_launch.sh](/home/developer/projects/HighBarV3/tests/headless/_launch.sh:1)
- [data/script/macro/main.as](/home/developer/projects/HighBarV3/data/script/macro/main.as:1)
- [tests/headless/scripts/macro-nullai.startscript](/home/developer/projects/HighBarV3/tests/headless/scripts/macro-nullai.startscript:1)

## 12. Best current explanation

The best-supported explanation after the follow-up fixes is:

1. The old all-`highBar` viewer attach failure was partly caused by the plugin still performing the known-bad in-process server bind in client-mode.
2. After fixing that, the remaining failure was triggered when `highBar` was also the active coordinator owner and client-mode relay was live.
3. The final matching mechanism was active coordinator client setup happening during Spring's pregame network join path. Deferring coordinator client construction until live frame startup keeps that path clear for graphical spectator attach.

The hot paths addressed by the follow-up fixes are:

- `CoordinatorClient::PushStateUpdate(...)`
- `CoordinatorClient` construction
- `CGrpcGatewayModule::FlushDelta(...)`
- `CGrpcGatewayModule::EmitKeepAlive(...)`
- `CGrpcGatewayModule::BroadcastSnapshot(...)`
- `CGrpcGatewayModule::OnFrameTick(...)`

The graphical attach fix is now proven end-to-end on the local viewer-capable host. The watched run still ended with `bootstrap_failed: no commander within 30s`, which is separate from the spectator attach failure.

## 13. Recommended next steps

The next debugging pass should target the live coverage/bootstrap path, not BNV attach.

Recommended sequence:

1. Investigate why watched Itertesting still reports `bootstrap_failed: no commander within 30s`.
2. Compare coordinator stream startup and game-frame advancement after the deferred coordinator-client change.
3. Decide whether the live workflow needs an earlier coordinator connection phase that still stays out of pregame spectator attach, or whether the bootstrap issue is in the cheat startscript/provisioning path.

## 14. Bottom line

The statement "this started only because we renamed BARbAI to highBar" is too shallow.

The accurate version is:

- the rename changed the active slot and ownership topology
- that exposed a real plugin bug, which is now fixed in the working tree
- and it exposed a second bug in the active coordinator-owner path, now addressed by moving coordinator push I/O off the engine thread and deferring coordinator client construction until after pregame

That is the current state of the evidence.

## 15. Follow-up fixes

The active coordinator-owner path had two issues:

1. `CGrpcGatewayModule` pushed state updates from engine-thread flush paths into `CoordinatorClient::PushStateUpdate(...)`, and that method performed synchronous gRPC `ClientWriter::Write(...)` calls. Under coordinator backpressure, stream setup, or write blocking, the host engine thread could stall.
2. `CoordinatorClient` itself was constructed during Spring's pregame load/join path. In the active-owner case, that was enough to make the graphical spectator timeout before the host logged a remote connection attempt.

Fixes applied:

- `CoordinatorClient::PushStateUpdate(...)` now only enqueues the state update into a bounded in-memory queue.
- A dedicated push worker owns the long-lived `PushState` client-streaming RPC and performs `Write(...)` calls off the Spring engine thread.
- The queue drops the oldest pending update under sustained backpressure instead of blocking the host loop.
- Shutdown cancels the active push context and joins the worker before coordinator teardown.
- `CGrpcGatewayModule` records the coordinator endpoint during construction but defers active `CoordinatorClient` construction until `OnFrameTick(...)` observes the first live frame.

Validation performed after the fixes:

- `cmake --build ~/recoil-engine/build --target BARb -j2` passed.
- `uv run --project clients/python pytest clients/python/tests/behavioral_coverage/test_bnv_watch.py clients/python/tests/behavioral_coverage/test_watch_registry.py clients/python/tests/behavioral_coverage/test_itertesting_runner.py clients/python/tests/behavioral_coverage/test_itertesting_report.py` passed: 76 tests.
- `tests/headless/test_live_run_viewer.sh` passed after updating its stale `BARb` assertion to the current `highBar` slot name.
- `HIGHBAR_ITERTESTING_WATCH=true HIGHBAR_ITERTESTING_MAX_IMPROVEMENT_RUNS=0 tests/headless/itertesting.sh` passed as a wrapper command and validated graphical attach:
  - host log: `Connection attempt from HighBarV3Watch`
  - host log: `Spectator HighBarV3Watch finished loading and is now ingame`
  - viewer log: `received local player number 1`
  - manifest: `viewer_access.availability_state=available`

Remaining non-attach issue:

- The same watched Itertesting run still ended with `bootstrap_failed: no commander within 30s`; the viewer attach problem is fixed, but live command coverage still has a bootstrap/provisioning blocker.

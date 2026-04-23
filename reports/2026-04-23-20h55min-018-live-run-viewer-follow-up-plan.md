# 018 Live Run Viewer Follow-Up Plan

**Date**: 2026-04-23  
**Repo**: `HighBarV3`  
**Feature context**: `018-live-run-viewer`  
**Primary validation command**: `HIGHBAR_ITERTESTING_WATCH=true HIGHBAR_ITERTESTING_MAX_IMPROVEMENT_RUNS=0 tests/headless/itertesting.sh`  
**Primary run bundle**: `reports/itertesting/itertesting-20260423T205520Z/`  
**Runtime attempt directory**: `/tmp/hb-run-itertesting/attempt-1/`

## 1. Current status

The graphical watched-run attach failure is fixed for the active coordinator-owner path.

The latest watched run proved that BAR's graphical client can attach to the active headless host while `highBar` is the coordinator owner:

- Host log recorded `Connection attempt from HighBarV3Watch`.
- Host log recorded `Spectator HighBarV3Watch finished loading and is now ingame`.
- Viewer log recorded `received local player number 1`.
- Run manifest recorded `viewer_access.availability_state=available`.

The original remaining attach timeout is therefore no longer the blocker.

The remaining failure in the same run is separate:

- `behavioral-coverage: bootstrap_failed: no commander within 30s`
- `direct_verified_total=0`
- `bootstrap_readiness=unknown`
- `callback_diagnostics=bootstrap_failure:missing`
- `transport_status=missing`

This means 018's BNV viewer path is usable, but the live command-coverage workflow still cannot bootstrap command evidence in this configuration.

## 2. Fixes now in the working tree

### 2.1 Client-mode server bind fix

`CGrpcGatewayModule` skips `HighBarService::Bind(...)` when `HIGHBAR_COORDINATOR` is set. Client-mode runs now log:

- `transport=client-mode`
- `bind=client-mode-only`

This avoids the known-bad in-process server bind interaction while Spring is running under the client-mode coordinator topology.

### 2.2 Coordinator PushState off engine thread

`CoordinatorClient::PushStateUpdate(...)` no longer performs synchronous gRPC `ClientWriter::Write(...)` calls from the Spring engine thread.

New behavior:

- Engine-thread callers enqueue `StateUpdate` objects into a bounded queue.
- A dedicated push worker owns the `PushState` stream.
- The push worker stamps `send_monotonic_ns` immediately before handing an update to gRPC.
- Sustained backpressure drops the oldest queued update rather than blocking the host loop.
- Shutdown cancels the active push context and joins the worker.

This preserves engine-thread responsiveness during relay backpressure.

### 2.3 Coordinator client construction deferred until live frame

The decisive attach fix was deferring active `CoordinatorClient` construction until `OnFrameTick(...)` observes the first live frame.

Before the fix, the active owner created gRPC client channels during Spring's pregame load/join path. In that state the graphical spectator never reached the host, and the viewer timed out with:

- `[PreGame::UpdateClientNet] server connection timeout`

After the fix, `CGrpcGatewayModule` records the coordinator endpoint and plugin identity during construction, but creates the actual coordinator client only after pregame has advanced to a live frame. This keeps gRPC client channel setup out of the spectator join window.

## 3. Validation completed

### 3.1 Build

Command:

```bash
cmake --build ~/recoil-engine/build --target BARb -j2
```

Result:

- Passed.
- Rebuilt plugin copied into `build/libSkirmishAI.so` for `_launch.sh`.

### 3.2 Unit and workflow validation

Commands:

```bash
uv run --project clients/python pytest \
  clients/python/tests/behavioral_coverage/test_bnv_watch.py \
  clients/python/tests/behavioral_coverage/test_watch_registry.py \
  clients/python/tests/behavioral_coverage/test_itertesting_runner.py \
  clients/python/tests/behavioral_coverage/test_itertesting_report.py
```

Result:

- Passed: 76 tests.

Command:

```bash
tests/headless/test_live_run_viewer.sh
```

Result:

- Passed.

### 3.3 Graphical watched run

Command:

```bash
HIGHBAR_ITERTESTING_WATCH=true \
HIGHBAR_ITERTESTING_MAX_IMPROVEMENT_RUNS=0 \
tests/headless/itertesting.sh
```

Result:

- Wrapper exited 0.
- Watch preflight succeeded.
- Viewer access was recorded as available.
- Graphical viewer attached successfully.
- The run still ended with `bootstrap_failed: no commander within 30s`.

Relevant artifacts:

- `reports/itertesting/itertesting-20260423T205520Z/manifest.json`
- `reports/itertesting/itertesting-20260423T205520Z/run-report.md`
- `/tmp/hb-run-itertesting/attempt-1/highbar-launch.log`
- `/tmp/hb-run-itertesting/attempt-1/viewer-launch.log`
- `/tmp/hb-run-itertesting/attempt-1/coord.log`

## 4. Remaining blocker

The remaining blocker is not BNV attach. It is live bootstrap/provisioning.

The live campaign connected to the coordinator and launched the viewer, but behavioral coverage did not receive enough live state to identify a commander within the expected 30-second bootstrap window.

Observed output:

```text
behavioral-coverage: connected schema=1.0.0 session=bcov-sess-1
behavioral-coverage: bootstrap_failed: no commander within 30s
```

Run interpretation symptoms:

- No direct command evidence was produced.
- Bootstrap readiness metadata remained unknown.
- Callback diagnostics were missing.
- Runtime capability profile reported `callbacks=none`.
- Transport provisioning remained unresolved.

This could be caused by one or more of:

- coordinator client startup being deferred too late for the Python bootstrap window
- `PushState` stream not opening soon enough after live frame startup
- no snapshot or unit-state event being sent before the bootstrap timeout
- the cheat startscript/provisioning path not creating or exposing the expected commander state
- callback proxy path still pointing at an unavailable `highbar-1.sock` in split setup
- Python bootstrap expecting server-mode callback surfaces that are absent in this client-mode/watched topology

## 5. Investigation plan

### Phase 1: Establish the state stream timeline

Goal: determine whether the coordinator receives any `StateUpdate` messages before behavioral coverage times out.

Actions:

1. Run the watched command with coordinator tracing enabled:

   ```bash
   HIGHBAR_COORDINATOR_TRACE=/tmp/hb-watch-coordinator.trace \
   HIGHBAR_ITERTESTING_WATCH=true \
   HIGHBAR_ITERTESTING_MAX_IMPROVEMENT_RUNS=0 \
   tests/headless/itertesting.sh
   ```

2. Compare timestamps for:
   - gateway startup
   - first live frame
   - deferred coordinator client construction
   - command channel start
   - first heartbeat
   - first PushState stream open
   - first pushed state update
   - Python `bootstrap_failed`

3. Add temporary trace points if needed around:
   - deferred client construction in `OnFrameTick(...)`
   - `CoordinatorClient::OpenPushStateStream()`
   - `CoordinatorClient::PushWorkerLoop()`
   - `BroadcastSnapshot(...)`
   - `EmitKeepAlive(...)`
   - `FlushDelta(...)`

Expected decision:

- If no state reaches the coordinator before timeout, fix coordinator startup or first-state emission.
- If state reaches the coordinator but Python ignores it, fix bootstrap parsing/selection.

### Phase 2: Verify first-state content

Goal: determine whether the first relayed updates contain unit or snapshot data that can identify the commander.

Actions:

1. Instrument the Python coordinator to log:
   - first `PushState` stream open
   - first 10 update `seq` values
   - each update payload case
   - snapshot unit count when payload is `snapshot`
   - delta event counts when payload is `delta`

2. Run a non-watch live command and a watch live command with identical startscript settings.

3. Compare:
   - first update arrival time
   - payload type distribution
   - whether any update contains own-team unit data
   - whether the commander appears in snapshot or delta payloads

Expected decision:

- If updates are only keepalives, force an initial snapshot shortly after coordinator client construction.
- If snapshots exist but lack commander data, inspect `SnapshotBuilder` and team-unit access timing.
- If deltas exist but no unit-created/finished event appears, inspect event hook timing before the coordinator client attaches.

### Phase 3: Confirm callback proxy expectations

Goal: resolve the mismatch where split setup still tries to use a callback proxy endpoint that may not exist.

Evidence from natural smoke:

```text
unix:/tmp/hb-run-itertesting/attempt-smoke/highbar-1.sock: connect failed: No such file or directory
```

Actions:

1. Trace how `HIGHBAR_CALLBACK_PROXY_ENDPOINT` is set in `tests/headless/itertesting.sh`.
2. Confirm whether deferred client-mode intentionally removes the local `highbar-1.sock` callback surface.
3. Verify whether behavioral coverage still requires callback data for:
   - commander def resolution
   - build options
   - economy readiness
   - transport unit def resolution

Expected decision:

- If callbacks are required, provide a valid client-mode callback path through the coordinator.
- If callbacks are optional for watched attach, make bootstrap degrade explicitly instead of timing out on commander discovery.

### Phase 4: Decide whether deferred coordinator startup needs a bounded pregame delay

Goal: avoid reintroducing spectator attach timeouts while still starting coordinator relay early enough for bootstrap.

Candidate strategies:

1. Current strategy: start coordinator client on first live frame.
   - Safest for viewer attach.
   - May be too late if bootstrap expects early state immediately.

2. Start coordinator client after remote spectator is accepted or after a fixed pregame grace delay.
   - Better relay startup timing.
   - Requires a reliable signal or conservative delay.

3. Start coordinator client in constructor only for non-watch runs, and defer only when watch mode is active.
   - Preserves previous non-watch behavior.
   - Requires a native-visible watch-mode signal.

4. Start only the command/heartbeat channel later, but construct an inert client object earlier.
   - Probably not enough, because channel construction itself correlated with the timeout.

Recommended next experiment:

- Keep current first-live-frame deferral.
- Add an immediate initial snapshot request once the coordinator client is constructed.
- Re-run watched Itertesting and check whether commander discovery succeeds without regressing viewer attach.

## 6. Proposed implementation tasks

1. Add structured trace lines for deferred coordinator startup and first push-worker events.
2. Add coordinator-side first-state logging in the test/example coordinator.
3. Add a focused regression script for active-owner watched attach that asserts:
   - viewer received a local player number
   - host logged the viewer as ingame
   - no viewer timeout occurred
4. Add an initial snapshot emission after deferred coordinator client creation if Phase 1 proves no useful state arrives before bootstrap timeout.
5. Fix or reroute callback proxy resolution if Phase 3 confirms the unavailable `highbar-1.sock` is still required.
6. Re-run:
   - Python 018 tests
   - `tests/headless/test_live_run_viewer.sh`
   - graphical watched Itertesting
   - non-watch Itertesting smoke

## 7. Success criteria

BNV attach remains fixed when:

- the graphical viewer receives a local player number
- the host logs the viewer connection attempt
- the host logs the viewer spectator as ingame
- no viewer `server connection timeout` appears

Live bootstrap is fixed when:

- behavioral coverage does not emit `bootstrap_failed: no commander within 30s`
- run manifest records explicit bootstrap readiness metadata
- callback diagnostics are present or explicitly marked unnecessary
- at least one live command evidence path progresses beyond bootstrap

The feature is ready to close when both are true in the same watched run:

- `viewer_access.availability_state=available`
- live bootstrap reaches a usable commander/provisioning state

## 8. Bottom line

The graphical live run viewer is now attachable under the active `highBar` coordinator-owner topology. The next work should not continue treating this as a BNV attach bug. The remaining problem is the live behavioral-coverage bootstrap path: the run can be watched, but command evidence collection cannot yet discover or use the commander state in the watched client-mode topology.

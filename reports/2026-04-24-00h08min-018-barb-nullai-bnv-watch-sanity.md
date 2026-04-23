# 018 BARb vs NullAI BNV Watch Sanity Check — 2026-04-24

## Summary

The requested sanity check was run against the actual BAR graphical client watch path:

- host: `spring-headless`
- viewer: graphical `spring`
- match: `BARb` vs `NullAI`
- viewer identity: `HighBarV3Watch`
- watch mode: direct BNV-style graphical spectator join, not the HighBar coordinator/itertesting wrapper

Result: **PASS**. The graphical watcher connected, loaded the game, reached live simulation frames, and only exited because the test process was intentionally terminated after the 20 second observation window.

This confirms the BAR graphical watcher can attach to and observe a BARb-vs-NullAI game on this host. The current HighBar watched-wrapper failure is therefore not a generic BAR engine, NullAI, BARb, map, or graphical-client networking failure.

## Important Caveat

The installed `BARb/stable` AI in this workspace is not guaranteed to be pristine upstream BARb. The installed tree contains:

```text
~/.local/state/Beyond All Reason/engine/recoil_2025.06.19/AI/Skirmish/BARb/stable/libSkirmishAI.so
~/.local/state/Beyond All Reason/engine/recoil_2025.06.19/AI/Skirmish/BARb/stable/libSkirmishAI.so.upstream-backup
```

The observed logs include `[hb-gateway]` startup from the `BARb` slot, so this `BARb` installation is still the instrumented HighBar/BARb fork rather than a clean upstream binary. Even with that caveat, the test is still valuable: it proves the same engine, same graphical client, same map, same `NullAI`, and a BARb-compatible skirmish slot can be watched successfully when launched with the direct BNV attach timing.

A stricter future control would temporarily restore `libSkirmishAI.so.upstream-backup` into `BARb/stable/libSkirmishAI.so` and rerun the same watch attach.

## Test Setup

The test used `tests/headless/scripts/minimal.startscript` as the base and changed only the AI slot under test plus speed/port:

```text
[AI0]
{
    Name=HighBarV3-team1;
    Team=1;
    ShortName=NullAI;
    Version=0.1;
    Host=0;
}

[AI1]
{
    Name=BARbAI-team0;
    Team=0;
    ShortName=BARb;
    Version=stable;
    Host=0;
}
```

The host was launched with `spring-headless`. The watcher was launched with graphical `spring` using a minimal client startscript:

```text
[GAME]
{
    HostIP=127.0.0.1;
    HostPort=<reserved-port>;
    SourcePort=0;
    MyPlayerName=HighBarV3Watch;
    IsHost=0;
}
```

The watcher was started about one second after the host, which kept it inside the pregame attach window.

## Evidence

The viewer log showed a successful client connection rather than a pregame timeout:

```text
[NetProto::InitClient] connecting to IP 127.0.0.1 on port 39029 using name HighBarV3Watch
[PreGame::UpdateClientNet] added new player "~HighBarV3Watch" with number 1 to team 0 (#active=2)
[Game::ClientReadNet] added new player ~HighBarV3Watch with number 1 to team 0
[Initial Spawn] automatic spawning using default map start positions, in fixed order
```

The viewer reached live frames:

```text
[f=0000695] [SpringApp::Kill][1] fromRun=1
```

The host also reached live frames in the same range:

```text
[f=0000697] ...
```

The viewer did not report:

```text
Error: [PreGame::UpdateClientNet] server connection timeout
```

That timeout is the failure seen in the HighBar watched-wrapper attempts when the graphical viewer exits before watch controls can attach.

## Comparison With Current HighBar Watched Wrapper

The direct BARb-vs-NullAI watch path succeeds. The HighBar watched wrapper still fails differently:

```text
watch_access state=unavailable reason=graphical BAR client exited before watch controls could attach
```

Earlier, before tightening watch reporting, the same underlying viewer exit was often masked by downstream callback-proxy errors such as:

```text
unix:/tmp/hb-run-itertesting/attempt-1/highbar-1.sock: connect failed: Connection refused
```

After the Python watch-recording change, the wrapper now reports the actual first-order watch failure: the graphical BAR client has already exited by the time BNV watch controls are attempted.

## What This Rules Out

This sanity check strongly argues against these explanations:

1. **NullAI inherently breaks watch mode**  
   False. `BARb` vs `NullAI` was watchable.

2. **The graphical BAR client cannot attach to this host at all**  
   False. The graphical client attached to the headless host and reached live frames.

3. **The map or base startscript is generally incompatible with watch mode**  
   False. The check used the same minimal startscript lineage and `Avalanche 3.4`.

4. **The current failure is just caused by the displayed AI name**  
   False. Display names are not the deciding factor; launch timing/topology is.

## What Remains Likely

The remaining HighBar watched-wrapper issue is likely in the launch topology and timing:

1. The successful direct run launches the graphical viewer quickly during the pregame attach window.
2. The HighBar watched wrapper currently waits for gateway startup and other setup before launching the viewer.
3. In the failing wrapper path, the viewer reaches:

   ```text
   Error: [PreGame::UpdateClientNet] server connection timeout
   ```

   then exits.

4. The Python watch layer then attempts bridge controls against a viewer process that is already gone, or now correctly reports it as unavailable.

The strongest hypothesis is therefore:

> The HighBar wrapper launches or validates the graphical watcher too late for the host's accepted join window, or otherwise after the host has transitioned into a state where this client startscript cannot complete the join.

## Related Fixes Already Made During This Investigation

Several fixes landed or were prepared during the broader April 23 investigation. They improve adjacent failures but do not by themselves solve the graphical attach timing:

1. **Deferred coordinator startup**  
   Client-mode coordinator construction is deferred until live frames to avoid Spring pregame join stalls.

2. **Deferred initial coordinator snapshot**  
   Initial snapshot emission is guarded until frame `>= 0` and own units exist.

3. **Coordinator latest snapshot replay**  
   `specs/002-live-headless-e2e/examples/coordinator.py` now replays the latest snapshot to late state subscribers, fixing the earlier `no commander within 30s` symptom.

4. **Deferred local HighBarService bind**  
   Client-mode now defers binding the local callback service until live frames instead of never binding it.

5. **Watch bridge hardening**  
   The Python BNV watch path now retries transient AI Bridge busy errors and applies force-start, speed, pause, and mouse-capture operations more cleanly.

6. **Exited viewer reporting**  
   `launch_viewer()` now checks the viewer PID before claiming watch access is available. This converts misleading downstream callback errors into the more accurate:

   ```text
   graphical BAR client exited before watch controls could attach
   ```

## Recommended Next Step

Change the HighBar watched wrapper to match the successful sanity-check timing:

1. Reserve the watch host port.
2. Start the graphical viewer immediately after the host UDP listener is bound, before waiting for gateway startup or coordinator readiness.
3. Only after the viewer has connected or at least remains alive through the pregame window, continue with HighBar bootstrap/coordinator setup.
4. Add a wrapper-level log assertion that distinguishes:
   - viewer process started
   - viewer connected to host
   - viewer reached live frame
   - AI Bridge controls available

This should be implemented as a focused wrapper/topology change rather than another C++ gRPC change. The BARb-vs-NullAI control demonstrates that the graphical watch client can work when launched with the right timing.

## Reproduction Sketch

The passing sanity check can be reproduced manually with this shape:

```bash
# 1. Create a BARb-vs-NullAI host startscript from minimal.startscript.
#    Set HostPort to a reserved loopback port.
#    Replace the HighBar AI slot with ShortName=BARb, Version=stable.

# 2. Create a graphical watch client startscript:
#    HostIP=127.0.0.1
#    HostPort=<same-port>
#    MyPlayerName=HighBarV3Watch
#    IsHost=0

# 3. Launch host:
tests/headless/_launch.sh \
  --start-script "$HOST_STARTSCRIPT" \
  --runtime-dir "$RUN_DIR/host" \
  --log "$RUN_DIR/host/engine.log" \
  --pid-file "$RUN_DIR/host/engine.pid"

# 4. Launch viewer quickly:
tests/headless/_launch.sh \
  --start-script "$CLIENT_STARTSCRIPT" \
  --engine "$HOME/.local/state/Beyond All Reason/engine/recoil_2025.06.19/spring" \
  --runtime-dir "$RUN_DIR/viewer" \
  --log "$RUN_DIR/viewer/viewer.log" \
  --pid-file "$RUN_DIR/viewer/viewer.pid" \
  --viewer-only true \
  --window-mode windowed \
  --window-width 1280 \
  --window-height 720 \
  --mouse-capture false
```

Success criteria:

```text
[PreGame::UpdateClientNet] added new player "~HighBarV3Watch"
[Game::ClientReadNet] added new player ~HighBarV3Watch
[Initial Spawn]
[f=0000...]
```

Failure criteria:

```text
Error: [PreGame::UpdateClientNet] server connection timeout
```

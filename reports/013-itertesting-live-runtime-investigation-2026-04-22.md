# 013 live-runtime investigation report: coordinator command dispatch hardening

**Date**: 2026-04-22
**Feature**: 013-itertesting-channel-stability
**Branch/landing**: `master`, commit `4f51b71e "Harden live coordinator command dispatch"`
**Engine**: spring-headless pin `recoil_2025.06.19` (sha `e4f63c1a391f`)
**Primary runtime**: client-mode coordinator over gRPC, exercised over both UDS and TCP
**Primary entrypoints**:
- `tests/headless/itertesting.sh`
- `tests/headless/_coordinator.sh`
- `tests/headless/_launch.sh`
- `specs/002-live-headless-e2e/examples/coordinator.py`
- `src/circuit/grpc/CoordinatorClient.cpp`
- `src/circuit/module/GrpcGatewayModule.cpp`

## 1. Executive summary

This investigation started from a live Itertesting failure that looked like a command-channel lifecycle bug:

- `channel_health.status=interrupted`
- `first_failure_stage=dispatch`
- `failure_signal="plugin command channel is not connected dispatcher_rejected"`
- `transport_interruption_total` in the mid-30s
- `direct_verified_total` near zero

The initial hypothesis was that the coordinator command stream itself was unstable. That was only partly true.

The main findings were:

1. The first observed live failure was not a raw gRPC transport bug.
   A real engine-thread wedge in `DispatchCommand()` caused the plugin to stop making forward progress, which later surfaced as a coordinator-side command-channel disconnect.

2. Two malformed external payload classes were sufficient to wedge the engine thread:
   - `build_unit` with `to_build_unit_def_id=0`
   - cheat/default payloads like `give_me(amount=0)` and `give_me_new_unit(unit_def_id=0)`

3. BARb's built-in flows usually avoid these payloads by construction, but the external coordinator path accepts generic proto commands from outside the planner. That path therefore needs explicit defensive validation and dispatch guards.

4. After the fixes landed, live Itertesting changed materially:
   - `channel_health` became `healthy`
   - `transport_interruption_total` fell to `0`
   - the stop boundary moved from `32s` to `70s`
   - `cmd-build-unit`, `cmd-give-me`, and `cmd-move-unit` verified naturally

5. The remaining blockers are no longer transport or command-channel lifecycle blockers. They are now fixture gaps plus a smaller set of predicate-gap / inert-dispatch issues in the Python closeout/report pipeline.

## 2. Initial symptom

Before the runtime fixes, the representative live closeout report looked like this:

- `status=blocked_foundational`
- `channel_health.status=interrupted`
- `failure_signal=plugin command channel is not connected dispatcher_rejected`
- `transport_interruption_total=33` to `36`
- `missing_fixture_total=11`
- `direct_verified_total=0` or `1`

The original interpretation was:

- maybe duplicate AI instances were owning the same coordinator session
- maybe gRPC over Unix sockets was unstable
- maybe the coordinator server-stream was dropping after two batches
- maybe the Python report was misclassifying later commands after a transport break

All of those were plausible. Only some were true.

## 3. Investigation timeline

### 3.1 Duplicate-owner hypothesis

The first real bug found was duplicate coordinator ownership.

`minimal.startscript` launches two BAR AI instances. Both were attempting to create client-mode coordinator sessions using the same plugin identity. That was fixed in:

- [GrpcGatewayModule.cpp](/home/developer/projects/HighBarV3/src/circuit/module/GrpcGatewayModule.cpp)
- [GrpcGatewayModule.h](/home/developer/projects/HighBarV3/src/circuit/module/GrpcGatewayModule.h)

The fix made coordinator client-mode owner-only via `HIGHBAR_COORDINATOR_OWNER_SKIRMISH_AI_ID` with AI `0` as default owner.

Result:

- real bug fixed
- but live Itertesting still failed afterward
- so duplicate ownership was contributing noise, not the terminal cause

### 3.2 Transport hypothesis: UDS vs TCP

To separate socket transport from protocol behavior, `_coordinator.sh` was extended to support:

- `HIGHBAR_COORDINATOR_FORCE_TRANSPORT=auto|uds|tcp`

File:

- [tests/headless/_coordinator.sh](/home/developer/projects/HighBarV3/tests/headless/_coordinator.sh)

Live A/B results:

- gRPC/UDS reproduced the failure
- gRPC/TCP reproduced the same failure

Conclusion:

- not a Unix-domain-socket-only problem
- root cause lived above raw socket transport

### 3.3 Minimal coordinator-only repro

A dedicated repro client was added:

- [specs/002-live-headless-e2e/examples/command_channel_repro.py](/home/developer/projects/HighBarV3/specs/002-live-headless-e2e/examples/command_channel_repro.py)
- [tests/headless/coordinator-command-channel-repro.sh](/home/developer/projects/HighBarV3/tests/headless/coordinator-command-channel-repro.sh)

This repro:

- starts only `coordinator.py`
- opens `OpenCommandChannel` as a fake plugin
- maintains heartbeats
- runs `Hello`
- opens `StreamState`
- sends multiple `SubmitCommands` batches

Results:

- passed over UDS
- passed over TCP
- command stream stayed open

Conclusion:

- the Python coordinator by itself was not the failing surface
- the failure required the real plugin / real engine path

### 3.4 Plugin-side tracing

To observe the live plugin directly, env-gated tracing was added in:

- [CoordinatorClient.cpp](/home/developer/projects/HighBarV3/src/circuit/grpc/CoordinatorClient.cpp)
- [GrpcGatewayModule.cpp](/home/developer/projects/HighBarV3/src/circuit/module/GrpcGatewayModule.cpp)

Trace file:

- `HIGHBAR_COORDINATOR_TRACE=/tmp/.../coordinator-client.trace`

Key trace points:

- command-reader connect/open/read/process
- heartbeat attempts with channel connectivity state
- engine-thread dispatch begin/end

This tracing changed the diagnosis completely.

## 4. Root causes found

### 4.1 `build_unit(def_id=0)` could wedge the engine thread

The first hard failure isolated by trace was:

- `cmd batch read seq=2`
- `cmd batch processed seq=2`
- `dispatch begin kind=build_unit target=...`
- no matching `dispatch end`

The bug was:

- [CircuitAI.h](/home/developer/projects/HighBarV3/src/circuit/CircuitAI.h) treated `unitDefId=0` as valid
- `GetCircuitDefSafe(0)` could return `&defsById[unitDefId - 1]`
- that underflowed the vector index and fed invalid memory into `CmdBuild`

Why it appeared here:

- Itertesting's bootstrap/registry could emit placeholder `to_build_unit_def_id=0`
- built-in BARb planner paths normally would not do that

Applied fix:

- `IsValidUnitDefId()` now requires `unitDefId > 0`
- `DispatchCommand(build_unit)` now explicitly rejects `def_id <= 0`

Files:

- [CircuitAI.h](/home/developer/projects/HighBarV3/src/circuit/CircuitAI.h)
- [CommandDispatch.cpp](/home/developer/projects/HighBarV3/src/circuit/grpc/CommandDispatch.cpp)

Validation:

- focused live repro `attack(0) -> build_unit(0) -> move(valid)` now reaches batch 3
- `cmd-build-unit` later verified naturally in full live Itertesting

### 4.2 Default cheat payloads could also wedge dispatch progress

After the build-unit fix, the next live stop moved later in the sweep. The next focused repro isolated the first cheat arm as the new wedge boundary:

- `give_me(amount=0)`
- `give_me_new_unit(unit_def_id=0)`

These shapes came from the generic minimal/default registry builders, not from BARb planner logic.

Applied fix:

- `give_me` now rejects `amount <= 0`
- `give_me_new_unit` now rejects `unit_def_id <= 0`

File:

- [CommandDispatch.cpp](/home/developer/projects/HighBarV3/src/circuit/grpc/CommandDispatch.cpp)

Validation:

- focused tail-sequence repro now returns clean `dispatch end` for both cheat arms
- full live Itertesting later verified `cmd-give-me` naturally

### 4.3 Coordinator client-mode was bypassing service-path validation assumptions

The service-side validator already had some protection:

- [CommandValidator.cpp](/home/developer/projects/HighBarV3/src/circuit/grpc/CommandValidator.cpp)

But that validator protects the `HighBarService` submission path. The coordinator client-mode path feeds commands from:

- [CoordinatorClient.cpp](/home/developer/projects/HighBarV3/src/circuit/grpc/CoordinatorClient.cpp)

directly into:

- [CommandQueue.cpp](/home/developer/projects/HighBarV3/src/circuit/grpc/CommandQueue.cpp)
- [GrpcGatewayModule.cpp](/home/developer/projects/HighBarV3/src/circuit/module/GrpcGatewayModule.cpp)

So planner-style safety assumptions were not sufficient there. The external seam needed independent guards.

This was the architectural reason the bugs could exist without BARb noticing them in normal play.

## 5. Hypotheses that were disproven

### 5.1 "This is just gRPC over UDS"

Disproved by forced UDS/TCP parity runs.

The failure reproduced over both:

- gRPC/UDS
- gRPC/TCP

### 5.2 "The Python coordinator alone is dropping the command stream"

Disproved by the coordinator-only repro.

The fake-plugin command-stream repro stayed healthy over both transports and delivered all batches.

### 5.3 "The remaining failure is still a pure command-channel lifecycle bug"

No longer true after the dispatcher hardening.

The second full live Itertesting run showed:

- `channel_health.status=healthy`
- `transport_interruption_total=0`

At that point the stop reason shifted away from transport and toward fixture/predicate/report semantics.

## 6. Applied code changes

The landed runtime and diagnostic changes covered these files:

- [src/circuit/CircuitAI.h](/home/developer/projects/HighBarV3/src/circuit/CircuitAI.h)
- [src/circuit/grpc/CommandDispatch.cpp](/home/developer/projects/HighBarV3/src/circuit/grpc/CommandDispatch.cpp)
- [src/circuit/grpc/CoordinatorClient.cpp](/home/developer/projects/HighBarV3/src/circuit/grpc/CoordinatorClient.cpp)
- [src/circuit/grpc/CoordinatorClient.h](/home/developer/projects/HighBarV3/src/circuit/grpc/CoordinatorClient.h)
- [src/circuit/module/GrpcGatewayModule.cpp](/home/developer/projects/HighBarV3/src/circuit/module/GrpcGatewayModule.cpp)
- [src/circuit/module/GrpcGatewayModule.h](/home/developer/projects/HighBarV3/src/circuit/module/GrpcGatewayModule.h)
- [tests/headless/_coordinator.sh](/home/developer/projects/HighBarV3/tests/headless/_coordinator.sh)
- [specs/002-live-headless-e2e/examples/coordinator.py](/home/developer/projects/HighBarV3/specs/002-live-headless-e2e/examples/coordinator.py)
- [specs/002-live-headless-e2e/examples/command_channel_repro.py](/home/developer/projects/HighBarV3/specs/002-live-headless-e2e/examples/command_channel_repro.py)
- [tests/headless/coordinator-command-channel-repro.sh](/home/developer/projects/HighBarV3/tests/headless/coordinator-command-channel-repro.sh)
- [specs/002-live-headless-e2e/examples/ai_client.py](/home/developer/projects/HighBarV3/specs/002-live-headless-e2e/examples/ai_client.py)
- [.github/runner-setup/build-plugin.sh](/home/developer/projects/HighBarV3/.github/runner-setup/build-plugin.sh)

Functionally, those changes fall into four buckets:

1. runtime hardening
2. owner-AI coordinator session gating
3. transport-selection diagnostics
4. focused repro tooling and trace instrumentation

## 7. Validation evidence

### 7.1 Focused repro: invalid trio

Sequence:

- `attack(target_unit_id=0)`
- `build_unit(to_build_unit_def_id=0)`
- `move_unit(valid)`

Before fix:

- engine thread stopped at `dispatch begin kind=build_unit`
- batch 3 never reached dispatch

After fix:

- `dispatch end kind=build_unit`
- `cmd batch read seq=3`
- `dispatch end kind=move_unit`

### 7.2 Focused repro: tail/default sequence

Sequence:

- `give_me`
- `give_me_new_unit`
- `group_add_unit`
- `group_remove_unit`
- `init_path`
- `move_unit`

Before cheat guards:

- first cheat arm entered dispatch and never cleanly returned

After cheat guards:

- both cheat arms logged clean `dispatch end`
- later sequence continued cleanly
- engine log showed explicit non-fatal dispatch errors:
  - `give_me: invalid amount <= 0`
  - `give_me_new_unit: invalid def_id <= 0`

### 7.3 Full live Itertesting: before hardening

Representative run:

- `runtime_seconds=32`
- `channel_health.status=interrupted`
- `transport_interruption_total=33`
- `direct_verified_total=3/47` was not yet achieved; earlier runs were lower
- foundational blockers were dominated by `validation_gap` entries tied to `plugin command channel is not connected`

### 7.4 Full live Itertesting: after hardening

Live run:

- `/tmp/hb-itertesting-postfix2/reports/itertesting-20260422T163347Z/run-report.md`

Results:

- `runtime_seconds=70`
- `channel_health.status=healthy`
- `first_failure_stage=none`
- `failure_signal=none`
- `commands_attempted_before_failure=37`
- `transport_interruption_total=0`
- `missing_fixture_total=11`
- `direct_verified_total=3/47`

Newly verified:

- `cmd-build-unit`
- `cmd-give-me`
- `cmd-move-unit`

Remaining foundational blockers:

- `cmd-attack`
- `cmd-fight`
- `cmd-patrol`
- `cmd-set-auto-repair-level`
- `cmd-set-base`
- `cmd-set-idle-mode`

All were reported as `inert_dispatch` / predicate-gap style issues rather than transport interruption.

## 8. What this means technically

The most important state change is this:

Before the fixes, the closeout path was lying about the dominant cause. It looked like a channel-lifecycle collapse. In practice, malformed external payloads were freezing engine-thread dispatch, and that eventually surfaced as a command-channel disconnect.

After the fixes:

- the live coordinator command path itself is healthy enough to continue
- malformed placeholder payloads no longer wedge the engine thread
- the remaining closeout failures are mostly about fixture coverage and how Python classification/reporting treats non-verified or weakly-verified arms

That changes the task ordering.

## 9. Remaining gaps

### 9.1 Fixture coverage remains a real blocker

The live profile still lacks:

- `capturable_target`
- `custom_target`
- `payload_unit`
- `restore_target`
- `transport_unit`
- `wreck_target`

This keeps `missing_fixture_total=11` and still blocks normal closeout.

### 9.2 Several arms are being treated as foundational `inert_dispatch`

These are not transport failures anymore. They fall into two groups:

1. real behavior may be weak or not happening
   - `attack`
   - `fight`

2. no reliable snapshot-diff predicate exists yet
   - `patrol`
   - `set_auto_repair_level`
   - `set_base`
   - `set_idle_mode`

Those should likely not all remain foundational blockers in the same way transport interruption was.

### 9.3 Registry/builders still emit planner-unlike default payloads

The registry in:

- [clients/python/highbar_client/behavioral_coverage/registry.py](/home/developer/projects/HighBarV3/clients/python/highbar_client/behavioral_coverage/registry.py)

still uses generic minimal/default builders for several query, cheat, and global arms. That is useful for serialization coverage, but it does not resemble how BARb internally constructs commands.

We now guard those safely in C++, but input shaping should still improve.

## 10. Recommended next steps

### 10.1 Python/reporting closeout work

Priority: high

Adjust the closeout/report pipeline so that:

- healthy channel runs are no longer smeared by transport semantics
- arms with "no reliable verifier yet" are treated as evidence gaps, not necessarily foundational runtime defects
- foundational blocker promotion is limited to real runtime contract failures, not generic `effect_not_observed`

Targets:

- [live_failure_classification.py](/home/developer/projects/HighBarV3/clients/python/highbar_client/behavioral_coverage/live_failure_classification.py)
- [itertesting_report.py](/home/developer/projects/HighBarV3/clients/python/highbar_client/behavioral_coverage/itertesting_report.py)
- [itertesting_runner.py](/home/developer/projects/HighBarV3/clients/python/highbar_client/behavioral_coverage/itertesting_runner.py)

### 10.2 Registry input shaping

Priority: medium

For externally generated test commands, prefer BARb-like valid payloads where practical:

- real build defs instead of `0`
- meaningful cheat payloads when cheats are enabled
- explicit query/group/path parameters where the arm expects them

This reduces noise and keeps live closeout focused on behavior instead of malformed inputs.

### 10.3 Keep dispatcher guards permanently

Priority: high

Do not remove the C++ guards just because registry/builders improve. The external seam accepts arbitrary callers. Defensive validation at dispatch remains necessary.

### 10.4 Add regression tests for the newly found malformed payload classes

Priority: high

Add unit or integration coverage for:

- `build_unit(def_id=0)` does not wedge and returns safely
- `give_me(amount<=0)` does not wedge
- `give_me_new_unit(def_id<=0)` does not wedge

That should live near:

- `tests/unit/command_validation_test.cc`
- `tests/integration/ai_move_flow_test.cc`

or a new focused integration test for the coordinator client-mode queue/drain seam.

## 11. Final conclusion

The investigation achieved the main runtime goal:

- the live command path is no longer failing because malformed external payloads wedge engine-thread dispatch
- coordinator channel health is now good enough for real closeout interpretation
- transport interruption is no longer the dominant blocker

The feature is not fully closed out, but the problem category changed decisively.

The next work is no longer "fix the command channel." It is:

- fixture provisioning
- predicate-gap handling
- closeout/report semantics for non-verified arms

That is a healthier place to be than the initial state, because the live runtime path is now stable enough to make those distinctions honestly.

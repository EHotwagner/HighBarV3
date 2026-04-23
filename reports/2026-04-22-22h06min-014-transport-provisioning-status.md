# 014 Transport Provisioning Status

Date: 2026-04-22
Branch: `014-fixture-bootstrap-simplification`
Head at write-up: `5dae1f38`

## Executive Summary

Feature 014 is materially improved and no longer blocked by broad fixture-model ambiguity.

Current live status:
- `wreck_target` is now provisioned in live Itertesting.
- `transport_unit` is the only remaining real missing fixture.
- The latest prepared live run blocks only 5 commands, all transport-dependent:
  - `cmd-load-onto`
  - `cmd-load-units`
  - `cmd-load-units-area`
  - `cmd-unload-unit`
  - `cmd-unload-units-area`

Latest authoritative run:
- Report: [run-report.md](/home/developer/projects/HighBarV3/reports/itertesting/itertesting-20260422T195308Z/run-report.md)
- Run id: `itertesting-20260422T195308Z`
- Campaign id: `itertesting-campaign-20260422T195300Z`

Bottom line:
- The remaining problem is no longer reporting or fixture classification.
- The remaining problem is real transport provisioning in the live client-mode workflow.

## Current Validated State

The latest prepared live Itertesting run shows:
- `direct_verified=4/47`
- `contract_health=blocked_foundational`
- `transport_unit=missing`
- `wreck_target=provisioned`
- `commands blocked by fixture=5`

From [run-report.md](/home/developer/projects/HighBarV3/reports/itertesting/itertesting-20260422T195308Z/run-report.md):
- planned fixtures include `transport_unit`
- provisioned fixtures include everything except `transport_unit`
- affected commands are only the five load/unload commands

This is a substantial reduction from earlier runs on 2026-04-22:
- `itertesting-20260422T192546Z`: 8 affected commands, missing `cloakable`, `payload_unit`, `transport_unit`, `wreck_target`
- `itertesting-20260422T194512Z`: 7 affected commands, only `transport_unit` and `wreck_target` missing
- `itertesting-20260422T195308Z`: 5 affected commands, only `transport_unit` missing

## What Was Fixed

### 1. False and inflated fixture blockers

The live fixture path previously overstated missing dependencies.

Fixed areas:
- load/unload rows no longer mark `payload_unit` missing when only `transport_unit` is absent
- `cmd-build-unit` no longer falsely requires a separate `builder` fixture in the authoritative dependency map
- `cmd-self-destruct` no longer depends on a narrow `cloakable`-only interpretation
- live failure classification now trusts exact missing-fixture detail when the run already identified the specific missing class

Relevant files:
- [bootstrap.py](/home/developer/projects/HighBarV3/clients/python/highbar_client/behavioral_coverage/bootstrap.py)
- [__init__.py](/home/developer/projects/HighBarV3/clients/python/highbar_client/behavioral_coverage/__init__.py)
- [live_failure_classification.py](/home/developer/projects/HighBarV3/clients/python/highbar_client/behavioral_coverage/live_failure_classification.py)
- [itertesting_runner.py](/home/developer/projects/HighBarV3/clients/python/highbar_client/behavioral_coverage/itertesting_runner.py)

### 2. Disposable unit selection for `self_destruct`

The selector was widened and reordered so the live runner prefers disposable non-commander units, with a bias toward ground-capable candidates before air-only ones.

This mattered because:
- it removed `self_destruct` as a false or secondary foundational blocker
- it helped the runner produce usable downstream evidence for corpse-related handling

Relevant file:
- [registry.py](/home/developer/projects/HighBarV3/clients/python/highbar_client/behavioral_coverage/registry.py)

### 3. `wreck_target` recovery

Two changes closed the `wreck_target` gap:
- `SnapshotBuilder.cpp` now fills `map_features` instead of leaving feature snapshots empty
- the Python bootstrap now falls back to a second reclaimable feature in the current snapshot when client-mode does not surface a `feature_created` delta

This was compile-validated through the intended engine-root build:
- `cmake --build /home/developer/recoil-engine/build --target BARb -j 8`

The rebuilt `libSkirmishAI.so` was installed into the BAR runtime and used for the later live reruns.

Relevant files:
- [SnapshotBuilder.cpp](/home/developer/projects/HighBarV3/src/circuit/grpc/SnapshotBuilder.cpp)
- [__init__.py](/home/developer/projects/HighBarV3/clients/python/highbar_client/behavioral_coverage/__init__.py)

## What Still Fails

Only the transport fixture remains unprovisioned in the live workflow.

The current live path in [__init__.py](/home/developer/projects/HighBarV3/clients/python/highbar_client/behavioral_coverage/__init__.py) still handles `transport_unit` passively:
- it looks for an own unit with `max_health ~= 265.0`
- that corresponds to `armatlas`
- if such a unit is not already present, the runner does nothing to create one

So the current logic is:
- detect if a transport already exists
- otherwise classify transport-dependent commands as fixture-blocked

That is not provisioning. It is discovery-only.

## Why This Is The Real Remaining Blocker

The transport commands in [registry.py](/home/developer/projects/HighBarV3/clients/python/highbar_client/behavioral_coverage/registry.py) are already wired correctly once the fixture exists:
- they know how to use `transport_unit`
- they know how to use `payload_unit`
- they already emit meaningful `load_*` / `unload_*` commands

The only missing piece is a reliable way to produce a live transport unit before those commands run.

## Native BAR Facts Relevant To Provisioning

From the current sparse BAR data:
- the ARM air factory builds `armatlas` and `armhvytrans`
- source: `/tmp/BAR-game-sparse/units/ArmBuildings/LandFactories/armap.lua`
- `armatlas` health is `265`
- source: `/tmp/BAR-game-sparse/units/ArmAircraft/armatlas.lua`
- `armhvytrans` health is `630`
- source: `/tmp/BAR-game-sparse/units/ArmAircraft/armhvytrans.lua`

This means the current live heuristic is too narrow even as a discovery path:
- it only recognizes `armatlas`
- it ignores `armhvytrans`

Even if a heavy transport exists, the runner would currently still miss it.

## Architectural Constraint

The current blocker is not missing protobuf schema. The protobuf types already exist.

Existing contracts already include:
- `InvokeCallback` in [service.proto](/home/developer/projects/HighBarV3/proto/highbar/service.proto)
- callback request/response types and callback IDs in [callbacks.proto](/home/developer/projects/HighBarV3/proto/highbar/callbacks.proto)
- `GiveMeNewUnitCommand` in [commands.proto](/home/developer/projects/HighBarV3/proto/highbar/commands.proto)

The real transport-layer gap is in the client-mode coordinator:
- [coordinator.py](/home/developer/projects/HighBarV3/specs/002-live-headless-e2e/examples/coordinator.py)
- it exposes `Hello`, `StreamState`, and `SubmitCommands`
- it does not forward `InvokeCallback`

So:
- the plugin-side minimal `InvokeCallback` bridge now exists
- but the maintainer live endpoint used by Itertesting cannot call it
- therefore the Python runner cannot yet resolve runtime `def_id_by_name` through the actual client-mode path

## What “Real Provisioning” Means

Real transport provisioning should mean all of the following:

1. Detect that no usable transport currently exists.
2. Resolve a native transport unit def at runtime.
3. Issue a command to create one naturally if the environment allows it.
4. Confirm that the created unit is actually transport-capable and alive.
5. Refresh or replace it if lost before later load/unload commands execute.

The current system only does step 1 partially and step 4 heuristically.

## Viable Next Steps

### Option A: Coordinator `InvokeCallback` forwarding plus natural transport provisioning

This is the best next step.

Work:
- add `InvokeCallback` forwarding to [coordinator.py](/home/developer/projects/HighBarV3/specs/002-live-headless-e2e/examples/coordinator.py)
- use existing callback contracts to build `def_id_by_name`
- teach the live bootstrap to resolve `armatlas` and `armhvytrans`
- track `factory_air` as a usable live builder capability
- add an `ensure_transport_unit()` step that issues `build_unit` from the air factory and waits for a transport to appear
- accept either `armatlas` or `armhvytrans` as satisfying `transport_unit`

Pros:
- shared infrastructure, not Python-only at the gRPC layer
- uses existing protobuf contracts
- supports natural live provisioning
- can be reused by any future client that speaks the same RPC

Cons:
- requires coordinator work, not just behavioral-coverage Python edits
- still leaves higher-level provisioning policy in the client unless abstracted further

### Option B: Expand passive discovery only

Work:
- recognize both `armatlas` and `armhvytrans`
- improve snapshot heuristics for transport detection

Pros:
- low effort
- may recover some cases if a transport already appears naturally

Cons:
- not real provisioning
- still nondeterministic
- still fails when no transport is present

This is not sufficient to close 014.

### Option C: Cheat-assisted transport creation fallback

Work:
- use `GiveMeNewUnitCommand` to spawn a transport when natural provisioning fails
- still requires runtime def-id resolution or hardcoded unit-def ids

Pros:
- may be fastest to make the fixture exist

Cons:
- not appropriate as the default path
- still blocked on reliable def-id resolution unless hardcoded
- hardcoding BAR unit-def ids is brittle across game revisions

Reasonable only as a fallback after natural provisioning.

### Option D: Server-side fixture provisioning abstraction

Work:
- move fixture provisioning logic into the plugin/server side
- client asks for a fixture class, not a specific unit-def workflow

Pros:
- avoids duplicating policy across multiple clients
- strongest long-term abstraction

Cons:
- much larger design change
- outside the narrowest path to finishing 014
- likely implies new higher-level contracts or plugin-owned policy surfaces

This is a longer-term architecture option, not the pragmatic next move.

## Recommended Implementation Sequence

1. Forward `InvokeCallback` through the client-mode coordinator.
2. In the Python live bootstrap, populate `def_id_by_name` through the real client-mode endpoint.
3. Track `factory_air` in `BootstrapContext`.
4. Add a natural `ensure_transport_unit()` path:
   - prefer `armatlas`
   - accept `armhvytrans` as fallback
5. Expand transport detection from a single health heuristic to capability-aware recognition.
6. Only if natural provisioning stalls, optionally use cheat fallback.
7. Rerun prepared live Itertesting until the transport commands are no longer fixture-blocked.

## Acceptance Criteria For The Remaining Work

The remaining work should be considered complete when a prepared live Itertesting run shows:
- `transport_unit=provisioned`
- `payload_unit=provisioned`
- no load/unload commands blocked by missing fixtures
- no regression in channel health
- no regression in the current `wreck_target` behavior

At that point, the foundational fixture blocker set for 014 should be eliminated.

## Additional Notes

- The current repo state is much better than the earlier 014 baseline; the work already removed broad fixture ambiguity and isolated the last true blocker.
- The remaining problem is now specific enough that future work should avoid more report-layer tuning and go directly to transport provisioning.
- The protobuf layer is not missing types; the missing piece is forwarding and use of the existing RPC in client-mode.


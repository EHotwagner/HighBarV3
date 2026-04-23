# Project State Audit

Date: 2026-04-23
Repo: `HighBarV3`
Branch at audit time: `master`
HEAD at audit time: `277044b1e823411809daf6e1cea34d6640023831` (`Implement live bootstrap hardening`)

## Executive Summary

The project is in a mixed but understandable state.

As a transport and relay layer, HighBarV3 is now credible. The client-mode architecture of plugin -> coordinator -> external client is implemented, exercised by automated tests, and the isolated coordinator relay path works for `Hello`, `StreamState`, `SubmitCommands`, and callback forwarding. The Python client and the synthetic Itertesting/reporting stack are in good shape.

As a fully functional remote AI runtime for prepared live closeout, the project is not there yet. The latest checked-in live evidence still shows `blocked_foundational`, `direct_verified_total=0`, `bootstrap_readiness=resource_starved`, and a large fixture deficit. The codebase now models capability-limited runtimes and records better bootstrap/callback semantics, but there is not yet a new checked-in post-016 live rerun proving that the hardened reporting surfaces appear correctly on a real host.

The short version is:

- The proxy/relay works.
- The reporting and synthetic validation work.
- Runtime prerequisite lookup works on the narrow supported callback path.
- Prepared live closeout is still blocked by environment/bootstrap reality, not by raw transport.
- Several key seams remain brittle enough that calling this a fully functional remote AI would be overstating the current state.

## Validation Run

I ran the executable tests that are available from this checkout without a live BAR headless runtime:

- `uv run --project clients/python pytest -q -rs`
  Result: `140 passed, 4 skipped in 0.76s`
  Skips:
  - `clients/python/tests/test_ai_role.py` x2 because `HIGHBAR_UDS_PATH + HIGHBAR_TOKEN_PATH` are not set
  - `clients/python/tests/test_observer.py` x2 because `HIGHBAR_UDS_PATH` is not set
- `tests/headless/test_command_contract_hardening.sh`
  Result: `PASS`
- `tests/headless/test_itertesting_campaign.sh`
  Result: `PASS`
- `tests/headless/test_live_itertesting_hardening.sh`
  Result: `PASS`
- `bash tests/headless/coordinator-command-channel-repro.sh`
  Result: `PASS transport=uds`
  Evidence:
  - `Hello OK`
  - `SubmitCommands ack ... accepted=1` for three batches
  - command-channel batches received in order
  - state stream remained live through the repro

I also checked the C++/CTest surface:

- `ctest --test-dir build -N`
  Result: `Total Tests: 0`

That is not a test failure in the feature code itself. This checkout simply does not contain a configured CMake build tree right now:

- no `build/CMakeCache.txt`
- no `build/CTestTestfile.cmake`
- no generated `highbar-root-tests.cmake`

So the C++ test sources exist, but root `ctest` is not runnable from the current workspace state.

## Recent Landed Features and What They Changed

The last meaningful feature sequence is coherent:

- `013` / `4f51b71e Harden live coordinator command dispatch`
  This was the turning point from "maybe transport is broken" to "the engine/plugin dispatch path was being wedged by malformed payloads." The investigation report in [reports/2026-04-22-18h42min-013-itertesting-live-runtime-investigation.md](./2026-04-22-18h42min-013-itertesting-live-runtime-investigation.md) shows that UDS vs TCP was not the root issue; the real bug was unsafe payload handling causing engine-thread loss of progress.
- `014` / `a1a5ddbe 014 fixture bootstrap simplification`
  This reduced false fixture blockers, improved fixture classification, and recovered some previously missing fixture evidence such as `wreck_target`. The checked-in status report in [reports/2026-04-22-22h06min-014-transport-provisioning-status.md](./2026-04-22-22h06min-014-transport-provisioning-status.md) shows the blocker narrowed down to real transport provisioning rather than general fixture ambiguity.
- `015` / `2c029a77 Land 015 live transport provisioning`
  This added transport provisioning semantics, supported transport variants, callback relay usage for runtime def resolution, and stronger reporting around transport-specific failures.
- `016` / `217f8329` and `277044b1`
  This adds bootstrap-readiness reporting, runtime capability profiling, callback-diagnostic retention, map-source decisions, and a better standalone build probe path for callback-limited hosts.

The overall trajectory is good: each feature is removing ambiguity and converting vague "live run failed" outcomes into narrower, evidence-backed failure classes.

## What Works Today

### 1. The core remote proxy pattern works

The project's central architectural choice is the client-mode coordinator:

- plugin dials outward to `HighBarCoordinator`
- external tools dial `HighBarProxy`
- the coordinator relays state and commands between them

That is implemented in:

- [specs/002-live-headless-e2e/examples/coordinator.py](../specs/002-live-headless-e2e/examples/coordinator.py)
- [src/circuit/grpc/CoordinatorClient.cpp](../src/circuit/grpc/CoordinatorClient.cpp)
- [src/circuit/grpc/CoordinatorClient.h](../src/circuit/grpc/CoordinatorClient.h)

What is concretely working:

- plugin heartbeat path
- plugin `PushState` stream to coordinator
- coordinator fan-out to `StreamState` observers
- external `SubmitCommands` forwarding to the plugin command channel
- minimal `InvokeCallback` relay path
- Python client handshake in [clients/python/highbar_client/session.py](../clients/python/highbar_client/session.py)

The isolated coordinator repro passed cleanly and is strong evidence that the relay architecture itself is not the current blocker.

### 2. Python client and reporting surfaces are healthy

The Python client/test surface is currently the strongest part of the repo:

- `140 passed, 4 skipped`
- the skipped tests are live-environment skips, not logic failures
- Itertesting reporting, semantic-gate modeling, bootstrap metadata, and hardened synthetic scenarios all passed

The main reporting and orchestration surfaces are under:

- [clients/python/highbar_client/behavioral_coverage/__init__.py](../clients/python/highbar_client/behavioral_coverage/__init__.py)
- [clients/python/highbar_client/behavioral_coverage/itertesting_runner.py](../clients/python/highbar_client/behavioral_coverage/itertesting_runner.py)
- [clients/python/highbar_client/behavioral_coverage/itertesting_report.py](../clients/python/highbar_client/behavioral_coverage/itertesting_report.py)

### 3. Runtime prerequisite lookup works on the limited callback host

This is one of the most important practical wins.

The latest checked-in live bundle at [reports/itertesting/itertesting-20260423T055133Z/run-report.md](./itertesting/itertesting-20260423T055133Z/run-report.md) shows:

- `armmex` prerequisite resolution succeeded
- `resolved_def_id: 149`
- callback path: `InvokeCallback/armmex`

The 016 hardening explicitly narrows def resolution to the two callback surfaces the live probe proved useful:

- `CALLBACK_GET_UNIT_DEFS` (`47`)
- `CALLBACK_UNITDEF_GET_NAME` (`40`)

That is the correct shape for a callback-limited runtime.

### 4. Transport loss is no longer the main explanation for live failures

This is a major maturity signal.

The 013 investigation established that the primary failures were not raw UDS/TCP instability. The newest live checked-in bundle still shows:

- `Channel Health: healthy`
- `transport_interruption_total: 0`

So the project has moved past the earlier "the wire itself is broken" phase.

## What Does Not Work, Or Is Not Yet Proven

### 1. Prepared live closeout is still not functioning as a full remote AI workflow

The newest checked-in live run is still fundamentally blocked:

- run: `itertesting-20260423T055133Z`
- `contract_health=blocked_foundational`
- `direct_verified_total=0`
- `missing_fixture_total=47`
- `bootstrap_readiness=resource_starved`

The immediate blocker is not command relay. It is that the prepared live environment starts from a state where the first commander-built bootstrap step is not realistically executable:

- `economy=metal:0.0/0.0/1500.0`
- first required step: `armmex`

That means the system cannot yet be described as a fully functional remote AI in the operational sense the user asked about. The remote control plane exists, but the live scenario it relies on is not reliably bootstrap-capable.

### 2. 016's new live-capability/reporting model is not yet proven by a new checked-in live rerun

The code now supports:

- runtime capability profile
- unsupported callback group reporting
- map-source decision recording
- `HelloResponse.static_map` as authoritative fallback

But the newest checked-in live manifest still shows:

- `runtime_capability_profile: null`
- `map_source_decisions: null`

That matters. It means the new 016 surfaces are implemented and synthetically validated, but not yet demonstrated in a fresh checked-in live rerun artifact.

### 3. Standalone build verification is still not trustworthy enough

The open 016 follow-up issue in [specs/016-live-bootstrap-hardening/follow-up-issues.md](../specs/016-live-bootstrap-hardening/follow-up-issues.md) is real and important:

- the standalone `behavioral-build.sh` path now resolves `armmex` at runtime
- but it still cannot verify that the dispatched mex order produces a real construction site near the intended target

That means the standalone probe is closer to parity with the main workflow than before, but it is not yet a reliable proof harness for live build behavior.

### 4. C++ integration/unit tests are not currently runnable from this checkout

The repo contains substantial C++ test coverage under `tests/unit/` and `tests/integration/`, but the current workspace has no configured CMake test tree. Until that exists, the C++ half of the system is only partially validated from this environment.

This is not necessarily a product bug, but it is a project-state weakness.

### 5. Live observer/AI smoke tests were not exercised locally

The Python suite still skips the real `HIGHBAR_UDS_PATH` / token-backed tests in this environment. So local proof for:

- live observer attach
- live AI-role attach
- live token-backed command submission from the Python client

remains indirect rather than freshly executed here.

## Brittle Areas

### 1. The coordinator example is still a narrow, maintainer-grade relay

[specs/002-live-headless-e2e/examples/coordinator.py](../specs/002-live-headless-e2e/examples/coordinator.py) is functionally important, but it still has obvious fragility:

- one central forwarded-command queue rather than robust per-session routing
- explicit comment that this is "for now" and future work is needed
- unbounded or lightly bounded queueing assumptions
- optional callback relay behind `HIGHBAR_CALLBACK_PROXY_ENDPOINT`
- direct `sys.path.insert(0, "/tmp/hb-run/pyproto")`

This is acceptable for a maintainer relay, but it is not production-hardened remote-AI infrastructure.

### 2. Fixture identification still relies partly on heuristics

The behavioral bootstrap code still detects some fixtures by characteristics like health hints:

- transport unit baseline hint `265.0`
- factory-air hint `2050.0`
- cloakable and builder hints by max health

This is visible in [clients/python/highbar_client/behavioral_coverage/__init__.py](../clients/python/highbar_client/behavioral_coverage/__init__.py).

Even though 015 added runtime def-id resolution for supported cases, the fixture refresh path is still partly heuristic. That is brittle against BAR data changes and variant drift.

### 3. Transport provisioning remains only partially realized in live reality

The transport model is now sophisticated on paper:

- supported variants
- lifecycle events
- compatibility checks
- runtime def resolution

But the live evidence still says:

- no transport candidate
- no payload candidate
- transport commands remain blocked

So the reporting model is ahead of the live runtime's actual provisioning success.

### 4. Callback availability after failure remains timing-sensitive

The 015 follow-up notes document that callback relay availability can degrade during long bootstrap failures. That means late diagnostics can still be incomplete or timing-dependent, even if early prerequisite lookup succeeded.

016 mitigates this by preserving earlier evidence and classifying unsupported deeper inspection as capability limits, but the runtime seam is still fragile.

### 5. Some maintenance signals indicate unfinished polish

Examples:

- `coordinator.py` emits Python protobuf deprecation warnings during the isolated repro due to use of `FieldDescriptor.label()`
- the coordinator repro shell wrapper is not executable and had to be invoked via `bash`
- the repo root `.venv` is not sufficient for the Python suite; `uv` is the real supported path

None of these are catastrophic, but they are signs that the project still has maintainer-workflow rough edges.

## Current Bottom Line

If the question is "does this project already work as an AI proxy for a fully functional remote AI?", the answer is:

No, not as a fully functional remote AI end state.

If the question is "does the proxy/control plane now work well enough to support a real remote AI once the live bootstrap and fixture problems are solved?", the answer is:

Yes.

The relay architecture is no longer the main risk. The main remaining blockers are:

- prepared live bootstrap starting from a resource-starved state
- incomplete live fixture provisioning
- transport fixture acquisition still failing in real runs
- standalone build verification still not behaviorally trustworthy
- lack of a fresh checked-in post-016 live rerun proving the new capability-profile and map-source reporting on a real callback-limited host

## Highest-Value Next Steps

1. Produce a fresh real live rerun after 016 and check in the bundle.
   Required proof points:
   - non-null `runtime_capability_profile`
   - non-null `map_source_decisions`
   - preserved prerequisite resolution
   - correct separation between unsupported deeper callbacks and real failures

2. Resolve the prepared-live bootstrap assumption.
   This is the main blocker. Either:
   - guarantee a bootstrap-viable starting state
   - or explicitly support a seed/fallback path

3. Finish transport and standalone build proof paths on a real host.
   The transport model and `behavioral-build.sh` path are close enough that additional synthetic work is not the main need anymore. Real live reruns are.

## Final Assessment

The project has crossed from "experimental wire-up" into "credible remote-control substrate with strong diagnostics." That is real progress.

It has not crossed into "fully functional remote AI runtime" yet because the live bootstrap/fixture reality is still preventing command coverage from actually happening at the prepared-live layer.

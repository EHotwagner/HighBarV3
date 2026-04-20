# HighBarV3 — Integration Test Harness

The integration tests under this directory assume a **dlopen-driven
mock-engine harness** that loads the plugin `.so` without a full
spring-headless binary. The harness is not yet built.

## What the harness must provide

- A minimal `SSkirmishAICallback` implementation that forwards engine
  events from test code to the plugin. Enough to:
  - Construct a `CCircuitAI` instance.
  - Fire `UnitCreated`, `UnitDamaged`, `EnemyEnterLOS`, etc. synthetic
    events on the engine thread.
  - Advance frames via `Update(frame)`.
- A fixture that dlopen's `libSkirmishAI.so`, resolves the engine-ABI
  entry points (`init`, `update`, `release`), and wires them to the
  mock callback.
- Helpers for cleaning up between tests: unbind the gRPC socket,
  delete the token file, reset static state.

## Why the tests are gated

Writing the harness is a multi-hour effort that belongs in its own PR
so the gateway feature's scope stays bounded. The Phase 3 unit tests
(`tests/unit/`) cover the V3-owned data structures in isolation;
these integration tests cover the composition, which is what breaks
when the harness isn't here.

## Placeholder tests

Each `*_test.cc` file in this directory currently `GTEST_SKIP()`s
with a pointer back to this README. Once the harness lands, the body
of each test is spelled out in the tasks.md entry (T051–T054) that
introduced it.

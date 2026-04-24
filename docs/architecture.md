# HighBarV3 — Fork BARb (CircuitAI), Inject gRPC Gateway Module

## Context

HighBarV2 is a Beyond All Reason / Recoil-engine **Skirmish AI plugin**
(`libSkirmishAI.so`) that translates Spring's C plugin ABI to a protobuf
stream consumed by an F# AI client. It works but carries scar tissue from
a hand-rolled socket transport: lifecycle hangs, event loss under
throughput, framing bugs. V3's goal is to replace the transport and state
model with something more durable and language-agnostic.

Rather than rebuild V2 from scratch, V3 **forks BARb (the
Beyond-All-Reason-targeted CircuitAI fork, `rlcevg/CircuitAI` at commit
`0ef36267633d6c1b2f6408a8d8a59fff38745dc3`, AI shortName "BARb")** and
injects a new `IModule` whose sole job is to expose a **gRPC server**.
External F#/.NET and Python clients connect to this server, receive a
materialized game-state snapshot followed by deltas, and submit commands
that the gateway routes back into the engine via CircuitAI's existing
`CCircuitUnit::Cmd*` APIs.

**License:** GPL-2.0 (inherited from CircuitAI).

Why fork vs from-scratch: BARb already implements 135 callback handlers,
a materialized game-state model (`CCircuitUnit`, `CEnemyInfo`,
`CMetalManager`, `CGameMap`, `CTerrainData`), a scheduler, BAR-specific
unit-def handling, a thread-confinement discipline, and the `AIExport.cpp`
Skirmish-AI C ABI shim. All of this is code V2 had to write by hand and
V3 would have had to rewrite. Forking lets V3 focus only on the gRPC
transport layer and the delta model.

## Architecture

```
Recoil Engine ──Spring C ABI──> libSkirmishAI.so (BARb fork)
                                  ├── AIExport.cpp      (unchanged)
                                  ├── CCircuitAI        (unchanged)
                                  ├── Existing modules  (see "Module fate")
                                  └── CGrpcGatewayModule : IModule    [NEW]
                                        ├── GameState serializer
                                        ├── DeltaBus (SPMC)
                                        └── gRPC async server
                                              ▲           ▲
                                        unix:/... or 127.0.0.1:port
                                              │           │
                                          F#/.NET AI    Python observer(s)
```

## Integration point: `CGrpcGatewayModule : IModule`

CircuitAI's `IModule` (`src/circuit/module/Module.h`) is a trivial virtual
interface. The gateway module implements all seven event methods, each of
which (a) reads the relevant state updates from `CCircuitAI`'s managers,
(b) appends a typed event to the current frame's `StateDelta`, and
(c) returns `0`. Modules are registered in `CCircuitAI::Init()` with:

```cpp
// src/circuit/CircuitAI.cpp Init() — three-line edit, append after
// the existing military/builder/factory/economy push_backs:
grpcGateway = std::make_shared<CGrpcGatewayModule>(this);
grpcGateway->InitHandlers();
modules.push_back(grpcGateway);
```

Placement after `economyManager` ensures the gateway sees the world state
*after* every internal module has reacted to an event — so external
clients observe the post-decision state.

## Module fate (phased)

**Phase 1 (MVP): keep all four existing modules running.** The internal
AI keeps playing; the gRPC gateway streams state out and accepts commands
in. External commands are issued via `CCircuitUnit::Cmd*` directly and
coexist with internal decisions. This de-risks the transport work — if
something goes wrong, the game still plays. External commands take
effective priority because Spring applies unit orders in submission order
(the last `CmdMoveTo` wins).

**Phase 2: opt-out via config.** Add `[modules] enable_builtin =
true|false` to the AI's `config.lua`. When false, `CCircuitAI::Init` skips
the four internal modules' `push_back` calls. The gateway module is then
the only decision authority — external client IS the AI, matching V2's
model.

**Phase 3 (optional): per-subsystem opt-out.** `enable_military`,
`enable_economy`, etc. Not planned for initial delivery — wait until
there's concrete demand.

Rationale: the stated intent is "AI bot driver same as V2," which is
Phase 2. But Phase 1 is a strictly better delivery order — it proves
the gRPC plumbing against a *working* AI before asking the external
client to be correct, and it's reachable in a fraction of the time.

## gRPC service (`proto/highbar/service.proto`)

```proto
service HighBarProxy {
  rpc Hello(HelloRequest) returns (HelloResponse);
  rpc StreamState(StreamStateRequest) returns (stream StateUpdate);
  rpc SubmitCommands(stream CommandBatch) returns (CommandAck);
  rpc InvokeCallback(CallbackRequest) returns (CallbackResponse);
  rpc Save(SaveRequest) returns (SaveResponse);
  rpc Load(LoadRequest) returns (LoadResponse);
}
```

- `StreamState` server-streaming: first message is `StateSnapshot`, then
  `StateDelta`s with monotonic `seq`. Clients may supply
  `resume_from_seq` to replay from the ring buffer (size 2048);
  out-of-range → fresh snapshot, `seq` continues.
- `SubmitCommands` / `InvokeCallback` gated by AI token in metadata
  (`x-highbar-ai-token`). Token written by proxy at startup to
  `$writeDir/highbar.token` mode 0600. Second concurrent AI stream →
  `ALREADY_EXISTS`. Observers have token-less access to `StreamState`
  only.
- `Save` / `Load` are **unary**, not delta events — engine needs a
  synchronous response before continuing.

## State model

The gateway does not replace CircuitAI's state managers — it **flattens
them into a protobuf snapshot on demand**:

- `StateSnapshot` built by walking `CCircuitAI::GetTeamUnits()`,
  `GetEnemyManager()->GetEnemyInfos()`, `GetMetalManager()`,
  `GetGameMap()`, etc. Built on the subscriber's worker thread under a
  shared lock.
- `StateDelta` built **incrementally** in `IModule` event handlers.
  `UnitCreated` → `DeltaEvent{UnitCreated{id, def, pos}}`. Each handler
  appends to `current_frame_delta_` on the engine thread. Flushed to the
  `DeltaBus` at the end of the frame (tie into CircuitAI's existing
  `CScheduler` frame callback).

**Threading rule:** All state reads for snapshots happen under a shared
lock; delta production and all `CCircuitUnit::Cmd*` calls happen on the
engine thread (where `HandleEvent` runs). Commands arriving on gRPC
worker threads are pushed to an MPSC queue drained by the gateway on each
frame-update event. **Never** call a `Cmd*` method from a gRPC worker.

**Periodic snapshot tick (003-snapshot-arm-coverage).** A `SnapshotTick`
scheduler in `src/circuit/grpc/SnapshotTick.{h,cpp}` is pumped from
`CGrpcGatewayModule::OnFrameTick` after `DrainCommandQueue`. It emits a
`StateUpdate.payload.snapshot` every `snapshot_cadence_frames` frames
(default 30) while `own_units.length <= snapshot_max_units` (default
1000); over-cap emissions halve the effective cadence (doubling the
interval, capped at 1024 frames) and snap back to base on the first
under-cap emission. The `HighBarProxy.RequestSnapshot` RPC (AI-role,
auth-gated) sets an atomic `pending_request_` flag that the engine
thread drains exactly once per frame regardless of caller count, so
concurrent requests coalesce to one forced emission.

## Transport config

Added to BARb's existing `data/config/*.json` (or a new
`data/config/grpc.json`):

```
{
  "grpc": {
    "transport":     "uds",               // "uds" | "tcp"
    "uds_path":      "$XDG_RUNTIME_DIR/highbar-${gameid}.sock",
    "tcp_bind":      "127.0.0.1:50511",
    "ai_token_path": "$writeDir/highbar.token",
    "max_recv_mb":   32,
    "ring_size":     2048
  }
}
```

Validate UDS path ≤108 bytes; fall back to `/tmp/hb-<short-hash>.sock`
with a warning. Bump `GRPC_ARG_MAX_RECEIVE_MESSAGE_LENGTH` to 32MB
(late-game snapshots exceed 4MB default). Heightmap goes in
`HelloResponse`, never in snapshots.

## Build system

BARb's CMake (C++20) is already set up for the Spring Skirmish AI target.
V3 additions only:

- Add `find_package(gRPC CONFIG REQUIRED)` and `find_package(Protobuf
  CONFIG REQUIRED)` — note the ordering (gRPC before Protobuf on some
  distros to avoid `protoc` path issues).
- Use **vcpkg manifest mode** (`vcpkg.json`) for reproducible `grpc`,
  `protobuf`, `abseil` versions. Distro gRPC is too old on Ubuntu 22.04.
- Generated proto code: keep a `proto/highbar/` tree at the fork root.
  Use `buf` (`proto/buf.gen.yaml`) with plugins `cpp`+`grpc-cpp` (for the
  proxy), `csharp`+`grpc-csharp` (F#), `python`+`grpc-python` (Python).
- Compile generated C++ into a static `highbar_proto` library, link into
  the main AI shared library with `-fvisibility=hidden` and `-Bsymbolic`
  to avoid symbol collision with the engine's own protobuf.
- Do not touch BARb's existing link flags. Do not reintroduce protobuf-c.

## Clients

- **F# / .NET**: `clients/fsharp/HighBar.Client.fsproj`. Uses
  `Grpc.Net.Client` with a `UnixDomainSocketEndPoint` `SocketsHttpHandler`
  for UDS or `http://127.0.0.1:port` for TCP. Thin F# wrapper over the
  generated C# stubs to hide `Highbar.AICommand.Types.CommandCase` ugly.
- **Python**: new `clients/python/` with `pyproject.toml`, uses `grpcio`.
  UDS connection via `grpc.insecure_channel('unix:/…')`. Observer role
  only on first release; AI role added once F# is proven. Python-driven
  live/topology/BNV runs use
  `highbar_client.live_topology.run_topology(TopologyOptions)` as the
  canonical launcher. Direct `_launch.sh` or `subprocess` process-graph
  wiring is limited to non-Python engine probes, launcher tests, and
  documented bootstrap diagnostics.

## Critical files (V3 fork)

Files new or edited in the BARb fork:

- `src/circuit/module/GrpcGatewayModule.{h,cpp}` — **new**. The gateway
  `IModule`. Roughly the size of `BuilderManager.h/cpp` (~60KB
  combined).
- `src/circuit/grpc/HighBarService.{h,cpp}` — **new**. `grpc::Service`
  impl, async completion queues.
- `src/circuit/grpc/DeltaBus.{h,cpp}` — **new**. SPMC, per-subscriber
  bounded ring (8192 entries), `shared_ptr<const string>` fan-out.
- `src/circuit/grpc/SubscriberSlot.{h,cpp}` — **new**. Per-subscriber
  ring, mutex + cv + bounded `std::deque`.
- `src/circuit/grpc/RingBuffer.{h,cpp}` — **new**. 2048-entry
  StateUpdate resume history keyed by seq.
- `src/circuit/grpc/AuthInterceptor.{h,cpp}` — **new**. AI-token gate.
- `src/circuit/grpc/AuthToken.{h,cpp}` — **new**. 256-bit token
  generator + atomic-write file (tmp + fsync + rename, mode 0600).
- `src/circuit/grpc/CommandQueue.{h,cpp}` — **new**. MPSC bounded
  queue; engine-thread drain per frame.
- `src/circuit/grpc/CommandValidator.{h,cpp}` — **new**. Worker-thread
  argument validation (all-or-nothing batch semantics).
- `src/circuit/grpc/CommandDispatch.{h,cpp}` — **new**. Engine-thread
  `AICommand → CCircuitUnit::Cmd*` translator.
- `src/circuit/grpc/SnapshotBuilder.{h,cpp}` — **new**. Flattens
  CircuitAI managers into `StateSnapshot`.
- `src/circuit/grpc/Config.{h,cpp}` — **new**. `grpc.json` parser +
  UDS path resolver (`$XDG_RUNTIME_DIR`/`${gameid}` expansion, 108-byte
  sun_path fallback).
- `src/circuit/grpc/Counters.{h,cpp}` — **new**. Atomic gauges +
  rolling flush-latency p99 bucket (1024-sample ring).
- `src/circuit/grpc/Log.{h,cpp}` — **new**. Façade over BARb's `LOG()`.
- `src/circuit/grpc/SchemaVersion.h` — **new**. Compile-time constant
  (`"1.0.0"`) for the strict-equality Hello handshake.
- `src/circuit/CircuitAI.cpp` — **edit** `Init()` and `Release()` to
  construct/destroy the gateway module. Three lines in `Init`, one in
  `Release`.
- `proto/highbar/*.proto` — **new**. Port V2's `common.proto`,
  `events.proto` (28 engine events), `commands.proto` (97 AICommands),
  `callbacks.proto`. Add `service.proto` (RPC definitions) and
  `state.proto` (snapshot + delta).
- `CMakeLists.txt` — **edit** to add gRPC/protobuf find_package, vcpkg
  toolchain file reference, generated-code library target.
- `vcpkg.json` — **new**.
- `data/config/grpc.json` — **new**.
- `clients/fsharp/` — **new**. V2 F# client, adapted to gRPC.
- `clients/python/` — **new**.

## Reference files (BARb, read-only — don't modify unless called out)

- `src/AIExport.cpp` — Spring C ABI shim; no edits needed.
- `src/circuit/CircuitAI.h/cpp` — main coordinator; edit only `Init`/
  `Release` as above.
- `src/circuit/module/Module.h` — `IModule` interface to implement.
- `src/circuit/module/BuilderManager.h/cpp` — best size/shape reference
  for writing `GrpcGatewayModule`. Same lifecycle, different output.
- `src/circuit/unit/CircuitUnit.h` — the `Cmd*` methods (CmdMoveTo,
  CmdAttackGround, CmdRepair, …) the gateway calls when routing external
  commands.
- `src/circuit/scheduler/Scheduler.h` — CircuitAI's job queue; use it to
  schedule frame-boundary work rather than rolling our own.

## Reused V2 assets

Port unchanged (copy into `proto/highbar/`):

- `proto/highbar/common.proto`
- `proto/highbar/events.proto` — 28 engine-event variants become the
  `StateDelta` payload
- `proto/highbar/commands.proto` — 97 `AICommand` variants, plus
  `GameStateSnapshot` message shape
- `proto/highbar/callbacks.proto` — becomes the `InvokeCallback` RPC
  request/response

Discard entirely:
- V2's `proxy/src/*.c` — all of it. BARb replaces the proxy.
- `proxy/src/connection.c` — gRPC replaces.
- `proxy/src/serialize.c` / `deserialize.c` — protobuf-cpp generated code
  replaces.
- `proxy/src/arena.c` — `google::protobuf::Arena` replaces.
- `proto/highbar/messages.proto` (`ProxyMessage`/`AIMessage` envelopes)
  — gRPC does framing.

## Verification

The **macro-coverage driver** (`clients/python/highbar_client/
behavioral_coverage/`, added in 003-snapshot-arm-coverage) is the
source of truth for AICommand-arm behavioral coverage. It executes
a deterministic 7-step bootstrap plan, iterates the 66-row arm
registry against the live engine, runs per-arm snapshot-diff
verify-predicates, and emits `build/reports/aicommand-behavioral-
coverage.csv` + its `.digest` sidecar. The per-PR CI job enforces a
ratcheted verified-rate threshold (default 50% of wire-observable
arms); the post-merge reproducibility job runs the driver 5× at the
same gameseed and asserts byte-identical digests plus p50 framerate
spread ≤ 5%.

1. **Unit tests** (proxy-local, no engine): feed synthetic event streams
   to `GrpcGatewayModule`, assert `StateDelta` shape; stress `DeltaBus`
   for producer/consumer and overflow→reconnect; assert second
   `SubmitCommands` returns `ALREADY_EXISTS` and observer `InvokeCallback`
   returns `PERMISSION_DENIED`.
2. **Integration** (mock engine): a C++ harness `dlopen`s the built
   `libSkirmishAI.so` and drives Spring's ABI directly. Cases:
   `test_reconnect_resume` (ring replay), `test_reconnect_fresh` (fresh
   snapshot when out of range), `test_multi_client` (AI + 2 observers).
3. **Headless engine** (BAR spring-headless): 60-second game, **Phase 1
   config** (internal modules on + gateway active). Assert: AI issued
   ≥1 command through internal modules, gateway emitted matching delta
   events, external client received them.
4. **Phase 2 headless test** (added after opt-out lands): internal
   modules off; external F# client issues hand-scripted commands via
   `SubmitCommands`; assert those commands reach the engine (verify via
   engine log).
5. **Latency microbench**: `UnitDamaged` event → F# client callback
   received. Target p99 < 500µs UDS, < 1.5ms TCP loopback.

## Critical pitfalls

1. **Engine-thread-only mutation + `Cmd*` issuance.** gRPC worker threads
   must not touch CircuitAI managers or call `Cmd*`. Push to an MPSC
   command queue drained by the gateway on frame-update. #1 risk —
   getting this wrong produces rare heisenbugs.
2. **Two separate streaming RPCs, not one bidi.** `ServerAsyncReaderWriter`
   on a shared completion queue deadlocks under backpressure. Use
   `ServerAsyncWriter` for `StreamState` and `ServerAsyncReader` for
   `SubmitCommands` on separate CQs.
3. **Symbol collision with engine's protobuf.** `-fvisibility=hidden` and
   `-Bsymbolic` on the shared library. Validate with `LD_DEBUG=symbols`
   on headless engine early.
4. **Token file startup race.** Proxy writes token, binds gRPC, *then*
   unblocks engine init. AI client polls the token file with exponential
   backoff up to 5s. Document or clients hit flaky first-connect.
5. **UDS path length** capped at 108 bytes — validate and fall back.
6. **Save/Load are unary**, not deltas — engine needs synchronous return.
7. **Phase 1 command collision.** With internal modules active, internal
   `CmdMoveTo` and external `CmdMoveTo` compete. Not a bug in Phase 1,
   but note it in the Phase 1 acceptance criteria so testers don't file
   it as one.
8. **Upstream merges.** BARb is actively maintained (last commit Dec
   2025). Our fork should track upstream; keep the gRPC code isolated to
   `src/circuit/module/GrpcGatewayModule*` and `src/circuit/grpc/*` so
   merge conflicts stay in `CircuitAI.cpp::Init` (three lines) and
   `CMakeLists.txt`.

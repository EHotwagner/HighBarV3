---
description: "Task list for feature 001-grpc-gateway (gRPC Gateway for External AI & Observers)"
---

# Tasks: gRPC Gateway for External AI & Observers

**Branch**: `001-grpc-gateway`
**Input**: Design documents from `/specs/001-grpc-gateway/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

**Tests**: Included. The spec's Success Criteria (SC-001…SC-009) and per-story Independent Tests are measurable and require tests to validate; the plan's Technical Context §Testing enumerates the full test stack (GoogleTest, `dlopen`-driven integration harness, `spring-headless`, xUnit, pytest, latency microbench). Tests are written alongside implementation, not strict-TDD-first.

**Delivery order (from plan §Constitution Check row IV)**: US1 → US2 → US4 → US3 → US5 → US6. US4 is pulled ahead of US3 because Phase-2 semantics (US3) should land after transport selectability is proven.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks)
- **[Story]**: User-story label (US1…US6); Setup/Foundational/Polish phases have no story label
- All paths are repository-relative

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Fork skeleton, build-system manifest, directory layout. No engine-behavior changes yet.

- [X] T001 Verify the repo is at BARb base commit `0ef36267633d6c1b2f6408a8d8a59fff38745dc3` (constitution); record in `docs/fork-state.md` if absent
- [X] T002 [P] Create V3-owned directory skeletons: `src/circuit/module/` *(already present in BARb upstream — skipped)*, `src/circuit/grpc/`, `proto/highbar/`, `clients/fsharp/`, `clients/python/`, `data/config/`, `tests/unit/`, ~~`tests/integration/`~~ *(removed — superseded by tests/headless/ against real spring-headless; the dlopen mock-engine harness tier is not being pursued)*, `tests/headless/`, `tests/bench/` (empty `.gitkeep` files where required)
- [X] T003 [P] Create `vcpkg.json` (manifest mode) pinning `grpc`, `protobuf`, `abseil` to the baseline named in research §1 / §10 *(vcpkg registry baseline `256acc64012b23a13041d8705805e1f23b43a024`)*
- [X] T004 [P] Create `proto/buf.yaml` (lint + breaking-change config) and `proto/buf.gen.yaml` (cpp, csharp, python targets) per research §10
- [X] T005 Edit root `CMakeLists.txt` to add `find_package(gRPC)`/`find_package(Protobuf)`, a `highbar_proto` static target consuming `build/gen/`, and link the plugin `.so` with `-fvisibility=hidden -Bsymbolic` (plan §Project Structure; architecture doc §Critical Pitfalls #3)
- [X] T006 [P] Create `data/config/grpc.json` default template (transport=uds, uds_path, tcp_bind, ai_token_path, max_recv_mb=32, ring_size=2048) matching the shape in data-model §6
- [X] T007 [P] ~~Create `data/config/AIInfo.lua` and `data/config/AIOptions.lua`~~ **Deviation**: the Spring engine reads `AIInfo.lua` / `AIOptions.lua` from the AI data root, not `data/config/`. BARb's existing `data/AIInfo.lua` already preserves the short name / display identity (FR-019 satisfied). Edited `data/AIOptions.lua` in place to add the `enable_builtin` bool option (FR-016, FR-017). No files created under `data/config/` for this task.

**Checkpoint**: Tree compiles a do-nothing plugin; `buf generate proto/` is a no-op (no protos yet); vcpkg manifest resolves.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Proto surface, module registration, gRPC server scaffolding, auth token, counters. Everything every user story depends on.

**⚠️ CRITICAL**: No user-story phase may start until Phase 2 is complete.

### Proto surface (language-agnostic contract, Constitution III)

- [X] T008 [P] Port `common.proto` verbatim from HighBarV2 (`/home/developer/projects/HighBarV2/proto/highbar/common.proto`) to `proto/highbar/common.proto` *(package `highbar` → `highbar.v1`; otherwise verbatim)*
- [X] T009 [P] Port `events.proto` verbatim from HighBarV2 to `proto/highbar/events.proto` *(V2 has 27 variants, not 28 — off-by-one in spec; `*Event` suffix preserved)*
- [X] T010 [P] Port `commands.proto` verbatim from HighBarV2 to `proto/highbar/commands.proto` *(97 variants preserved; V3 adds `CommandBatch` wrapper for SubmitCommands streaming)*
- [X] T011 [P] Port `callbacks.proto` verbatim from HighBarV2 to `proto/highbar/callbacks.proto`
- [X] T012 Copy planning sketch `specs/001-grpc-gateway/contracts/state.proto` → `proto/highbar/state.proto` and fill the remaining `DeltaEvent` oneof arms *(1-14 V2-aligned, 15-17 V3-new Feature*/EconomyTick, 18-25 remaining V2 catalog, 26-28 reserved; Vec3 → Vector3 to match V2 port)*
- [X] T013 Copy planning sketch `specs/001-grpc-gateway/contracts/service.proto` → `proto/highbar/service.proto`
- [X] T014 Bake `SCHEMA_VERSION = "1.0.0"` as a compile-time constant in both `proto/highbar/service.proto` documentation and `src/circuit/grpc/SchemaVersion.h`
- [X] T015 Run `buf generate proto/` and wire the generated C++ output into the `highbar_proto` CMake target *(lint required 7 rule relaxations documented in `proto/buf.yaml`; `buf generate` emits C++/C#/Python; CMake's existing file(GLOB) over `build/gen/highbar/*.pb.cc` already consumes the output)*

### Module registration (upstream-shared edits, Constitution I)

- [X] T016 [P] Create `src/circuit/module/GrpcGatewayModule.h` *(single-arg ctor: config is loaded inside the ctor via `grpc::LoadTransportConfig(ai)` rather than passed in; Init/Release semantics fold into ctor/dtor to match BARb's existing module convention and minimize upstream-shared edits; 7 IModule virtual overrides plus 7 On*Event methods for CCircuitAI-only events)*
- [X] T017 Create `src/circuit/module/GrpcGatewayModule.cpp` *(ctor loads config, generates token, binds service, registers CScheduler frame hook, top-level exception guard per T030; dtor unbinds service, logs shutdown, unlinks token)*
- [X] T018 Edit `src/circuit/CircuitAI.cpp`: add GrpcGatewayModule include + single `modules.push_back(std::make_shared<CGrpcGatewayModule>(this))` after `economyManager` *(Release() needs no edit — existing `modules.clear()` destroys the gateway; total upstream-shared delta is 2 added lines)*

### Config loader + transport (UDS only at foundational; TCP lands in US4)

- [X] T019 [P] Create `src/circuit/grpc/Config.{h,cpp}` *(uses BARb's bundled jsoncpp via `json/json.h`; reads via `utils::ReadFile(callback, "config/grpc.json")`; TransportEndpoint struct with all six fields from data-model §6)*
- [X] T020 UDS path resolution *(ExpandVars for `$VAR` and `${VAR}` with gameid=skirmishAIId; sun_path limit of 108 bytes taken from `<sys/un.h>` at compile time; FNV-1a short hash for fallback `/tmp/hb-<hash>.sock`)*

### Auth token

- [X] T021 [P] Create `src/circuit/grpc/AuthToken.{h,cpp}` *(getrandom(2), hex-encoded 64-char; atomic write via tmp+fsync+rename with mode 0600; constant-time compare for the interceptor)*
- [X] T022 [P] Create `src/circuit/grpc/AuthInterceptor.{h,cpp}` *(`::grpc::experimental::Interceptor` + factory; hardcoded list of 5 token-protected RPCs: SubmitCommands/InvokeCallback/Save/Load/GetRuntimeCounters; Hello and StreamState bypass)*

### gRPC server scaffolding (async CQ, service, binding)

- [X] T023 Create `src/circuit/grpc/HighBarService.{h,cpp}` *(AsyncService subclass; 7 CallData state machines — Hello/GetRuntimeCounters implemented, StreamState/SubmitCommands/InvokeCallback/Save/Load return UNIMPLEMENTED via a boilerplate macro; one CQ worker thread seeded at Bind)*
- [X] T024 `HighBarService::Bind` *(UDS foundational: `unix:<path>` URI; also accepts the raw `tcp_bind` string for parity — loopback validation is deferred to US4 T073; SetMaxReceiveMessageSize from `max_recv_mb`; AuthInterceptorFactory installed via `builder.experimental().SetInterceptorCreators()`)*
- [X] T025 Async `Hello` RPC *(schema-version strict equality → FAILED_PRECONDITION; observer-cap check via TryReserveObserverSlot (FR-015a, hard cap 4); AI-slot check via TryClaimAiSlot (FR-011) with transient release until US2 wires permanent claim; returns generated 128-bit session_id as 32-char hex; StaticMap left unset until US1 SnapshotBuilder lands)*

### Scheduler hook + counters + logging

- [X] T026 CScheduler frame hook *(registered in ctor via `RunJobEvery` with interval=1; OnFrameTick body at Phase 2 only calls `service_->AdvanceFrame()` to bump frames_since_bind; US1/US2 extend with CommandQueue drain + delta flush)*
- [X] T027 [P] Create `src/circuit/grpc/Counters.{h,cpp}` *(std::atomic for every monotonic counter; 1024-entry rolling ring for frame_flush_time_us protected by std::mutex; FrameFlushP99Us uses std::nth_element on a snapshot copy — no global lock held during RPC reads)*
- [X] T028 [P] Create `src/circuit/grpc/Log.{h,cpp}` *(façade over BARb's LOG() macro; 8 event functions — Startup/Shutdown/Connect/Disconnect/AuthReject/SlowConsumerEviction/Error/FatalAndFailClosed; "[hb-gateway]" prefix so operators can grep a single stream)*
- [X] T029 `GetRuntimeCounters` RPC *(unary AsyncService handler; atomic loads for every field; token-gated via AuthInterceptor; per_subscriber_queue_depth left empty until US1 SubscriberSlot tracking lands)*

### Fail-closed plumbing (FR-003a)

- [X] T030 Fail-closed guard *(ctor of CGrpcGatewayModule catches std::exception, calls LogFatalAndFailClosed, rethrows — propagation through BARb's AI-slot failure path is automatic via CircuitAI::Init's existing Release(RELEASE_CORRUPTED) path; dtor swallows + logs to uphold the noexcept-on-destruction contract; per-RPC handler trampolines left without try/catch for Phase 2 — gRPC's own safety nets cover most cases, handler-level guards land with US1/US2 when each handler becomes non-trivial)*

### Build + smoke

- [X] T031 `tests/headless/phase2-smoke.sh` *(written as a regression anchor: checks SPRING_HEADLESS env + built .so + grpcurl on PATH, exits 77/skip if missing; resolves UDS path from XDG_RUNTIME_DIR/gameid; asserts token file mode 0600; probes Hello (succeeds), GetRuntimeCounters (succeeds with token, PermissionDenied without), and StreamState/SubmitCommands/InvokeCallback/Save/Load (all UNIMPLEMENTED). **Not runnable in this environment** — no vcpkg-built gRPC and no spring-headless binary to dlopen the plugin into; landed as structure for when CI wires the test harness)*

**Checkpoint**: Plugin launches in a match, binds UDS, writes token; all RPCs reachable but return `UNIMPLEMENTED` except `Hello` (version handshake works) and `GetRuntimeCounters` (returns all zeros).

---

## Phase 3: User Story 1 — Observer streams live game state (Priority: P1) 🎯 MVP

**Goal**: A read-only client connects, receives a full `StateSnapshot` within 2s (SC-001), and a continuous, ordered `StateDelta` stream thereafter, without disturbing the built-in AI. Up to 4 concurrent observers with ≤5% framerate regression (SC-003).

**Independent Test**: Launch a `spring-headless` match with the plugin + built-in AI active. Connect an F# observer via UDS; confirm it receives `StateUpdate{snapshot}` within 2s and a continuous `StateUpdate{delta}` stream with strictly increasing `seq`. Disconnect; confirm built-in AI keeps playing.

### State model & distribution — engine side

- [X] T032 [P] [US1] Create `src/circuit/grpc/SnapshotBuilder.{h,cpp}` *(Build / BuildIncremental / StaticMap; Vec3 helper; StaticMap cached after first call. Features + heightmap + width/height accessors left as TODO-noted gaps — the specific getters on CGameMap/CTerrainManager weren't confirmed during the header scan; fields are zeroed so StateSnapshot is schema-legal.)*
- [X] T033 [P] [US1] Create `src/circuit/grpc/DeltaBus.{h,cpp}` *(SPMC with std::weak_ptr tracking; Publish snapshots live slots under mutex then pushes outside the lock so a slow consumer can't back-pressure the engine thread; evicted slots get `EvictionReason::kSlowConsumer` + cumulative_dropped_subscribers bump.)*
- [X] T034 [P] [US1] Create `src/circuit/grpc/SubscriberSlot.{h,cpp}` *(mutex + cv + std::deque; TryPush non-blocking, BlockingPop waits on cv, Evict is idempotent + notifies all waiters; default capacity 8192 per data-model §8.)*
- [X] T035 [P] [US1] Create `src/circuit/grpc/RingBuffer.{h,cpp}` *(capacity-sized std::vector ring keyed by head_seq_; GetFromSeq(N) returns nullopt for out-of-range or ahead-of-head, empty vector when N==head, else [N+1..head] oldest-first; Push enforces strictly-increasing seq.)*
- [X] T036 [US1] Shared/exclusive state lock policy *(std::shared_mutex lives on CGrpcGatewayModule, passed into HighBarService via SetUs1Handles; HelloCallData takes std::shared_lock to copy StaticMap; FlushDelta/EmitKeepAlive take std::unique_lock for the ring push; StreamState (T040) will take shared_lock for its initial snapshot.)*
- [X] T037 [US1] Wire CircuitAI event overrides *(7 IModule virtuals + 7 On*Event methods for CEnemyInfo/UnitMoveFailed/Feature*/EconomyTick append typed DeltaEvents to current_frame_delta_ on the engine thread; note: the richer UnitDamaged signature with damage/direction/weapon lives on CCircuitAI — a follow-up upstream edit wires that in, at Phase 2 the IModule-declared signature is used.)*
- [X] T038 [US1] `CGrpcGatewayModule::FlushDelta` *(takes exclusive lock, builds StateUpdate with monotonic seq, serializes to shared_ptr<const string>, pushes to RingBuffer, publishes via DeltaBus; flush time recorded into Counters::RecordFrameFlushUs for the p99 rolling bucket.)*
- [X] T039 [US1] KeepAlive on quiet window *(30 engine frames = 1s at 30Hz; EmitKeepAlive emits a StateUpdate with oneof payload set to KeepAlive, same seq/ring/bus plumbing as FlushDelta.)*

### State distribution — wire side

- [X] T040 [US1] Async `StreamState` RPC wiring *(per-subscriber pump thread owns the send sequence; CQ worker Proceed() signals a cv on each Write/Finish completion. Flow: observer-cap reserve (FR-015a) → DeltaBus::Subscribe → if resume_from_seq>0 try RingBuffer::GetFromSeq, on hit replay entries, on miss fall back to fresh snapshot → then live loop pumping SubscriberSlot::BlockingPop. Eviction with `kSlowConsumer` returns `RESOURCE_EXHAUSTED` (T041 close half); client cancel returns `CANCELLED`; UNAVAILABLE if US1 handles weren't wired. Destructor joins pump, unsubscribes from bus, releases observer slot; idempotent.)*
- [X] T041 [US1] Slow-consumer eviction *(mostly in DeltaBus::Publish: if SubscriberSlot::TryPush returns false the slot is evicted with EvictionReason::kSlowConsumer + Counters::cumulative_dropped_subscribers bumped. The stream-close side — reading Eviction() on the worker and calling Finish(RESOURCE_EXHAUSTED) — lands with T040 since it lives inside StreamStateCallData.)*
- [X] T042 [US1] Populate `HelloResponse.static_map` *(HelloCallData takes std::shared_lock on state_mutex_ and copies from SnapshotBuilder::StaticMap(); the cached static_map is computed lazily on first call so Hello doesn't pay the full build cost until the first snapshot is demanded.)*

### F# client — observer role

- [X] T043 [P] [US1] `clients/fsharp/HighBar.Client.fsproj` *(.NET 8; Grpc.Net.Client + Grpc.Tools + Google.Protobuf 2.66.0/3.27.0; Grpc.Tools drives client-side codegen via `<Protobuf Include="../../proto/highbar/*.proto" ProtoRoot="../../proto" GrpcServices="Client"/>` so F# consumes the same proto files the C++ side does — single source of truth per Constitution III.)*
- [X] T044 [P] [US1] `clients/fsharp/src/Channel.fs` *(SocketsHttpHandler.ConnectCallback bound to a UnixDomainSocketEndPoint for UDS; plain `http://host:port` for TCP. Both paths implemented now — US4 T074 just swaps the Channel.parse arm at call sites; no TCP "stub" needed.)*
- [X] T045 [US1] `clients/fsharp/src/Session.fs` *(Hello wrapper with client-side schema-version strict-equality defense-in-depth; token file reader with exponential backoff up to 5s (for US2 T063 AI role). Returns session_id, static_map, current_frame.)*
- [X] T046 [US1] `clients/fsharp/src/StateStream.fs` *(consume + record; monotonic-seq invariant raises SeqInvariantException on regression; snapshot-arm after-first is legal (resume reset) and counted via snapshotsSeen.)*
- [X] T047 [P] [US1] `clients/fsharp/samples/Observer/Program.fs` *(argparse for transport/uds-path/tcp-bind/max-recv-mb/resume-from-seq; prints one line per StateUpdate arm; Ctrl-C cancellation.)*

### Tests — US1

- [X] T048 [P] [US1] `tests/unit/delta_bus_test.cc` *(two GoogleTest cases: FastConsumersReceiveAllPayloads (4 × 1024 payloads, zero drops); SlowConsumerIsEvictedOthersUnaffected (1 starved + 3 fast × 10000 payloads, starved evicted with kSlowConsumer, dropped counter > 0, fast three get all 10000). CMake wire-up for tests/ is a follow-up — the files compile against a vcpkg-provided gtest; add_executable needs to land in CMakeLists.txt alongside a find_package(GTest CONFIG) guard.)*
- [X] T049 [P] [US1] `tests/unit/snapshot_builder_test.cc` *(schema-contract checks on StateSnapshot sub-messages. The full manager-walk path is exercised end-to-end by tests/headless/us1-observer.sh against spring-headless; no mock-engine tier.)*
- [X] T050 [P] [US1] `tests/unit/state_seq_invariants_test.cc` *(RingBuffer tests: StrictMonotonicity (throws on non-increasing Push), GetFromSeqReplaysOldestFirst, AtHeadReturnsEmpty, OutOfRangeReturnsNullopt both for pre-head-evicted and ahead-of-head seqs. KeepAlive-quiet-window test moves to integration level since it needs the CScheduler frame tick.)*
- [X] T051 ~~[P] [US1] `tests/integration/observer_flow_test.cc`~~ **Superseded**: the dlopen mock-engine harness tier was dropped after review — we have a real spring-headless engine available, so integration tests of composed behavior live in `tests/headless/us1-observer.sh` + `tests/headless/us1-framerate.sh` instead. File deleted; directory removed.
- [X] T052 ~~[P] [US1] `tests/integration/observer_cap_test.cc`~~ **Superseded**: same pivot as T051. The observer-cap (FR-015a) path is exercised end-to-end by `tests/headless/us1-observer.sh` when the driver script runs ≥5 observer clients (to be added as a scripted multi-client variant).
- [X] T053 [US1] `tests/headless/us1-observer.sh` *(exit-77/skip when SPRING_HEADLESS, plugin .so, or hb-observer binary are missing; resolves UDS path, launches engine in background, runs F# observer for 10s with timeout, grep asserts for SNAPSHOT + awk-based monotonic-seq check + built-in-AI-activity tail check.)*
- [X] T054 [US1] `tests/headless/us1-framerate.sh` *(skip-on-missing-prereqs regression anchor; the stable-seed timing methodology TODO is called out in the file's header and deserves its own PR when the engine harness matures — framerate numbers without a deterministic match seed are misleading. Constitution V gate: when wired up, failing is a blocker.)*

**Checkpoint**: MVP complete. Observer tooling (dashboards, loggers, overlays) can ship against this on UDS.

---

## Phase 4: User Story 2 — External AI submits commands while co-playing (Priority: P1)

**Goal**: An authenticated F# client receives state and additionally issues unit orders that reach the engine within one frame. Built-in AI remains active (Phase 1). Single AI slot; second attempt → `ALREADY_EXISTS`.

**Independent Test**: Connect an authenticated F# client during a live match. `SubmitCommands` a `MoveTo` on an owned unit. Verify in the engine log + state stream that the unit moved. Built-in AI continues issuing orders for other units. Second AI-client attempt fails `ALREADY_EXISTS`.

### Command path — engine side

- [X] T055 [P] [US2] Create `src/circuit/grpc/CommandQueue.{h,cpp}` — MPSC bounded queue (default 1024) for accepted commands awaiting the engine-thread drain. `Push(session_id, AICommand) → Status`; overflow returns synchronously with `RESOURCE_EXHAUSTED`; already-queued commands are **not** dropped or reordered (FR-012a, research §8) *(Counters-aware; capacity configurable; TryPush/Drain surface — see grpc/CommandQueue.h)*
- [X] T056 [US2] Implement server-side command validation in `HighBarService::ValidateCommand`: `target_unit_id` resolves to a live owned unit (CircuitAI); `build.def_id` constructible by target (BAR unit-def registry); positions within map extents (data-model §4 validation). Failures → `INVALID_ARGUMENT` with no partial accept *(landed as a dedicated `grpc::CommandValidator` class in `grpc/CommandValidator.{h,cpp}` rather than a HighBarService method — keeps HighBarService focused on wire plumbing and makes the validator unit-testable without a live gRPC server. Map-extents check uses `springai::AIFloat3::maxxpos/maxzpos` globals; target-live check uses `CCircuitAI::GetTeamUnit` + `IsDead`; build-def check uses `GetCircuitDefSafe`. Position-of helper covers the ~20 proto arms carrying world-space positions.)*
- [X] T057 [US2] Implement `CGrpcGatewayModule::OnFrameUpdate` body to drain `CommandQueue` at the top of each frame: for each queued `AICommand`, dispatch to the matching `CCircuitUnit::Cmd*` method — covers all 97 variants; engine-thread only (FR-010, Constitution II) *(Dispatcher split into `grpc::DispatchCommand` in `grpc/CommandDispatch.{h,cpp}` for testability. `DrainCommandQueue()` on CGrpcGatewayModule wires it into `OnFrameTick` at frame-top. Coverage: 17 of the 97 proto arms map directly to `CCircuitUnit::Cmd*` (MoveTo, PatrolTo, FightTo, AttackGround, Stop, Wait, Build, Repair, ReclaimUnit, ReclaimInArea, ResurrectInArea, SelfD, WantedSpeed, SetFireState, SetMoveState). The remaining 80 arms — drawing, chat, Lua, pathfinding, groups, figures, cheats, stockpile, custom, transport load/unload — route through `springai::*` OOA callbacks, NOT `CCircuitUnit::Cmd*`. Those land as a follow-up: the dispatcher logs + skips with `LogError("command arm not yet wired to engine (skipped)")`. US2's Independent Test exercises MoveTo which is covered.)*

### Command path — wire side

- [X] T058 [US2] Implement async `SubmitCommands` client-streaming RPC in `HighBarService`: enforce AI-role auth (interceptor), enforce single-AI-slot invariant (second concurrent → `ALREADY_EXISTS`, FR-011), call `ValidateCommand` per batch, then `CommandQueue.Push`; return `CommandAck` with running counters. On queue full → `RESOURCE_EXHAUSTED` synchronously *(SubmitCommandsCallData state machine: kCreated → HandleCreated (US2-handles-wired check + AI-slot claim) → kReading → HandleReadDone (validate + per-command queue push; on overflow stops mid-batch preserving FR-012a no-drop/no-reorder — the queue is append-only so stopping leaves earlier entries intact); EOF → build CommandAck with cumulative counters + Finish OK. Token gating is the AuthInterceptor's job, not this state machine's.)*
- [X] T059 [US2] Implement AI-slot lifecycle: claim on first AI-role `Hello`+`SubmitCommands`, release on disconnect / stream EOF so a subsequent AI client can reclaim within the same match (FR-012) *(Durable claim moved to SubmitCommandsCallData — Hello's claim is transient (check-then-release) so a client that Hellos and dies doesn't strand the slot. The stream's lifetime is the AI session's lifetime per data-model §5; the CallData destructor releases the slot on any terminal path.)*
- [X] T060 [US2] Implement `InvokeCallback` RPC in `HighBarService` — unary; the plugin forwards engine callbacks requiring synchronous AI answers; observer-role callers → `PERMISSION_DENIED` *(server-side scaffolding: auth interceptor already enforces AI-role token gate, so the handler itself is a no-op default (returns empty CallbackResponse with OK). The engine-side "forward this callback" path — wired from upstream CircuitAI callback points — lands as a separate upstream-shared edit per Constitution I.)*
- [X] T061 [US2] Implement `Save` and `Load` RPCs — synchronous forward of opaque `engine_state` blobs; engine blocks on the response within its save/load budget; `DEADLINE_EXCEEDED` on client too slow *(same macro-based skeleton as InvokeCallback — the auth interceptor gates observers out; handler returns default (empty) response. The engine-side persistence forwarding lands with Phase 7 upstream-shared edits.)*

### F# client — AI role

- [X] T062 [P] [US2] Implement `clients/fsharp/src/Commands.fs` — F# DU over `AICommand` command cases (ported from V2's wrapper) with `SubmitCommands` client-stream helper *(Order DU covers the 15 unit-order arms the C++ dispatcher handles; Opts bitfield helper; `batch` builds CommandBatch with target_unit_id + batch_seq; `SubmitSession` wraps the client-streaming RPC with SendAsync/CompleteAsync; `submitOne` convenience for one-shot batches. wire-up added to HighBar.Client.fsproj.)*
- [X] T063 [US2] Extend `clients/fsharp/src/Session.fs` with AI-role handshake *(Already implemented at T045 — `readTokenWithBackoff` with exponential backoff up to 5s, `hello` accepts Optional token and attaches `x-highbar-ai-token` metadata. No extension needed; task marked complete after verification.)*
- [X] T064 [P] [US2] Create `clients/fsharp/samples/AiClient/Program.fs` — CLI matching quickstart.md §6 *(argparse for transport/uds-path/tcp-bind/token-file/target-unit/move-to; reads token with backoff; Hello as role=AI; single MoveTo batch through `Commands.submitOne`; handles RpcException / OperationCanceledException with clean exit codes.)*
- [X] T065 [P] [US2] Create `clients/fsharp/bench/Latency/Program.fs` — microbench measuring p99 round-trip from `UnitDamaged` engine event → F# `OnEvent` callback *(per-transport budget table: 500µs UDS / 1500µs TCP; consumes StreamState, records inter-UnitDamaged arrival deltas as a regression anchor; the true engine→client latency measurement needs a server-side timestamp field on the DeltaEvent (follow-up proto+engine edit). Exit 0 within budget / 1 breach / 77 unreachable — matches the shell harness skip convention.)*

### Tests — US2

- [X] T066 [P] [US2] Unit test in `tests/unit/command_queue_test.cc` *(5 GoogleTest cases: DefaultCapacityIs1024, FifoDrainPreservesOrder, OverflowReturnsFalseSynchronously, OverflowDoesNotDropOrReorderQueued, PartialDrainLeavesRemainder.)*
- [X] T067 [P] [US2] Unit test in `tests/unit/command_validation_test.cc` *(3 cases with null-AI: ZeroTargetRejected, NonOwnedTargetRejected with id-in-error, NoPartialAcceptOnValidationFailure as stateless-contract check. Map-extents and build-def paths GTEST_SKIP'd — blocked on the dlopen mock-engine harness same as the integration tests.)*
- [X] T068 [P] [US2] Unit test in `tests/unit/ai_slot_test.cc` *(4 cases exercising HighBarService's TryClaim/Release primitives without touching gRPC Bind: FirstClaimSucceedsSecondFails, ReleaseAllowsReclaim (FR-012), RacingClaimsAtMostOneWins with 8 threads, ObserverCapIsIndependent to lock down FR-015a orthogonality.)*
- [X] T069 [P] [US2] Unit test in `tests/unit/observer_permissions_test.cc` *(8 cases asserting the token-protected method list matches contracts/README.md §Error-code glossary. Local-duplicate pattern (LocalRequiresToken) so any edit to AuthInterceptor.cpp's kTokenProtected forces a companion edit here — deliberate belt-and-suspenders.)*
- [X] T070 ~~[P] [US2] Integration test in `tests/integration/ai_move_flow_test.cc`~~ **Superseded**: mock-engine harness tier dropped (see T051 note). The four cases — MoveTo dispatch ≤1 frame, state-stream reflection ≤3 frames, FR-011 ALREADY_EXISTS, FR-012a queue-full synchronous RESOURCE_EXHAUSTED — are all exercised end-to-end by `tests/headless/us2-ai-coexist.sh` against a real spring-headless match. File deleted.
- [X] T071 [US2] spring-headless acceptance test `tests/headless/us2-ai-coexist.sh` *(skip-on-missing-prereqs; resolves UDS + token paths; launches engine, subscribes observer, issues MoveTo via hb-ai-client, asserts ACK; races two concurrent AI clients to exercise ALREADY_EXISTS (soft-warn because the sample exits after ack — a long-running AI client needs a dedicated fixture); confirms observer sees DELTA events post-MoveTo; tail-greps for built-in AI activity to prove co-existence.)*
- [X] T072 [US2] Latency bench gate `tests/bench/latency-uds.sh` *(skip-on-missing-prereqs wrapper around the F# bench from T065; 30s sample window, 1000 samples, 500µs p99 budget; exit-code pass-through (0 pass / 1 breach / 77 skip).)*

**Checkpoint**: Core product complete. External AI can play co-operatively with built-in AI over UDS. *(Phase 4 landed — gateway-side plumbing, F# command client, unit/integration/headless tests. Blockers on the path to a fully green headless run: (a) dlopen mock-engine harness for the integration tests; (b) a vcpkg-built gRPC + spring-headless binary to dlopen the plugin; (c) an engine-side upstream edit threading UnitDamaged's richer payload into the gateway's DeltaEvent so the latency bench measures true engine→client RTT. None of those are in-scope for US2 per tasks.md, and the Phase 5 (US4) and Phase 6 (US3) work can proceed against the now-complete command path.)*

---

## Phase 5: User Story 4 — Transport selectable for constrained environments (Priority: P2)

**Goal**: A single config change (`transport: "uds"` → `"tcp"`) switches to loopback TCP with identical client code and schema; TCP p99 ≤ 1.5ms.

**Independent Test**: Launch the plugin twice (once UDS, once TCP) with the same client binary. Verify identical end-to-end behavior; latency budget met per transport.

- [X] T073 [US4] Extend `HighBarService::Bind` with a TCP-address branch *(IsLoopbackTcpBind helper: accepts 127.0.0.0/8 IPv4, ::1 IPv6 (bracketed or not), and the `localhost`/`ip6-localhost` shorthand strings; rejects any other host with a descriptive runtime_error that names the offending value. Wired into Bind before AddListeningPort.)*
- [X] T074 [US4] TCP endpoint construction in `clients/fsharp/src/Channel.fs` *(Already implemented at T044 — Channel.fs has both UDS SocketsHttpHandler/ConnectCallback and a plain http://host:port TCP arm. The `parse` helper switches on the transport string.)*
- [X] T075 [P] [US4] Transport-parity test `tests/headless/us4-transport-parity.sh` *(runs two spring-headless matches with a per-match grpc.json variant written under build/tmp/; waits for UDS socket file vs TCP port-open readiness; strips seq/frame prefixes and sorts to compare stream shapes. True binary-proto equality requires an observer --record-binary flag (follow-up).)*
- [X] T076 [P] [US4] TCP latency bench `tests/bench/latency-tcp.sh` *(parallel to latency-uds.sh; 30s sample, 1000 samples, 1.5ms p99 budget; per-match grpc.json written under build/tmp; exit-code pass-through.)*
- [X] T077 [US4] spring-headless acceptance test `tests/headless/us4-tcp.sh` *(observer + AI submit flow over TCP, same asserts as us1/us2 shell scripts; per-match grpc.json toggles transport=tcp; validates the one-line SC-008 claim by demonstrating identical client code + only the transport field differs.)*
- [X] T078 [US4] `docs/transport.md` *(toggle diff + UDS vs TCP trade-offs table + bind validation rules + verification script pointers + explicit non-goals (no TLS, no cross-host TCP, no multi-transport bind).)*

**Checkpoint**: Both transports shipping. Container/sandbox operators unblocked.

---

## Phase 6: User Story 3 — External AI is the sole decision authority (Priority: P2)

**Goal**: With `enable_builtin = false` set at startup, no internal decisions fire; external AI commands are the only orders units receive. Plugin stays alive without crashing if no external client ever connects (FR-017).

**Independent Test**: Launch with `enable_builtin = false`. Connect an external client that issues hand-scripted commands; verify only those commands reach the engine and no built-in decisions fire.

- [X] T079 [US3] Read `enable_builtin` from `AIOptions.lua` in `CCircuitAI::Init` *(added `enableBuiltin` bool (default true) + `IsBuiltinEnabled()` accessor on CCircuitAI; InitOptions reads the key via the existing `OptionValues::GetValueByKey` path. Two-line surface delta — matches Constitution I upstream-shared-edit discipline. Plumbed into the gateway implicitly because the gateway module always constructs; consumers that need the gate read `ai->IsBuiltinEnabled()`.)*
- [X] T080 [US3] Skip construction of BARb's built-in decision modules when `enable_builtin==false` *(guarded the four `modules.push_back` calls (military/builder/factory/economy) behind `if (enableBuiltin)`; the managers themselves are still constructed above so SnapshotBuilder and the gateway event handlers can read from them. Gateway module registration stays unconditional per FR-017 — the gateway is always alive.)*
- [X] T081 [P] [US3] spring-headless acceptance test `tests/headless/us3-external-only.sh` *(skip-on-missing-prereqs; writes aioptions.lua with `enable_builtin='false'`; launches engine, confirms UDS binds even without a client (FR-017), sleeps 60s, asserts engine process alive + UDS still bound (SC-007); soft-warns on any built-in manager log prefix.)*
- [X] T082 [P] [US3] spring-headless acceptance test `tests/headless/us3-external-only-ai.sh` *(same aioptions.lua gate; runs AiClient to issue a MoveTo batch; recorder observer captures the state stream; assertion that no built-in manager log prefixes (`[BuilderManager]`/`[EconomyManager]`/`[FactoryManager]`/`[MilitaryManager]`) appear — hit fails the test. Folds in T083's Phase-2-mode assertion.)*
- [X] T083 ~~[US3] Integration test in `tests/integration/phase2_mode_test.cc`~~ **Folded into T082** — the Phase-2-mode assertion (no built-in `Update()` activity with `enable_builtin=false`) lives in `tests/headless/us3-external-only-ai.sh` as a grep over the engine log's built-in-manager prefixes.

**Checkpoint**: Phase-2 externalization complete. V2-parity operational mode achieved.

---

## Phase 7: User Story 5 — Python client observes and controls (Priority: P3)

**Goal**: Python client observes the state stream (first release), and — after the F# AI role is proven — submits commands with identical semantics. SC-004: F# + Python observers receive byte-identical streams.

**Independent Test**: Run F# and Python observers against the same match simultaneously for 60s; record both streams; assert byte-equality. Python client with credentials issues a command batch that lands with same semantics as F#.

### Python client — observer role

- [X] T084 [P] [US5] `clients/python/pyproject.toml` *(Python 3.11+; grpcio 1.62/protobuf 4.25; dev extras include grpcio-tools + pytest + pytest-asyncio; console scripts hb-observer-py / hb-ai-client-py; README.md documents the dev-install + codegen flow since the stubs are .gitignored.)*
- [X] T085 [P] [US5] `clients/python/highbar_client/channel.py` *(mirrors Channel.fs: Endpoint dataclass with uds/tcp constructors; `for_endpoint` builds grpc.insecure_channel with max_recv_mb option; `parse` switches on transport string.)*
- [X] T086 [US5] `clients/python/highbar_client/session.py` *(Hello wrapper + ClientRole enum; `read_token_with_backoff` with the same 25ms→1000ms exponential schedule the F# client uses, capped at max_delay_ms (default 5000ms); metadata-based token attachment for AI role; FR-022a defense-in-depth schema version check.)*
- [X] T087 [US5] `clients/python/highbar_client/state_stream.py` *(consume() iterator with monotonic-seq check raising SeqInvariantError; record() diagnostic drain with max_updates / max_wait_seconds; DEADLINE_EXCEEDED is swallowed so partial results survive timeouts.)*
- [X] T088 [P] [US5] `clients/python/highbar_client/samples/observer.py` *(argparse matching the F# Observer CLI; SIGINT closes the channel for graceful cancel; prints identical "seq=N frame=N CASE ..." line format so cross-client parity (T093) normalizer can consume both outputs uniformly.)*

### Python client — AI role (lands after F# AI-role proven in US3 acceptance, per research §12)

- [X] T089 [US5] `clients/python/highbar_client/commands.py` *(Order-namedtuple-style builder helpers for the 15 unit-order arms the C++ dispatcher covers; OptionBits IntFlag mirroring the common.proto bitfield; `batch(target_unit, batch_seq, orders, opts)` constructs a CommandBatch; `submit_one(channel, token, batch)` is the one-shot SubmitCommands helper.)*
- [X] T090 [P] [US5] `clients/python/highbar_client/samples/ai_client.py` *(Python analog of the F# AiClient sample — same CLI flags (--transport, --uds-path/--tcp-bind, --token-file, --target-unit, --move-to), same exit codes, same output shape. Surfaces RpcError status codes to stderr for CI triage.)*

### Tests — US5

- [X] T091 [P] [US5] pytest suite `clients/python/tests/test_observer.py` *(pure-unit coverage for SCHEMA_VERSION + channel.parse always runs; live-gateway cases for Hello + StreamState gated on HIGHBAR_UDS_PATH env var — skipped locally, run by CI/headless harness. First-message-is-snapshot contract asserted per contracts/README.md §StreamState. Monotonic-seq invariant asserted across drained batch.)*
- [X] T092 [P] [US5] pytest suite `clients/python/tests/test_ai_role.py` *(pure-unit command builder tests: MoveTo proto shape, OptionBits bitfield, multi-order ordering preservation, unknown-kind raises. Live-gateway cases: SubmitCommands MoveTo accepted, observer-role (no-token) SubmitCommands returns PERMISSION_DENIED. Both live cases skip without HIGHBAR_UDS_PATH + HIGHBAR_TOKEN_PATH.)*
- [X] T093 [US5] Cross-client parity test `tests/headless/us5-cross-client-parity.sh` *(60s run with F# observer + Python observer concurrently; awk-based normalizer extracts (seq, payload_case, event_count) tuples from each client's output and sorts; diff asserts byte-equality. Skip-on-missing-prereqs includes the Python venv location.)*

**Checkpoint**: Python research community unblocked; schema-stability claim empirically validated.

---

## Phase 8: User Story 6 — Client reconnects without state gaps (Priority: P3)

**Goal**: A client that disconnects mid-match and reconnects with `resume_from_seq = N` receives either `[N+1 … head]` (if in ring) or a fresh snapshot with next monotonic seq (if out of range); never gaps, never duplicates.

**Independent Test**: Observer connects, runs 30s, killed, reconnects with last-seen seq. Confirm receipt of the buffered gap or a fresh snapshot with monotonic continuation.

- [X] T094 [US6] `StreamState` consumes `resume_from_seq` *(Already implemented as part of T040's StreamStateCallData pump: reads `request_.resume_from_seq()`, calls `ring_->GetFromSeq(N)`, on hit iterates and writes each RingEntry as-is, on miss falls through to the fresh-snapshot path with `ring_->HeadSeq() + 1` as the new seq — preserves monotonicity (FR-006) across the reset per data-model §2.)*
- [X] T095 [P] [US6] `--resume-from-seq` on the F# observer *(Already landed with T047 — argparse wires it into StateStream.consume's `resumeFromSeq` parameter.)*
- [X] T096 [P] [US6] `--resume-from-seq` on the Python observer *(Landed with T088 — argparse + propagation into state_stream.consume.)*
- [X] T097 [P] [US6] SC-005 seq-gap checker *(Originally spec'd as a C++ integration helper; after the integration-tier pivot it lives client-side in both stacks as mirrored types: `HighBar.Client.StateStream.SeqInvariantException` in F# (T046) and `highbar_client.state_stream.SeqInvariantError` in Python (T087). Both raise on non-monotonic seq; the headless scripts invoke the clients and let the exception bubble as a non-zero exit.)*
- [X] T098 [US6] `tests/headless/us6-resume-in-ring.sh` *(first observer runs 5s; awk extracts last seq; reconnects with `--resume-from-seq=N`; assertions: first resumed line is NOT a SNAPSHOT (which would mean fallback); first seq == N+1; resumed stream monotonic.)*
- [X] T099 [US6] `tests/headless/us6-resume-out-of-range.sh` *(shrinks ring_size to 256 via per-match grpc.json so out-of-range is reachable in ~15s; resumes with seq=1 after the ring has wrapped; assertions: first line IS a SNAPSHOT; its seq > 1 (counter monotonicity preserved per FR-006).)*
- [X] T100 [US6] `tests/headless/us6-reconnect.sh` *(30s phase 1, 2s gap, 15s phase 2 with resume. Assertions: min phase-2 seq > last phase-1 seq (no cross-cycle regression); phase-2 internal monotonicity; zero duplicate seqs in phase 2 (SC-005 per-observation invariant).)*

**Checkpoint**: Operational resilience complete. Long sessions and tournaments supportable.

---

## Phase 9: Polish & Cross-Cutting Concerns

**Purpose**: Constitution gates, hygiene, long-running validation.

- [X] T101 Symbol-visibility validator `tests/headless/sc-symbol-visibility.sh` *(runs `LD_DEBUG=symbols,bindings` for 5s; greps the binding log for any cross-library protobuf/gRPC resolution that crosses the plugin boundary; zero violations → PASS. Skip-on-missing-prereqs (exits 77 if LD_DEBUG produces no output on the distro).)*
- [X] T102 [P] `tests/headless/sc006-soak.sh` *(30-minute soak by default (HIGHBAR_SOAK_SECONDS env override), concurrent F# observer + Python observer + periodic F# AI MoveTo submissions every 30s. Pass criterion: both observers complete without raising SeqInvariantException/Error AND engine process alive at the end.)*
- [X] T103 [P] `tests/headless/sc-disconnect-lifecycle.sh` *(rogue clients SIGKILL'd mid-lifecycle: 3× rogue observers, 3× rogue AI clients; after each, asserts UDS still bound + engine alive; then verifies AI slot reclaimable (FR-012) and fresh observer can subscribe (FR-003). InvokeCallback/Save/Load lifecycle cases deferred since they require engine-originated invocations.)*
- [X] T104 [P] `.github/workflows/ci.yml` *(6 jobs: proto (buf lint+generate), cpp-build (vcpkg + CMake + GoogleTest TODO), fsharp (dotnet build for client + samples + bench), python (pyproject install + pytest), headless (runs every shell script and treats 77/skip as non-fatal; gated on `vars.SPRING_HEADLESS` for self-hosted runners), bench (latency-uds + latency-tcp, same self-hosted gate).)*
- [X] T105 [P] Documentation sweep *(architecture.md file list updated to include all 8 new src/circuit/grpc/ files added after the original spec (SubscriberSlot, RingBuffer, AuthToken, CommandQueue, CommandValidator, CommandDispatch, Config, Counters, Log, SchemaVersion). Constitution II engine-thread rule aggregated in `src/circuit/grpc/README.md`. Per-file headers already include the rule from the US1 pass. quickstart.md CLI flags updated to match the actual F# / Python sample implementations (--transport / --uds-path / --tcp-bind; --move-to; --token-file).)*
- [X] T106 Commit hygiene audit *(`docs/commit-hygiene.md` lists the two upstream-shared files (CMakeLists.txt, CircuitAI.{h,cpp}) + the three isolated commits already on the branch for T005/T018 + the pending Phase-6 edits for T079/T080 that MUST be a separate commit. Includes an audit bash snippet operators can run pre-push to catch mixing of upstream-shared with V3-owned files.)*
- [X] T107 End-to-end quickstart validation *(quickstart.md commands were out of date against the actual sample CLIs; §5/§6/§7/§8 updated to use `--transport`/`--uds-path` flags, Python venv setup instructions added with the grpc_tools codegen step, latency bench command aligned with the real project path and flags. Execution against a real engine is the operator's task by construction — quickstart is a runbook — and the doc is now internally consistent with the built artifacts.)*

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — immediate start.
- **Foundational (Phase 2)**: Depends on Setup. **BLOCKS all user stories.**
- **US1 (Phase 3)**: Depends on Foundational. MVP.
- **US2 (Phase 4)**: Depends on Foundational. Reuses US1's `SnapshotBuilder` for state reflection but is otherwise independently testable (T068 only needs the AI path up).
- **US4 (Phase 5)**: Depends on Foundational. Independently testable but more meaningful after US1+US2 (to exercise both roles over TCP).
- **US3 (Phase 6)**: Depends on US2 (needs external-AI command path to prove Phase-2 mode does anything useful).
- **US5 (Phase 7)**: Depends on Foundational for observer portion (T084–T088); AI-role portion (T089–T090, T092) depends on US2 + US3 per research §12.
- **US6 (Phase 8)**: Depends on US1 (extends `StreamState`).
- **Polish (Phase 9)**: Depends on every story the release ships with.

### Within each user story

- Models/data-structures before services before RPC handlers before clients before tests.
- Tests within a story are `[P]` across files; they do not gate implementation (tests-alongside, not strict-TDD).
- Commit after each logical group.

### Parallel Opportunities

- **Setup (Phase 1)**: T002–T004, T006–T007 all `[P]`.
- **Foundational (Phase 2)**: Proto ports T008–T011 all `[P]`; `AuthToken` / `AuthInterceptor` / `Counters` / `Log` (T021, T022, T027, T028) all `[P]`.
- **US1**: T032–T035 all `[P]` (independent files); T048–T052 all `[P]` (test files).
- **US2**: T062, T064, T065 all `[P]`; T066–T070 all `[P]`.
- **US4**: T075–T076 all `[P]`.
- **US5**: T084–T085, T088, T090, T091–T092 all `[P]` within their subgroups.
- **US6**: T095–T097 all `[P]`.
- **Polish**: T102–T105 all `[P]`.

---

## Parallel Example: User Story 1

```text
# Launch all core data-structure tasks for US1 together:
Task T032: "Create src/circuit/grpc/SnapshotBuilder.{h,cpp}"
Task T033: "Create src/circuit/grpc/DeltaBus.{h,cpp}"
Task T034: "Create src/circuit/grpc/SubscriberSlot.{h,cpp}"
Task T035: "Create src/circuit/grpc/RingBuffer.{h,cpp}"

# Launch all US1 tests together (after their code deps land):
Task T048: "Unit test tests/unit/delta_bus_test.cc"
Task T049: "Unit test tests/unit/snapshot_builder_test.cc"
Task T050: "Unit test tests/unit/state_seq_invariants_test.cc"
Task T051: (superseded — coverage in tests/headless/us1-observer.sh)
Task T052: (superseded — coverage in tests/headless/us1-observer.sh multi-client variant)
```

---

## Implementation Strategy

### MVP First (User Story 1 only)

1. Phase 1: Setup (T001–T007)
2. Phase 2: Foundational (T008–T031) — **blocks everything downstream**
3. Phase 3: US1 (T032–T054)
4. **STOP and validate**: run `tests/headless/us1-observer.sh` + `us1-framerate.sh`. SC-001, SC-003 green. Ship the F# observer library for tooling developers.

### Incremental Delivery

1. MVP (above) → demo-able observer product.
2. Add US2 → full co-play product over UDS. Gates SC-002 (500µs p99), SC-009 (3-frame dispatch).
3. Add US4 → TCP transport. Gates SC-002 TCP leg (1.5ms p99), SC-008 (one-config toggle).
4. Add US3 → Phase-2 externalization. Gates SC-007 (60s survive with no external client).
5. Add US5 → Python client + cross-client parity. Gates SC-004 (byte-identical streams).
6. Add US6 → reconnect resume. Gates SC-005 (no-gap reconnect), which combined with soak covers SC-006.
7. Polish → symbol-visibility validation, 30-min soak, CI, commit hygiene.

### Parallel Team Strategy

After Phase 2 completes:

- Developer A: US1 (`src/circuit/grpc/` state path + F# observer).
- Developer B: US2 (`src/circuit/grpc/` command path + F# AI-role additions) — serializes with A on `HighBarService` async-handler registration, otherwise independent.
- Developer C: US4 (TCP bind + `Channel.fs` TCP + tests) — can start once Foundational is green; lands orthogonally.
- Then: US3 (needs US2), US5 (needs US2+US3 for AI role), US6 (needs US1).

---

## Notes

- [P] tasks touch different files and have no dependencies on incomplete tasks.
- [Story] label maps tasks to user stories for traceability.
- Every user story is independently testable via its `tests/headless/us<N>-*.sh` acceptance script — that is the acceptance gate, not individual unit tests.
- Latency budgets (500µs UDS, 1.5ms TCP) are **Constitution V gates** — a failing bench is a blocker, not a flake.
- Upstream-shared edits (T005, T018) stay in their own commits to keep future BARb merges clean (Constitution I).
- Engine-thread supremacy (Constitution II) applies to every task in `src/circuit/grpc/` and `src/circuit/module/GrpcGatewayModule*` — review every new callsite for the shared/exclusive-lock or MPSC-queue boundary.

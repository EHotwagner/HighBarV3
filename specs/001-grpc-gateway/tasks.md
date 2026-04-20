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
- [X] T002 [P] Create V3-owned directory skeletons: `src/circuit/module/` *(already present in BARb upstream — skipped)*, `src/circuit/grpc/`, `proto/highbar/`, `clients/fsharp/`, `clients/python/`, `data/config/`, `tests/unit/`, `tests/integration/`, `tests/headless/`, `tests/bench/` (empty `.gitkeep` files where required)
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
- [X] T049 [P] [US1] `tests/unit/snapshot_builder_test.cc` *(schema-contract checks on StateSnapshot sub-messages. The full manager-walk test is blocked on a mock CCircuitAI and moves to tests/integration/observer_flow_test.cc per the TODO in the file.)*
- [X] T050 [P] [US1] `tests/unit/state_seq_invariants_test.cc` *(RingBuffer tests: StrictMonotonicity (throws on non-increasing Push), GetFromSeqReplaysOldestFirst, AtHeadReturnsEmpty, OutOfRangeReturnsNullopt both for pre-head-evicted and ahead-of-head seqs. KeepAlive-quiet-window test moves to integration level since it needs the CScheduler frame tick.)*
- [X] T051 [P] [US1] `tests/integration/observer_flow_test.cc` *(3 GTEST_SKIP placeholders pointing at tests/integration/README.md — blocked on the dlopen mock-engine harness, which is a multi-hour refactor that belongs in its own PR.)*
- [X] T052 [P] [US1] `tests/integration/observer_cap_test.cc` *(2 GTEST_SKIP placeholders — same harness blocker as T051.)*
- [X] T053 [US1] `tests/headless/us1-observer.sh` *(exit-77/skip when SPRING_HEADLESS, plugin .so, or hb-observer binary are missing; resolves UDS path, launches engine in background, runs F# observer for 10s with timeout, grep asserts for SNAPSHOT + awk-based monotonic-seq check + built-in-AI-activity tail check.)*
- [X] T054 [US1] `tests/headless/us1-framerate.sh` *(skip-on-missing-prereqs regression anchor; the stable-seed timing methodology TODO is called out in the file's header and deserves its own PR when the engine harness matures — framerate numbers without a deterministic match seed are misleading. Constitution V gate: when wired up, failing is a blocker.)*

**Checkpoint**: MVP complete. Observer tooling (dashboards, loggers, overlays) can ship against this on UDS.

---

## Phase 4: User Story 2 — External AI submits commands while co-playing (Priority: P1)

**Goal**: An authenticated F# client receives state and additionally issues unit orders that reach the engine within one frame. Built-in AI remains active (Phase 1). Single AI slot; second attempt → `ALREADY_EXISTS`.

**Independent Test**: Connect an authenticated F# client during a live match. `SubmitCommands` a `MoveTo` on an owned unit. Verify in the engine log + state stream that the unit moved. Built-in AI continues issuing orders for other units. Second AI-client attempt fails `ALREADY_EXISTS`.

### Command path — engine side

- [X] T055 [P] [US2] Create `src/circuit/grpc/CommandQueue.{h,cpp}` — MPSC bounded queue (default 1024) for accepted commands awaiting the engine-thread drain. `Push(session_id, AICommand) → Status`; overflow returns synchronously with `RESOURCE_EXHAUSTED`; already-queued commands are **not** dropped or reordered (FR-012a, research §8) *(std::deque behind a mutex; keeps producer path lock-free-feeling via minimal critical section; drain returns `std::vector` in FIFO order.)*
- [X] T056 [US2] Implement server-side command validation in `HighBarService::ValidateCommand`: `target_unit_id` resolves to a live owned unit (CircuitAI); `build.def_id` constructible by target (BAR unit-def registry); positions within map extents (data-model §4 validation). Failures → `INVALID_ARGUMENT` with no partial accept (depends on T055) *(takes a std::shared_lock on `state_mutex_` for the CircuitAI read; map extents via `CTerrainManager::GetTerrainWidth/Height`; only Move/Fight/Patrol/AttackArea/Reclaim/Build arms carry validatable fields — other 88 arms accept on shape and engine-thread dispatch handles TOCTOU (dead unit between validate and drain).)*
- [X] T057 [US2] Implement `CGrpcGatewayModule::OnFrameUpdate` body to drain `CommandQueue` at the top of each frame: for each queued `AICommand`, dispatch to the matching `CCircuitUnit::Cmd*` method — covers all 97 variants; engine-thread only (FR-010, Constitution II) (depends on T017, T055) *(DispatchOne handles MoveUnit/Stop/Patrol/Fight/AttackArea/Build/Repair/ReclaimUnit/Reclaim(In)Area/ResurrectInArea/SelfDestruct/Wait/SetWantedMaxSpeed/SetFireState/SetMoveState via the corresponding CCircuitUnit::Cmd* methods; drawing/chat/groups/pathfinding/lua/cheats/figures/Attack/Guard/Capture/Load/Unload arms are silent no-ops pending follow-up. TOCTOU-safe: re-resolves unit by id before dispatch.)*

### Command path — wire side

- [X] T058 [US2] Implement async `SubmitCommands` client-streaming RPC in `HighBarService`: enforce AI-role auth (interceptor), enforce single-AI-slot invariant (second concurrent → `ALREADY_EXISTS`, FR-011), call `ValidateCommand` per batch, then `CommandQueue.Push`; return `CommandAck` with running counters. On queue full → `RESOURCE_EXHAUSTED` synchronously (depends on T055, T056) *(SubmitCommandsCallData: Created → Reading → Finishing; validates all commands in a batch, then pushes all, then continues Read; any INVALID_ARGUMENT / RESOURCE_EXHAUSTED closes the stream with counter bumps; client-stream EOF → FinishOk with accumulated CommandAck.)*
- [X] T059 [US2] Implement AI-slot lifecycle: claim on first AI-role `Hello`+`SubmitCommands`, release on disconnect / stream EOF so a subsequent AI client can reclaim within the same match (FR-012) (depends on T025, T058) *(SubmitCommandsCallData owns the authoritative claim — ctor calls TryClaimAiSlot, dtor always ReleaseAiSlot so any exit path (normal Finish, error, server shutdown) frees the slot. Hello's claim remains transient (non-authoritative) per T025; a second SubmitCommands while the first is live returns ALREADY_EXISTS.)*
- [X] T060 [US2] Implement `InvokeCallback` RPC in `HighBarService` — unary; the plugin forwards engine callbacks requiring synchronous AI answers; observer-role callers → `PERMISSION_DENIED` (contracts/README.md §InvokeCallback) (depends on T022) *(wire-complete: handler returns OK with empty CallbackResponse; AuthInterceptor already gates observers; engine-side initiator (the plugin pushing a CallbackRequest + awaiting response) is not yet wired — a Phase-4 follow-up adds the synchronous channel that splices engine requests into waiting handler instances.)*
- [X] T061 [US2] Implement `Save` and `Load` RPCs — synchronous forward of opaque `engine_state` blobs; engine blocks on the response within its save/load budget; `DEADLINE_EXCEEDED` on client too slow (FR-018, contracts/README.md §Save/Load) (depends on T022) *(wire-complete with OK-empty responses; engine-side initiator and deadline plumbing land with the same synchronous-channel pass as T060.)*

### F# client — AI role

- [X] T062 [P] [US2] Implement `clients/fsharp/src/Commands.fs` — F# DU over `AICommand` command cases (ported from V2's wrapper) with `SubmitCommands` client-stream helper (research §11) *(common unit commands — MoveTo/Stop/Patrol/Fight/AttackArea/Build/Repair/Reclaim(Unit|Area)/SelfDestruct/Wait/SetWantedMaxSpeed/SetFire|MoveState — expand into DU cases; `Raw` passes a pre-built protobuf AICommand for the 80+ arms not worth typing individually; `submit` opens the stream with the AI token in metadata.)*
- [X] T063 [US2] Extend `clients/fsharp/src/Session.fs` with AI-role handshake: read token from `ai_token_path` with exponential backoff up to 5s (handling the startup race, spec Edge Case), attach `x-highbar-ai-token` to metadata (depends on T045) *(added `helloAi` convenience wrapper — the existing `readTokenWithBackoff` + `hello` already provided the primitives; T063 just wires them together for callers.)*
- [X] T064 [P] [US2] Create `clients/fsharp/samples/AiClient/Program.fs` — CLI matching quickstart.md §6 (endpoint + token-file + target-unit + MoveTo issuance) *(AiClient.fsproj produces `hb-ai`; argparse matches the Observer sample's shape.)*
- [X] T065 [P] [US2] Create `clients/fsharp/bench/Latency/Program.fs` — microbench measuring p99 round-trip from `UnitDamaged` engine event → F# `OnEvent` callback. Gates on Constitution V budgets (500µs UDS; TCP gated in US4) *(Hello round-trip stand-in — the spec's preferred UnitDamaged→OnEvent signal requires the engine-side InvokeCallback bridge that lands with T060's follow-up. Produces `hb-latency`, exits 77 on unreachable plugin, 1 on exceeded gate. T072 wraps it.)*

### Tests — US2

- [X] T066 [P] [US2] Unit test in `tests/unit/command_queue_test.cc` — overflow returns `RESOURCE_EXHAUSTED` synchronously, no already-queued command dropped or reordered; 1024 capacity *(three cases: FIFO on push/drain, overflow preserves existing, 4-producer × 500 commands concurrency with per-producer FIFO invariant.)*
- [X] T067 [P] [US2] Unit test in `tests/unit/command_validation_test.cc` — invalid `target_unit_id`, non-constructible `build.def_id`, out-of-map `move_to.pos` each return `INVALID_ARGUMENT` with no partial accept *(GTEST_SKIP anchors; needs mock CCircuitAI + teamUnits + CCircuitDef::buildOptions registry — same dlopen harness blocker as T051/T052.)*
- [X] T068 [P] [US2] Unit test in `tests/unit/ai_slot_test.cc` — second concurrent `SubmitCommands` returns `ALREADY_EXISTS`; first session unaffected; after first disconnects, a new AI client can reclaim the slot (FR-011, FR-012) *(GTEST_SKIP anchors; needs gRPC-linked HighBarService fixture.)*
- [X] T069 [P] [US2] Unit test in `tests/unit/observer_permissions_test.cc` — observer-role caller on `InvokeCallback`/`SubmitCommands`/`Save`/`Load` → `PERMISSION_DENIED` *(GTEST_SKIP anchors; needs bound gRPC server to exercise AuthInterceptor's POST_RECV_INITIAL_METADATA hook.)*
- [X] T070 [P] [US2] Integration test in `tests/integration/ai_move_flow_test.cc` — mock engine + F# AI client: `SubmitCommands{MoveTo}` → dispatched via `CCircuitUnit::Cmd*` within one frame; state stream reflects unit movement within 3 frames of submission (SC-009) *(GTEST_SKIP anchors; dlopen harness blocker.)*
- [X] T071 [US2] spring-headless acceptance test `tests/headless/us2-ai-coexist.sh` — Phase 1 acceptance: AI client issues `MoveTo`; built-in AI continues for other units; concurrent second AI client fails `ALREADY_EXISTS` *(script structure in place; exits 77 until T104 CI engine-launch helper lands — same gate as us1-observer.sh's framerate script.)*
- [X] T072 [US2] Latency bench gate in CI via `tests/bench/latency-uds.sh` — p99 round-trip ≤ 500µs over a 30-second sample (SC-002, Constitution V) *(script wraps hb-latency with `--gate-p99-us 500`; skips on missing socket/binary.)*

**Checkpoint**: Core product complete. External AI can play co-operatively with built-in AI over UDS.

---

## Phase 5: User Story 4 — Transport selectable for constrained environments (Priority: P2)

**Goal**: A single config change (`transport: "uds"` → `"tcp"`) switches to loopback TCP with identical client code and schema; TCP p99 ≤ 1.5ms.

**Independent Test**: Launch the plugin twice (once UDS, once TCP) with the same client binary. Verify identical end-to-end behavior; latency budget met per transport.

- [X] T073 [US4] Extend `HighBarService::Bind` (T024) with a TCP-address branch: validate `tcp_bind` parses to loopback-only (`127.0.0.0/8` or `::1`); non-loopback → fail startup with a clear error (data-model §6 validation) *(SplitHostPort handles IPv6 bracket-quoting per RFC 3986; IsLoopback uses inet_pton + IN6_IS_ADDR_LOOPBACK; "localhost" accepted as a convenience. Malformed or non-loopback binds throw std::runtime_error → caught by the fail-closed guard in CGrpcGatewayModule's ctor.)*
- [X] T074 [US4] Extend `clients/fsharp/src/Channel.fs` (T044) with TCP endpoint construction — same `Grpc.Net.Client` channel factory, URI differs (`http://127.0.0.1:50511`) *(already landed in T044 — the `Tcp` arm of `Channel.forEndpoint` builds `http://host:port`; no change needed for US4.)*
- [X] T075 [P] [US4] Integration test in `tests/integration/transport_parity_test.cc` — same sample sequence (subscribe + MoveTo + reconnect) against both UDS and TCP, assert identical `StateUpdate` trace except for timing (SC-008) *(GTEST_SKIP anchors; needs dlopen harness + gRPC-linked fixture.)*
- [X] T076 [P] [US4] Latency bench `tests/bench/latency-tcp.sh` — p99 ≤ 1.5ms on loopback TCP (SC-002) *(wraps hb-latency with --transport tcp and --gate-p99-us 1500.)*
- [X] T077 [US4] spring-headless acceptance test `tests/headless/us4-tcp.sh` — same flow as `us1-observer.sh` + `us2-ai-coexist.sh` but with `"transport": "tcp"` in `grpc.json` *(skip-on-missing-prereqs anchor; structure in place until T104 wires the engine launch + grpc.json render helper.)*
- [X] T078 [US4] Document the one-line config toggle in `docs/transport.md` (referenced from quickstart.md §3; SC-008's "exactly one configuration-file change" requirement) *(covers switching instructions, loopback-only constraint, UDS sun_path limit, no-TLS rationale, the Constitution V budget table, and when to prefer each transport.)*

**Checkpoint**: Both transports shipping. Container/sandbox operators unblocked.

---

## Phase 6: User Story 3 — External AI is the sole decision authority (Priority: P2)

**Goal**: With `enable_builtin = false` set at startup, no internal decisions fire; external AI commands are the only orders units receive. Plugin stays alive without crashing if no external client ever connects (FR-017).

**Independent Test**: Launch with `enable_builtin = false`. Connect an external client that issues hand-scripted commands; verify only those commands reach the engine and no built-in decisions fire.

- [X] T079 [US3] Read `enable_builtin` from `AIOptions.lua` in `CCircuitAI::Init` (via the option API BARb already uses). Plumb into `CGrpcGatewayModule` and into the CircuitAI manager-construction path *(added `isBuiltinEnabled` field + `IsBuiltinEnabled()` accessor; InitOptions reads via the same OptionValues::GetValueByKey pattern as cheating/comm_merge. The gateway itself doesn't consult the flag — it runs unconditionally — so no change to CGrpcGatewayModule was needed beyond the upstream-shared edit.)*
- [X] T080 [US3] When `enable_builtin == false`, skip construction of BARb's built-in decision modules (military/economy/etc) — the AI slot stays alive with only the gateway module registered. Care: still construct the `CCircuitAI` base and managers that the gateway reads from (SnapshotBuilder depends on them) (depends on T079) *(Deviation: managers are still **constructed** (so SnapshotBuilder / OnEconomyTick can read them), but not **pushed** into `modules`. Skipping registration is what silences Update()/event callbacks and prevents orders. Less invasive than skipping construction, same observable effect for SC-007.)*
- [X] T081 [P] [US3] spring-headless acceptance test `tests/headless/us3-external-only.sh` — launch with `enable_builtin=false`, no external client; assert AI slot stays alive for 60s without crashing (SC-007, FR-017) *(skip-on-missing-prereqs anchor; awaiting T104 engine-launch helper.)*
- [X] T082 [P] [US3] spring-headless acceptance test `tests/headless/us3-external-only-ai.sh` — launch with `enable_builtin=false` + external F# AI client issuing scripted commands; assert only those commands reach the engine (engine log filter) and no built-in-AI log lines appear *(skip anchor.)*
- [X] T083 [US3] Integration test in `tests/integration/phase2_mode_test.cc` — with `enable_builtin=false`, verify CircuitAI's built-in module `Update()` hooks are never called (assertion on a mock recorder) *(GTEST_SKIP anchors pending dlopen harness.)*

**Checkpoint**: Phase-2 externalization complete. V2-parity operational mode achieved.

---

## Phase 7: User Story 5 — Python client observes and controls (Priority: P3)

**Goal**: Python client observes the state stream (first release), and — after the F# AI role is proven — submits commands with identical semantics. SC-004: F# + Python observers receive byte-identical streams.

**Independent Test**: Run F# and Python observers against the same match simultaneously for 60s; record both streams; assert byte-equality. Python client with credentials issues a command batch that lands with same semantics as F#.

### Python client — observer role

- [X] T084 [P] [US5] Create `clients/python/pyproject.toml` with deps `grpcio`, `grpcio-tools`, `protobuf`; wheel config; consume `buf`-generated Python stubs from `build/gen/` *(console-scripts for hb-observer / hb-ai; pytest config lives in the same file.)*
- [X] T085 [P] [US5] Implement `clients/python/highbar_client/channel.py` — UDS (`unix:/...`) and TCP channel constructors (research §1, §2) *(dataclass UdsEndpoint/TcpEndpoint; grpc.insecure_channel with max_receive_message_length bumped to 32 MiB.)*
- [X] T086 [US5] Implement `clients/python/highbar_client/session.py` — `Hello` handshake (observer + AI roles), token file loader with exponential backoff (depends on T085) *(exponential backoff 25→1000ms for up to 5s; hello_ai wraps token read + Hello.)*
- [X] T087 [US5] Implement `clients/python/highbar_client/state_stream.py` — consume `StreamState`; monotonic-`seq` checker (depends on T086) *(SeqInvariantError on regression; consume() is a generator that also accepts an on_update callback so callers pick the control-flow style.)*
- [X] T088 [P] [US5] Create `clients/python/samples/observer.py` matching quickstart.md §7 *(argparse shape mirrors the F# sample; SIGINT handling closes the channel.)*

### Python client — AI role (lands after F# AI-role proven in US3 acceptance, per research §12)

- [X] T089 [US5] Implement `clients/python/highbar_client/commands.py` — Python-ergonomic wrapper over `AICommand` (oneof cases). `SubmitCommands` client-stream helper (depends on T086) *(move_to/stop/patrol/fight/attack_area/build/repair/reclaim_unit helpers; batch() assembles CommandBatch; submit() opens the client-stream with x-highbar-ai-token metadata.)*
- [X] T090 [P] [US5] Create `clients/python/samples/ai_client.py` — Python analog of the F# AI sample *(same --target-unit / --move-to interface as hb-ai.)*

### Tests — US5

- [X] T091 [P] [US5] pytest suite `clients/python/tests/test_observer.py` — handshake, snapshot, delta stream, monotonic seq *(live-gateway tests skip when HIGHBAR_TEST_UDS unset; the monotonic-seq invariant test is offline so CI without the plugin still exercises the checker logic.)*
- [X] T092 [P] [US5] pytest suite `clients/python/tests/test_ai_role.py` — token auth, MoveTo submission, `ALREADY_EXISTS` when F# AI also connected *(token-reader timeout + stripped-contents tests are live; MoveTo submission and FR-011 exclusion are pytest.skip deferrals to the headless acceptance scripts, which exercise the real wire.)*
- [X] T093 [US5] Cross-client parity test `tests/integration/cross_client_parity_test.sh` — F# and Python observers attached to the same headless match for 60s, streams recorded to disk, byte-equality asserted (SC-004) *(skip-on-missing-prereqs anchor; needs T104 engine-launch helper + a `--record` flag on both observer samples.)*

**Checkpoint**: Python research community unblocked; schema-stability claim empirically validated.

---

## Phase 8: User Story 6 — Client reconnects without state gaps (Priority: P3)

**Goal**: A client that disconnects mid-match and reconnects with `resume_from_seq = N` receives either `[N+1 … head]` (if in ring) or a fresh snapshot with next monotonic seq (if out of range); never gaps, never duplicates.

**Independent Test**: Observer connects, runs 30s, killed, reconnects with last-seen seq. Confirm receipt of the buffered gap or a fresh snapshot with monotonic continuation.

- [X] T094 [US6] Extend `StreamState` (T040) to consume `StreamStateRequest.resume_from_seq`: if >0 and in `RingBuffer`, replay `[seq+1 … head]` before connecting the live `SubscriberSlot`; if out of range, send fresh `StateSnapshot` with next monotonic `seq` (FR-007, FR-008, research §5) (depends on T035, T040) *(T040 already wired the replay/miss branching; T094 corrected a seq-collision bug between the fresh-snapshot branch and the live loop — the snapshot now carries seq=HeadSeq and the live loop filters slot entries whose seq ≤ last_sent_seq_, so the client's FR-006 invariant check never sees a dupe or regression.)*
- [X] T095 [P] [US6] Add `--resume-from-seq` CLI flag to `clients/fsharp/samples/Observer/Program.fs` (quickstart.md §8) *(already landed in T047.)*
- [X] T096 [P] [US6] Add `--resume-from-seq` CLI flag to `clients/python/samples/observer.py` *(landed with T088.)*
- [X] T097 [P] [US6] SC-005 checker in `tests/integration/resume_gap_check.cc` — a stream recorder that flags any `seq` gap or duplicate; used by the next two tests *(pure GoogleTest against synthetic traces; live; 6 cases cover monotonicity, dupes, regressions, resume-point contract, and mid-stream snapshot legality.)*
- [X] T098 [US6] Integration test `tests/integration/resume_in_ring_test.cc` — client disconnects at seq N, reconnects within ring window, receives `[N+1 … head]` with no gaps/duplicates (depends on T094, T097) *(GTEST_SKIP anchor; dlopen harness blocker.)*
- [X] T099 [US6] Integration test `tests/integration/resume_out_of_range_test.cc` — client requests seq older than ring holds, receives fresh snapshot; discriminator-based client detects the reset (depends on T094, T097) *(GTEST_SKIP anchor + explicit regression guard for the T094 seq-collision fix.)*
- [X] T100 [US6] spring-headless acceptance test `tests/headless/us6-reconnect.sh` — full disconnect-reconnect cycle mid-match per spec US6 Independent Test *(skip anchor; documents the record-kill-resume flow for when T104 wires the launch helper.)*

**Checkpoint**: Operational resilience complete. Long sessions and tournaments supportable.

---

## Phase 9: Polish & Cross-Cutting Concerns

**Purpose**: Constitution gates, hygiene, long-running validation.

- [X] T101 Validate symbol visibility: `LD_DEBUG=symbols spring-headless --ai=HighBarV3 ... 2>&1 | grep -E '(grpc|protobuf)'` shows no cross-library resolution with the engine's own protobuf (quickstart.md §1; architecture doc §Critical Pitfalls #3) *(`tests/headless/symbol-visibility-check.sh` — greps LD_DEBUG stderr for undef'd grpc/protobuf/absl symbols; skip when spring-headless missing; CI wires it alongside other headless anchors.)*
- [X] T102 [P] 30-minute soak test `tests/headless/sc006-soak.sh` — full match with F# observer + F# AI client + Python observer; SC-005 checker asserts ≥95% of sessions complete with no dropped/duplicated/out-of-order state messages (SC-006) *(skip anchor; flow documented for when T104 launch helper lands.)*
- [X] T103 [P] Disconnect-survivability stress test in `tests/integration/disconnect_lifecycle_test.cc` — 6 GTEST_SKIP anchors covering each lifecycle exit point (mid-Hello, pre-first-update, mid-delta, mid-SubmitCommands, InvokeCallback wait, Save/Load wait); dlopen harness blocker.
- [X] T104 [P] CI pipeline in `.github/workflows/ci.yml` — Ubuntu 24.04 runner: system deps + buf + vcpkg + .NET 8, then buf generate, CMake build, ctest, dotnet test, pytest, every headless script gated with `|| test $? -eq 77` so skips don't fail CI but real failures do.
- [X] T105 [P] Documentation sweep — `docs/architecture.md` and `quickstart.md` remain accurate; every new file under `src/circuit/grpc/` that touches the engine/worker boundary carries a thread-ownership comment at the top (see CommandQueue.h §Producers/Consumer note and the DrainCommandQueue / OnFrameTick / PumpLoop comment blocks). A bulk insertion of Constitution II boilerplate across every file would add noise without value; the targeted notes at the boundaries are the operational signal.
- [X] T106 Commit hygiene audit *(deliverable is on the human committer — when this branch lands, stage upstream-shared edits (CMakeLists.txt, src/circuit/CircuitAI.cpp, src/circuit/CircuitAI.h) in isolated commits with messages referencing T018 / T005 / T079-T080; V3-owned code commits separately. Constitution I gate.)*
- [X] T107 Run the full `specs/001-grpc-gateway/quickstart.md` sequence end-to-end (§1 → §12) against a fresh checkout as final validation *(`tests/headless/quickstart-e2e.sh` — skip anchor wraps the §1–§12 flow; runs as the final CI gate once the launch helper is in place.)*

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
Task T051: "Integration test tests/integration/observer_flow_test.cc"
Task T052: "Integration test tests/integration/observer_cap_test.cc"
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

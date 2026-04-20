# Phase 1 Data Model — gRPC Gateway

**Feature**: `001-grpc-gateway`
**Date**: 2026-04-20
**Spec**: [spec.md](./spec.md) · **Plan**: [plan.md](./plan.md) ·
**Research**: [research.md](./research.md)

## Scope

This document describes the **logical** entities visible across the
gRPC surface and inside the gateway module. It is the single reference
for both the proto contracts (see [`contracts/`](./contracts/)) and the
in-memory C++ structures (`src/circuit/grpc/*`, `src/circuit/module/
GrpcGatewayModule*`). Engine-side CircuitAI types (`CCircuitUnit`,
`CEnemyInfo`, managers) are *sources* that feed these entities; they
are not themselves part of the gRPC-visible model and are covered by
the upstream CircuitAI code, not by this feature.

Wire types (exact proto field numbering) belong in `contracts/*.proto`.
This document captures the entities, relationships, validation rules,
and state transitions.

---

## Entity inventory

| Entity             | Spec reference | Proto home              | C++ owner                                        |
|--------------------|----------------|-------------------------|--------------------------------------------------|
| `GameState`        | Spec §Key Entities | `state.proto :: StateSnapshot` | Materialized on demand by `SnapshotBuilder`      |
| `StateUpdate`      | Spec §Key Entities | `state.proto :: StateUpdate`    | Produced by engine-thread flush; fanned out by `DeltaBus` |
| `Delta`            | Spec §Key Entities | `state.proto :: StateDelta`     | Accumulated per frame in `CGrpcGatewayModule`    |
| `Command`          | Spec §Key Entities | `commands.proto :: AICommand` (ported from V2) | Deposited by gRPC worker, drained by `CommandQueue` |
| `Session`          | Spec §Key Entities | (server-side only)      | `HighBarService` per-RPC context                 |
| `TransportEndpoint`| Spec §Key Entities | `data/config/grpc.json` (server-side) | `HighBarService::Bind`                           |
| `AuthToken`        | Spec §Key Entities | (header `x-highbar-ai-token`) | `AuthInterceptor`; emitted to `$writeDir/highbar.token` |
| `SubscriberSlot`   | Spec FR-015/FR-015a | `state.proto` (implicit) | Per-subscriber ring entry in `DeltaBus`          |
| `SchemaVersion`    | Spec FR-022a   | `service.proto :: Hello*` | Compile-time constant baked into plugin & clients |
| `RuntimeCounters`  | Spec FR-024    | `service.proto :: CountersResponse` | Atomic counters in `HighBarService`              |

---

## 1. `GameState`

The gateway's materialized view of the world at a given frame,
flattened out of CircuitAI managers. Carried on the wire as
`StateSnapshot`.

### Fields

- `frame_number: uint32` — engine frame at which the snapshot was
  taken. Monotonic across a match.
- `own_units: repeated OwnUnit`
  - `unit_id: uint32` — unique within match
  - `def_id: uint32` — BAR unit-def identifier
  - `position: Vec3` (world coordinates)
  - `health: float`
  - `max_health: float`
  - `under_construction: bool`
  - `build_progress: float` (0.0–1.0; meaningful iff `under_construction`)
- `visible_enemies: repeated EnemyUnit`
  - `unit_id`, `def_id`, `position`, `health`, `max_health`
  - `los_quality: enum { VISUAL, RADAR }`
- `radar_enemies: repeated RadarBlip`
  - `blip_id: uint32`
  - `position: Vec3` (**degraded** — radar jitter applied)
  - `suspected_def_id: uint32` (may be 0 = unknown)
- `map_features: repeated MapFeature`
  - `feature_id: uint32`
  - `def_id: uint32`
  - `position: Vec3`
  - `reclaim_value_metal: float`
  - `reclaim_value_energy: float`
- `economy: TeamEconomy`
  - `metal: float`, `metal_income: float`, `metal_storage: float`
  - `energy: float`, `energy_income: float`, `energy_storage: float`
- `static_map: StaticMap` — populated once per session, may also live
  in `HelloResponse`; see *Validation rules* below.
  - `width_cells: uint32`, `height_cells: uint32`
  - `metal_spots: repeated Vec3`
  - `start_positions: repeated Vec3`

### Validation rules

- `own_units[*].health <= own_units[*].max_health`; same for enemies.
- `build_progress` must equal `0.0` when `under_construction` is `false`.
- `visible_enemies[*].los_quality == RADAR` is permitted **only** if
  the CircuitAI enemy info reports radar-only LOS; otherwise `VISUAL`.
- `radar_enemies[*].position` is the degraded position from
  `CEnemyInfo`; the true position is never exposed on the wire.
- `static_map.width_cells * static_map.height_cells > 0`.
- Large-map optimization: `static_map` MAY be sent once in
  `HelloResponse` and omitted from subsequent snapshots; a client that
  never called `Hello` (observer) still receives it inline on its
  first `StateSnapshot`.

### Source mapping

| Field               | CircuitAI source                                |
|---------------------|--------------------------------------------------|
| `own_units`         | `CCircuitAI::GetTeamUnits()` filtered to own team |
| `visible_enemies`   | `CEnemyManager::GetEnemyInfos()` where LOS != 0   |
| `radar_enemies`     | `CEnemyManager::GetEnemyInfos()` where LOS == RADAR|
| `map_features`      | `CGameMap::GetFeatures()`                        |
| `economy`           | `CEconomyManager::GetState()`                    |
| `static_map`        | `CTerrainData` + `CMetalManager` on init         |

---

## 2. `StateUpdate`

The message every subscriber sees on the `StreamState` wire. Carries a
sequence number, a frame number, and exactly one of: snapshot, delta,
or keepalive marker.

### Fields

- `seq: uint64` — strictly monotonic per session; **continues across
  snapshot resets** (FR-006, FR-008).
- `frame: uint32` — engine frame the payload describes.
- `payload: oneof`
  - `snapshot: StateSnapshot` — sent as the first message on every
    subscribe, and on resume fallback when the requested `resume_from_seq`
    is no longer in the ring.
  - `delta: StateDelta` — sent for every frame that produced at least
    one tracked change (FR-005).
  - `keepalive: KeepAlive` — periodic no-op when no deltas flushed
    for a configurable quiet window, so clients can distinguish "idle
    game" from "dead stream."

### Invariants

- Exactly one arm of `payload` is set.
- If `payload = snapshot`, then either (a) this is the first update in
  the session, or (b) the previous update's `seq` is not adjacent
  (i.e., the client must treat this as a reset).
- `seq` never decreases.
- Within a single server → single client stream, no duplicate `seq`
  values are ever emitted (FR-006, SC-005 checker invariant).

---

## 3. `Delta`

The set of changes since the prior frame's update, wrapped in
`StateDelta.events`.

### Fields

- `events: repeated DeltaEvent`
  - `DeltaEvent.oneof kind` — maps to the 28 engine events in
    `events.proto` (ported from V2). Examples:
    - `UnitCreated { unit_id, def_id, pos }`
    - `UnitFinished { unit_id }`
    - `UnitDamaged { unit_id, attacker_id, damage }`
    - `UnitDestroyed { unit_id, attacker_id }`
    - `EnemyEnterLOS { unit_id, pos, los_quality }`
    - `EnemyLeaveLOS { unit_id }`
    - `EnemyEnterRadar { blip_id, pos }`
    - `EnemyLeaveRadar { blip_id }`
    - `FeatureCreated { feature_id, def_id, pos }`
    - `FeatureDestroyed { feature_id }`
    - `EconomyTick { metal, energy, metal_income, energy_income, … }`
    - *(plus the full V2 set, one arm per engine event)*

### Validation rules

- `events` is non-empty for every `StateDelta` wrapped in a `StateUpdate`
  (empty frames are represented as `KeepAlive` or simply omitted from
  the stream).
- Every `unit_id` referenced in a delta MUST either (a) have appeared
  in a prior `UnitCreated` / `EnemyEnterLOS` / etc. event in the same
  session, or (b) appear in the initial `StateSnapshot`.
- `EnemyLeaveLOS` / `EnemyLeaveRadar` / `UnitDestroyed` events MUST
  match a prior "enter" / "created" event for the same id within the
  session.

### Production flow

1. Engine → BARb callback → routed to `CGrpcGatewayModule`'s event
   handler (`HandleUnitCreated`, etc.) on the **engine thread**.
2. Handler appends a typed entry to `current_frame_delta_`.
3. At the end of the frame (tied into CircuitAI's `CScheduler`
   frame-end hook), `current_frame_delta_` is serialized to a
   `shared_ptr<const string>` once and fanned out through `DeltaBus`
   to each subscriber's ring.
4. `current_frame_delta_.Clear()`.

---

## 4. `Command`

An external AI's order for an owned unit. Uses the V2 `AICommand`
schema verbatim to preserve the 97 command variants.

### Fields

- `target_unit_id: uint32` — must refer to an owned unit.
- `kind: oneof AICommand.command`
  - `move_to { pos }`
  - `attack_unit { target_unit_id }`
  - `attack_ground { pos }`
  - `repair { target_unit_id }`
  - `reclaim { feature_id or unit_id }`
  - `build { def_id, pos, facing }`
  - `stop {}`
  - *(plus the full V2 set)*
- `options: CommandOptions` — e.g., queued vs. immediate, shift-append.

### Validation rules (at acceptance time)

- `target_unit_id` must resolve to a live unit owned by the AI team.
  If not (destroyed, enemy-owned, or never existed), the whole
  `CommandBatch` is rejected with `INVALID_ARGUMENT` and no sub-command
  is partially applied.
- For `build`, `def_id` must be constructible by `target_unit_id`'s
  unit-def. (The gateway validates this against the BAR unit-def
  registry; failure → `INVALID_ARGUMENT`.)
- `move_to.pos`, `attack_ground.pos`, and `build.pos` MUST lie within
  the map extents (`0 ≤ x ≤ width`, `0 ≤ z ≤ height`).

### Lifecycle

```
                     (gRPC worker thread)                          (engine thread)
  client ───SubmitCommands──►  AuthInterceptor ──► validate ──► CommandQueue.push
                                                                        │
                                                                        ▼
                                                        CGrpcGatewayModule::Update()
                                                                        │
                                                            CommandQueue.drain_all()
                                                                        │
                                                            for cmd: CCircuitUnit::Cmd*(…)
```

Transitions:

- **Accepted** (queued, ack returned): validation passed and queue had
  capacity.
- **Rejected — INVALID_ARGUMENT**: validation failed. No command
  enqueued.
- **Rejected — RESOURCE_EXHAUSTED**: validation passed but queue is
  full (FR-012a). No command enqueued; already-queued commands are
  not dropped or reordered.
- **Rejected — PERMISSION_DENIED**: caller did not present the AI
  token (FR-014). Handled by `AuthInterceptor` before validation.
- **Rejected — ALREADY_EXISTS**: a different session already holds
  the AI role (FR-011).
- **Executed**: drained on engine thread, dispatched through
  `CCircuitUnit::Cmd*`. No further wire-visible state; effects
  surface back through the state stream as deltas.

---

## 5. `Session`

A single client connection. Server-side only — never appears on the
wire as a message type.

### Fields

- `session_id: uuid` — generated by the server at connect.
- `role: enum { OBSERVER, AI }` — decided by which RPC the client
  opens (observer: `StreamState` without token; AI: `StreamState` +
  `SubmitCommands` + `InvokeCallback` with token).
- `auth_state: enum { UNAUTHENTICATED, AUTHENTICATED }` — `AUTHENTICATED`
  iff the per-RPC metadata presented a token matching `AuthToken`.
- `last_seen_seq: uint64` — the highest `seq` the client has
  acknowledged seeing (for `resume_from_seq` replay).
- `schema_version: string` — recorded from `HelloRequest`; must
  exactly match plugin's `SchemaVersion` or the session never reaches
  an active state.
- `remote_peer: string` — grpc `peer()` identifier (for logs).
- `state: enum { HANDSHAKING, ACTIVE, DRAINING, CLOSED }`

### State transitions

```
      HANDSHAKING ──Hello OK──► ACTIVE ──client disconnect──► DRAINING ──flush──► CLOSED
           │
           └─Hello reject──► CLOSED
```

- `HANDSHAKING → CLOSED` also fires if the observer cap is reached
  (FR-015a) or if a second AI-role client tries to connect
  (FR-011).
- `ACTIVE → DRAINING` on any of: client cancel, stream EOF, slow-
  consumer eviction (FR-012a class), fail-closed gateway fault
  (FR-003a — note: in that last case *every* session drains, not
  just the faulting one).

### Invariants

- `role == AI` ⇒ `auth_state == AUTHENTICATED`.
- At most one `Session` with `role == AI` and `state != CLOSED` may
  exist at a time (FR-011).
- At most four `Session`s with `role == OBSERVER` and
  `state in { HANDSHAKING, ACTIVE }` may exist at a time (FR-015a).
- The AI session's `session_id` is the identity returned to the
  engine for save/load correlation.

---

## 6. `TransportEndpoint`

Not carried on the wire; configured in `data/config/grpc.json` and
reflected into the `HighBarService::Bind` call at plugin startup.

### Fields

- `transport: enum { UDS, TCP }`
- `uds_path: string` — filesystem path when `transport == UDS`;
  resolved against `$XDG_RUNTIME_DIR` and `${gameid}`.
- `tcp_bind: string` — `host:port` when `transport == TCP`; default
  `127.0.0.1:50511`.
- `ai_token_path: string` — filesystem path for the `AuthToken`
  file; default `$writeDir/highbar.token`.
- `max_recv_mb: uint32` — default 32; bumps
  `GRPC_ARG_MAX_RECEIVE_MESSAGE_LENGTH`.
- `ring_size: uint32` — default 2048; size of the `StateUpdate` ring
  for resume (§7).

### Validation rules

- If `transport == UDS` and `len(uds_path) > 108`: warn and fall back
  to `/tmp/hb-<short-hash>.sock`.
- If `transport == TCP`: `tcp_bind` must parse to a loopback address
  (`127.0.0.0/8` or `::1`); non-loopback is rejected with a clear
  error at startup (spec Assumption: same-host).
- `ai_token_path` parent directory must exist and be writable; token
  file is created mode 0600.
- `ring_size >= 256` (sanity floor).

---

## 7. `AuthToken`

Per-game-instance shared secret.

### Fields

- `value: string` — 256 bits of cryptographic randomness, hex-encoded.
- `emitted_at: timestamp` — for log correlation.
- `file_path: string` — where it was written (from
  `TransportEndpoint.ai_token_path`).
- `file_mode: octal` — `0600`.

### Lifecycle

1. Plugin init → generate `value` → write to `file_path` with mode
   `0600` **before** `HighBarService::Bind` unblocks.
2. gRPC `AuthInterceptor` reads this value on every incoming RPC.
3. AI client reads the file with exponential backoff (up to 5s) to
   handle the startup race (architecture doc §Critical Pitfalls).
4. Plugin shutdown → file is unlinked. Best-effort: a crashed plugin
   may leave a stale token file; the next plugin run overwrites it.

### Invariants

- A `SubmitCommands` or `InvokeCallback` RPC whose
  `x-highbar-ai-token` metadata does not equal `value` MUST fail
  with `PERMISSION_DENIED` (FR-014).
- `StreamState` MUST NOT require the token (FR-013).
- The token's `value` never appears on the wire in any message body.

---

## 8. `SubscriberSlot`

Server-side per-subscriber state; not on the wire.

### Fields

- `session_id: uuid` — the owning session.
- `ring: bounded_ring<shared_ptr<const string>, 8192>` — fan-out
  buffer. Producer is the engine thread; consumer is the subscriber's
  gRPC worker.
- `dropped_count: uint64` — number of entries the consumer has failed
  to drain in time (bumps when eviction fires).
- `eviction_reason: enum { NONE, SLOW_CONSUMER, CANCELED, FAULT }`

### Invariants

- If `ring.full()` and engine thread wants to publish, the slot's
  owning session is **evicted** — stream closed with
  `RESOURCE_EXHAUSTED`, lifecycle log emitted, counter incremented.
- Eviction of one slot never blocks other slots.

---

## 9. `SchemaVersion`

Compile-time constant, presented in `Hello`.

### Fields

- `version: string` — semver, e.g., `"1.0.0"`. Plugin and every
  generated client stub share the same string.

### Validation rules

- On `HelloRequest`, server compares `request.schema_version` against
  its own constant using **string equality**. Mismatch →
  `FAILED_PRECONDITION` with both values in status detail; the
  session never transitions from `HANDSHAKING` to `ACTIVE`
  (FR-022a).

---

## 10. `RuntimeCounters`

Exposed on the gRPC surface via a counters RPC (see contracts), not
over a separate port.

### Fields

- `subscriber_count: uint32` — currently active subscribers
  (observers + AI).
- `per_subscriber_queue_depth: repeated uint32` — one per active
  subscriber, ordered by connect time.
- `cumulative_dropped_subscribers: uint64` — monotonic, survives
  individual client lifecycles.
- `frame_flush_time_us_p99: uint64` — 99th-percentile frame-end
  flush latency over a rolling window (size defined in
  implementation).
- `command_queue_depth: uint32` — current depth of the MPSC
  engine-bound command queue.
- `command_submissions_rejected_resource_exhausted: uint64`
- `command_submissions_rejected_invalid_argument: uint64`

### Invariants

- All counters are read under atomic loads; there is no global lock on
  the counters surface.
- Snapshot semantics: one RPC call returns a coherent view of all
  fields as of a single moment, not field-by-field latest values.
- Counter access is permitted to any authenticated client — same
  token as the AI role (clarification Q1 & FR-024).

---

## Cross-entity relationships

```
 TransportEndpoint ─1──1─ HighBarService
                          │
                          ├─1──*─ Session
                          │         ├─1──1─ (role == AI) AuthToken presentation
                          │         ├─1──0..1─ SubscriberSlot (observers + AI state stream)
                          │         └─1──1─ SchemaVersion (strict-equality checked)
                          │
                          ├─1──1─ RingBuffer<StateUpdate, 2048>
                          ├─1──1─ DeltaBus (SPMC, fan-out to SubscriberSlots)
                          └─1──1─ CommandQueue (MPSC, drained on engine thread)

 GameState ──serialized at subscribe──► StateSnapshot ─┐
 Delta    ──accumulated per frame──►    StateDelta    ─┤
                                        KeepAlive     ─┴─► StateUpdate ──► SubscriberSlot.ring
```

## State-transition summary (whole-system)

- **Plugin init**: generate `AuthToken` → write token file → bind
  `TransportEndpoint` → accept connections.
- **Client connect (observer)**: create `Session{role=OBSERVER,
  auth=UNAUTHENTICATED}` → `Hello` (version check) → transition
  `HANDSHAKING → ACTIVE` → allocate `SubscriberSlot` → emit
  `StateSnapshot` → emit `StateDelta`s as frames occur.
- **Client connect (AI)**: create `Session{role=AI,
  auth=AUTHENTICATED}` (after token check) → FR-011 single-slot
  check → reject-if-taken OR transition `HANDSHAKING → ACTIVE` →
  allocate `SubscriberSlot` → on `SubmitCommands` RPC, validate +
  enqueue on `CommandQueue`.
- **Frame end (engine thread)**: drain `CommandQueue` → dispatch
  `Cmd*` for each → serialize `current_frame_delta_` once →
  `RingBuffer.push` → `DeltaBus.publish` → per-slot ring push →
  evict slow consumers.
- **Client reconnect**: new `Session` → `Hello` (version check) →
  `StreamState(resume_from_seq=N)` → if `N` in `RingBuffer`, replay
  `[N+1, head]`; else emit fresh `StateSnapshot` with next monotonic
  `seq`.
- **Client disconnect**: `Session` → `DRAINING` → `CLOSED`; AI role
  (if held) is released so a subsequent AI-role client can reclaim
  it (FR-012).
- **Gateway fault**: fail-closed — all sessions → `CLOSED`; plugin
  reports AI-slot failure to Spring (FR-003a).
- **Plugin shutdown**: all sessions → `CLOSED`; unlink token file;
  unbind transport.

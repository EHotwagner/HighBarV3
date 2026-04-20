# Phase 0 Research — gRPC Gateway for External AI & Observers

**Feature**: `001-grpc-gateway`
**Date**: 2026-04-20
**Spec**: [spec.md](./spec.md) · **Plan**: [plan.md](./plan.md) ·
**Architecture**: [docs/architecture.md](../../docs/architecture.md)

## Method

The feature spec reached `/speckit.plan` with no open
`NEEDS CLARIFICATION` markers — all five clarifications were resolved
in Session 2026-04-20 (spec §Clarifications). The plan's Technical
Context section therefore references no unknown fields. This Phase 0
document captures the **decisions** that were either (a) made in the
architecture doc and now need to be confirmed as still correct, or
(b) technology-choice and best-practice items that a first-time
reader of this feature should see justified before Phase 1 design
produces contracts and the data model.

Each decision block follows the template: *Decision → Rationale →
Alternatives considered*.

---

## 1. gRPC stack selection

**Decision**: **gRPC C++** on the plugin side (async API with
per-transport completion queues), **`Grpc.Net.Client` on .NET 8** for
the F# client, **`grpcio` + `grpcio-tools`** for the Python client.
Dependencies pinned via **vcpkg manifest mode** (`vcpkg.json`) on the
C++ side, NuGet for F#, PyPI for Python.

**Rationale**:

- The CircuitAI plugin is already C++20; gRPC C++ is the only
  transport that doesn't add a language or FFI boundary on the hot
  path. Async API (not the sync one) is required because the plugin
  must never block the engine thread on I/O — see Decision §3.
- `Grpc.Net.Client` is the only .NET gRPC client that still receives
  updates; `Grpc.Core` (the older native client) is in maintenance
  mode. `Grpc.Net.Client` also has first-class UDS support via
  `SocketsHttpHandler` + `UnixDomainSocketEndPoint`, which is what
  HighBarV2's client already uses.
- Distro gRPC (Ubuntu 22.04 ships 1.30) is far too old for the
  features we need (channelz, per-call metadata interceptors on async
  servers). vcpkg manifest mode pins a known-good triple of
  `grpc` / `protobuf` / `abseil` so headless-engine CI is
  reproducible.
- Python's `grpcio` supports `unix:/…` channel URIs natively; no
  custom transport plumbing needed.

**Alternatives considered**:

- *nanopb / protobuf-c + hand-rolled framing over UDS (V2's approach).*
  Rejected — V2 specifically exits this design because of lifecycle
  hangs, event loss, and framing bugs. The constitution's "no
  side-channel formats" principle forbids regressing to it.
- *FlatBuffers / Cap'n Proto.* Rejected — would give up cross-language
  RPC codegen, and the spec mandates proto-based language-agnostic
  bindings (FR-022). Performance gains would not pay for the
  ecosystem loss.
- *gRPC-Go server with a C++ shim.* Rejected — introduces a second
  language and process into the AI-slot plugin, violating
  "the plugin is a shared library" assumption in BARb's Spring ABI.
- *System gRPC packages instead of vcpkg.* Rejected — version skew
  between CI, dev machines, and user installs; already a known pain
  in adjacent BAR tooling.

---

## 2. Transport: UDS default, loopback TCP alternative

**Decision**: The gateway binds **one** transport per run, chosen at
startup by `data/config/grpc.json`:

- `transport: "uds"` (default) → bind at
  `$XDG_RUNTIME_DIR/highbar-${gameid}.sock`, fall back to
  `/tmp/hb-<short-hash>.sock` if the path exceeds 108 bytes.
- `transport: "tcp"` → bind at a loopback address (default
  `127.0.0.1:50511`).

Same RPCs, same proto schema, same client code — only the channel URI
differs.

**Rationale**:

- UDS wins on latency (p99 <500µs budget in SC-002 and Constitution V)
  and avoids the Linux TCP stack's overhead for same-host traffic.
  Filesystem permissions (mode 0600 on the token) are also a simpler
  trust model than port-based ACLs.
- TCP is necessary for users running the plugin in containers or
  sandboxes that virtualize or hide UDS paths — a real problem that
  V2 specifically ran into (spec §User Story 4 rationale).
- 108-byte `sun_path` limit is a hard Linux constraint; the fallback
  to `/tmp/hb-<short>.sock` is the minimum-effort way to stay
  compliant without failing startup.
- A single transport per run (vs. binding both simultaneously) keeps
  the attack surface small and the test matrix tractable; SC-008 bakes
  the "one config change" ergonomic guarantee.

**Alternatives considered**:

- *Bind both UDS and TCP simultaneously.* Rejected — doubles the
  listen sockets, doubles the auth surface, and creates ambiguity
  about which address the token secures. Spec assumption is
  single-host anyway.
- *Abstract socket (`@highbar-…`).* Rejected — not portable; works on
  Linux only via a path-prefix convention, and the permissions model
  is weaker than a real filesystem path.
- *Named pipes.* Rejected — Windows-only semantics; BAR headless
  targets Linux primarily.

---

## 3. Threading model: engine-thread supremacy + MPSC command queue

**Decision**: Every CircuitAI state mutation and every
`CCircuitUnit::Cmd*` call runs on the engine thread. gRPC worker
threads are forbidden from touching managers. Specifically:

- `SubmitCommands` handler on a worker thread → enqueue onto an
  MPSC queue (`src/circuit/grpc/CommandQueue.cpp`), drained by
  `CGrpcGatewayModule` at the top of each `UpdateN()` / frame-update
  callback.
- `StreamState` snapshot serialization runs on the worker thread
  under a **shared** read lock. The engine thread takes the lock
  **exclusive** only when publishing a frame's accumulated `StateDelta`
  to the `DeltaBus`. Writers never block on gRPC I/O.
- Per-subscriber fan-out ring (8192 `shared_ptr<const string>`
  entries) writes happen on the engine thread; reads happen on the
  subscriber's worker thread.

**Rationale**:

- Constitution II is **NON-NEGOTIABLE** on this. Spring's callback
  API is not documented as thread-safe; race-based heisenbugs are
  the single most expensive class of defect to diagnose in this
  codebase.
- The MPSC queue keeps the hot path lock-free on the producer side
  while preserving strict submission order per AI session, which
  matters for the "last order wins" semantics in Phase 1 when
  internal + external modules both drive the same unit.
- A shared/exclusive lock is cheaper than serializing snapshots
  onto the engine thread. Snapshots can be large (multi-MB late
  game); doing them on the engine thread would blow the per-frame
  budget when a new subscriber joined.

**Alternatives considered**:

- *A single-threaded gRPC server.* Rejected — can't serve 4
  observers plus 1 AI client without head-of-line blocking on slow
  consumers; slow-client eviction becomes impossible to implement
  cleanly.
- *Route every RPC back to the engine thread.* Rejected — pushes
  the engine thread off-budget under load, and creates a single
  point of blocking on any slow consumer.
- *Run the gateway in a child process with shared memory.* Rejected
  — defeats the whole "inject as an IModule" decision in the
  architecture doc; also re-introduces framing & lifecycle bugs V2
  had.

---

## 4. State model: flatten CircuitAI managers on subscribe, incremental deltas thereafter

**Decision**: The gateway does **not** hold a parallel copy of the
game state. On each `StreamState` subscription it walks CircuitAI's
managers (`GetTeamUnits`, `GetEnemyManager()->GetEnemyInfos`,
`GetMetalManager`, `GetGameMap`, …) and flattens them into a
`StateSnapshot` proto. After the snapshot, per-frame `StateDelta`s
are built incrementally inside the gateway's `IModule` event handlers
(`UnitCreated`, `UnitDamaged`, …) as events arrive, and flushed to
the `DeltaBus` at frame end.

**Rationale**:

- Avoids double-bookkeeping — the single source of truth remains the
  CircuitAI managers, and we can't drift from them.
- Late-joining subscribers get a consistent view (read under shared
  lock) without requiring the plugin to retain snapshot history.
- Per-frame incremental delta build has the right granularity for
  SC-002's latency budget (one event → one delta entry → one
  `shared_ptr<string>` fan-out).

**Alternatives considered**:

- *Materialize full state on every frame.* Rejected — wasteful for
  observer SC-003 (<5% framerate regression) and would balloon the
  engine-thread CPU budget.
- *Event-sourcing with no snapshot.* Rejected — new subscribers
  would need to replay from game start, which (a) is unbounded
  memory and (b) doesn't fit the "first snapshot within 2s" SC-001.

---

## 5. Resume semantics: 2048-entry ring buffer, fresh-snapshot on out-of-range

**Decision**: Keep the last **2048 `StateUpdate`s** in a ring buffer
(`src/circuit/grpc/RingBuffer.cpp`). A client reconnecting with
`resume_from_seq = N` gets messages `N+1 … head` replayed in order
when `N` is still in the ring. When `N` is out of range (too old, or
never reached), the server sends a fresh `StateSnapshot` carrying the
next monotonic `seq` and the client can detect the reset by the
`StateUpdate` oneof discriminator (snapshot vs. delta).

**Rationale**:

- 2048 frames ≈ 68 seconds at 30Hz sim — comfortably covers the
  60-second reconnect window named in SC-005.
- Monotonic sequence numbering across both replays and resets
  preserves FR-006 and the checker's invariant in SC-006.
- Snapshot-on-fallback avoids ambiguity: the client never has to
  guess whether it missed updates. The snapshot discriminator is
  self-identifying.

**Alternatives considered**:

- *Unbounded history buffer.* Rejected — memory grows with match
  length; a 30-minute match can emit hundreds of thousands of
  deltas.
- *Time-based eviction (e.g., "last 60s").* Rejected — makes
  correctness depend on wall clock rather than on a deterministic
  index. Ring size is simpler to reason about and easier to test.
- *Sequence-gap-only replay (no fresh snapshot fallback).* Rejected
  — leaves the client in an undefined state when it's been gone too
  long; the spec's edge case "resume from a sequence never reached"
  would have no correct handler.

---

## 6. Schema versioning: strict equality at Hello

**Decision**: `HelloRequest` carries the client's built-against
schema version (string, semver). `HelloResponse` carries the server's
version. If they do not match **exactly**, the server returns
`FAILED_PRECONDITION` with both versions in the status detail and
closes the stream. No "additive-only" inference.

**Rationale**:

- This is spec clarification Q2 and FR-022a, and it rides on
  Constitution III's proto-first discipline.
- The V2 predecessor had subtle bugs where old clients and new
  servers silently disagreed on field meanings; strict equality
  makes version mismatch a loud, fast failure instead of a
  heisenbug.
- Shipping both F# and Python clients doubles the surface that could
  diverge; strict equality keeps regression pressure on the
  client-release workflow rather than on silent runtime decoding.

**Alternatives considered**:

- *Semver-compatible (minor additive).* Rejected by spec clarification
  — was offered as option B and explicitly not chosen.
- *Per-field capability negotiation.* Rejected — too much engineering
  for too little benefit at this scale; the whole plugin is one
  process shipping one matched trio of plugin + F# client + Python
  client.

---

## 7. Observability: structured logs + counters over the gRPC surface

**Decision**: Two signals:

1. **Structured log records** for connection lifecycle events
   (connect, disconnect, auth reject, slow-consumer eviction),
   startup/shutdown milestones, and recoverable errors. Emitted
   through the engine's existing log sink (FR-023).
2. **Runtime counters** — `subscriber_count`, per-subscriber
   `queue_depth`, cumulative `dropped_subscribers`, p99
   `frame_flush_time_us` — exposed via a new RPC on the same
   `HighBarProxy` service (FR-024, clarification Q1). No separate
   Prometheus/statsd endpoint.

**Rationale**:

- Reusing the engine's log sink keeps operators consuming a single
  log stream and avoids a second side-channel that would violate
  Constitution III.
- Same-surface counters satisfy the clarification's "exposed through
  the gRPC surface" choice and let an authenticated AI or ops
  tooling poll without needing a second port or token scheme.
- Counter selection is the minimum set that lets an operator
  diagnose the spec's three operational failure modes: slow client
  (queue depth + drops), framerate impact (flush-time p99), overload
  (subscriber count vs. cap).

**Alternatives considered**:

- *Prometheus exporter.* Rejected by clarification — option B.
  Would need a second bound port and its own auth model.
- *OpenTelemetry.* Rejected for this iteration — worthwhile later,
  but adds a significant dep (OTel C++ SDK) for marginal gain now.
- *Side-band counters file.* Rejected — same "no ad-hoc formats"
  violation as V2.

---

## 8. Bounded queues everywhere, fail-synchronous on overflow

**Decision**: Two bounded queues:

- **Per-subscriber fan-out queue**: 8192 entries. Overflow →
  **evict** that subscriber (close stream with `RESOURCE_EXHAUSTED`),
  emit a lifecycle log, bump the drop counter. Other subscribers
  unaffected.
- **AI command queue (engine-bound)**: smaller (sized in research
  with the integration harness, starting at 1024). Overflow →
  synchronous **submission failure** with a distinct status
  (`RESOURCE_EXHAUSTED`), and already-queued commands are **not**
  dropped or reordered to make room (FR-012a, clarification Q4).

**Rationale**:

- Per-subscriber eviction matches the spec's slow-client edge case
  and keeps the engine thread out of per-client flow control.
- Synchronous rejection on command-queue overflow is the
  clarification's chosen behavior — it puts backpressure in the
  client's face instead of silently dropping orders, which is the
  worst possible outcome for an AI driver.
- Separating the two queues means observer slowness can never
  starve the AI command path, and an AI flood can never blow out
  the observer stream.

**Alternatives considered**:

- *Unbounded queues.* Rejected — unbounded memory + hidden latency.
- *Drop-oldest on overflow (for commands).* Rejected by
  clarification — explicitly not the chosen behavior; it would
  also make debugging "why didn't my order land?" a nightmare.

---

## 9. Fail-closed on internal gateway faults

**Decision**: Any unrecoverable internal fault in the gateway
(unhandled exception on a gRPC worker, broken invariant, failed
assertion) propagates through the AI-slot failure path Spring
expects — the plugin reports the AI slot as failed. No in-process
recovery, no silent degradation, no attempt to keep the rest of the
plugin alive when the gateway has died.

**Rationale**:

- Clarification Q5 is explicit: fail-closed is the chosen behavior.
- The constitution's "regressions observable rather than
  catastrophic" argument cuts both ways — visible fail-closed is
  better than silent degrade, which is neither observable *nor*
  recoverable.
- Applies whether or not the built-in AI is enabled, because
  Phase 1 users need to trust that "the AI stopped" means "the AI
  stopped," not "the AI stopped only externally-commanding."

**Alternatives considered**:

- *Disable the gateway, keep the built-in AI running.* Rejected by
  clarification (option B). Also complicates the Phase 2 story where
  there is no built-in AI to fall back to.
- *Best-effort retry on gRPC worker exceptions.* Rejected — papering
  over invariant violations is exactly the class of bug the
  constitution rules out.

---

## 10. Build system: vcpkg manifest + buf codegen, `-fvisibility=hidden -Bsymbolic`

**Decision**:

- C++ deps via `vcpkg.json` in manifest mode. Toolchain file driven
  by CMake. Pinned baseline checked in.
- Proto codegen via `buf` (`proto/buf.gen.yaml`) producing:
  - C++ + gRPC C++ → static `highbar_proto` lib linked into the
    plugin `.so`
  - C# + gRPC C# → NuGet package consumed by `clients/fsharp/`
  - Python + gRPC Python → wheel consumed by `clients/python/`
- Plugin shared library built with `-fvisibility=hidden` and
  `-Bsymbolic` to prevent the bundled protobuf from colliding with
  the engine's own copy.

**Rationale**:

- `buf` gives one canonical codegen command with consistent plugin
  versioning across all three targets, which is exactly what
  Constitution III's "proto is the only contract" clause assumes.
- Symbol hiding is not optional: the engine loads its own
  protobuf; unhidden symbols would get resolved across library
  boundaries and crash rarely and dramatically. `LD_DEBUG=symbols`
  validation is part of the smoke-test workflow.
- vcpkg manifest mode is the only way to ship a reproducible
  gRPC+protobuf+abseil triple across dev/CI/user installs given
  how slow distros track gRPC.

**Alternatives considered**:

- *System gRPC + manual `protoc` invocations.* Rejected — tried in
  V2, version drift killed it.
- *CMake's `protobuf_generate_cpp` without buf.* Rejected — splits
  codegen across CMake and .NET/Python build systems, three different
  plugin paths to keep in sync.
- *Static-linking every dep into the plugin .so.* Rejected — unshippably
  large, and duplicates symbols Spring already loads.

---

## 11. F# client sourcing: port HighBarV2, adapt to gRPC

**Decision**: The F# client in `clients/fsharp/` is **ported** from
HighBarV2's F# client, not rewritten. The public F# API surface
(observer + AI session types, DU-based command ergonomics) is
preserved where possible; the transport layer underneath is swapped
from V2's hand-rolled socket/framing to `Grpc.Net.Client`.

**Rationale**:

- Spec Assumption explicitly says V2's F# client is the starting
  point.
- Preserving the F# public shape keeps existing V2 bot code buildable
  against V3 with only a dependency/config change, which de-risks
  the migration for known users.
- V2's F# client already has a DU wrapper over the awkward
  generated-C# `Highbar.AICommand.Types.CommandCase` — we want that
  code, not its runtime.

**Alternatives considered**:

- *Greenfield F# client.* Rejected — abandons users on V2 and
  throws away working domain-wrapping code.
- *Use the generated C# client directly from F#.* Rejected — the
  generated API is painful to consume from F# idiomatically (oneof
  cases marshalled via nested enum types); the V2 wrapper exists
  for exactly this reason.

---

## 12. Python client scope: observer first, AI role after F# proven

**Decision**: The Python client ships with the observer role
supported at first release (FR-021). The AI role (credentialed
`SubmitCommands` + `InvokeCallback`) lands in Python only after the
F# AI role is proven in a headless match (US3 acceptance).

**Rationale**:

- Priority order in the spec puts Python as P3. Shipping the
  observer role first lets the ML research community iterate on
  state consumption while the AI-role correctness story is being
  stabilized against the F# client, which is the V2-parity
  language.
- SC-004 (F# + Python see byte-identical state streams) is the
  schema-stability acceptance; it requires the observer role on
  both clients but not the AI role.

**Alternatives considered**:

- *Full Python client (both roles) in first release.* Rejected —
  doubles the first-release AI-role QA surface without evidence of
  demand.
- *Observer-only Python client, no future AI role.* Rejected — the
  ML community is the named audience, and bots are the eventual
  goal for that audience.

---

## Outcomes

- All five `/speckit.clarify` questions already resolved in the spec;
  no unresolved `NEEDS CLARIFICATION` items remain.
- 12 decisions captured above, each with rationale tied to the spec,
  the constitution, or the architecture document.
- No Constitution Check gates regressed after Phase 0; plan remains
  in PASS state.

**Phase 0 complete. Proceeding to Phase 1 (data model + contracts + quickstart).**

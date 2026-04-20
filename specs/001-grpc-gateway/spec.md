# Feature Specification: gRPC Gateway for External AI & Observers

**Feature Branch**: `001-grpc-gateway`
**Created**: 2026-04-20
**Status**: Draft
**Input**: User description: "create specs from @docs/architecture.md"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Observer streams live game state (Priority: P1) 🎯 MVP

A developer building a coaching tool, overlay, or replay logger connects a
read-only client to a running match. Immediately they receive a full
picture of the AI's visible world (owned units, spotted enemies, map
features, economy) and from that moment forward they receive every change
as it happens, in order, with no gaps. The built-in AI continues playing
the match normally — the observer never disturbs it.

**Why this priority**: This is the MVP. It validates that the plugin can
materialize state, publish a schema-stable stream, and do so without
interfering with gameplay. Delivering only this story produces a usable
product for passive tooling (dashboards, loggers, streaming overlays) and
proves the transport before any two-way AI work begins.

**Independent Test**: Launch a BAR match with the plugin loaded and the
built-in AI active. Connect a client; confirm it receives an initial
snapshot within 2 seconds and a continuous delta stream thereafter.
Disconnect the client; confirm the match keeps playing normally.

**Acceptance Scenarios**:

1. **Given** a running match with the plugin active and the built-in AI
   playing, **When** a client opens a state-subscription call, **Then**
   it receives one snapshot message followed by delta messages each
   carrying a strictly increasing sequence number, with no gaps.
2. **Given** an active state subscription, **When** the game creates,
   damages, or destroys a unit, **Then** the client sees a corresponding
   delta message within one game frame.
3. **Given** an active state subscription, **When** the observer client
   disconnects, **Then** the game continues and the built-in AI's play
   is unaffected.

---

### User Story 2 - External AI submits commands while co-playing (Priority: P1)

An AI bot developer writing a remote decision engine in F#/.NET connects
an authenticated client to a running match. They receive the same state
stream as an observer, and additionally can issue unit orders (move,
attack, repair, build, etc.) that take effect in the game on the next
available frame. The built-in AI is still active in this phase — both
command sources coexist, with the last order on any given unit winning.

**Why this priority**: Without two-way command flow the plugin is only a
telemetry tool. This story completes the core product promise (external
AI can play) while keeping the built-in AI as a working baseline that
makes regressions observable rather than catastrophic. It is P1 because
the product is not fit for purpose without it.

**Independent Test**: Connect an authenticated F# client during a live
match. Issue a `MoveTo` command on a specific unit. Verify in the engine
log and in the state stream that the unit received the order and moved.
Confirm the built-in AI continues issuing its own orders for other units.

**Acceptance Scenarios**:

1. **Given** an authenticated client with a state subscription, **When**
   it submits a `MoveTo` order referencing an owned unit, **Then** the
   engine records the order and the unit begins moving within one game
   frame.
2. **Given** an active AI-role session, **When** a second client
   attempts to open an authenticated command session, **Then** the
   second attempt is rejected with a clear "already in use" error and
   the first session remains unaffected.
3. **Given** an authenticated session, **When** the client disconnects,
   **Then** the AI role is released and a subsequent authenticated
   client can reclaim it without restarting the game.

---

### User Story 3 - External AI is the sole decision authority (Priority: P2)

An operator running a bot-vs-bot tournament wants the external client to
be the only brain driving the AI slot, with no internal decisions
competing. They set a configuration flag at game start; the plugin skips
its built-in decision logic entirely. The external AI's commands are the
only orders the units receive.

**Why this priority**: This is the target end-state and matches the
predecessor product (V2). It is P2, not P1, because Story 2 is a strictly
better delivery order — the transport must be proven against a known-good
AI before the external AI can be relied on.

**Independent Test**: Launch a match with `enable_builtin_ai = false`.
Connect an authenticated external client that issues hand-scripted
commands (e.g. "build one solar panel, then one commander-walk"). Verify
only those commands reach the engine and no built-in decisions fire.

**Acceptance Scenarios**:

1. **Given** the built-in-AI flag is disabled at startup, **When** the
   match begins, **Then** no unit receives any order until an
   authenticated external client sends one.
2. **Given** the built-in AI is disabled and no external client
   connects, **When** the match plays, **Then** the AI slot idles
   without crashing and without affecting other players.

---

### User Story 4 - Transport selectable for constrained environments (Priority: P2)

An operator running the plugin in a container or sandbox where Unix
domain sockets behave unpredictably chooses loopback TCP instead via a
single config change. Client code and game behavior are unchanged — only
the endpoint address differs.

**Why this priority**: Local-socket transport is the default and
preferred for latency, but the V2 predecessor specifically avoided TCP
because of container-networking issues. Making TCP a first-class
selectable alternative widens deployability without burdening the common
path.

**Independent Test**: Launch the plugin twice — once configured for UDS,
once for TCP. Run the same client binary against both; verify identical
behavior end-to-end, with latency within the documented budget for each
transport.

**Acceptance Scenarios**:

1. **Given** a config file selecting TCP, **When** the plugin starts,
   **Then** it binds to the configured loopback address and clients
   connect using a TCP URL.
2. **Given** a config file selecting UDS, **When** the plugin starts,
   **Then** it creates a socket file at the configured path and clients
   connect using a filesystem URL.
3. **Given** either transport, **When** a client runs the same sequence
   of subscribe/command operations, **Then** it sees the same state
   stream and commands take effect identically.

---

### User Story 5 - Python client observes and controls (Priority: P3)

A researcher writing a machine-learning-driven bot in Python connects
using generated Python client bindings, receives the state stream, and
(with credentials) issues commands. The schema and behavior are
identical to the F# client.

**Why this priority**: F# is the V2 parity language; Python is net-new
and serves the ML research community. It is P3 because the schema
stability guarantee (tested via two independent clients seeing the same
stream) is itself the success criterion — delivering just the F# client
leaves that claim unverified.

**Independent Test**: Run the F# and Python clients against the same
game simultaneously as observers; record both state streams; assert they
are identical message-for-message.

**Acceptance Scenarios**:

1. **Given** a match with an F# and a Python observer both connected,
   **When** the match runs for 60 seconds, **Then** both clients report
   the same sequence of state-change events.
2. **Given** a Python client with valid credentials, **When** it issues
   a command batch, **Then** the orders reach the engine with the same
   semantics as the F# client.

---

### User Story 6 - Client reconnects without state gaps (Priority: P3)

An AI client process crashes or is restarted mid-match. When it
reconnects and supplies the last sequence number it successfully
processed, it either (a) receives exactly the updates it missed in
order, or (b) if too much time has passed, receives a fresh snapshot
and resumes — never silent gaps, never duplicated events.

**Why this priority**: Operational resilience. Not required for first
demo, but needed before running long sessions or tournaments.

**Independent Test**: Start a client, let it subscribe for 30 seconds,
kill it, restart it with the last-seen sequence number, and confirm it
receives either the gap or a fresh snapshot with monotonic sequence
numbers continuing from there.

**Acceptance Scenarios**:

1. **Given** a client that disconnected at sequence N with the game
   still running, **When** it reconnects within the buffered window
   requesting resume-from-N, **Then** it receives messages N+1 onward
   with no gaps and no duplicates.
2. **Given** a client requesting a sequence number that is no longer
   buffered, **When** it reconnects, **Then** the plugin sends a fresh
   snapshot and continues sequence numbering, and the client detects
   the snapshot rather than silently misinterpreting deltas.

---

### Edge Cases

- **Socket path over 108 bytes**: plugin warns and falls back to a short
  temporary path rather than failing to bind.
- **Snapshot larger than default message size**: plugin advertises a
  raised per-message ceiling so late-game snapshots are not rejected.
- **Slow client**: if a subscriber's queue backs up past a bounded
  capacity, the plugin disconnects that subscriber and requires it to
  reconnect for a fresh snapshot, rather than stalling the engine
  thread or dropping messages silently.
- **Token file read race at startup**: client cannot find the token
  file immediately after game start; client retries with backoff for a
  bounded window before failing.
- **Two AI clients attempt to connect at the same time**: first wins;
  second receives a clear "already in use" error.
- **Engine issues a Save or Load mid-match**: plugin handles it
  synchronously so the engine does not stall; the authenticated AI
  client sees the request and its response is returned to the engine.
- **Client asks to resume from a sequence it never reached**: plugin
  treats as out-of-range and sends a fresh snapshot.

## Clarifications

### Session 2026-04-20

- Q: What diagnostic/observability signals must the plugin surface to operators? → A: Structured logs plus counters (subscriber count, queue depth, drops, p99 frame flush time) exposed through the gRPC surface.
- Q: How must the plugin handle a client whose compiled schema version differs from the plugin's? → A: Strict equality — the `Hello` handshake rejects any client whose schema version does not exactly equal the plugin's.
- Q: What is the ceiling on concurrent observer subscriptions? → A: Hard cap of 4; connection attempts beyond 4 are rejected.
- Q: How must the plugin respond when the AI client submits commands faster than the engine can drain them? → A: Bounded queue; overflow causes the submission to fail synchronously with a `RESOURCE_EXHAUSTED`-class error and no command is accepted.
- Q: If the gateway itself faults mid-match (unhandled exception, thread panic, broken invariant), what must the plugin do? → A: Fail-closed — propagate the error through the AI-slot failure path; do not attempt in-process recovery or silent degradation. Applies whether or not the built-in AI is enabled.

## Requirements *(mandatory)*

### Functional Requirements

**Transport & connectivity**

- **FR-001**: The plugin MUST expose an RPC service endpoint selectable
  at plugin startup between two transports: a filesystem-path socket
  and a loopback network address.
- **FR-002**: The plugin MUST write the current session's authentication
  token to a filesystem location readable only by the game process
  owner, before the engine's initialization call returns to the engine.
- **FR-003**: The plugin MUST survive a client disconnect at any
  lifecycle point without affecting the engine or other connected
  clients.
- **FR-003a**: If the plugin detects an unrecoverable internal fault
  within the gateway (e.g., unhandled exception on a gateway thread,
  violated state invariant, failed assertion), it MUST fail closed:
  the error MUST be propagated through the normal AI-slot failure
  path and surfaced to the engine and operator. The plugin MUST NOT
  attempt in-process recovery, silently disable the gateway, or
  continue running in a degraded state. This requirement applies
  regardless of whether the built-in AI is enabled.

**State distribution**

- **FR-004**: On each client subscription, the plugin MUST send, as the
  first message on the stream, a complete state snapshot including
  current frame number, owned units, visible and radar-detected enemy
  units, map features, team economy readings, and static map data.
- **FR-005**: After the snapshot, the plugin MUST send one delta
  message per game frame in which a tracked change occurred, carrying
  the events that occurred in that frame.
- **FR-006**: Each state message (snapshot or delta) MUST carry a
  sequence number that is strictly monotonic within a session's
  lifetime.
- **FR-007**: The plugin MUST buffer recent state messages for a
  bounded window sufficient for clients to resume after transient
  disconnects.
- **FR-008**: When a resumption request references a buffered sequence
  number, the plugin MUST replay from that point; when the number is
  out of range, the plugin MUST send a fresh snapshot and continue
  numbering monotonically.

**Command flow**

- **FR-009**: An authenticated client MUST be able to submit unit
  orders covering at minimum movement, attack, repair, reclaim, build,
  and stop semantics, targeting owned units by identifier.
- **FR-010**: Commands submitted on a non-engine thread MUST be
  deferred until the next engine-provided execution boundary before
  reaching the engine, with no command lost in the hand-off.
- **FR-011**: The plugin MUST accept at most one command-submitting
  client at a time; concurrent attempts to open a second such session
  MUST be rejected with a distinct error code.
- **FR-012**: On disconnect of the command-submitting client, the
  plugin MUST release its exclusive slot so a reconnecting client can
  reclaim it within the same match.
- **FR-012a**: The plugin MUST maintain a bounded queue for commands
  awaiting execution on the engine thread. When the queue is full, a
  submission MUST fail synchronously with a distinct,
  resource-exhaustion error naming the condition; no command in the
  rejected submission may be partially accepted, and already-queued
  commands MUST NOT be dropped or reordered to admit the new one.

**Role model & authentication**

- **FR-013**: Observer (state-only) subscriptions MUST NOT require
  authentication.
- **FR-014**: Command submission and engine-callback invocation MUST
  require the per-session token.
- **FR-015**: The plugin MUST support 4 concurrent observer clients
  without degrading gameplay framerate by more than 5% of the baseline
  established with no observers attached.
- **FR-015a**: The plugin MUST enforce a hard cap of 4 concurrent
  observer subscriptions. A connection attempt that would raise the
  active observer count above 4 MUST be rejected with a distinct,
  named error before the subscription stream begins, and MUST NOT
  affect any already-connected subscriber.

**Operational modes**

- **FR-016**: The plugin MUST support a startup configuration that
  enables or disables the built-in decision logic, independently of
  whether an external client is connected.
- **FR-017**: When the built-in AI is disabled and no external client
  is connected, the plugin MUST keep the AI slot alive without
  crashing the engine.

**Engine integration**

- **FR-018**: The plugin MUST handle engine save and load requests
  synchronously, including forwarding data to and from the
  authenticated AI client before yielding control back to the engine.
- **FR-019**: The plugin MUST install as a BAR Skirmish AI that an
  operator can select at game start via the existing game UI,
  preserving the identity (short name, display name) of its upstream
  base.

**Client distribution**

- **FR-020**: The plugin MUST ship with a client library for F#/.NET
  that supports both transports and both roles.
- **FR-021**: The plugin MUST ship with a client library for Python
  that supports both transports; the observer role is required for
  first release, the AI role after the F# client is proven.
- **FR-022**: The message schema MUST be described in a form that can
  generate language-agnostic client bindings, and MUST be the only
  contract between plugin and clients.
- **FR-022a**: The schema MUST carry an explicit version identifier.
  The initial handshake MUST require the client to present the schema
  version it was built against; if it does not exactly equal the
  plugin's schema version, the plugin MUST reject the connection with
  a distinct, named error that reports both versions. Partial or
  additive-only compatibility MUST NOT be inferred silently.

**Observability**

- **FR-023**: The plugin MUST emit structured log records for
  connection lifecycle events (client connect, disconnect, auth
  reject, slow-consumer eviction), startup/shutdown milestones, and
  recoverable errors, in a form consumable by the engine's existing
  log sink.
- **FR-024**: The plugin MUST expose a machine-readable set of runtime
  counters — at minimum current subscriber count, per-subscriber queue
  depth, cumulative dropped/evicted subscribers, and the 99th-percentile
  per-frame delta flush time — queryable by an authenticated client
  over the same gRPC surface (no separate network endpoint).

### Key Entities *(include if feature involves data)*

- **GameState**: the plugin's materialized view of the world at a given
  frame — owned units (live and under construction), visible enemies,
  radar-detected enemies (with degraded positions), map features, per
  team economy readings, and static map data populated once.
- **StateUpdate**: the envelope a client receives — carries a sequence
  number, a frame number, and either a full snapshot, a delta, or a
  keepalive marker.
- **Delta**: the set of changes applied to `GameState` since the prior
  frame's update — unit lifecycle events, economy ticks, feature
  changes.
- **Command**: an external AI's order for an owned unit — target unit
  identifier, action kind (move/attack/build/…), and action parameters.
- **Session**: a single client connection — carries its role (observer
  or AI), its authentication state, and its last-seen sequence number.
- **TransportEndpoint**: the plugin's configured entry point — a
  filesystem path or a loopback network address with port, selected at
  startup.
- **AuthToken**: a per-game-instance secret established at plugin
  startup and required for the AI role.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: An observer client receives its first game-state snapshot
  within 2 seconds of subscribing during an active match.
- **SC-002**: The round-trip from an in-game event to an F# client's
  corresponding notification is under 500 microseconds at the 99th
  percentile on local-socket transport, and under 1.5 milliseconds at
  the 99th percentile on loopback-network transport.
- **SC-003**: Four concurrent observer clients connected to the same
  match reduce playable framerate by no more than 5% compared to a
  match with no observers attached.
- **SC-004**: An F# client and a Python client attached to the same
  match receive byte-identical sequences of state messages for a
  60-second window.
- **SC-005**: A client that disconnects mid-match and reconnects within
  60 seconds with its last-seen sequence number receives either the
  missed messages in order, or a fresh snapshot, with no gaps and no
  duplicates detected by a checker that inspects sequence numbers.
- **SC-006**: In a 30-minute match, at least 95% of client sessions
  complete without any dropped, duplicated, or out-of-order state
  message.
- **SC-007**: A BAR match with the plugin selected as one AI slot
  completes 60 seconds of play without the plugin crashing the engine
  in either built-in-AI-on or built-in-AI-off configurations.
- **SC-008**: Switching between local-socket and loopback-network
  transport requires exactly one configuration-file change and no
  changes to client code.
- **SC-009**: An authenticated client submitting a unit order observes
  the corresponding unit state change in its state stream within 3
  game frames of submission.

## Assumptions

- Clients and the game run on the same host. Cross-host transports are
  out of scope for this release.
- The game process and any client process share a filesystem namespace
  sufficient to exchange the token file and the domain socket.
- The upstream AI base (BARb) is responsible for BAR-specific
  unit-definition handling; this feature adds a transport layer on top
  and does not alter gameplay logic in built-in-AI-enabled mode.
- Per-subsystem opt-out (selectively disabling only the military, or
  only the economy, module) is out of scope for this release and will
  be handled in a later feature if demand is demonstrated.
- The F# client codebase from the predecessor product (HighBarV2) is
  the starting point for the new F# client; the Python client is net
  new.
- Licensing of delivered artifacts is inherited from the upstream base
  (GPL-2.0) as recorded in the project constitution.
- A single AI-role client per match is sufficient; multi-brain
  coordination scenarios are out of scope.

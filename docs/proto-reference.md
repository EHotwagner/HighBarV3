# HighBarV3 Proto Reference

This document is the working reference for the public wire contract in
`proto/highbar/*.proto`. The package is `highbar.v1`; breaking changes
must land in a new package such as `highbar.v2` rather than mutating the
existing package in place.

## Compatibility Rules

- Schema version is `"1.0.0"` and is checked by `HighBarProxy.Hello`.
- Clients must compare the returned `HelloResponse.schema_version` with
  the version they were generated against.
- The package is versioned as `highbar.v1`, while files live under
  `proto/highbar/`; `proto/buf.yaml` intentionally relaxes the Buf
  directory/package suffix rule for this layout.
- Unknown protobuf fields must be ignored by clients, as normal for
  proto3.
- Do not depend on generated enum display names as stable UI text.

## Transport And Metadata

HighBar is a same-host service. Supported transports are:

| Transport | Endpoint form | Notes |
| --- | --- | --- |
| UDS | `unix:/path/to/highbar.sock` | Preferred local transport. Directory permissions protect access. |
| TCP | `127.0.0.1:PORT` or `[::1]:PORT` | Loopback only. No TLS. |

Mutating AI-role RPCs require the per-session token:

```text
x-highbar-ai-token: <token>
```

Admin RPCs also use metadata that identifies the caller and intended
role. The Python helper uses:

```text
x-highbar-admin-role: operator | admin | test-harness | ai | observer
x-highbar-client-id: stable-client-id
```

Generated clients should make metadata explicit and avoid hiding auth
failures. `PERMISSION_DENIED` means the token or role metadata is
missing, invalid, or insufficient.

## Service Summary

### `HighBarProxy`

Primary state and AI-control service in `proto/highbar/service.proto`.

| RPC | Shape | Role | Purpose |
| --- | --- | --- | --- |
| `Hello` | unary | observer or AI | Schema handshake, session id, static map, current frame. |
| `StreamState` | server stream | observer or AI | Initial snapshot, deltas, keepalives, resume support. |
| `SubmitCommands` | client stream | AI token | Submit `CommandBatch` messages to the engine-thread command queue. |
| `ValidateCommandBatch` | unary | AI token | Dry-run command validation with no queue or simulation mutation. |
| `GetCommandSchema` | unary | client | Discover supported command arms, limits, queue depth, option masks. |
| `GetUnitCapabilities` | unary | client | Discover legal commands and build options for one unit generation. |
| `InvokeCallback` | unary | AI token | Synchronous callback bridge for client implementations that need it. |
| `Save` | unary | AI token | Synchronous engine save hook; carries opaque client state. |
| `Load` | unary | AI token | Synchronous engine load hook; restores opaque client state. |
| `GetRuntimeCounters` | unary | token | Runtime health counters and queue/drop metrics. |
| `RequestSnapshot` | unary | AI token | Ask the gateway to emit one forced snapshot on the existing stream. |

### `HighBarAdmin`

Administrative and test-harness control service in
`proto/highbar/service.proto`.

| RPC | Shape | Purpose |
| --- | --- | --- |
| `GetAdminCapabilities` | unary | Discover enabled roles, supported actions, speed range, ids, map limits. |
| `ValidateAdminAction` | unary | Validate an admin action without mutating state. |
| `ExecuteAdminAction` | unary | Execute a pause, speed, cheat, resource, spawn, lifecycle, or transfer action. |

Admin actions are intentionally separate from AI commands. A generated
client should not map admin controls into `AICommand`; use
`AdminAction` and `HighBarAdmin`.

### `HighBarCoordinator`

Coordinator/client-mode service in `proto/highbar/coordinator.proto`.
The plugin can dial out to this service when the runtime topology uses a
separate coordinator process.

| RPC | Shape | Purpose |
| --- | --- | --- |
| `Heartbeat` | unary | Plugin-to-coordinator liveness and schema check. |
| `PushState` | client stream | Plugin streams `StateUpdate` messages to the coordinator. |
| `OpenCommandChannel` | server stream | Coordinator streams `CommandBatch` messages back to the plugin. |

Most third-party AI clients should implement `HighBarProxy` consumers
first. Use `HighBarCoordinator` only when embedding HighBar in a
coordinator process.

## Connection Flow

### Observer

1. Build a plaintext gRPC channel to UDS or loopback TCP.
2. Call `HighBarProxy.Hello` with `Role.ROLE_OBSERVER`.
3. Check `schema_version`.
4. Call `StreamState`.
5. Treat the first snapshot as the baseline and apply subsequent
   `StateDelta` events in `seq` order.

Observers do not submit commands and do not need the AI token for the
basic state stream.

### AI Client

1. Read the token file written by the proxy, usually with retry/backoff
   because startup is asynchronous.
2. Build a channel and call `Hello` with `Role.ROLE_AI` and
   `x-highbar-ai-token`.
3. Start `StreamState` and maintain the latest snapshot/delta basis.
4. Use `GetCommandSchema` and `GetUnitCapabilities` before issuing
   strict command batches.
5. Send `CommandBatch` values on `SubmitCommands`.
6. Reconcile the returned `CommandAck.results` and later
   `CommandDispatchEvent` deltas.

## State Stream Contract

`StreamState` emits `StateUpdate` envelopes:

| Field | Meaning |
| --- | --- |
| `seq` | Strictly monotonic per stream/session. |
| `frame` | Engine frame for the payload. |
| `snapshot` | Complete materialized state baseline. |
| `delta` | Incremental `DeltaEvent` list for one frame. |
| `keepalive` | Empty heartbeat when the game is idle. |
| `send_monotonic_ns` | Server-side monotonic timestamp for latency measurement. |

`StreamStateRequest.resume_from_seq` resumes from a known sequence if
the ring buffer still contains it. If the sequence is out of range, the
server sends a fresh snapshot and continues with monotonic `seq`
values.

Snapshot data:

- `own_units`: controllable units for the proxy team.
- `visible_enemies`: LOS-visible enemy units.
- `radar_enemies`: degraded radar contacts.
- `map_features`: reclaimable features.
- `economy`: team metal/energy state.
- `static_map`: usually delivered once in `HelloResponse`, not every
  snapshot.
- `effective_cadence_frames`: snapshot cadence active for that
  emission.

Delta event categories:

- Unit lifecycle: created, finished, idle, damaged, destroyed, given,
  captured, move failed.
- Enemy visibility: enter/leave LOS, enter/leave radar, damaged,
  destroyed, created, finished.
- World state: features, economy ticks, messages, weapons, seismic
  pings.
- HighBar diagnostics: `CommandDispatchEvent` and `AdminAuditEvent`.

Clients should keep an immutable last snapshot plus a small event log,
or materialize state in a mutable model. Either approach must reject
sequence regressions.

## Command Contract

`CommandBatch` is the unit of AI command submission.

Required for modern strict-mode clients:

| Field | Meaning |
| --- | --- |
| `batch_seq` | Client stream sequence for acknowledgements. |
| `target_unit_id` | Unit receiving every command in the batch. |
| `commands` | One or more `AICommand` oneof arms. |
| `client_command_id` | Stable caller correlation id. |
| `based_on_frame` | Frame observed before building the batch. |
| `based_on_state_seq` | State `seq` observed before building the batch. |
| `conflict_policy` | Replace, queue, or reject if the unit is busy. |

`AICommand` contains the command catalog. Common unit-order arms:

- `move_unit`, `patrol`, `fight`
- `attack`, `attack_area`
- `guard`, `repair`
- `reclaim_unit`, `reclaim_area`, `reclaim_feature`
- `build_unit`
- `stop`, `wait`
- `set_wanted_max_speed`
- `set_fire_state`, `set_move_state`, `set_trajectory`
- `self_destruct`

Legacy/admin-like arms that mutate global state or rely on cheats are
not a substitute for `HighBarAdmin`; generated clients should use the
admin service for pause, speed, resource grants, unit spawn, lifecycle,
and unit transfer.

Validation results:

- `CommandAck.results[]` gives per-batch `CommandBatchResult`.
- `CommandIssue` includes a stable issue code, field path, detail, and
  retry hint.
- `CommandDispatchEvent` later confirms whether the engine-thread
  dispatch applied or skipped the command.

## Admin Contract

`AdminAction` carries one of:

- `pause`
- `global_speed`
- `cheat_policy`
- `resource_grant`
- `unit_spawn`
- `lifecycle`
- `unit_transfer`

Every action should set:

- `action_seq`
- `client_action_id`
- optional `based_on_frame`
- optional `based_on_state_seq`
- `conflict_policy`
- human-readable `reason`

`AdminActionResult.status` reports whether the action was accepted,
executed, or rejected. Behavioral tests must not treat status alone as
success; they require state-stream, snapshot/delta, or engine-log
evidence that the requested effect happened or that a rejected action
left state unchanged.

## Proto File Map

| File | Contents |
| --- | --- |
| `common.proto` | `Vector3`, `UnitRef`, `CommandOptions`. |
| `service.proto` | `HighBarProxy`, `HighBarAdmin`, handshake, command schema, admin, save/load, counters. |
| `state.proto` | `StateUpdate`, snapshots, deltas, state event types, dispatch/admin audit events. |
| `events.proto` | Engine event payload messages reused by `StateDelta`. |
| `commands.proto` | `AICommand`, command arms, batches, validation diagnostics. |
| `callbacks.proto` | Callback request/response and game-state callback records. |
| `coordinator.proto` | Coordinator/client-mode heartbeat, state push, command channel. |

## Generated Code Locations

| Language | Location |
| --- | --- |
| C++ | Generated during native build under `build/gen`; linked into the plugin. |
| Python | Committed under `clients/python/highbar_client/highbar/`; regenerate with `make -C clients/python codegen`. |
| C# / F# | Generated by `clients/fsharp/HighBar.Proto.csproj` using `Grpc.Tools`. |
| Other languages | Generate from `proto/highbar/*.proto` with Buf or `protoc`. |

## Error Handling Checklist

- `FAILED_PRECONDITION`: schema mismatch, gateway not healthy, or
  request cannot be served in current state.
- `PERMISSION_DENIED`: missing or invalid token/role metadata.
- `INVALID_ARGUMENT`: structurally invalid command or admin action.
- `RESOURCE_EXHAUSTED`: command queue or stream pressure limit.
- `ALREADY_EXISTS`: second concurrent AI-role session where only one is
  allowed.
- `UNAVAILABLE`: endpoint missing, process exited, socket reset, or
  coordinator disconnected.

Clients should preserve `grpc-status-details-bin` if their runtime
exposes it, log `client_id`, and include `client_command_id` or
`client_action_id` in every mutating request.

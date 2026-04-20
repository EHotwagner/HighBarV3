# Contracts — gRPC Gateway

**Feature**: `001-grpc-gateway`
**Phase**: 1 (design artifacts)

This directory holds the **planning sketches** of the proto contracts
for feature 001-grpc-gateway. These files are the reference shape for
the final `proto/highbar/*.proto` build inputs that `/speckit.implement`
will create (by copying this sketch into `proto/highbar/` and porting
HighBarV2's `common.proto`, `events.proto`, `commands.proto`, and
`callbacks.proto` alongside it).

Files:

- [`service.proto`](./service.proto) — the `HighBarProxy` RPC surface:
  `Hello`, `StreamState`, `SubmitCommands`, `InvokeCallback`, `Save`,
  `Load`, `GetRuntimeCounters`.
- [`state.proto`](./state.proto) — `StateUpdate` envelope,
  `StateSnapshot`, `StateDelta`, `DeltaEvent` oneof wrapper.

See also:

- [`../data-model.md`](../data-model.md) — entity definitions,
  validation rules, state transitions.
- [`../research.md`](../research.md) — decisions feeding the contract
  design (strict-equality versioning, bounded queues, fail-closed
  semantics, etc.).
- [`../../../docs/architecture.md`](../../../docs/architecture.md) —
  runtime guidance: module integration points, threading discipline,
  critical pitfalls.

---

## Per-RPC contract summary

The sections below codify the non-proto-expressible rules — auth, role
gating, error codes, and invariants — that each RPC must honor.
Implementations and tests both consult this table.

### `Hello`

| Property                  | Contract                                                                                |
|---------------------------|-----------------------------------------------------------------------------------------|
| Auth                      | None required. If `role == ROLE_AI`, the `x-highbar-ai-token` metadata MUST be present and valid. |
| Role gate                 | `ROLE_OBSERVER` always allowed. `ROLE_AI` requires the token and fails `PERMISSION_DENIED` without it; a second live AI-role `Hello` fails `ALREADY_EXISTS` (FR-011). |
| Version gate              | Strict string equality on `schema_version`. Mismatch → `FAILED_PRECONDITION` with both versions in status detail (FR-022a). |
| Side effects              | Creates a `Session` (data-model §5), returns its `session_id`, and emits `StaticMap` once. |
| Observer cap              | Counted against FR-015a's hard cap of 4 at this point, before `StreamState` opens. Rejection → `RESOURCE_EXHAUSTED`. |
| Error code summary        | `FAILED_PRECONDITION` (version mismatch) · `PERMISSION_DENIED` (AI role without token) · `ALREADY_EXISTS` (second AI client) · `RESOURCE_EXHAUSTED` (observer cap) · `INVALID_ARGUMENT` (malformed request). |

### `StreamState`

| Property                  | Contract                                                                                |
|---------------------------|-----------------------------------------------------------------------------------------|
| Auth                      | **None** for observers (FR-013). AI-role clients typically present the token for consistency, but the server does not require it on this RPC. |
| First message             | Always a `StateUpdate` with `payload = snapshot` and `seq` equal to the next monotonic sequence number (FR-004). |
| Resume semantics          | `resume_from_seq == 0` → fresh snapshot. `resume_from_seq > 0` in range → replay `[seq+1, head]` in order. Out of range → fresh snapshot with next monotonic `seq` (FR-007, FR-008). |
| Keepalive                 | Emitted after a configurable quiet window with no delta flushes. |
| Slow consumer             | Per-subscriber ring is 8192 entries. Overflow → server closes stream with `RESOURCE_EXHAUSTED`; other subscribers unaffected (data-model §8). |
| Sequence invariant        | `seq` strictly monotonic within a session, including across snapshot resets (FR-006). |
| Error code summary        | `RESOURCE_EXHAUSTED` (slow consumer evicted; observer cap reached at stream start) · `CANCELLED` (client disconnect) · `INTERNAL` (gateway fault; fail-closed per FR-003a). |

### `SubmitCommands`

| Property                  | Contract                                                                                |
|---------------------------|-----------------------------------------------------------------------------------------|
| Auth                      | AI token required on every request. Missing/invalid → `PERMISSION_DENIED` (FR-014). |
| Role gate                 | Exactly one AI-role session at a time. Second concurrent → `ALREADY_EXISTS` (FR-011). |
| Validation                | `target_unit_id` must resolve to an owned, live unit. `build.def_id` must be constructible by the target. Coordinates must be in-map. Failures → `INVALID_ARGUMENT` with no partial accept. |
| Threading                 | Validated on gRPC worker; successful commands enqueue on the MPSC `CommandQueue`; dispatched on the engine thread at frame-update (FR-010, Constitution II). |
| Queue overflow            | `CommandQueue` is bounded. Full → synchronous `RESOURCE_EXHAUSTED`; already-queued commands are NOT dropped or reordered (FR-012a). |
| Ordering                  | Within a single session, commands issued on engine thread in the same order they were accepted by the server. |
| Error code summary        | `PERMISSION_DENIED` · `ALREADY_EXISTS` · `INVALID_ARGUMENT` · `RESOURCE_EXHAUSTED` · `INTERNAL`. |

### `InvokeCallback`

| Property                  | Contract                                                                                |
|---------------------------|-----------------------------------------------------------------------------------------|
| Auth                      | AI token required (FR-014). |
| Semantics                 | Unary RPC used by the plugin to forward engine callbacks requiring a synchronous answer from the external AI. |
| Threading                 | Request handler runs on a worker thread; the synchronous response is returned to the engine on the engine thread (the engine waits). |
| Error code summary        | `PERMISSION_DENIED` · `FAILED_PRECONDITION` (engine state does not permit this callback) · `INTERNAL`. |

### `Save` / `Load`

| Property                  | Contract                                                                                |
|---------------------------|-----------------------------------------------------------------------------------------|
| Auth                      | AI token required. |
| Semantics                 | Unary. Engine blocks waiting for the response; SC-007's "plugin does not crash the engine" depends on these returning within the engine's save/load budget. |
| Payload                   | Opaque `bytes`. The plugin never parses `engine_state` or `client_state`. |
| Error code summary        | `PERMISSION_DENIED` · `DEADLINE_EXCEEDED` (client too slow) · `INTERNAL`. |

### `GetRuntimeCounters`

| Property                  | Contract                                                                                |
|---------------------------|-----------------------------------------------------------------------------------------|
| Auth                      | Token required (same token as the AI role — clarification Q1, FR-024). |
| Semantics                 | Unary, coherent snapshot of `CountersResponse` taken under atomic loads. |
| Guarantees                | Single call returns a single coherent moment; fields do not mix observations from different instants. |
| Error code summary        | `PERMISSION_DENIED` · `INTERNAL`. |

---

## Error-code glossary (normative)

| gRPC status            | Plugin meaning in this service                                                     |
|------------------------|------------------------------------------------------------------------------------|
| `FAILED_PRECONDITION`  | Schema version mismatch at handshake (FR-022a).                                    |
| `PERMISSION_DENIED`    | AI-role RPC without a matching `x-highbar-ai-token` (FR-014).                      |
| `ALREADY_EXISTS`       | Second concurrent AI-role session attempt (FR-011).                                |
| `RESOURCE_EXHAUSTED`   | Observer cap reached (FR-015a); per-subscriber ring overflow; command queue full (FR-012a). |
| `INVALID_ARGUMENT`     | Malformed request body; command validation failed (unknown unit, out-of-map).      |
| `CANCELLED`            | Normal client disconnect on a streaming RPC.                                        |
| `DEADLINE_EXCEEDED`    | Save/Load blob round-trip exceeded the deadline the engine set.                     |
| `INTERNAL`             | Gateway fault — paired with a fail-closed shutdown (FR-003a). Clients should reconnect; repeated `INTERNAL` indicates a plugin bug. |

---

## What is intentionally NOT in this directory

- **`common.proto`, `events.proto`, `commands.proto`, `callbacks.proto`**
  — these are **ported verbatim** from HighBarV2 (`/home/developer/
  projects/HighBarV2/proto/highbar/*.proto`) during `/speckit.implement`.
  The Phase 1 plan does not restate them; they are fixed by the V2
  schema (FR-020, FR-021, spec Assumption on V2 reuse) and any
  divergence would be a breaking change relative to V2's shipped
  clients.

- **`messages.proto`** (V2's `ProxyMessage` / `AIMessage` envelopes)
  — gRPC does framing for us. These V2 files are **discarded** per
  architecture doc §Reused V2 assets.

- **Build configuration** (`buf.gen.yaml`, `buf.yaml`) — lives in the
  repo at `proto/` at implementation time, not here.

- **Heightmap format, unit-def registry** — engine-side concerns, not
  part of the wire contract.

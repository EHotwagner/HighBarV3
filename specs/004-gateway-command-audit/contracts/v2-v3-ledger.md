# Contract — V2/V3 Ledger Row (`audit/v2-v3-ledger.md`)

**Applies to**: every row in `audit/v2-v3-ledger.md`.
**Referenced from**: plan.md (Structure), data-model.md (`V2V3LedgerRow`).

## Row-block Markdown schema

`audit/v2-v3-ledger.md` is a single Markdown document with one
heading-anchored section per V2 pathology. Unlike
`command-audit.md`, the ledger is small (≥ 6 rows) and
individual-row narrative is important — table format would compress
out the V2 source excerpts FR-009 requires.

Document skeleton:

```markdown
# V2 → V3 Problem Ledger

> Source-of-truth for V2 pathologies: `/home/developer/projects/HighBarV2/docs/known-issues.md`
> and `/home/developer/projects/HighBarV2/reports/017-fix-client-socket-hang.md`.
> (Spec FR-009 cites `reports/known-issues.md` — the file actually lives at
> `docs/known-issues.md`; see specs/004-gateway-command-audit/research.md §1
> for the path correction.)
>
> Every row quotes the V2 source excerpt inline so the ledger is
> self-contained on any reviewer host, per FR-009.

## Row table summary

| Pathology | V3 status | Audit row | Residual risk |
|---|---|---|---|
| Callback frame interleaving | fixed | rpc-invoke-callback | none |
| Client `recvBytes` infinite loop | fixed | rpc-stream-state | HTTP/2 idle timeouts are gRPC-lib defaults |
| 8 MB max-message-size insufficient | fixed | rpc-stream-state | monitor under 32×32 maps |
| Single-connection lockout, no auto-reconnect | fixed | rpc-submit-commands | single-AI lockout is now intentional |
| Frame-budget timeout and AI removal | partial | rpc-submit-commands | bounded queue, but drop policy cited |
| Save / Load proxy-side TODO stubs | not-addressed | — | hypothesis plan entry: cmd-… / rpc-save |

## Details

### callback-frame-interleaving

**V2 source**: `HighBarV2/docs/known-issues.md:40-62`

> ### Callback Frame Interleaving During Initialization
>
> When an AI client sends `CallbackRequest` messages outside the
> frame processing window (e.g., during initialization after
> `Step()` completes), the proxy may have already sent the next
> `Frame` message. The client's `sendCallback` then reads a `Frame`
> instead of the expected `CallbackResponse`, causing protocol
> desynchronization.
> …
> **Root cause**: After `Step()` returns
> (receiveFrame → sendFrameResponse), the engine immediately
> triggers the next `EVENT_UPDATE`, causing the proxy to send the
> next `Frame`.

**V3 status**: **fixed** by construction.

**V3 source**: `proto/highbar/service.proto` (separate RPCs for
`StreamState` and `InvokeCallback`); `src/circuit/grpc/HighBarService.cpp`
(their independent dispatch paths).

**V3 mechanism**: V2 multiplexed callbacks and frame-state over a
single protobuf-over-UDS stream. V3's gRPC service splits them:
`StreamState` is a server-streaming RPC carrying
`StateSnapshot`/`StateDelta` messages on its own HTTP/2 stream, and
`InvokeCallback` is a unary RPC on a different HTTP/2 stream. Two
streams, two flow-controlled channels — no in-stream race possible.
V3 inherits gRPC's HTTP/2 multiplexing guarantees (one logical
channel per RPC stream ID).

**Audit row reference**: `rpc-invoke-callback` (Hello → InvokeCallback
round-trip during StreamState active → CallbackResponse received on
its own stream, no Frame interleave).

**Residual risk**: none within the fix's scope. An unrelated HTTP/2
idle-timeout behaviour inherited from gRPC defaults is tracked
separately.

### client-recvbytes-infinite-loop

**V2 source**: `HighBarV2/reports/017-fix-client-socket-hang.md:33-40`

> ```fsharp
> let recvBytes (s: NetworkStream) : byte[] =
>     let headerBuf = Array.zeroCreate<byte> 4
>     let mutable read = 0
>     while read < 4 do
>         read <- read + s.Read(headerBuf, read, 4 - read)  // Returns 0 on peer close
>     // ... same pattern for data buffer
> ```
>
> Per .NET documentation, `NetworkStream.Read()` returns 0 when the
> remote end closes the connection. The code adds 0 to `read` and
> loops forever.

**V3 status**: **fixed** by replacement (transport swap).

**V3 source**: `clients/fsharp/` uses `Grpc.Net.Client`. The
`recvBytes` framing loop is gone — gRPC's HTTP/2 transport handles
peer-close as a normal `RpcException(StatusCode.Unavailable)` or
stream-cancel, surfacing through `StreamState.MoveNext()` with a
typed exception that callers can catch.

**V3 mechanism**: HTTP/2 PING and END_STREAM semantics detect peer
death; gRPC's client-side ClientCall state machine translates those
into `RpcException`. The V2 infinite loop was specific to the hand-
rolled framed-blob socket reader; that code path does not exist in
V3.

**Audit row reference**: `rpc-stream-state` (kill the plugin mid-
stream; the F# StreamState consumer's `await foreach` raises
`RpcException(Unavailable)` without spinning).

**Residual risk**: gRPC default HTTP/2 idle timeouts can add up to
~minutes of silent hang if KeepAlive isn't configured. Tracked in
the Config tests (002 US6).

### max-message-size-8mb

**V2 source**: `HighBarV2/docs/known-issues.md:64-74`

> ### Max Message Size for Large Maps
>
> The default `max_message_size` is 8 MB. Map data arrays for large
> maps (32x32 SMU) can exceed this:
>
> | Map Size | HeightMap Size |
> |----------|---------------|
> | 8x8 SMU | ~1 MB |
> | 16x16 SMU | ~4 MB |
> | 32x32 SMU | ~16 MB |

**V3 status**: **fixed** by default + override.

**V3 source**: `data/config/grpc.json` sets `max_recv_mb: 32`.
`src/circuit/grpc/HighBarService.cpp` applies the value to gRPC
ChannelArguments at server init.

**V3 mechanism**: V3's default gRPC channel config doubles V2's
raw default and is itself overridable from `data/config/grpc.json`.
The client F# and Python stubs read the same config and match on
their side.

**Audit row reference**: `rpc-stream-state` (Hello returns
StateSnapshot on the largest available test map; message size
measured; under 32 MB). A dedicated 32×32-map row may be added once
the test host has such a map installed.

**Residual risk**: monitor under 32×32-map matches; if Hello grows
past 32 MB (unlikely — StateSnapshot does not carry heightmap at
all in V3 wire format), a config bump is a one-line change.

### single-connection-lockout

**V2 source**: `HighBarV2/docs/known-issues.md:76-78`

> ### Single Connection
>
> The proxy supports one AI client connection at a time. If the AI
> process disconnects, the proxy will report an error to the engine
> on the next frame. There is no automatic reconnection.

**V3 status**: **fixed** intentionally.

**V3 source**: `docs/architecture.md` §gRPC service (single-AI
lockout is by design: second AI `SubmitCommands` → `ALREADY_EXISTS`).
Reconnect is supported for both AI and observer roles via the
delta ring buffer (`resume_from_seq`).

**V3 mechanism**: V3 keeps the single-AI invariant (one decision
authority) but supports reconnection: the plugin holds the delta
ring buffer for ring-buffer-size frames; a dropped AI client can
resume via `resume_from_seq`. If the seq is out of range, a fresh
StateSnapshot is sent. Observers can connect/disconnect freely.

**Audit row reference**: `rpc-submit-commands` (includes the
deliberate duplicate-AI test from spec edge cases — second
`SubmitCommands` returns `ALREADY_EXISTS`).

**Residual risk**: single-AI is now an intentional architectural
invariant, not a limitation. Documented.

### frame-budget-timeout

**V2 source**: `HighBarV2/docs/known-issues.md:80-82`

> ### Frame Budget
>
> The default timeout is 25ms. If the AI consistently exceeds this
> budget, the engine may remove the AI. The
> `GameState.processFrame` function enforces a 20ms internal budget
> for manager evaluation and logs warnings when frames exceed 25ms.

**V3 status**: **partial**.

**V3 source**: `src/circuit/grpc/CommandQueue.cpp` (bounded MPSC);
`src/circuit/grpc/DeltaBus.cpp` (drop-if-full policy on slow
subscribers). The plugin itself never blocks on gRPC I/O on the
engine thread.

**V3 mechanism**: V3 inherits the same fundamental constraint
(Spring calls the AI plugin on the engine thread with a budget),
but V3's engine-thread work is bounded: (a) CommandQueue drains
the MPSC queue with a bounded size, (b) DeltaBus fan-out is
non-blocking — slow subscribers drop deltas rather than stall the
engine thread, (c) gRPC workers do all serialization. The result:
a slow client cannot cause AI removal.

**Audit row reference**: `rpc-submit-commands` (queue-full drop
behaviour exercised in the CommandQueue unit tests; load-induced
drop recorded in the latency benches).

**Residual risk**: the drop-if-full policy means a very-slow
subscriber loses deltas. The expected recovery is
`resume_from_seq`; if the subscriber is also slow enough to fall
out of the ring buffer, they receive a fresh snapshot. Documented.

### save-load-proxy-stubs

**V2 source**: `HighBarV2/docs/known-issues.md:3-10` and
`HighBarV2/proxy/src/proxy.c:382` (SaveRequest handler),
`HighBarV2/proxy/src/proxy.c:391` (LoadRequest handler).

> | Feature | Location | Notes |
> |---------|----------|-------|
> | Save state passthrough | `proxy/src/proxy.c:382` | `TODO: pass save data back to engine` — SaveRequest handler sends empty state |
> | Load state passthrough | `proxy/src/proxy.c:391` | `TODO: pass saved state blob from engine` — LoadRequest handler is a stub |

**V3 status**: **not-addressed** (determined by audit).

**V3 source**: `proto/highbar/service.proto` defines `Save` /
`Load` RPCs. The audit's evidence will determine whether V3's
engine-side handlers are implemented, stubbed, or proxied (spec
edge case "Save / Load"). Until the audit runs, status is
`not-addressed` / pending evidence.

**V3 mechanism**: n/a at ledger time; updated after audit rows
`rpc-save` and `rpc-load` land.

**Hypothesis plan reference**: `RECOMMEND_ADD` — the audit rows
for `rpc-save` and `rpc-load` will dispatch the RPC and observe
whether the response carries engine state or an empty blob. If
empty-blob, log as `broken` with `dispatcher_defect` hypothesis
class and a follow-up test "call `Save` after commander build,
assert response blob is non-empty."

**Residual risk**: saved-game round-trip is untested in V3 at
ledger authoring time.
```

## Field-by-field rules

For each field defined in `data-model.md` §V2V3LedgerRow:

| Field | Markdown placement | Validation |
|-------|-------------------|------------|
| `pathology_id` | Level-3 heading (`### callback-frame-interleaving`). | Kebab-case; unique. |
| `pathology_name` | Implicit from heading. | Human-readable. |
| `v2_source_citation` | `**V2 source**:` bullet. | `file:line_start-line_end` under `HighBarV2/`. |
| `v2_excerpt` | Blockquote immediately after the `V2 source` bullet. | Non-empty. FR-009 inline-quote requirement. |
| `v3_status` | `**V3 status**:` bullet. | One of `fixed` / `partial` / `not-addressed`. |
| `v3_source_citation` | `**V3 source**:` bullet. | Required for `fixed` / `partial`. |
| `v3_mechanism` | Paragraph under `**V3 mechanism**:`. | Required for `fixed` / `partial`. |
| `audit_row_reference` | `**Audit row reference**:` bullet. | Required for `fixed`. Must resolve to an `AuditRow.row_id` with `outcome=verified`. |
| `hypothesis_plan_reference` | `**Hypothesis plan reference**:` bullet. | Required for `not-addressed`. Either an existing entry arm_name or `RECOMMEND_ADD` with a one-sentence test. |
| `residual_risk` | Paragraph under `**Residual risk**:`. | Optional; default "none" if the fix is complete. |

## Completeness rule

Per FR-010, the ledger MUST contain at least the six rows named by
content. A static enumeration in the generator asserts this:

```python
REQUIRED_PATHOLOGY_IDS = {
    "callback-frame-interleaving",
    "client-recvbytes-infinite-loop",
    "max-message-size-8mb",
    "single-connection-lockout",
    "frame-budget-timeout",
    "save-load-proxy-stubs",
}
assert REQUIRED_PATHOLOGY_IDS <= {row.pathology_id for row in rows}, \
    f"missing FR-010 pathologies: {REQUIRED_PATHOLOGY_IDS - ids}"
```

## Ordering

- The summary table at the top lists rows in FR-010's named order.
- The details section orders rows the same way; any additional
  non-FR-010 rows appear after the six required.

# V2 -> V3 Problem Ledger

> Latest completed run: `live-audit-20260422T064705Z`

## Row table summary

| Pathology | V3 status | Audit row | Residual risk |
|---|---|---|---|
| Callback frame interleaving | fixed | rpc-invoke-callback | None within the split-RPC design. |
| Client recvBytes infinite loop | fixed | rpc-stream-state | Transport liveness still depends on gRPC keepalive configuration. |
| 8 MB max-message-size insufficient | fixed | rpc-stream-state | Large-map coverage should still be rechecked on bigger pools. |
| Single-connection lockout, no auto-reconnect | fixed | rpc-submit-commands | The single-AI invariant still intentionally rejects duplicate AI writers. |
| Frame-budget timeout and AI removal | partial | rpc-submit-commands | Very slow consumers may fall out of the ring buffer and require a fresh snapshot. |
| Save / Load proxy-side TODO stubs | fixed | rpc-save | Live save/load evidence is linked from the latest completed manifest. |

## Details

### callback-frame-interleaving

**V2 source**: `/home/developer/projects/HighBarV2/docs/known-issues.md:40-62`

> Callback requests could receive the next Frame instead of a CallbackResponse, desynchronizing the protocol.

**V3 status**: **fixed**

**V3 source**: `proto/highbar/service.proto:38-82`

**V3 mechanism**: V3 splits state streaming and callback invocation into separate gRPC RPCs, removing the V2 multiplexing race.

**Audit row reference**: [`rpc-invoke-callback`](command-audit.md#rpc-invoke-callback)

**Residual risk**: None within the split-RPC design.

### client-recvbytes-infinite-loop

**V2 source**: `/home/developer/projects/HighBarV2/reports/017-fix-client-socket-hang.md:33-40`

> The F# framed-socket reader added zero bytes on peer close and looped forever.

**V3 status**: **fixed**

**V3 source**: `proto/highbar/service.proto:43-44`

**V3 mechanism**: The framed socket loop is gone; the clients now ride gRPC and surface disconnects as typed RPC failures.

**Audit row reference**: [`rpc-stream-state`](command-audit.md#rpc-stream-state)

**Residual risk**: Transport liveness still depends on gRPC keepalive configuration.

### max-message-size-8mb

**V2 source**: `/home/developer/projects/HighBarV2/docs/known-issues.md:64-74`

> The default 8 MB framing limit was too small for large-map payloads.

**V3 status**: **fixed**

**V3 source**: `data/config/grpc.json:1-40`

**V3 mechanism**: The message-size limit is now configurable through shared gRPC settings instead of hard-coded framed I/O defaults.

**Audit row reference**: [`rpc-stream-state`](command-audit.md#rpc-stream-state)

**Residual risk**: Large-map coverage should still be rechecked on bigger pools.

### single-connection-lockout

**V2 source**: `/home/developer/projects/HighBarV2/docs/known-issues.md:76-78`

> The proxy supported one client connection and had no structured reconnect path.

**V3 status**: **fixed**

**V3 source**: `docs/architecture.md:116-152`

**V3 mechanism**: Single-AI ownership remains intentional, but reconnect and resume semantics exist for supported client roles.

**Audit row reference**: [`rpc-submit-commands`](command-audit.md#rpc-submit-commands)

**Residual risk**: The single-AI invariant still intentionally rejects duplicate AI writers.

### frame-budget-timeout

**V2 source**: `/home/developer/projects/HighBarV2/docs/known-issues.md:80-82`

> Slow client-side processing could violate the frame budget and get the AI removed.

**V3 status**: **partial**

**V3 source**: `src/circuit/grpc/CommandQueue.cpp:1-220`

**V3 mechanism**: V3 bounds engine-thread work through queues and async serialization, but slow clients can still drop data and need resume logic.

**Audit row reference**: [`rpc-submit-commands`](command-audit.md#rpc-submit-commands)

**Residual risk**: Very slow consumers may fall out of the ring buffer and require a fresh snapshot.

### save-load-todos

**V2 source**: `/home/developer/projects/HighBarV2/docs/known-issues.md:84-92`

> Save and Load handling remained stubbed or incomplete in the proxy.

**V3 status**: **fixed**

**V3 source**: `proto/highbar/service.proto:55-63`

**V3 mechanism**: Save and Load now exist as first-class unary RPCs in the service contract and service implementation.

**Audit row reference**: [`rpc-save`](command-audit.md#rpc-save)

**Residual risk**: Live save/load evidence is linked from the latest completed manifest.

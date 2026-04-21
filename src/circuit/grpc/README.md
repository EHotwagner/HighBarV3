# `src/circuit/grpc/` — HighBarV3 gRPC Gateway internals

This directory holds every V3-owned source file for the gRPC gateway
module. It exists as a self-contained subtree so that upstream BARb
merges only ever touch three files outside it: `CircuitAI.cpp` (module
registration), `CMakeLists.txt` (gRPC target wire-up), and
`module/GrpcGatewayModule.{h,cpp}` (the `IModule` shim).

## Threading contract (Constitution II, NON-NEGOTIABLE)

Every `.cpp` in this directory MUST make its threading discipline
obvious in the file header. Two rules apply to every line of code
here:

1. **Engine-thread supremacy.** All CircuitAI state writes, every
   `CCircuitUnit::Cmd*` call, and every mutation of the gateway's
   engine-side accumulators (`current_frame_delta_`, `seq_`,
   `frames_since_last_flush_`) happen on the single engine callback
   thread driven by Spring. gRPC worker threads never call into these
   paths directly.

2. **The one read-side carve-out.** Worker threads can **read**
   serialized snapshots / deltas via the shared/exclusive
   `state_mutex_` — the writer (engine thread, `FlushDelta`) never
   blocks on gRPC I/O, and workers never block the writer for longer
   than a `memcpy` of a `shared_ptr<const string>`.

Command flow: workers validate on their own thread, deposit onto the
MPSC `CommandQueue`, and the engine thread drains at the top of each
`OnFrameTick`. State flow: the engine thread publishes to the SPMC
`DeltaBus`, per-subscriber pump threads consume.

## File map

| File | Role |
|---|---|
| `HighBarService.{h,cpp}` | Async gRPC server, CallData state machines. |
| `SnapshotBuilder.{h,cpp}` | Materializes `StateSnapshot` from CircuitAI managers. |
| `DeltaBus.{h,cpp}` | SPMC fan-out from engine thread to subscribers. |
| `SubscriberSlot.{h,cpp}` | Per-subscriber bounded ring. |
| `RingBuffer.{h,cpp}` | 2048-entry resume-history. |
| `CommandQueue.{h,cpp}` | MPSC drop-off, engine-thread drain. |
| `CommandValidator.{h,cpp}` | Worker-thread argument validation. |
| `CommandDispatch.{h,cpp}` | Engine-thread `AICommand → CCircuitUnit::Cmd*`. |
| `AuthToken.{h,cpp}` | 256-bit token + atomic-write file. |
| `AuthInterceptor.{h,cpp}` | Per-RPC token gate. |
| `Config.{h,cpp}` | `grpc.json` parse + UDS path resolution. |
| `Counters.{h,cpp}` | Atomic gauges + rolling flush-latency bucket. |
| `Log.{h,cpp}` | Façade over BARb's `LOG()`. |
| `SchemaVersion.h` | Compile-time constant — strict-equality handshake. |

See also: [`docs/architecture.md`](../../../docs/architecture.md) and
[`specs/001-grpc-gateway/`](../../../specs/001-grpc-gateway/).

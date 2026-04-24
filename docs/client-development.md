# HighBarV3 Client Development Guide

This guide explains how to create HighBar clients in languages beyond
the maintained Python and F# clients. HighBar uses ordinary proto3 and
gRPC, so any language with support for client-side streaming,
server-side streaming, unary RPCs, and plaintext UDS or loopback TCP can
interoperate.

Read this with [Proto Reference](proto-reference.md), which defines the
service surface and message contracts.

## Client Types

| Client type | Required service | Typical capabilities |
| --- | --- | --- |
| Observer | `HighBarProxy` | `Hello`, `StreamState`, counters. |
| AI policy | `HighBarProxy` | Observer flow plus token-authenticated `SubmitCommands`, validation, callbacks, save/load. |
| Admin/test harness | `HighBarAdmin` | Capabilities, dry-run validation, pause/speed/spawn/resource/transfer actions. |
| Coordinator | `HighBarCoordinator` | Plugin dial-out topology, state fan-out, command channel. |

Start with an observer. It exercises transport, schema compatibility,
and stream handling without mutating the match.

## Repository-Owned Clients

### Python

The supported Python package lives in `clients/python`.

```bash
cd clients/python
python -m pip install -e '.[dev]'
make codegen
make test
```

Generated stubs are committed under
`clients/python/highbar_client/highbar/`. Useful modules:

- `highbar_client.channel`: endpoint construction.
- `highbar_client.session`: `Hello`, token reading, schema checks.
- `highbar_client.state_stream`: stream recording and invariants.
- `highbar_client.commands`: command batch helpers and diagnostics.
- `highbar_client.admin`: admin action builders.
- `highbar_client.live_topology`: standard Python launcher for live
  Recoil/BAR topologies and BNV demos.

### F# / .NET

The F# wrapper lives in `clients/fsharp`.

- `HighBar.Proto.csproj` generates C# stubs from `proto/highbar/*.proto`.
- `HighBar.Client.fsproj` wraps channel, session, command, state, and
  admin helpers.
- Samples are in `clients/fsharp/samples/Observer` and
  `clients/fsharp/samples/AiClient`.

## Generate Stubs For Another Language

### With Buf

Create a local generation template for your language instead of editing
`proto/buf.gen.yaml` unless you intend to commit generated outputs for
that language.

Example `buf.gen.go.yaml`:

```yaml
version: v2
plugins:
  - remote: buf.build/protocolbuffers/go
    out: gen/go
    opt: paths=source_relative
  - remote: buf.build/grpc/go
    out: gen/go
    opt: paths=source_relative
```

Run:

```bash
buf generate proto --template buf.gen.go.yaml
```

For languages without a Buf remote plugin, install the standard protoc
plugin and call `protoc` directly.

### With `protoc`

Every generator needs `proto` as its import root:

```bash
protoc -I proto \
  --<language>_out=gen/<language> \
  --grpc-<language>_out=gen/<language> \
  proto/highbar/*.proto
```

The generated package/namespace comes from `package highbar.v1` unless
your generator has its own namespace options.

## Required Runtime Flow

### Observer Flow

1. Create a plaintext gRPC channel to UDS or loopback TCP.
2. Call `HighBarProxy.Hello`:

   - `schema_version = "1.0.0"`
   - `client_id = "your-client/name-version"`
   - `role = ROLE_OBSERVER`

3. Verify the response schema equals your generated schema.
4. Start `StreamState(StreamStateRequest{resume_from_seq: 0})`.
5. Require monotonic `StateUpdate.seq`.
6. Treat the first `snapshot` as baseline and apply later `delta`
   events in order.

### AI Flow

1. Read the token file with retry/backoff.
2. Call `Hello` with `role = ROLE_AI` and metadata
   `x-highbar-ai-token`.
3. Start `StreamState`.
4. Call `GetCommandSchema` once after handshake.
5. For a unit, call `GetUnitCapabilities` before building strict
   batches.
6. Use `ValidateCommandBatch` during client development and before
   uncertain commands.
7. Open `SubmitCommands` and stream `CommandBatch` messages.
8. Reconcile both:

   - immediate `CommandAck.results`
   - later `CommandDispatchEvent` deltas

### Admin Flow

1. Call `GetAdminCapabilities`.
2. Build `AdminAction` with action sequence, client action id, conflict
   policy, basis fields when available, and reason.
3. Call `ValidateAdminAction` for dry-run checks.
4. Call `ExecuteAdminAction` with metadata:

   - `x-highbar-ai-token`
   - `x-highbar-admin-role`
   - `x-highbar-client-id`

5. Verify success behaviorally through state stream, snapshot/delta, or
   engine-log evidence. Do not treat `ADMIN_ACTION_EXECUTED` alone as
   proof.

## Transport Patterns

### TCP

Use plaintext HTTP/2 over loopback:

```text
127.0.0.1:50511
```

Do not expose the service on non-loopback interfaces. HighBar has no TLS
or cross-host auth model.

### UDS

Use the gRPC runtime's Unix-domain-socket support.

Endpoint strings vary by language:

| Runtime | Typical endpoint |
| --- | --- |
| Python `grpcio` | `unix:/tmp/highbar.sock` |
| Go `grpc-go` | custom dialer with `network="unix"` |
| .NET `Grpc.Net.Client` | `SocketsHttpHandler.ConnectCallback` |
| Java grpc-netty | `NettyChannelBuilder.forAddress(new DomainSocketAddress(path))` with native transport |
| Rust `tonic` | `Endpoint::connect_with_connector` and `tokio::net::UnixStream` |
| Node `@grpc/grpc-js` | use TCP; UDS support depends on runtime and path form |

When UDS support is awkward, use loopback TCP.

## Language Notes

### Go

Generate stubs with `protoc-gen-go` and `protoc-gen-go-grpc`. Use
stream APIs directly:

- `client.StreamState(ctx, req)` returns a receive stream.
- `client.SubmitCommands(ctx)` returns a send stream followed by
  `CloseAndRecv`.

For UDS, use `grpc.DialContext` with a custom context dialer that calls
`net.Dialer.DialContext(ctx, "unix", path)`.

### Rust

Use `prost` and `tonic`. Add the proto files to `build.rs`, include
`proto` as the import path, and generate client modules for
`highbar.v1`. `StreamState` is an inbound stream; `SubmitCommands`
requires an outbound stream such as `tokio_stream::iter`.

For UDS, build a `tonic::transport::Endpoint` with a custom connector
backed by `tokio::net::UnixStream`, or use loopback TCP.

### Java / Kotlin

Use `protobuf-gradle-plugin` with `grpc-java`. Generated service clients
are:

- `HighBarProxyGrpc`
- `HighBarAdminGrpc`
- `HighBarCoordinatorGrpc`

For TCP, use `ManagedChannelBuilder.forAddress("127.0.0.1", port)
.usePlaintext()`. UDS requires Netty native epoll/kqueue domain socket
support; otherwise prefer TCP.

### Node / TypeScript

Use either static generation (`grpc-tools`, `ts-proto`) or dynamic
loading (`@grpc/proto-loader` plus `@grpc/grpc-js`). Make sure oneof
fields are preserved; HighBar relies heavily on oneof command/action
arms.

Use loopback TCP unless your stack has verified UDS support.

### C++ Tools

The native plugin already builds C++ stubs into `build/gen`. Separate C++
tools can also generate from `proto/highbar/*.proto` using
`grpc_cpp_plugin`. Avoid linking those tools into the Recoil process
unless they use the same protobuf/gRPC ABI as the native plugin.

## Minimum Client Invariants

Every client should enforce:

- `HelloResponse.schema_version == "1.0.0"`.
- `StateUpdate.seq` never decreases or repeats on one stream.
- `StateUpdate.payload` oneof is recognized; unknown payloads are
  logged and skipped.
- Command batches set `client_command_id`, `based_on_frame`, and
  `based_on_state_seq` once the client has observed state.
- Retried command batches use a fresh `batch_seq`; keep
  `client_command_id` stable if the retry represents the same intent.
- Admin success requires behavioral evidence.
- `UNAVAILABLE` is recoverable only by reconnecting and resuming the
  state stream.

## Command Batch Example

Pseudo-code independent of generated language names:

```text
latest = wait_for_snapshot_or_delta()
unit = choose own unit from latest.own_units

cmd = AICommand {
  move_unit: {
    unit_id: unit.unit_id
    options: 0
    timeout: 0
    to_position: { x: 1024, y: 0, z: 1024 }
  }
}

batch = CommandBatch {
  batch_seq: next_batch_seq()
  target_unit_id: unit.unit_id
  commands: [cmd]
  client_command_id: next_client_command_id()
  based_on_frame: latest.frame
  based_on_state_seq: latest.seq
  conflict_policy: COMMAND_CONFLICT_REPLACE_CURRENT
}

result = ValidateCommandBatch(batch)
if result.status is acceptable:
  send batch on SubmitCommands
```

## Admin Action Example

```text
action = AdminAction {
  action_seq: next_action_seq()
  client_action_id: next_client_action_id()
  based_on_frame: latest.frame
  based_on_state_seq: latest.seq
  conflict_policy: ADMIN_CONFLICT_REJECT_IF_CONTROLLED
  reason: "demo speed change"
  global_speed: { speed: 2.0 }
}

result = ExecuteAdminAction(action, metadata)
assert result.status == ADMIN_ACTION_EXECUTED
observe "Speed set to 2.0" in engine log or speed-equivalent state evidence
```

## CI-Safe Contribution Workflow

Documentation-only changes should not require generated code, but API
or client changes do. Run the hosted workflow equivalents before
pushing:

```bash
buf lint proto
cd proto && buf generate
cd ../clients/python
python -m pip install -e '.[dev]'
make codegen
make test
```

Also run shell syntax checks when touching `tests/headless` or
`tests/bench`:

```bash
bash -n tests/headless/*.sh tests/bench/*.sh
```

If `.proto` files change, commit regenerated Python stubs and update
this guide plus [Proto Reference](proto-reference.md). Do not edit
generated `*_pb2.py` files manually.

## Common Pitfalls

- Calling mutating RPCs before `Hello`.
- Forgetting `x-highbar-ai-token` on AI/admin RPCs.
- Building command batches without a target unit or basis fields.
- Treating `CommandAck` as final execution evidence; dispatch happens on
  the engine thread and is reflected later.
- Holding the state stream receive loop on the UI thread.
- Assuming UDS endpoint syntax is identical across language runtimes.
- Adding generated code for a new language without updating `.gitignore`
  and CI expectations.

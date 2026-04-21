# Contract: Gateway fault observability

**Addresses**: FR-023, FR-024, spec Clarification Q4.

When `CGrpcGatewayModule` catches an exception at its IModule
boundary (or at a gRPC service-impl boundary or inside the
serializer), three externally-observable signals are emitted
atomically from the engine thread before the gateway transitions to
`Disabled`. Every acceptance script and CI job asserting on fault
behavior reads these signals from one of three sources:

1. The engine's stdout log, via a structured `[hb-gateway] fault` line.
2. A health file on disk at `$writeDir/highbar.health`.
3. gRPC stream trailers on closed subscriber streams.

## 1. Log line format

```
[hb-gateway] fault subsystem=<subsystem> reason=<code> detail="<escaped free-text>" schema=highbar.v1 pid=<pid> frame=<engine-frame-num>
```

Field grammar:

| Field | Grammar | Notes |
|---|---|---|
| `subsystem` | one of: `transport`, `serialization`, `dispatch`, `callback`, `handler` | Named at the catch site. See C++ constant table in `src/circuit/grpc/Log.h`. |
| `reason` | snake_case identifier, ≤32 chars | Stable across releases. Mapping from C++ exception types lives in `src/circuit/grpc/Log.cpp::ReasonCodeFor`. |
| `detail` | double-quoted, backslash-escaped | Typically `e.what()`. May be empty (`detail=""`). |
| `schema` | literal `highbar.v1` | Pinned here so grepping across years of logs is cheap. |
| `pid` | decimal | Enables correlating against kernel oops / OOM killer logs. |
| `frame` | decimal | Engine frame at fault. Zero if the fault occurs before the first frame callback. |

The line is written exactly once per match. A match that never
faults emits one healthy startup line and no fault line. A match
that faults once emits one fault line and then nothing further from
the gateway.

### Reason-code namespace (open — add as needed)

| `reason` | Triggered by | Typical subsystem |
|---|---|---|
| `oom` | `std::bad_alloc` during serialize or send | `serialization` |
| `malformed_frame` | `protobuf::InvalidArgument` decoding client payload | `transport` |
| `rpc_internal` | unexpected `grpc::Status::INTERNAL` from handler | `handler` |
| `dispatch_threw` | exception thrown from a `CCircuitUnit::Cmd*` call | `dispatch` |
| `engine_callback_threw` | exception thrown inside an IModule hook | `callback` |
| `assertion_failed` | CircuitAI internal assert (caught as exception) | depends on site |

Adding a reason code is a patch-level change; removing one is a
MINOR-level change (clients may grep for specific codes).

## 2. Health file format

Path: `$writeDir/highbar.health` (same directory as
`highbar.token`). Mode `0644` (world-readable — this is diagnostic
signal, not a secret).

Format: single-line JSON, stable field order, trailing newline.

```json
{"status":"healthy","schema":"highbar.v1","pid":12345}
```

On fault:

```json
{"status":"disabled","schema":"highbar.v1","pid":12345,"subsystem":"serialization","reason":"oom","detail":"std::bad_alloc","frame":9042}
```

Fields:

| Field | Type | Notes |
|---|---|---|
| `status` | `"healthy"` \| `"disabled"` | Two values only. |
| `schema` | `"highbar.v1"` | Pinned. |
| `pid` | integer | Gateway process id. |
| `subsystem` / `reason` / `detail` / `frame` | Same grammar as the log line. | Present only when `status=disabled`. |

Writing is performed via write-temp-and-rename so readers never
observe a half-written file.

The file is *not* removed on match exit. Its presence across matches
is harmless: the `pid` field lets any reader tell whether it
reflects the current run.

## 3. Stream trailer metadata

When `TransitionToDisabled` closes active subscriber streams, each
stream's final `grpc::Status` is:

```
code  = UNAVAILABLE (14)
message = "highbar gateway disabled — see highbar.health"
trailing metadata =
    highbar-fault-subsystem: <subsystem>
    highbar-fault-reason:    <reason>
```

Clients that ignore trailers get the canonical `UNAVAILABLE` status
with an informative message. Clients that read trailers (the F# and
Python reference implementations from 001) can log the structured
fields without parsing the health file.

## 4. Assertion helper for acceptance scripts

A helper shell function lives at
`tests/headless/_fault-assert.sh` and is sourced by any test that
needs to distinguish healthy-gateway from disabled-gateway state:

```bash
# Exits 0 if gateway is healthy; 2 if disabled; 77 if no highbar.health
# file is present (state indeterminate); other non-zero on parse errors.
fault_status() {
    local write_dir="${1:?write_dir required}"
    # ...parses $write_dir/highbar.health...
}
```

Acceptance scripts call `fault_status` before declaring PASS; a
disabled-state finding converts the script's exit from 0 to 1
(explicit failure), never to 77 (skip). This is how FR-024's
"disabled gateway must be treated as a failure, not a skip" is
mechanized.

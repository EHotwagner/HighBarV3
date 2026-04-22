# Contract: `HighBarProxy.RequestSnapshot` RPC

**Feature**: 003-snapshot-arm-coverage
**Consumes**: FR-006; research.md §R1
**Back-compat**: additive service method within `highbar.v1`.

---

## Proto surface (additive edit)

### `proto/highbar/service.proto` — new RPC + messages

Add to the `HighBarProxy` service:

```proto
service HighBarProxy {
  rpc Hello(HelloRequest) returns (HelloResponse);
  rpc StreamState(StreamStateRequest) returns (stream highbar.v1.StateUpdate);
  rpc SubmitCommands(stream highbar.v1.CommandBatch) returns (CommandAck);
  rpc InvokeCallback(highbar.v1.CallbackRequest) returns (highbar.v1.CallbackResponse);
  rpc Save(SaveRequest) returns (SaveResponse);
  rpc Load(LoadRequest) returns (LoadResponse);
  rpc GetRuntimeCounters(CountersRequest) returns (CountersResponse);

  // NEW (003-snapshot-arm-coverage).
  //
  // Request an out-of-cadence StateSnapshot. The plugin emits exactly
  // one extra snapshot on the next engine frame following the RPC,
  // regardless of how many concurrent callers made the request. The
  // snapshot arrives on the caller's existing `StreamState` subscription
  // — this RPC does not itself return snapshot data.
  //
  // AI role only (same token as SubmitCommands); observers use the
  // periodic tick or their existing StreamState resume path.
  //
  // Use sparingly — the plugin guards against DoS via the 1-per-frame
  // coalescing described in FR-006.
  rpc RequestSnapshot(RequestSnapshotRequest) returns (RequestSnapshotResponse);
}
```

Add the two new messages at the end of `service.proto`:

```proto
message RequestSnapshotRequest {
  // Empty. Reserved for future extensions (e.g., per-team restriction
  // if multi-team subscriptions ever land).
}

message RequestSnapshotResponse {
  // Engine frame the plugin committed to emit the forced snapshot
  // on. Clients MAY use this to correlate the forced snapshot on
  // their StreamState stream (match `StateSnapshot.frame_number ==
  // scheduled_frame`). Zero if the gateway was not Healthy at
  // dispatch time — the RPC then returns with status code
  // FAILED_PRECONDITION.
  uint32 scheduled_frame = 1;
}
```

---

## Handler behavior contract

The plugin-side RPC handler MUST observe the following invariants:

1. **Role enforcement.** `RequestSnapshot` requires the `x-highbar-
   ai-token` metadata header; without it, the RPC returns status
   `PERMISSION_DENIED` and no state is touched.

2. **Health gating.** If the gateway is not `Healthy` at the moment
   the handler runs, the RPC returns status `FAILED_PRECONDITION`
   with message `gateway state=<state>` and `scheduled_frame = 0`.

3. **Coalescing.** Concurrent callers racing to set
   `pending_request` observe the same outcome: exactly one extra
   snapshot fires at the next engine frame after the first flip,
   and all callers receive `scheduled_frame` equal to that frame.
   Implementation note: the handler reads `CurrentFrame() + 1`
   while holding `state_mutex_` shared, sets the atomic, and
   returns. The engine-thread tick, on observing the atomic, drains
   it and emits.

4. **Non-blocking.** The handler MUST NOT block waiting for the
   forced snapshot to fire. It returns as soon as the atomic is
   set. Clients that need to *observe* the snapshot do so on their
   existing `StreamState` subscription.

5. **Thread discipline.** The handler runs on a gRPC worker
   thread; it MUST NOT call the serializer, touch CircuitAI
   managers, or invoke any `CCircuitUnit::Cmd*` method. The only
   cross-thread state it touches is `pending_request_`
   (`std::atomic<bool>`) and `CurrentFrame()` (atomic uint32).
   (Constitution II.)

---

## Client expectations

### Python (`highbar_client`)

Test drivers wrap the RPC in a helper inside
`clients/python/highbar_client/behavioral_coverage/`:

```python
async def request_snapshot_and_wait(session, stream, timeout=2.0):
    resp = await session.proxy.RequestSnapshot(RequestSnapshotRequest())
    if resp.scheduled_frame == 0:
        raise GatewayNotHealthyError("cannot force snapshot")
    async for update in stream.iter_state_updates(timeout=timeout):
        if update.payload.kind == "snapshot" and \
           update.payload.snapshot.frame_number >= resp.scheduled_frame:
            return update.payload.snapshot
    raise TimeoutError(f"forced snapshot for frame {resp.scheduled_frame} not observed in {timeout}s")
```

### F# (`HighBar.Client`)

Codegen regenerates the stub; a thin `RequestSnapshotAsync(CancellationToken)`
wrapper in `HighBar.Client` exposes it to consumers. F# behavioral
tests are deferred (spec §Out of Scope), so the wrapper is defined
but not exercised in this feature.

### C++ (plugin)

Server-side only. No C++ client consumes this RPC.

---

## Rate / DoS protection

FR-006 requires the plugin to coalesce repeat requests to at most
one extra snapshot per engine frame. The atomic-flag implementation
satisfies this exactly: N concurrent handlers all set the same
`std::atomic<bool>`; the engine thread observes it once, serializes
one snapshot, clears the flag. Subsequent same-frame handlers find
the flag already set, do not re-trigger, and return the same
`scheduled_frame`.

No per-caller rate limiting is needed beyond this coalescing — a
single misbehaving client cannot force more than one extra snapshot
per frame regardless of how fast it calls the RPC.

---

## Acceptance-script surface

The macro driver uses `RequestSnapshot` at three points:

- **Pre-dispatch snapshot capture.** Before dispatching each arm's
  `CommandBatch`, the driver calls `RequestSnapshot` to guarantee
  a snapshot no older than 1 frame; it uses that as
  `SnapshotPair.before`.
- **Pre-reset snapshot capture.** Before each bootstrap-state
  reset, the driver calls `RequestSnapshot` to get the current
  `own_units[]` for manifest diffing.
- **Post-reset confirmation.** If the periodic tick would arrive
  outside the reset's 10-second budget, the driver forces one to
  confirm the reset completed.

No new dedicated acceptance script is needed for `RequestSnapshot`
itself; `snapshot-tick.sh` (US5) exercises the periodic path and
`aicommand-behavioral-coverage.sh` (US4) exercises the forced path
via the macro driver's behavior. The unit-test surface
(`snapshot_tick_test.cc`) covers the coalescing invariant
directly.

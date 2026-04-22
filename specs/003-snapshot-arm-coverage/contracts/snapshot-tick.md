# Contract: Snapshot tick & `effective_cadence_frames`

**Feature**: 003-snapshot-arm-coverage
**Consumes**: FR-001, FR-011; data-model §7; research.md §R1–R2
**Back-compat**: additive within `highbar.v1`; no version bump.

---

## Proto surface (additive edit)

### `proto/highbar/state.proto` — new field

Add to `message StateSnapshot`:

```proto
message StateSnapshot {
  uint32 frame_number                 = 1;
  repeated OwnUnit    own_units       = 2;
  repeated EnemyUnit  visible_enemies = 3;
  repeated RadarBlip  radar_enemies   = 4;
  repeated MapFeature map_features    = 5;
  TeamEconomy         economy         = 6;
  StaticMap           static_map      = 7;

  // NEW (003-snapshot-arm-coverage).
  //
  // The effective cadence, in engine frames, that was in effect when
  // this snapshot fired. Clients compute the expected next-snapshot
  // frame as `frame_number + effective_cadence_frames`.
  //
  // Equals SnapshotTickConfig.snapshot_cadence_frames under normal
  // load. Doubles (up to a 1024-frame cap) on each emission while
  // own_units.length > snapshot_max_units; snaps back to the
  // configured base value on the first emission with the count back
  // under the cap.
  //
  // Zero (proto3 default) iff the snapshot was emitted by the Hello
  // one-shot path rather than by the tick scheduler; clients that
  // need a cadence hint in that case treat 0 as "unknown, assume
  // configured default."
  uint32 effective_cadence_frames     = 8;
}
```

Field number `8` is the next free number after 001's
`static_map = 7`. This is the only `state.proto` edit this feature
makes.

### Client expectations

- **Python (`highbar_client`)**: auto-generated from the regenerated
  stub after `clients/python/Makefile codegen`. Test drivers read
  `snapshot.effective_cadence_frames` to set adaptive wait windows.
- **F# (`HighBar.Proto`)**: regenerates from `buf` like every other
  field; no hand-written code touches this.
- **C++ (plugin internal)**: the serializer on the plugin side is
  the only writer. Construction happens in
  `src/circuit/grpc/SnapshotTick.cpp` and nowhere else. Readers
  (if any — none expected in-plugin) would go through the generated
  `StateSnapshot::effective_cadence_frames()` accessor.

### Back-compat / client upgrade story

- Clients built against the pre-003 schema that ignore unknown
  fields will continue to work unchanged. `StateSnapshot` they
  receive has a new tail field they don't know about; the proto3
  contract guarantees this is fine.
- Clients built against the post-003 schema but talking to a
  pre-003 plugin will see `effective_cadence_frames = 0` (proto3
  default). The "unknown, assume configured default" escape
  hatch above is the contract for this case.
- Schema version stays `1.0.0` because additive fields are
  backward-compatible within a MINOR release per Constitution III.

---

## Plugin-side config surface (`data/config/grpc.json`)

Add a new top-level object to the existing config file:

```json
{
  "...existing 002 config (uds_path, tcp_port, enable_builtin, ...)": "...",
  "snapshot_tick": {
    "snapshot_cadence_frames": 30,
    "snapshot_max_units": 1000
  }
}
```

### Fields

| Key | Type | Default | Range | On violation |
|---|---|---|---|---|
| `snapshot_tick.snapshot_cadence_frames` | `uint32` | `30` | `[1, 1024]` | Plugin refuses to load; `[hb-gateway] fault reason=cfg_invalid detail=snapshot_cadence_frames=<N>` log line; gateway transitions to `Disabled` before any subscribers connect. |
| `snapshot_tick.snapshot_max_units` | `uint32` | `1000` | `[1, 100000]` | Same as above, with `detail=snapshot_max_units=<N>`. |

### Missing-block behavior

If the entire `snapshot_tick` object is absent from `grpc.json`,
the plugin applies both defaults. This matches the 002 pattern
where `enable_builtin` defaults to `true` if unset.

---

## Scheduler behavior contract

The plugin's `SnapshotTick` scheduler MUST observe the following
invariants:

1. **Call-site discipline.** The scheduler is pumped exclusively
   from `CGrpcGatewayModule::OnFrameTick` on the engine thread. No
   other thread invokes the serializer or the fan-out helper.
   (Constitution II.)

2. **Emission cadence.** While the gateway is `Healthy` and
   `own_units.length <= snapshot_max_units`, snapshots fire
   exactly every `snapshot_cadence_frames` frames (measured against
   `CGrpcGatewayModule::CurrentFrame()`). On fire, the next
   emission is scheduled at `current_frame + effective_cadence_frames`.

3. **Halving on over-cap emissions.** If an emission occurs while
   `own_units.length > snapshot_max_units`, `effective_cadence_frames`
   doubles for the next emission (capped at 1024). The current
   emission's payload carries the pre-double value.

4. **Snap-back on under-cap emissions.** If an emission occurs
   while `own_units.length <= snapshot_max_units` AND
   `effective_cadence_frames > snapshot_cadence_frames`,
   `effective_cadence_frames` resets to `snapshot_cadence_frames`
   immediately (not next frame). The current emission's payload
   carries the pre-reset value; the next emission carries the
   reset value.

5. **Gateway state gating.** While the gateway is `Disabling` or
   `Disabled` (per 002's fault contract), the scheduler does not
   fire. It resumes only after a `Healthy` transition.

6. **Forced emission on `RequestSnapshot`.** If the
   `pending_request` atomic is `true` at the top of `OnFrameTick`,
   the scheduler emits a snapshot this frame (regardless of
   cadence), clears the atomic, and schedules the next periodic
   emission at `current_frame + effective_cadence_frames`. See
   `request-snapshot.md` for the RPC side.

7. **`send_monotonic_ns` stamping.** Every emission's
   `StateUpdate.send_monotonic_ns` is stamped at the moment of
   the serializer's `BroadcastStateUpdate` call (same code path
   002's coordinator uses for delta emissions). This preserves
   Constitution V's measurement method.

---

## Unit-test surface

The scheduler's behavior is unit-testable under a fake frame clock.
`tests/unit/snapshot_tick_test.cc` MUST cover:

- Cadence stability at `snapshot_cadence_frames = 30`,
  `own_units.length = 100`: emit at frames 30, 60, 90, … for 300
  frames. Exactly 10 emissions.
- Halving once: `snapshot_max_units = 50`; at frame 0 simulate
  `own_units.length = 51`. Expect emissions at 30 (cadence 30 →
  60), 90 (cadence 60 → 120), 210 (cadence 120 → 240), 450 …
- Snap-back: continuing from above, drop `own_units.length = 40`
  at frame 460. Expect emission at 690 with
  `effective_cadence_frames = 240`, then next at 720
  (snapped back to 30).
- Forced emission coalescing: flip `pending_request` N times
  between two `OnFrameTick` calls, observe exactly one extra
  emission fires at the first tick after the flips.
- Emission count is **zero** while gateway is `Disabled`.

---

## Acceptance-script surface

`tests/headless/snapshot-tick.sh` (US5 anchor) validates the
wire-side manifestation of this contract:

- Subscribes via `StreamState`.
- Counts `StateUpdate` payloads where `payload.kind = snapshot` in
  a 30-second window.
- Asserts count ≥ 25 (allows slack for startup).
- Asserts max inter-snapshot gap ≤ 2 seconds of wall-clock.
- Asserts `effective_cadence_frames` is populated (non-zero) on
  every snapshot after the first tick.
- Asserts `send_monotonic_ns` is populated (non-zero) on every
  snapshot.

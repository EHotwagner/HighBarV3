# Contract: `UnitDamagedEvent` payload widening

**Addresses**: FR-014, Constitution V (latency measurement method).

## Proto (unchanged — fields already declared)

```proto
// proto/highbar/events.proto lines 86–93
message UnitDamagedEvent {
  int32 unit_id = 1;
  optional int32 attacker_id = 2;
  float damage = 3;
  Vector3 direction = 4;
  int32 weapon_def_id = 5;
  bool is_paralyzer = 6;
}
```

No schema edit; the fields are already at these field numbers. This
contract pins the *engine-to-proto mapping* so the gateway's
serializer is not free to reinterpret.

## Engine → proto field mapping

The CircuitAI `CCircuitAI::UnitDamaged` richer signature is:

```cpp
int CCircuitAI::UnitDamaged(CCircuitUnit* unit,
                            CCircuitUnit* attacker,
                            float damage,
                            springai::AIFloat3 dir,
                            int weaponDefId,
                            bool paralyzer);
```

The gateway populates `UnitDamagedEvent` as:

| Proto field | Source | Notes |
|---|---|---|
| `unit_id` | `unit->GetId()` | Unchanged from 001. |
| `attacker_id` | `attacker->GetId()` if `attacker != nullptr`; otherwise field is unset (optional). | Unchanged from 001. |
| `damage` | `damage` parameter | Clamped to `[0, +inf)`. Negative damage is engine-side malformed; gateway logs a warning and sets field to 0. |
| `direction.x` / `.y` / `.z` | `dir.x` / `dir.y` / `dir.z` | Not renormalized by the gateway. |
| `weapon_def_id` | `weaponDefId` | Passed through verbatim, including `-1` (engine's sentinel for unknown). |
| `is_paralyzer` | `paralyzer` | Passed through verbatim. |

## Flow (engine thread)

```
CCircuitAI::UnitDamaged(unit, attacker, damage, dir, wdefId, paralyzer)
    ├── existing module fanout (builder / military / economy / factory)
    └── CGrpcGatewayModule::OnUnitDamagedFull(unit, attacker,
                                              damage, dir, wdefId, paralyzer)
          └── current_frame_delta_.add_events()->mutable_unit_damaged()
              ├── set_unit_id
              ├── set_attacker_id (if attacker non-null)
              ├── set_damage(clamped)
              ├── mutable_direction()->{set_x,set_y,set_z}
              ├── set_weapon_def_id
              └── set_is_paralyzer
```

`CGrpcGatewayModule::UnitDamaged(unit, attacker)` (the old two-arg
IModule hook) remains present for interface compliance but its body
becomes a no-op: the real work moved to `OnUnitDamagedFull`.

## Test assertions

Every acceptance test in `tests/headless/` that exercises the damage
path must assert non-zero values on at least `damage` and one
component of `direction`. The latency bench
(`tests/bench/latency-uds.sh`, `latency-tcp.sh`) additionally
requires a frame-marker timestamp to be attached to the outgoing
`UnitDamagedEvent` via existing delta-metadata fields (not the
payload itself), which is how the F# client computes the true
round-trip.

## Compatibility

Strictly backward-compatible within `highbar.v1`:

- No field numbers added or changed.
- No field types changed.
- Clients that ignored the zero-valued fields under 001 continue to
  work; clients that read them now see meaningful values.
- `Hello` handshake version string unchanged.

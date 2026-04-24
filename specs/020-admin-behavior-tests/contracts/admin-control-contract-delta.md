# Contract: Admin Control Delta

## Service Surface

Continue using the existing service:

```proto
service HighBarAdmin {
  rpc GetAdminCapabilities(AdminCapabilitiesRequest) returns (AdminCapabilitiesResponse);
  rpc ValidateAdminAction(AdminAction) returns (AdminActionResult);
  rpc ExecuteAdminAction(AdminAction) returns (AdminActionResult);
}
```

## Additive Proto Changes

Add unit ownership transfer to `AdminAction`:

```proto
message UnitTransferAction {
  int32 unit_id = 1;
  int32 from_team_id = 2;
  int32 to_team_id = 3;
  bool preserve_orders = 4;
}

message AdminAction {
  // existing fields unchanged

  oneof action {
    PauseAction pause = 10;
    SpeedAction global_speed = 11;
    CheatPolicyAction cheat_policy = 12;
    ResourceGrantAction resource_grant = 13;
    UnitSpawnAction unit_spawn = 14;
    LifecycleAction lifecycle = 15;
    UnitTransferAction unit_transfer = 16;
  }
}
```

Field number 16 is additive in `highbar.v1`. Existing field numbers and enum values remain unchanged.

## Capability Expectations

`AdminCapabilitiesResponse.supported_actions` uses stable action names:

- `pause`
- `global_speed`
- `resource_grant`
- `unit_spawn`
- `unit_transfer`
- `cheat_policy` when the run mode allows it
- `lifecycle` when enabled for the harness

If implementation adds richer capability metadata, it must remain additive and generated-client-safe. Useful optional fields include valid team ids, resource ids, unit definition ids, map extents, speed min/max, and whether transfer/spawn require cheat-enabled test mode.

## Validation Expectations

`ValidateAdminAction` must reject without mutation when:

- caller role is missing, AI, observer, or unknown
- action is disabled by config or run mode
- `global_speed.speed` is non-finite, <= 0, or above the advertised maximum
- `resource_grant.resource_id`, `team_id`, or `amount` is invalid
- `unit_spawn.unit_def_id`, `team_id`, or `position` is invalid
- `unit_transfer.unit_id`, `from_team_id`, or `to_team_id` is invalid
- `based_on_frame` or `based_on_state_seq` is stale beyond configured limits
- another caller owns the active lease and conflict policy does not allow release

Rejections use structured `AdminIssueCode` values where an existing code fits. If transfer needs a new issue code, add it rather than overloading human-readable `detail`.

## Execution Expectations

`ExecuteAdminAction` returns `ADMIN_ACTION_EXECUTED` only after the action has been accepted for engine-thread application. The behavior suite then verifies the corresponding observable state change.

Required execution effects:

- `pause.paused=true`: frame progression stops within the observation window.
- `pause.paused=false`: frame progression resumes.
- `global_speed`: frame progression rate changes within tolerance.
- `resource_grant`: target team's observed resource balance increases by requested amount within tolerance.
- `unit_spawn`: target team gains a unit of the requested definition near the requested position.
- `unit_transfer`: existing unit remains present and ownership changes to the requested team.

## Lease Expectations

Pause and global speed retain single-owner lease behavior. A conflicting caller without an allowed release policy receives `ADMIN_ACTION_REJECTED_CONFLICT` and the original lease remains effective.

## Compatibility Requirements

Generated C++, C#, and Python stubs must be regenerated after proto changes. Existing Python/F# admin helper calls remain source-compatible for existing actions.

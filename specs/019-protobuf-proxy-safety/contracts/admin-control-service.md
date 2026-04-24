# Contract: Admin Control Service

## Service Surface

Add a sibling service:

```proto
service HighBarAdmin {
  rpc GetAdminCapabilities(AdminCapabilitiesRequest) returns (AdminCapabilitiesResponse);
  rpc ValidateAdminAction(AdminAction) returns (AdminActionResult);
  rpc ExecuteAdminAction(AdminAction) returns (AdminActionResult);
}
```

The admin service uses separate run-scoped credentials from normal AI command submission.

## Admin Actions

`AdminAction` includes:

- `action_seq`
- `client_action_id`
- `based_on_frame`
- `based_on_state_seq`
- `AdminConflictPolicy`
- oneof action for pause, global speed, cheat policy, resource grant, unit spawn, lifecycle/test-harness controls
- reason text where required by policy

Actions in scope:

- pause/unpause
- global simulation speed, min speed, max speed
- cheat enable policy for test actions
- resource grant
- unit spawn
- future lifecycle/test-harness controls

Normal per-unit orders, including per-unit wanted max speed, remain on the AI command surface.

## Authorization

Roles:

- AI: normal command submission and AI-scoped validation.
- Observer: read-only state where allowed.
- Admin/operator: pause, global speed, and operational controls enabled by run config.
- Test harness: cheat and fixture controls only when run mode allows them.

Rejection reasons:

- missing or invalid credential
- role lacks required scope
- admin service disabled
- action disabled by config
- run mode forbids action
- stale basis
- invalid target/team/resource/unit definition
- invalid speed or amount
- conflicting live lease
- engine lifecycle not ready

## Admin Result

`AdminActionResult` includes:

- `action_seq`
- `client_action_id`
- `status`
- `issues[]`
- optional lease state
- `frame`
- `state_seq`
- `dry_run`

Representative issue codes:

- `ADMIN_PERMISSION_DENIED`
- `ADMIN_ACTION_DISABLED`
- `ADMIN_RUN_MODE_FORBIDS_CHEATS`
- `ADMIN_STALE_SNAPSHOT_EPOCH`
- `ADMIN_CONTROL_CONFLICT`
- `ADMIN_INVALID_SPEED`
- `ADMIN_INVALID_SPEED_RANGE`
- `ADMIN_INVALID_RESOURCE`
- `ADMIN_INVALID_AMOUNT`
- `ADMIN_UNKNOWN_UNIT_DEF`
- `ADMIN_POSITION_OUT_OF_MAP`
- `ADMIN_INVALID_TEAM`
- `ADMIN_ENGINE_NOT_READY`
- `ADMIN_ACTION_NOT_DISPATCHED`

## Lease Rules

- Pause and global speed use single-owner leases by default.
- Conflicting admin actions are rejected until explicit release or heartbeat expiry.
- Lease expiry produces an audit event.
- A takeover policy may be added later, but the default strict behavior is reject-if-controlled.

## Audit Event

Every accepted or rejected admin action, explicit release, and lease expiry emits an audit record containing:

- caller credential identity for caller-initiated events
- role
- action type
- frame or state reference
- result
- reason
- lease owner/control where applicable
- run mode

## Acceptance Criteria Mapping

- FR-014 to FR-017: separate authorization, capabilities, validation, lease, and audit model.
- SC-005: normal AI credentials denied privileged actions.
- SC-006: audit record contains enough information to identify caller, action, result, and reason quickly.

# Contract: Admin Behavioral Suite

## Entry Point

Add a stable headless entry point:

```bash
tests/headless/admin-behavioral-control.sh \
  --startscript tests/headless/scripts/admin-behavior.startscript \
  --output-dir build/reports/admin-behavior \
  --timeout-seconds 10 \
  --repeat-index 1
```

The wrapper launches the local live topology, waits for gateway readiness, then invokes the Python admin behavioral driver.

## Exit Codes

- `0`: all required scenarios pass
- `1`: at least one behavioral scenario fails
- `2`: internal harness or report consistency error
- `77`: local runtime prerequisite missing or gateway disabled before scenarios start

## Required Success Scenarios

| Scenario | Request | Required observation |
|---|---|---|
| `pause_match` | operator executes `pause.paused=true` | frame progression stops and result reports success |
| `resume_match` | same caller executes `pause.paused=false` | frame progression resumes and result reports success |
| `set_speed_fast` | operator executes valid `global_speed` | progression rate changes within tolerance |
| `grant_resource` | operator grants known resource to known team | target balance increases within tolerance |
| `spawn_enemy_unit` | operator spawns known enemy unit at valid position | new enemy unit appears near requested position |
| `transfer_unit` | operator transfers existing unit to target team | unit remains present and ownership changes |

## Required Rejection Scenarios

| Scenario | Invalid request | Required observation |
|---|---|---|
| `reject_unauthorized` | AI or observer role executes mutating action | permission rejection and unchanged state |
| `reject_invalid_speed` | speed outside range | invalid-value rejection and speed unchanged |
| `reject_invalid_resource` | unknown resource or invalid amount | invalid-value/target rejection and balance unchanged |
| `reject_invalid_spawn` | unknown unit, invalid team, or off-map position | rejection and no matching unit appears |
| `reject_invalid_transfer` | unknown unit, from-team mismatch, invalid target team, or transfer disabled by run mode | rejection and unit ownership remains unchanged |
| `reject_lease_conflict` | second caller controls leased action without release policy | conflict rejection and original lease remains effective |

## Capability Scenarios

The driver must call `GetAdminCapabilities` before mutating scenarios.

Rules:

- If admin is enabled, all advertised required controls must be executable by an allowed role in the fixture run.
- If admin is disabled or restricted, mutating controls must be absent or rejected consistently.
- The suite fails when a control is advertised but cannot be executed for reasons not documented by capabilities or run mode.

## Observation Rules

- Success observations time out after 10 seconds by default.
- Pause checks compare frame progression over a stable window rather than a single frame read.
- Speed checks compare relative frame progression before and after the speed action with tolerance.
- Resource checks compare team economy before and after the grant.
- Spawn checks compare visible unit inventories and position tolerance.
- Transfer checks prefer ownership delta events; if unavailable, compare ownership in before/after snapshots.
- Rejection checks compare the relevant state before and after the rejected request and fail on mutation.

## Cleanup Rules

The driver must attempt cleanup after each scenario and before exit:

- resume play if paused
- restore normal speed
- release or allow expiry of pause/speed leases
- record cleanup failures in the run summary

Cleanup failure after otherwise passing scenarios is a behavioral failure because repeatability depends on usable post-run state.

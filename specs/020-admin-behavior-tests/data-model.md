# Data Model: Comprehensive Admin Channel Behavioral Control

## AdminCaller

Represents the caller identity and role used for privileged admin decisions.

**Fields**: `client_id`, `role`, `token_identity`, `metadata_source`.

**Validation**: Mutating actions require `operator`, `admin`, or `test-harness` role metadata. Missing, AI, observer, or unknown roles are rejected before mutation.

**Relationships**: Owns or conflicts with `AdminLease` records. Appears in `AdminEvidenceRecord` and audit events.

## AdminAction

Privileged operation requested through `HighBarAdmin`.

**Fields**: `action_seq`, `client_action_id`, `based_on_frame`, `based_on_state_seq`, `conflict_policy`, `reason`, and one action body.

**Action bodies**: `pause`, `global_speed`, `resource_grant`, `unit_spawn`, `unit_transfer`, existing `cheat_policy`, and existing `lifecycle`.

**Validation**: Exactly one action body must be present. Values must be finite and in capability-advertised bounds. Team ids, resource ids, unit definitions, positions, and unit ids must be valid for the current fixture/run. Stale basis and lease conflicts reject before mutation.

## UnitTransferAction

Additive admin action for changing ownership of an existing unit.

**Fields**: `unit_id`, `from_team_id`, `to_team_id`, `preserve_orders`.

**Validation**: `unit_id` must identify a live unit visible to the gateway. `from_team_id` must match current ownership when supplied. `to_team_id` must be a valid opposing or fixture-allowed team. Transfer is rejected when the unit is destroyed, unknown, already owned by the target team without a policy allowing no-op, or the run mode disables ownership changes.

**Observable effect**: The unit remains present and its owner changes to `to_team_id`, represented by a state delta such as `UnitGivenEvent` or by a before/after snapshot ownership view.

## AdminResult

Structured outcome returned by validation or execution.

**Fields**: `action_seq`, `client_action_id`, `status`, `issues[]`, `lease`, `frame`, `state_seq`, `dry_run`.

**Statuses**: Accepted or executed for valid actions; permission denied, disabled, run mode, stale, conflict, invalid target, invalid value, or not dispatched for rejection/failure cases.

**Validation**: Successful execution means the action was accepted for the engine-thread application path. Behavioral success still requires a matching `AdminObservation`.

## AdminCapabilitySet

Discoverable description of admin controls for the current run.

**Fields**: `enabled`, `roles[]`, `supported_actions[]`, `feature_flags[]`, optional `resource_ids[]`, `team_ids[]`, `unit_def_ids[]`, map extents, speed bounds, and run-mode flags if added by implementation.

**Validation**: A mutating control advertised in `supported_actions` must be executable by a valid caller in the same run, or the behavioral suite fails capability matching. Disabled controls must either be absent or rejected consistently with an explanatory issue.

## AdminLease

Single-owner control record for conflict-prone admin controls.

**Fields**: `control`, `owner_client_id`, `owner_role`, `acquired_frame`, `last_heartbeat_frame`, `expires_frame`, `released_frame`, `release_reason`.

**State transitions**: `none -> held` on pause or global speed control acquisition; `held -> refreshed` on heartbeat by the same caller; `held -> released` on release policy; `held -> expired` after heartbeat loss. Conflicting callers are rejected while another caller holds the lease unless the action policy explicitly releases it.

## ObservedMatchState

Before/after state used to prove behavior.

**Fields**: `snapshot_before`, `snapshot_after`, `delta_window[]`, `start_frame`, `end_frame`, `state_seq_start`, `state_seq_end`, `engine_log_path`.

**Validation**: Observations must be captured from the state stream for the same run and action window. Missing stream data within the timeout is a behavioral failure unless startup prerequisites failed before the scenario began.

## AdminObservation

Action-specific expected and actual match-state comparison.

**Fields**: `action_name`, `expected_kind`, `expected_value`, `actual_value`, `tolerance`, `deadline_seconds`, `observed`, `failure_reason`.

**Expected kinds**: frame stopped, frame advanced, speed multiplier reflected in progression, resource balance increased, unit spawned near position, unit owner changed, state unchanged for rejections, capabilities matched execution.

**Validation**: Accepted mutating actions require `observed=true` within 10 seconds. Rejected actions require unchanged relevant state. Speed and position comparisons use tolerance windows.

## AdminBehaviorScenario

One executable test case in the admin behavioral suite.

**Fields**: `scenario_id`, `priority`, `action_name`, `caller`, `action`, `preconditions`, `expected_result`, `expected_observation`, `cleanup_actions`, `capability_requirement`.

**Validation**: Preconditions must be checked before action dispatch. If a prerequisite is missing, the scenario records a prerequisite failure rather than a behavioral failure. Cleanup runs after each scenario where possible.

## AdminEvidenceRecord

Reviewable per-action evidence artifact.

**Fields**: `scenario_id`, `request`, `caller`, `capability_snapshot`, `result_status`, `issues[]`, `expected_observation`, `actual_observation`, `pass`, `diagnostics`, `log_location`.

**Validation**: Failed records must include action name, expected observation, actual observation, and log location. Passing records must include enough before/after data to audit the state transition.

## AdminBehaviorRun

Aggregate result for one suite invocation.

**Fields**: `run_id`, `fixture_id`, `repeat_index`, `started_at`, `completed_at`, `prerequisite_status`, `capabilities`, `records[]`, `cleanup_status`, `exit_code`, `report_path`.

**Exit classification**: `0` for all required behavior passing; `1` for behavioral regression; `2` for internal harness error; `77` for missing local runtime prerequisites.

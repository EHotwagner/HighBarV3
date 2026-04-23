# Contract: BNV Watch Launch

## Purpose

Define how a compatible live run requests, validates, and launches BAR Native Game Viewer in a non-controlling spectator context.

## Requirements

1. Watch mode must be enabled through one explicit launch option plus an optional structured profile reference for detailed settings.
2. The default watch profile must launch BNV windowed at `1920x1080` with mouse capture disabled.
3. BNV readiness must be validated before live execution starts for a requested watched run.
4. If requested watch launch cannot be made ready or cannot be launched, the run request must fail before or at launch with a user-readable reason.
5. Launch behavior must remain spectator-only and must not grant control over the live run.

## Required preflight checks

| Check | Failure outcome |
|-------|-----------------|
| Profile parses and resolves | `profile_invalid` with user-readable reason |
| BNV executable resolves | `bnv_missing` with executable path detail |
| Host prerequisites are present | `environment_unready` with missing prerequisite detail |
| Target run is compatible with live viewing | `run_incompatible` with run-mode or lifecycle detail |
| Run selection is unambiguous | `selection_failed` when attach-later context is ambiguous |

## Launch invariants

1. A watched run must retain the same `run_id` and `campaign_id` regardless of BNV launch.
2. The launch command may be recorded for diagnosis, but the persisted state must remain readable without replaying shell history.
3. Non-watch runs must continue to use the existing live launch path with no additional required steps.
4. Post-launch viewer disconnect must be represented as a lifecycle transition, not as hidden control over gameplay.

## Prohibited shortcuts

1. No watch request may silently degrade to a non-watch run after the maintainer explicitly requested BNV launch.
2. No profile may enable controlling input or other non-spectator behavior.
3. No shell-only watch logic may become the sole implementation seam for launch policy.

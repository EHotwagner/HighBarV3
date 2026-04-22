# Contract: Dispatch Target Invariant

**Feature**: [Command Contract Hardening](../plan.md)

## Purpose

Define the authoritative target-unit rules for `CommandBatch` so validation, queueing, and engine-thread dispatch all agree on which unit a command is for.

## Invariant

1. `CommandBatch.target_unit_id` is the authoritative batch target for every unit-bound command in the batch.
2. Commands on different units must be sent in separate batches.
3. If a unit-bound command carries its own `unit_id`, it must either match `target_unit_id` exactly or be rejected as `target_drift`.
4. Queue entries and engine-thread drain must dispatch the normalized authoritative target accepted by validation, not a later best-effort reinterpretation.

## Required Behaviors

- Validation rejects the whole batch on the first detected target mismatch.
- Rejection reason is explicit enough for maintainers to identify the command and the conflicting unit ids.
- Successful acceptance guarantees that dispatch will not silently select another unit.
- Game-wide commands that do not bind to a unit remain exempt, but that exemption must be explicit and documented in the dispatcher.

## Non-Goals

- This contract does not introduce a new wire schema.
- This contract does not allow heterogeneous multi-unit batches as an optimization path.

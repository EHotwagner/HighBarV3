# Contract: Authoritative Fixture Model

**Feature**: [Fixture Bootstrap Simplification](../plan.md)

## Purpose

Define the single authoritative command-to-fixture dependency source for live Itertesting and eliminate duplicate simplified-bootstrap blocker rules.

## Authoritative Sources

The fixture model for 014 is derived from:

- `DEFAULT_LIVE_FIXTURE_CLASS_BY_COMMAND` in `clients/python/highbar_client/behavioral_coverage/bootstrap.py`
- `DEFAULT_LIVE_FIXTURE_CLASSES`
- `OPTIONAL_LIVE_FIXTURE_CLASSES`
- The derived `LiveFixtureProfile` and command-specific dependency records

## Required Behaviors

1. Every direct `channel_a_command` must resolve its fixture requirements from the authoritative dependency map.
2. The live bootstrap and Itertesting report layers must use the same dependency source.
3. `_SIMPLIFIED_BOOTSTRAP_TARGET_MISSING_ARMS` or any equivalent second blocker list must not remain the deciding source for fixture-blocked outcomes.
4. The six currently missing classes in scope for provisioning expansion are `transport_unit`, `payload_unit`, `capturable_target`, `restore_target`, `wreck_target`, and `custom_target`.
5. Existing classes such as `commander`, `builder`, `hostile_target`, `movement_lane`, `resource_baseline`, `cloakable`, `damaged_friendly`, and `reclaim_target` must continue to be represented through the same model rather than special-case report logic.

## Review Expectations

- Maintainers can inspect one dependency source to learn why a command needs a given fixture class.
- The report bundle never needs a second hard-coded exception path to explain a fixture blocker.
- Removing or adding a dependency for a command changes both bootstrap behavior and report interpretation together.

## Non-Goals

- This contract does not require external proto changes.
- This contract does not require every optional class to be provisioned in every run.

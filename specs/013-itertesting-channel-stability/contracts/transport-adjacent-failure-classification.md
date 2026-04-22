# Contract: Transport-Adjacent Failure Classification

**Feature**: [Itertesting Channel Stability](../plan.md)

## Purpose

Define how the live workflow separates transport interruptions, missing fixtures, ambiguous evidence, and clean command-behavior failures.

## Allowed Primary Causes

| Cause | Meaning |
|-------|---------|
| `transport_interruption` | The session became unhealthy enough that the command outcome cannot be treated as a clean behavior verdict. |
| `missing_fixture` | Required fixture classes were absent for the command. |
| `predicate_or_evidence_gap` | The command ran, but the live evidence window or predicate remained ambiguous. |
| `behavioral_failure` | The session was stable, required fixtures were present, and the command still failed to produce the expected effect. |

## Precedence Rules

1. When `channel_health.status != healthy`, classify a row as `transport_interruption` if the row carries a channel-failure signal or if the row is not already explained by a required missing fixture.
2. Otherwise classify the row as `missing_fixture` when the command is listed in `affected_command_ids` or its required fixture classes are absent from `provisioned_fixture_classes`.
3. Otherwise classify `predicate_or_evidence_gap` for inconclusive rows or rows whose verification rule explicitly falls back to evidence ambiguity.
4. Use `behavioral_failure` only when the session was stable enough and the command had the required fixture surface.

## Required Behaviors

1. `manifest.json` must serialize one classification entry for every unverified direct command.
2. `run-report.md` must render a `## Failure Cause Summary` section from those classifications.
3. Transport-adjacent outcomes must remain distinct from clean regressions across repeated reruns.
4. Changing simulation speed for a rerun must not change the interpretation when the same lifecycle signal or fixture gap still explains the failure.
5. Commands intentionally exempt from durable-effect expectations must not be promoted into misleading transport or inert-dispatch claims unless the session itself actually failed.

## Review Expectations

- `cmd-build-unit` should be treated as a clean behavior regression only when the session stayed healthy and the required builder/resource fixture classes were present.
- A command that was interrupted mid-session must not silently appear in reviewer summaries as if it were a pure semantic failure.
- Missing-fixture and transport-interruption counts in the run summary must match the per-command classification entries.

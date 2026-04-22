# Contract: Fixture Provisioning And Blockers

**Feature**: [Itertesting Channel Stability](../plan.md)

## Purpose

Define how the live workflow records fixture coverage and how missing fixtures block command interpretation before behavior is judged.

## Authoritative Sources

The fixture surface for 013 is derived from:

- `DEFAULT_LIVE_FIXTURE_CLASS_BY_COMMAND` in `clients/python/highbar_client/behavioral_coverage/bootstrap.py`
- `DEFAULT_LIVE_FIXTURE_CLASSES`
- `OPTIONAL_LIVE_FIXTURE_CLASSES`
- The derived `LiveFixtureProfile` and `FixtureProvisioningResult`

## Required Record Shape

### `fixture_profile`

| Field | Meaning |
|-------|---------|
| `profile_id` | Stable fixture profile identifier. |
| `fixture_classes` | Baseline classes expected for the live run. |
| `supported_command_ids` | Direct command rows supported by the profile. |
| `optional_fixture_classes` | Specialized classes whose absence blocks subsets of commands. |
| `provisioning_budget_seconds` | Budgeted time for fixture preparation. |
| `fallback_behavior` | How the workflow behaves when classes remain missing. |

### `fixture_provisioning`

| Field | Meaning |
|-------|---------|
| `run_id` | Parent run id. |
| `profile_id` | Active fixture profile id. |
| `provisioned_fixture_classes` | Classes actually present. |
| `missing_fixture_classes` | Classes that were still absent. |
| `affected_command_ids` | Commands blocked by the missing classes. |
| `completed_at` | Completion time for the provisioning evaluation. |

## Required Behaviors

1. Every live-closeout run must record both the planned fixture profile and the actual provisioning result.
2. `run-report.md` must render a `## Fixture Provisioning` section that exposes both provisioned and missing classes.
3. A command that requires a missing fixture class must be classified as fixture-blocked before the workflow blames command behavior.
4. The fixture result must name the affected command ids so maintainers can tell which commands were never in a valid setup state.
5. `cmd-build-unit` and other specialized-fixture commands must remain explicitly blocked until the required classes are present or until independent evidence proves the blocker is transport-related instead.

## Non-Goals

- This contract does not require all optional fixtures to be present in every run.
- This contract does not require cheat-backed provisioning to hide genuine setup gaps.
- This contract does not reinterpret a healthy verified command as fixture-blocked just because the broader profile had unrelated missing classes.

# Contract: Fixture Blocker Classification And Reporting

**Feature**: [Fixture Bootstrap Simplification](../plan.md)

## Purpose

Define how the authoritative fixture provisioning result drives per-command blocker classification and reviewer-facing reporting.

## Precedence Rules

1. When `channel_health.status != healthy`, classify a command as `transport_interruption` if the session became unhealthy and the command is not already explained by a currently missing or unusable required fixture class.
2. Otherwise classify the command as `missing_fixture` when any required fixture class is `missing` or `unusable` for that run.
3. Otherwise classify `predicate_or_evidence_gap` for inconclusive rows whose setup was valid but evidence remained ambiguous.
4. Use `behavioral_failure` only when the session stayed healthy enough and all required fixture classes were usable.

## Required Behaviors

1. Only commands named by the authoritative provisioning result may be reported as fixture-blocked.
2. The report bundle must expose the missing class names and the affected command ids.
3. The phrase or concept of "simplified bootstrap blocker" must not be the final reviewer-facing explanation once authoritative provisioning is available.
4. Commands newly unblocked by richer fixture provisioning must be evaluated on live evidence instead of remaining automatically blocked by legacy setup exceptions.
5. Commands that still lack a valid class must remain explicitly fixture-blocked rather than being mislabeled as transport failures or generic regressions.

## Output Expectations

- `manifest.json` serializes the class-level fixture status plus aggregate fixture blocker lists.
- `run-report.md` renders fixture provisioning detail and the failure-cause summary from the same underlying provisioning result.
- `campaign-stop-decision.json` continues to block ordinary Itertesting tuning while missing or unusable classes still gate intended coverage commands.

## Review Expectations

- A maintainer can tell which class blocked `cmd-load-units`, `cmd-capture`, `cmd-restore-area`, `cmd-resurrect`, or `cmd-custom` from the bundle alone.
- A command no longer remains blocked solely because it appears on an obsolete blocklist after the required class is actually usable.

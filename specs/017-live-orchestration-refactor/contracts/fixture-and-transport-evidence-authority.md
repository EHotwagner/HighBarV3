# Contract: Fixture And Transport Evidence Authority

## Purpose

Define how fixture and transport availability are derived from explicit evidence so the final bundle never claims more than the run actually proved.

## Requirements

1. Final fixture availability must be derived from explicit state transitions plus explicit run-mode policy; absence of evidence may not be treated as proof of provisioning.
2. When fixture evidence changes during a run, the latest explicit state is authoritative for final availability while earlier states remain preserved as diagnostic history.
3. A live run that records bootstrap metadata but never reaches command-row or transport evidence must report transport availability as `unknown` or `unproven` unless explicit transport evidence exists.
4. Synthetic and skipped-live modes must report fixture and transport results as mode-qualified non-live outcomes where appropriate and must not be counted as established live evidence.
5. Failure classification and affected-command summaries must consume these authoritative fixture and transport decisions rather than applying separate hidden inference rules later in the bundle pipeline.

## Authoritative transition model

| Concern | Required authority |
|---------|--------------------|
| Fixture final status | Latest explicit `FixtureStateTransition` for the class plus run-mode policy |
| Fixture history | Complete ordered transition list preserved in diagnostics |
| Transport status | Explicit transport evidence when present, otherwise explicit `unknown`, `unproven`, or `mode_qualified_non_live` |
| Affected commands | Derived from the authoritative final state, not broad generic fallback lists |

## Prohibited shortcuts

1. No report section may upgrade a fixture to `provisioned` only because no contradictory row was found.
2. No transport summary may claim live availability only because the run mode is synthetic or skipped-live.
3. No later rendering step may rewrite authoritative final state with a presentation-only heuristic.

## Expected outcomes

- Bootstrap-blocked or partially observed live runs produce internally consistent fixture and transport summaries.
- Maintainers can distinguish missing evidence from explicit invalidation or explicit baseline guarantees.
- Transport remains a trustworthy diagnostic category instead of a side effect of whichever layer happened to inspect the rows last.

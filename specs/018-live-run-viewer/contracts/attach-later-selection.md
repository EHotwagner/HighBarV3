# Contract: Attach-Later Selection

## Purpose

Define how a maintainer attaches BNV to an already active run without ambiguity.

## Requirements

1. Attach-later requests must accept an explicit run reference.
2. If no run reference is provided, the system may auto-select only when exactly one compatible active watchable run exists.
3. When multiple compatible active runs exist, the system must refuse auto-selection and require explicit run choice.
4. Selection must be driven by filesystem-backed active watch state, not hidden process-local memory.
5. Attach-later results must preserve the same watch profile and spectator-only constraints as launch-time watch mode.

## Selection rules

| Context | Required behavior |
|---------|-------------------|
| Explicit run id provided | Resolve that run or return a run-specific unavailability reason |
| No run id, exactly one compatible active run | Auto-select that run |
| No run id, multiple compatible active runs | Return ambiguity and require explicit selection |
| No run id, zero compatible active runs | Return explicit unavailability reason |

## Active index invariants

1. The active watch index must contain enough run context for a maintainer to distinguish candidates.
2. Expired or completed runs must not remain eligible for auto-selection.
3. The index must survive separate command invocations within the same reports directory.

## Prohibited shortcuts

1. “Latest run wins” is not an allowed selection rule when multiple compatible active runs exist.
2. Attach-later may not infer run identity from only PID ordering or filesystem timestamps when explicit run records are available.
3. Ambiguous attach requests may not launch BNV against a guessed target.

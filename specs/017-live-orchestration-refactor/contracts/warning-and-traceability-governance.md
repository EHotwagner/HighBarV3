# Contract: Warning And Traceability Governance

## Purpose

Define how the refactored workflow preserves unhandled metadata, exposes interpretation gaps, and lets maintainers trace final decisions back to the responsible layer.

## Requirements

1. A metadata record collected without a defined interpretation rule must be preserved in the manifest and surfaced as a maintainer-visible warning.
2. An unhandled or partially handled metadata record that affects bundle meaning must block the run from being classified as fully interpreted or successful.
3. The bundle must expose enough traceability for maintainers to tell whether a major decision came from the execution layer, metadata collection, or interpretation logic.
4. Traceability must remain available for bootstrap readiness, fixture availability, transport availability, blocker classification, and interpretation warnings.
5. Report rendering may summarize traceability, but the underlying manifest must retain the authoritative trace information.

## Required bundle concepts

| Concept | Required behavior |
|---------|-------------------|
| `interpretation_warnings` | Lists preserved but not fully interpreted metadata and whether each warning blocks success |
| `decision_trace` | Maps major decisions to source layer, record type, and interpretation rule |
| `fully_interpreted` | False whenever blocking warnings remain |

## Review outcomes

1. Maintainers can inspect a representative failure bundle and identify the responsible layer without reverse-engineering oversized orchestration modules.
2. New metadata additions fail loudly but diagnostically when interpretation support is incomplete.
3. Success classification remains trustworthy because preserved-but-uninterpreted evidence cannot silently coexist with a clean success state.

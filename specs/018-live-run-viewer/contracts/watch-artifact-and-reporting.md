# Contract: Watch Artifact And Reporting

## Purpose

Define the maintainer-visible watch state that must be persisted in the existing Itertesting bundle and surfaced through stdout/reporting.

## Requirements

1. The run bundle must record whether watch mode was requested, which profile was used, and whether BNV access became available.
2. User-facing output must render explicit reasons for unavailability, expiration, ambiguity, or readiness failure.
3. The existing `manifest.json` and `run-report.md` files remain the authoritative durable artifacts for completed runs.
4. An active watch index may exist for attach-later discovery, but it does not replace the run bundle as the durable source of truth.
5. Watch reporting must never imply that BNV interaction can control the live run.

## Required persisted concepts

| Concept | Required behavior |
|---------|-------------------|
| `watch_requested` | Records whether the maintainer requested watch mode |
| `watch_profile` | Identifies the chosen profile and resolved defaults |
| `preflight_result` | Stores launch-readiness status and user-readable reason |
| `viewer_access` | Stores availability state, reason, and key timestamps |
| `selection_mode` | Distinguishes explicit selection from single-run auto-selection |

## Rendering expectations

1. Stdout must surface watch request state and any failure reason alongside the existing run/campaign summary.
2. `run-report.md` must contain a dedicated watch-status section.
3. Manifest fields and report wording must agree on the same lifecycle state and reason.
4. Expired or disconnected viewer access must remain visible for diagnosis after the run completes.

## Prohibited shortcuts

1. No watch failure reason may exist only in logs while the manifest/report remain silent.
2. No report section may describe viewer access as “available” when the active index or manifest has already expired it.
3. No artifact may omit the distinction between readiness failure before launch and disconnect after launch.

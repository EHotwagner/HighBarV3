# Phase 0 Research — Live Bootstrap Hardening

**Branch**: `016-live-bootstrap-hardening` | **Date**: 2026-04-23  
**Plan**: [plan.md](./plan.md)

## Decision 1: Treat resource starvation as an explicit bootstrap-readiness outcome and support an explicit seeded-readiness path

**Decision**: Prepared live closeout should classify an obviously starved start state before the first commander-built bootstrap step and pair that with a maintainer-visible seeded-readiness path when the standard prepared scenario cannot naturally supply viable opening resources.

**Rationale**:

- The failing run `itertesting-20260423T024247Z` already showed the real defect: bootstrap reached `factory_ground/armvp` with `economy=metal:0.1/0.0/1500.0` and later `economy=metal:0.0/0.0/1450.0`, which is not a realistic opening state for natural commander progression.
- The existing Python workflow already contains `_economy_obviously_starved()` and raises a `resource_starved` runtime error before commander-built steps when the start snapshot has almost no metal and no metal income.
- A seeded-readiness path is safer than hiding the problem behind runtime cheats or late fallback logic because it keeps the deviation explicit at the maintainer workflow boundary and does not change the command-verification model itself.

**Alternatives considered**:

- Keep the current natural-only assumption and merely improve reporting.
  Rejected because it leaves the workflow unable to make forward progress in the known prepared scenario and still burns the maintainer’s failure budget on a misleading timeout.
- Inject ad-hoc economy or unit state from inside the live bootstrap code.
  Rejected because it would blur the line between workflow preparation and behavior verification, making run-bundle interpretation less trustworthy.
- Defer all readiness handling to a later transport-only fallback path.
  Rejected because the first hard blocker happens before transport provisioning begins.

## Decision 2: Preserve callback-derived diagnostics early and treat late refresh as best-effort

**Decision**: The workflow should capture the essential callback-derived diagnostics near bootstrap start, preserve them in the run bundle, and only attempt later refresh opportunistically.

**Rationale**:

- The April 23, 2026 failure proved that callback reachability can disappear while bootstrap is still failing, with `StatusCode.UNAVAILABLE` against `unix:/tmp/hb-run-itertesting/attempt-1/highbar-1.sock`.
- The current bootstrap code already emits commander-focused callback diagnostics through `_commander_build_context_debug()` and includes the degraded callback error in the failure detail.
- Preserving an early snapshot is more reliable than requiring the relay endpoint to stay alive for the full duration of every failure path. It also produces a deterministic review surface in `run-report.md` and `manifest.json`.

**Alternatives considered**:

- Require the callback relay endpoint to stay alive for the entire closeout window and treat any loss as a hard feature failure.
  Rejected because relay lifetime is partly an environment concern and makes maintainers lose already-available evidence when the late path degrades.
- Ignore late callback failures and rely only on bootstrap timeout strings.
  Rejected because that collapses resource, capability, and relay failures into one ambiguous message.
- Write callback diagnostics to a separate temporary shell log outside the run bundle.
  Rejected because the Itertesting bundle is already the authoritative maintainer review surface.

## Decision 3: Reuse the existing callback-based def-resolution helper as the single prerequisite-resolution model

**Decision**: Both prepared live closeout and `tests/headless/behavioral-build.sh` should use the existing `_resolve_live_def_ids()` callback path and a shared resolution trace model rather than manual environment overrides or hardcoded ids.

**Rationale**:

- The Python client already resolves runtime def names through `CALLBACK_GET_UNIT_DEFS` plus `CALLBACK_UNITDEF_GET_NAME`, and 015 already records transport resolution through a structured trace.
- The standalone build probe still exits `77` on April 23, 2026 because it expects `HIGHBAR_ARMMEX_DEF_ID`, which makes it diverge from the main live workflow.
- Sharing one resolution path reduces drift, eliminates stale per-engine def-id setup, and gives maintainers one place to inspect whether runtime prerequisite resolution succeeded or failed.

**Alternatives considered**:

- Keep `HIGHBAR_ARMMEX_DEF_ID` as the normal path and treat runtime resolution as optional.
  Rejected because it preserves the exact mismatch this feature is meant to remove.
- Hardcode Armada def ids for the pinned engine/mod pair.
  Rejected because the repo already documents def-id churn across BAR versions and the plan explicitly avoids reviving that maintenance burden.
- Add a new proto or callback just for the build probe.
  Rejected because the current callback contract already supports bulk def lookup and name resolution.

## Decision 4: Extend the existing run bundle instead of introducing a separate diagnostics artifact

**Decision**: Bootstrap readiness, callback-diagnostic retention, and prerequisite-resolution status should all land in the existing Itertesting manifest/report surface.

**Rationale**:

- `tests/headless/itertesting.sh` and `tests/headless/README.md` already treat `manifest.json`, `run-report.md`, and `campaign-stop-decision.json` as the authoritative maintainer outputs.
- The current run bundle already includes fixture provisioning, transport provisioning, channel health, and failure-cause summaries. Extending that structure keeps review localized to one evidence set.
- A bundle-first design also makes it easier to align headless validation, reporting tests, and terminal summaries without inventing another workflow-specific output format.

**Alternatives considered**:

- Emit bootstrap-readiness and callback-retention data only to stderr.
  Rejected because shell-only output is hard to compare across runs and easy to lose in long live sessions.
- Add a new ad-hoc JSON file just for bootstrap hardening.
  Rejected because it would fragment maintainer review and duplicate the existing report model.
- Restrict the extra state to the standalone build probe only.
  Rejected because the main workflow is where the authoritative failure evidence is produced.

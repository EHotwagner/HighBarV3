# Phase 0 Research — Live Bootstrap Hardening

**Branch**: `016-live-bootstrap-hardening` | **Date**: 2026-04-23  
**Plan**: [plan.md](./plan.md)

## Decision 1: Keep bootstrap readiness as an explicit first-class outcome

**Decision**: Prepared live closeout should continue to classify an obviously starved start state before the first commander-built bootstrap step and should keep any non-natural readiness path explicit in the run bundle.

**Rationale**:

- The failing prepared live run already showed the root problem: bootstrap reached `factory_ground/armvp` with effectively no usable metal income, which is not a viable opening state for natural commander progression.
- The existing behavioral-coverage code already has `_economy_obviously_starved()` and `_assess_bootstrap_readiness()`, so the correct fix surface is to preserve and sharpen that readiness classification rather than defer it behind later build timeouts.
- Making a seeded or otherwise non-natural readiness path explicit preserves maintainer trust in the closeout evidence.

**Alternatives considered**:

- Keep the natural-only assumption and only improve wording around downstream timeouts.
  Rejected because it leaves the known prepared scenario fundamentally ambiguous.
- Hide readiness handling inside later bootstrap fallback logic.
  Rejected because the first defect occurs before downstream provisioning becomes meaningful.

## Decision 2: Model the live runtime as callback-limited, not callback-broken

**Decision**: The workflow should record a runtime capability profile and treat unsupported callbacks as an expected capability limit on this host rather than as generic relay or workflow failure.

**Rationale**:

- The April 23, 2026 probe showed that only `CALLBACK_GET_UNIT_DEFS (47)` and `CALLBACK_UNITDEF_GET_NAME (40)` succeed on the observed runtime. `47` returned 581 unit defs, and `40(149)` resolved to `armmex`.
- The same probe showed that `CALLBACK_UNIT_GET_DEF (23)`, `CALLBACK_UNITDEF_GET_BUILD_OPTIONS (42)`, all economy callbacks, all map callbacks, and the team/mod/cheat/datadir/info groups are explicitly unsupported.
- Treating those outcomes as capability limits gives maintainers a coherent explanation for why prerequisite lookup still works while deeper commander/build-option diagnostics do not.

**Alternatives considered**:

- Continue treating late commander/build-option failures as relay instability.
  Rejected because the probe shows those specific callbacks are unavailable even while the relay can still resolve unit definitions by name.
- Assume all runtimes expose the full callback enum and keep retrying unsupported groups.
  Rejected because it wastes failure budget and obscures the real host capability boundary.

## Decision 3: Use the session-start map payload as the authoritative map source on callback-limited hosts

**Decision**: When callback-based map inspection is unsupported but `HelloResponse.static_map` is present, the workflow should use that session-start map payload as the authoritative source for metal-spot targeting and map-derived diagnostics.

**Rationale**:

- The same runtime that rejects `CALLBACK_MAP_GET_METAL_SPOTS` still exposes metal spots through `HelloResponse.static_map`.
- `tests/headless/behavioral-build.sh` already consumes `static_map` and chooses a nearby metal spot from that payload.
- Using the session-start map payload avoids false “map unavailable” diagnoses when the data is already available through the supported handshake path.

**Alternatives considered**:

- Require callback-based map inspection for any map-derived targeting.
  Rejected because it would block behavior that the current runtime already supports through the hello path.
- Fall back to hardcoded or guessed build positions when callback map inspection fails.
  Rejected because the project already has a richer authoritative map source on the same session.

## Decision 4: Constrain runtime prerequisite resolution to the proven `47`/`40` path

**Decision**: Both prepared live closeout and `tests/headless/behavioral-build.sh` should keep using the shared runtime prerequisite-resolution helper, but the contract should now explicitly define that helper as the `CALLBACK_GET_UNIT_DEFS` plus `CALLBACK_UNITDEF_GET_NAME` path.

**Rationale**:

- The existing `_resolve_live_def_ids()` helper already resolves runtime def names through that exact pair of callbacks.
- The standalone build probe already uses the same path to resolve `armmex`, which means the main workflow and the probe can stay aligned without manual def-id injection.
- Narrowing the contract to the proven path avoids accidental dependence on commander/build-option callbacks that the live host does not support.

**Alternatives considered**:

- Reintroduce a manual `HIGHBAR_ARMMEX_DEF_ID` setup path as the default.
  Rejected because it recreates the drift this feature is explicitly trying to remove.
- Expand prerequisite resolution to include commander/build-option callbacks for additional verification.
  Rejected because those callbacks are unsupported on the observed runtime and do not help identity resolution.

## Decision 5: Keep capability-aware reporting inside the existing Itertesting bundle

**Decision**: Bootstrap readiness, runtime capability limits, prerequisite-resolution evidence, map-source selection, and standalone probe parity should all remain inside the existing Itertesting manifest/report surface.

**Rationale**:

- `tests/headless/itertesting.sh` and the report renderer already treat `manifest.json`, `run-report.md`, and `campaign-stop-decision.json` as the maintainer review surface.
- Keeping all of this evidence in one bundle makes it easier to distinguish unsupported callbacks, transport loss, missing session-start data, and actual command-behavior failures.
- The feature does not need a parallel ad-hoc diagnostics artifact to be reviewable.

**Alternatives considered**:

- Emit callback capability results only to shell output.
  Rejected because it makes cross-run comparison and report review weaker.
- Add a separate JSON artifact just for callback support scanning.
  Rejected because the maintainer workflow already has an authoritative bundle and report path.

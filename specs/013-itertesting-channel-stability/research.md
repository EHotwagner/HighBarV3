# Phase 0 Research — Itertesting Channel Stability

**Branch**: `013-itertesting-channel-stability` | **Date**: 2026-04-22  
**Plan**: [plan.md](./plan.md) | **Spec**: [spec.md](./spec.md)

The repository already contains the live Itertesting wrapper, run-manifest/report model, fixture-profile helpers, and transport-aware failure classification seams. The planning problem for 013 is not inventing a new workflow; it is deciding which existing surfaces become the authoritative closeout truth when a live session collapses, when fixture coverage is partial, and when commands such as `cmd-build-unit` sit near the boundary between transport instability and true behavior regression.

---

## 1. Live closeout entrypoint

**Decision**: Use `tests/headless/itertesting.sh` and the existing Python `itertesting` CLI as the only authoritative live closeout surface for 013.

**Rationale**: The wrapper already owns coordinator startup, live/synthetic selection, retrying a fresh live topology after an early degraded session, and surfacing the latest manifest and stop-decision artifacts. Adding a second closeout runner would create another source of truth while the real problem remains lifecycle continuity and evidence interpretation inside the current workflow.

**Alternatives considered**:

- Add a new one-shot live closeout wrapper: rejected. The existing wrapper already exposes the required control points and artifact paths.
- Treat only the Python CLI as authoritative: rejected. Maintainers use the shell wrapper to start the full live topology, not just the reporting layer.
- Treat raw coordinator and engine logs as the primary interface: rejected. Logs are supporting evidence; the manifest/report bundle is the maintainer contract.

---

## 2. Canonical evidence surfaces

**Decision**: Treat `manifest.json`, `run-report.md`, and `campaign-stop-decision.json` under `reports/itertesting/<run-id>/` as the canonical 013 evidence bundle, with `channel_health`, `fixture_provisioning`, `failure_classifications`, and `contract_health_decision` as the fields that control interpretation.

**Rationale**: Those surfaces already exist, are rendered by the current reporting code, and are consumed by the wrapper when it decides whether to stop or retry. 013 needs stable reviewer-facing evidence, not a sidecar diagnostics format.

**Alternatives considered**:

- Add a separate channel-stability summary artifact: rejected. That would duplicate information already present in the run bundle.
- Rely on shell stdout for blocker interpretation: rejected. Closeout decisions need machine-readable state.
- Expand the proto surface to report more lifecycle detail: rejected. This is an internal workflow problem, not a new client contract.

---

## 3. Channel lifecycle truth model

**Decision**: Use `ChannelHealthOutcome` as the minimum lifecycle record for live-session trustworthiness, with `status`, `first_failure_stage`, `failure_signal`, and `commands_attempted_before_failure` treated as required review fields.

**Rationale**: The spec requires maintainers to know what disconnected and when. The current type already captures exactly that without forcing a protocol change. It is also the field the wrapper can inspect to decide whether a live session degraded before meaningful direct coverage was achieved.

**Alternatives considered**:

- Infer lifecycle health only from coordinator logs: rejected. Useful for diagnosis, but too indirect for the closeout contract.
- Add per-batch lifecycle events as a new artifact family: rejected. Over-specified for the current evidence need.
- Reduce lifecycle reporting to a single interrupted/healthy flag: rejected. The feature needs the first failure point, not just a boolean.

---

## 4. Fixture coverage authority

**Decision**: Use `bootstrap.py` as the authoritative fixture map for 013, specifically `DEFAULT_LIVE_FIXTURE_CLASS_BY_COMMAND`, `DEFAULT_LIVE_FIXTURE_CLASSES`, `OPTIONAL_LIVE_FIXTURE_CLASSES`, and the derived `LiveFixtureProfile` / `FixtureProvisioningResult`.

**Rationale**: The repository already encodes which commands need which fixture classes, and `live_failure_classification.py` already derives affected commands from missing fixtures. Re-declaring that mapping in a second document or wrapper would guarantee drift.

**Alternatives considered**:

- Hand-maintain a second fixture matrix in shell scripts: rejected. The Python model already drives classification and reporting.
- Treat all non-default fixtures as generic setup noise: rejected. 013 explicitly needs fixture-blocked outcomes to be distinct and reviewable.
- Force cheat-backed provisioning for all specialized commands: rejected. The feature is about trustworthy interpretation, not masking missing setup.

---

## 5. Failure-classification precedence

**Decision**: Preserve the current precedence model in `classify_failure_cause`: classify a row as `transport_interruption` when the session is unhealthy and the row is not already explained by a required missing fixture, classify `missing_fixture` for rows impacted by the fixture profile, then fall back to predicate/evidence gaps or behavioral failure.

**Rationale**: This precedence matches the feature’s intent. Transport collapse should not be misread as a clean regression, but commands that are clearly missing required targets or unit classes should still be marked as fixture-blocked instead of being hidden inside a generic transport bucket.

**Alternatives considered**:

- Always let transport interruption override fixture blockers: rejected. That would erase useful setup information for commands whose prerequisites were never present.
- Always classify missing fixtures before channel health: rejected. That would mislabel commands that were already beyond their fixture dependency surface when the channel collapsed.
- Collapse predicate/evidence gaps into behavioral failure: rejected. The repo already distinguishes ambiguous verification from true behavioral regressions.

---

## 6. Closeout readiness gate

**Decision**: Define 013 readiness as a stable live session plus trustworthy evidence, not merely a passing shell exit code. The prepared-environment gate is three consecutive live reruns without dispatch-time channel disconnect, with missing fixtures and transport-adjacent rows remaining explicit blockers rather than acceptable noise.

**Rationale**: The spec’s success criteria are about repeated live reliability and interpretability. A single green-ish run with ambiguous evidence would still send maintainers into the wrong follow-up work.

**Alternatives considered**:

- Accept a single successful live rerun: rejected. The success criteria require repeated stability.
- Treat fixture gaps as deferred improvements once the session stays up: rejected. The feature explicitly requires fixture blockers to be visible before behavior is judged.
- Let simulation-speed differences change the blocker interpretation: rejected. The classification must be anchored to lifecycle and fixture evidence, not to the speed setting used for the rerun.

---

## 7. Agent context update

**Decision**: Update `AGENTS.md` manually to point the Speckit marker at `specs/013-itertesting-channel-stability/plan.md`.

**Rationale**: The repository exposes the marker but `.specify/scripts/` has no helper dedicated to agent-context updates. A direct marker replacement is the smallest compliant change.

**Alternatives considered**:

- Leave `AGENTS.md` on 012: rejected. The active feature for planning is now 013.
- Add a one-off helper script solely for this marker swap: rejected. Unnecessary complexity.

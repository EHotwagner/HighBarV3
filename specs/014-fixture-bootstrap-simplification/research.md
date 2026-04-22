# Phase 0 Research — Fixture Bootstrap Simplification

**Branch**: `014-fixture-bootstrap-simplification` | **Date**: 2026-04-22  
**Plan**: [plan.md](./plan.md) | **Spec**: [spec.md](./spec.md)

The repository already has most of the semantics 014 needs: a static fixture dependency map in `bootstrap.py`, report-ready fixture and failure-cause types, and Itertesting bundle rendering. The remaining gap is that live bootstrap execution still uses a separate simplified-bootstrap blocker list in `behavioral_coverage/__init__.py`, while Itertesting summaries already reason from `fixture_profile` and `fixture_provisioning`. 014 should remove that split instead of layering a second interpretation path on top of it.

---

## 1. Authoritative fixture dependency source

**Decision**: Make `DEFAULT_LIVE_FIXTURE_CLASS_BY_COMMAND` in `clients/python/highbar_client/behavioral_coverage/bootstrap.py` the only authoritative command-to-fixture dependency map for live Itertesting.

**Rationale**: The map already encodes the fixture classes required by each direct command and is shared by `live_failure_classification.py`. Keeping a second blocklist in `behavioral_coverage/__init__.py` guarantees drift between bootstrap blocking and report classification.

**Alternatives considered**:

- Keep `_SIMPLIFIED_BOOTSTRAP_TARGET_MISSING_ARMS` and synchronize it manually: rejected. It duplicates the dependency source and will drift again.
- Move the mapping into shell scripts: rejected. The Python runner already owns command ids, reports, and failure classification.
- Add a new JSON config file for fixture dependencies: rejected. The repo already has a typed Python source of truth.

---

## 2. Provisioning execution layer

**Decision**: Keep fixture provisioning and refresh orchestration inside the Python behavioral-coverage workflow rather than moving it into `tests/headless/itertesting.sh`, new coordinator RPCs, or transport-side code.

**Rationale**: `itertesting_runner.py` already computes `fixture_profile`, `fixture_provisioning`, failure classifications, and contract-health decisions. The shell wrapper should stay the maintainer entrypoint, not become the owner of fixture lifecycle logic.

**Alternatives considered**:

- Push provisioning rules into the shell wrapper: rejected. The wrapper should report artifacts, not own per-command fixture semantics.
- Add new proto or gateway support for fixture provisioning: rejected. 014 is an internal closeout workflow change, not an external transport contract.
- Split provisioning into a separate helper tool: rejected. That would introduce another source of truth and another place to debug failures.

---

## 3. Missing-class expansion strategy

**Decision**: Expand live provisioning around reusable shared fixtures for the six currently missing classes named in the spec: `transport_unit`, `payload_unit`, `capturable_target`, `restore_target`, `wreck_target`, and `custom_target`.

**Rationale**: Those classes are the current dominant blockers for direct live coverage. They also map cleanly onto reusable live objects or targets that can be refreshed when consumed, destroyed, or moved out of a valid state.

**Alternatives considered**:

- Provision all optional classes in one undifferentiated pass: rejected. 014 needs explicit per-class status and refresh behavior, not a vague "try more setup" phase.
- Keep treating those classes as permanently missing until command-specific work exists: rejected. That leaves the closeout surface blocked even though the dependency model already knows what is missing.
- Force cheat-only provisioning for all six classes: rejected. The feature is about trustworthy live closeout, not masking unsupported setup behind a different execution mode.

---

## 4. Run-bundle evidence model

**Decision**: Keep `manifest.json`, `run-report.md`, and `campaign-stop-decision.json` as the authoritative review bundle, but extend fixture reporting so maintainers can see planned, provisioned, refreshed, missing, and affected-command information from a single model.

**Rationale**: Maintainers already review the Itertesting bundle, and `itertesting_report.py` already renders fixture sections. 014 needs a richer record inside the existing bundle, not a sidecar diagnostics format.

**Alternatives considered**:

- Add a separate fixture-debug artifact: rejected. It would duplicate bundle data and split review.
- Rely on raw live log strings for fixture interpretation: rejected. Closeout decisions need structured state.
- Report only aggregate counts: rejected. The spec requires the missing class names and affected commands.

---

## 5. Failure classification precedence

**Decision**: Preserve the 013 failure-cause split, but derive fixture blockers solely from the authoritative provisioning result and per-command dependency map.

**Rationale**: The existing classification already separates `missing_fixture`, `transport_interruption`, `predicate_or_evidence_gap`, and `behavioral_failure`. The problem is not the categories; it is that live bootstrap can still block commands through a separate simplified-bootstrap message path before the authoritative provisioning result gets the final say.

**Alternatives considered**:

- Let transport interruption swallow all fixture blockers: rejected. That hides actionable setup gaps.
- Let fixture blockers override every unhealthy-session result: rejected. Commands affected by real channel collapse still need transport-adjacent classification.
- Collapse evidence gaps into fixture blockers when a command has complex setup: rejected. Ambiguous evidence and missing fixtures are different review outcomes.

---

## 6. Validation and rollout surface

**Decision**: Validate 014 through the existing targeted pytest suite, `tests/headless/test_live_itertesting_hardening.sh`, and prepared live reruns via `tests/headless/itertesting.sh`.

**Rationale**: Those entrypoints already verify the report bundle, campaign semantics, and live closeout flow. Adding a second validation path would weaken, not strengthen, the maintainer contract.

**Alternatives considered**:

- Create a separate fixture bootstrap demo script: rejected. It would be helpful for debugging, but not as the shipping validation gate.
- Treat synthetic tests alone as sufficient: rejected. 014 must preserve healthy live closeout behavior.
- Require transport latency benches on every change: rejected. They remain required only if implementation touches transport-facing C++ paths.

---

## 7. Agent context update

**Decision**: Update `AGENTS.md` manually so the Speckit marker points to `specs/014-fixture-bootstrap-simplification/plan.md`.

**Rationale**: The repository has the marker, but no dedicated helper script for agent-context updates.

**Alternatives considered**:

- Leave `AGENTS.md` on 013: rejected. The active planning context is now 014.
- Add a one-off helper just for this marker update: rejected. That would add tooling only to avoid a one-line document edit.

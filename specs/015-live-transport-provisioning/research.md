# Phase 0 Research — Live Transport Provisioning

**Branch**: `015-live-transport-provisioning` | **Date**: 2026-04-22  
**Plan**: [plan.md](./plan.md) | **Spec**: [spec.md](./spec.md)

The remaining live blocker after 014 is no longer ambiguous fixture reporting. The latest validated prepared run already shows that `transport_unit` alone blocks exactly five commands and that the report bundle can surface class-level fixture state cleanly. 015 therefore focuses on turning transport from a narrow discovery heuristic into a full provisioning lifecycle that still fits the existing coordinator, bundle, and closeout workflow.

---

## 1. Coordinator relay boundary

**Decision**: Extend `specs/002-live-headless-e2e/examples/coordinator.py` to relay `InvokeCallback` on the existing `HighBarProxy` surface.

**Rationale**: The current coordinator example already hosts the live endpoint maintainers use for `Hello`, `StreamState`, and `SubmitCommands`, while `proto/highbar/service.proto` already defines `InvokeCallback`. The missing gap is relay implementation, not contract shape. Reusing the existing RPC keeps 015 inside current seams and avoids side-channel plumbing.

**Alternatives considered**:

- Add a new transport-specific RPC for unit-def lookup: rejected. The proto surface already has the general callback bridge.
- Hardcode transport unit-def ids in Python: rejected. BAR unit defs can vary across data revisions, and the spec requires environment-grounded eligibility.
- Skip callback forwarding and stay discovery-only: rejected. The status report already shows that passive discovery is insufficient to close the blocker.

---

## 2. Runtime transport def resolution

**Decision**: Resolve candidate transport unit defs at runtime through `InvokeCallback` and the existing callback id set instead of static ids or report-only heuristics.

**Rationale**: `BootstrapContext` already carries `def_id_by_name`, and the current behavioral-coverage package is structured to use runtime def-name resolution for provisioning decisions. Filling that map through the actual client-mode path lets the workflow provision transports naturally and keeps transport choice tied to the live environment.

**Alternatives considered**:

- Keep the current `max_health ~= 265.0` `armatlas` check as the primary selector: rejected. It misses supported alternatives such as `armhvytrans`.
- Resolve only through offline audit scripts: rejected. Audit helpers are useful for review, not for the shipping live workflow.
- Require proto/schema updates to expose def-name lookup directly: rejected. Existing callback contracts already cover the need.

---

## 3. Supported transport variant model

**Decision**: Treat `transport_unit` as a supported-variant class, initially satisfied by at least `armatlas` and `armhvytrans`, with capability-aware validation instead of a single health heuristic.

**Rationale**: The status report confirms the current live logic only recognizes `armatlas` and misses `armhvytrans` even though both are buildable from the ARM air factory. The spec also requires that any supported transport variant may satisfy coverage if it can perform the intended load/unload behavior.

**Alternatives considered**:

- Define `transport_unit` as exactly one canonical unit type: rejected. That fails the spec's variant requirement and remains brittle against game-data changes.
- Accept every flying unit as transport-compatible: rejected. Coverage must still be trustworthy and tied to actual transport behavior.
- Model transport support entirely in shell scripts: rejected. The Python runner already owns fixture classes, command ids, and reporting.

---

## 4. Provisioning lifecycle policy

**Decision**: Use a two-tier lifecycle: first reuse any already-usable transport, then attempt natural provisioning through the ordinary live workflow; only if an exceptional fallback is added later should it remain explicitly labeled in the run bundle.

**Rationale**: The spec requires both reuse and ordinary provisioning before declaring transport coverage missing. It also requires fallback paths to stay explicit rather than silently blending into normal provisioning. This matches the current trust model of the run bundle.

**Alternatives considered**:

- Always spawn a transport through `GiveMeNewUnitCommand`: rejected. That would hide whether ordinary live provisioning actually works.
- Never provision, only rediscover between commands: rejected. That preserves the current blocker.
- Treat refresh and replacement as out of scope: rejected. Later unload commands remain untrustworthy if the first transport is lost mid-run.

---

## 5. Compatibility gating before each command

**Decision**: Add an explicit transport-payload compatibility check before each transport-dependent command is evaluated.

**Rationale**: The spec is clear that a transport is only usable if it is alive, ready, and compatible with the pending payload. Reusing 014's generic fixture status alone is not enough; the workflow needs a per-command compatibility gate so load/unload coverage is not falsely treated as ready.

**Alternatives considered**:

- Assume any live transport can carry the chosen payload: rejected. That would turn payload-shape mismatch into false behavioral failures.
- Fold compatibility failures into generic missing-fixture text: rejected. The reviewer needs transport-specific reasoning when a candidate exists but cannot satisfy the scenario.
- Block the entire run when one transport-payload pairing fails: rejected. Only affected transport-dependent commands should be blocked.

---

## 6. Reporting surface

**Decision**: Keep `manifest.json`, `run-report.md`, and `campaign-stop-decision.json` as the only authoritative review bundle, but enrich the `transport_unit` status with lifecycle, provenance, compatibility, and affected-command detail.

**Rationale**: The latest run bundle already surfaces `planned`, `provisioned`, `missing`, and `affected` data in a usable format. 015 needs more precise transport detail inside that structure, not a sidecar report.

**Alternatives considered**:

- Add a transport-only debug artifact: rejected. That would split the maintainer review surface.
- Report only aggregate fixture counts: rejected. The spec requires lifecycle visibility and exact affected commands.
- Hide fallback usage once coverage succeeds: rejected. Exceptional provisioning must stay explicit.

---

## 7. Validation loop

**Decision**: Validate 015 through the existing Python behavioral-coverage tests, headless hardening/campaign checks, and three prepared live closeout reruns against the 2026-04-22 baseline bundle.

**Rationale**: Those entrypoints already govern the maintainer workflow and artifact bundle. Transport provisioning is complete only when the same closeout path shows healthy channel status and transport-dependent commands are no longer fixture-blocked where coverage is achievable.

**Alternatives considered**:

- Accept synthetic tests alone: rejected. The blocker is specifically in the live workflow.
- Create a separate transport-only smoke script as the shipping gate: rejected. It could help debugging but would weaken the actual closeout contract.
- Require transport latency benches unconditionally: rejected. They remain mandatory only if implementation touches transport-facing plugin code.

---

## 8. Agent context update

**Decision**: Update `AGENTS.md` manually so the Speckit marker points to `specs/015-live-transport-provisioning/plan.md`.

**Rationale**: The repository has the marker, but `.specify/scripts/` only contains setup/prerequisite helpers and no agent-context update script.

**Alternatives considered**:

- Leave the marker on 014: rejected. The active planning context is now 015.
- Add a one-off helper just for this document edit: rejected. The cost is not justified for a single marker replacement.

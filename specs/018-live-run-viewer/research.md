# Phase 0 Research — BAR Live Run Viewer

**Branch**: `018-live-run-viewer` | **Date**: 2026-04-23  
**Plan**: [plan.md](./plan.md)

## Decision 1: Keep BNV watch orchestration in the Python behavioral-coverage layer

**Decision**: Implement watch-mode policy, BNV readiness checks, and auto-launch behavior inside the Python behavioral-coverage / Itertesting layer instead of pushing them down into `tests/headless/itertesting.sh` or `_launch.sh`.

**Rationale**:

- The current shell wrappers are maintainer conveniences around live topology startup, but attach-later behavior and bundle persistence belong to the same orchestration layer that already owns `manifest.json`, `run-report.md`, and campaign decisions.
- Keeping watch logic in Python makes launch-time and attach-later paths share one policy surface instead of duplicating rules in Bash and Python.
- `_launch.sh` is specifically the `spring-headless` seam; expanding it to own BNV spectator policy would mix two different responsibilities.

**Alternatives considered**:

- Launch BNV directly from `tests/headless/itertesting.sh`.  
  Rejected because attach-later requests and bundle-visible watch lifecycle would still need a Python ownership seam.
- Put BNV launch behavior into `_launch.sh`.  
  Rejected because `_launch.sh` is a pinned headless-engine launcher, not the right home for maintainer viewer selection logic.

## Decision 2: Use one watch flag plus an optional structured watch profile

**Decision**: The live launch path should add one watch enablement option plus an optional structured watch profile reference, with defaults of windowed `1920x1080` spectator launch and mouse capture disabled.

**Rationale**:

- This satisfies the clarified spec: non-watch flows remain unchanged, while watched runs gain a comprehensive but contained configuration surface.
- A profile-based model lets maintainers override executable path, window behavior, or future spectator settings without exploding the CLI with one-off flags.
- Consistent defaults reduce operator error and keep watch mode usable in the common maintainer case.

**Alternatives considered**:

- Add many independent CLI flags for every watch parameter.  
  Rejected because it would erode `SC-001` and make the launch surface harder to reason about.
- Hardcode one default with no override path.  
  Rejected because the feature explicitly requires comprehensive configuration beyond the default spectator window.

## Decision 3: Resolve BNV executable and local prerequisites through explicit profile data backed by `HIGHBAR_`-style environment defaults

**Decision**: `WatchProfile` should resolve the BNV executable path and related local launch prerequisites from explicit profile data, while allowing profile defaults to inherit from environment-backed machine-local values such as `HIGHBAR_BNV_BINARY`.

**Rationale**:

- The repository already uses `HIGHBAR_...` environment variables and `docs/local-env.md` for machine-specific host prerequisites such as `SPRING_HEADLESS`.
- A profile can remain portable inside the repository while the executable path stays host-specific.
- This keeps local BNV discovery explicit and testable instead of relying on opaque PATH lookup heuristics.

**Alternatives considered**:

- Require PATH-based discovery only.  
  Rejected because BAR installs are machine-specific and PATH assumptions would be fragile on maintainer hosts.
- Store an absolute BNV path directly in repo-tracked spec/config docs.  
  Rejected because the repository should not encode one maintainer machine’s install path as a project-level invariant.

## Decision 4: Persist watch lifecycle in the bundle and a filesystem-backed active watch index

**Decision**: Watch state should live in two places: the per-run manifest/report for durable diagnosis and a repo-local `reports/itertesting/active-watch-sessions.json` index for attach-later discovery while runs are still active.

**Rationale**:

- Attach-later requests need a current source of truth for active watchable runs without depending on hidden in-memory state from an earlier invocation.
- The manifest/report remain the durable maintainer-facing truth after a run completes, while the active index solves the narrower discovery problem during execution.
- This stays aligned with the project’s existing filesystem-backed campaign model and avoids introducing a service or proto extension.

**Alternatives considered**:

- Use only process-local state from the original run launcher.  
  Rejected because attach-later requests must work from a separate command invocation.
- Use only completed manifests with no active index.  
  Rejected because attach-later needs to distinguish active, unavailable, and expired sessions before run completion.

## Decision 5: Make watch readiness a preflight gate before live execution

**Decision**: When watch mode is requested, the system must validate BNV prerequisites and launch readiness before live execution begins; if the requested watch launch cannot be established, the run aborts before live start and records a viewer-readiness failure.

**Rationale**:

- The clarified spec makes viewer-launch failure terminal for requested watch mode, so the cleanest implementation is to fail early before consuming live setup time.
- A preflight result gives the bundle and stdout one authoritative reason for watch unavailability instead of mixing startup failures with later gameplay failures.
- This also keeps non-watch runs unaffected and preserves a clear contract between watch request and run outcome.

**Alternatives considered**:

- Start the live run first and fail after BNV launch fails.  
  Rejected because it wastes live setup work and creates a less deterministic operator experience.
- Degrade watch mode silently when launch fails.  
  Rejected because the user explicitly clarified that requested watch launch failure should fail the run.

## Decision 6: Keep post-launch disconnects as watch-lifecycle events, not hidden run-control behavior

**Decision**: Distinguish BNV preflight/launch failure from later viewer disconnect. Preflight or initial launch failure aborts the run request, but a later viewer disconnect is recorded as a watch lifecycle event that expires access while leaving the already-running live evaluation path intact.

**Rationale**:

- The spec separately calls out viewer disconnect during a run as an edge case where the run still needs complete artifacts.
- This preserves the explicit terminal policy for requested launch failure without letting the viewer become an ongoing control plane over gameplay.
- Maintainers still receive durable artifact evidence that watch access was lost and why.

**Alternatives considered**:

- Treat every later disconnect as a run failure.  
  Rejected because it would make the viewer an ongoing availability dependency rather than a launch-time requirement.
- Ignore disconnects entirely.  
  Rejected because FR-005 and FR-008 require watch state and reasons to remain visible.

## Decision 7: Update `AGENTS.md` manually for the active plan context

**Decision**: Update the Speckit marker in `AGENTS.md` manually so it points to `specs/018-live-run-viewer/plan.md`.

**Rationale**:

- `.specify/scripts/` contains setup helpers, but no dedicated agent-context update script.
- The repository already uses manual marker replacement as the minimal compliant approach.

**Alternatives considered**:

- Leave `AGENTS.md` on `017`.  
  Rejected because it would point future work at the wrong planning context.
- Add a new helper script during planning.  
  Rejected because that would expand scope beyond the feature documentation workflow.

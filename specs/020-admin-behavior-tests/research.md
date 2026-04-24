# Research: Comprehensive Admin Channel Behavioral Control

## Decision: Extend the Existing HighBarAdmin Service

Add the missing unit ownership transfer as an additive `UnitTransferAction` in `proto/highbar/service.proto` and keep pause, speed, resource grant, unit spawn, validation, execution, leases, and capabilities on the existing `HighBarAdmin` service.

**Rationale**: Feature 019 already created the privileged admin surface, generated-client helpers, role headers, result statuses, and lease model. Reusing it keeps the contract proto-first and avoids splitting admin behavior across competing APIs.

**Alternatives considered**:
- Reuse legacy AI command arms such as `give_me` or `pause_team`: rejected because privileged actions must stay off the normal AI command surface.
- Add a test-only RPC service: rejected because clients need one discoverable admin contract, not separate production and test contracts.

## Decision: Apply All Accepted Mutations on the Engine Thread

RPC handlers perform role parsing, preliminary validation, and response mapping, then enqueue accepted execution work for the gateway module to drain on the engine frame callback.

**Rationale**: The constitution forbids worker-thread mutation of CircuitAI state or engine callbacks. The behavioral suite specifically proves effects in the running match, so accepted results must correspond to work accepted for the engine-thread execution path.

**Alternatives considered**:
- Execute simple controls directly from `AdminService`: rejected because Spring callback thread-safety is not documented.
- Use locks around engine calls from workers: rejected because locks do not make engine callback APIs thread-safe.

## Decision: Use Snapshots and Deltas as Primary Evidence

The suite observes state through `PushState`/snapshots and deltas, then records engine log paths only for diagnostics and prerequisite failures.

**Rationale**: The feature's central requirement is proving client-observable match-state changes. Snapshot/delta evidence exercises the same wire contract used by admin clients and avoids relying on local-only log text for pass/fail decisions.

**Alternatives considered**:
- Parse engine logs for every assertion: rejected because logs are diagnostic text, not a stable client contract.
- Trust `AdminActionResult` alone: rejected because current gap is success acknowledgement without behavioral proof.

## Decision: Use a Deterministic Fixture With Runtime Capability Discovery

The headless wrapper uses a fixed admin fixture map/startscript and a fixture metadata file for candidate teams, resources, unit definitions, spawn positions, and an existing transferable unit. The driver still queries `GetAdminCapabilities` before executing mutating cases.

**Rationale**: Deterministic fixtures make before/after expectations stable while capability discovery prevents the suite from assuming controls disabled by the current run mode.

**Alternatives considered**:
- Fully dynamic discovery from arbitrary matches: rejected for the first comprehensive version because resource, unit, and map constraints would make failures harder to classify.
- Hard-code actions without capabilities: rejected because the spec requires advertised controls to match executable behavior.

## Decision: Timing Assertions Use Tolerance Windows

Pause, resume, speed, spawn, resource, and transfer checks use frame/time windows and action-specific tolerances instead of exact wall-clock equality.

**Rationale**: Live frame progression and state publication have jitter. The suite must distinguish real no-op behavior from harmless scheduling variance.

**Alternatives considered**:
- Exact frame equality: rejected as flaky for speed and state-publication checks.
- Very long timeouts: rejected because the suite must complete in under 3 minutes and failures should surface quickly.

## Decision: Separate Prerequisite Failures From Behavioral Failures

The headless wrapper exits 77 for missing local runtime prerequisites and the Python driver emits prerequisite records. Behavioral mismatches exit 1 with per-action evidence.

**Rationale**: Developers need to know whether BAR/headless setup is missing or the admin channel regressed. The existing headless scripts already use 77 for setup skips.

**Alternatives considered**:
- Treat all startup failures as test failures: rejected because it would create false regressions on machines without a prepared runtime.
- Silently skip unavailable controls: rejected because unsupported controls must be reflected in capabilities and the evidence summary.

## Decision: Cleanup Is Part of the Suite Contract

The driver resumes play, restores normal speed, and releases or expires leases before continuing after timing-sensitive cases and before exit.

**Rationale**: Repeatability criteria require three consecutive prepared runs without leftover pause, speed, lease, resource, or spawned-unit state causing false failures.

**Alternatives considered**:
- Leave cleanup to the fixture restart: rejected because tests can fail mid-run and still need usable diagnostic state.
- Omit cleanup for failed actions: rejected because one failed pause/speed case could poison later evidence.

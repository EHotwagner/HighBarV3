# Research: Snapshot-grounded behavioral verification of AICommand arms

**Feature**: 003-snapshot-arm-coverage
**Date**: 2026-04-21
**Status**: Complete

This document resolves the technical unknowns raised by the plan's
Technical Context and closes out each of the five clarification
questions from the spec (Session 2026-04-21). Format follows Spec
Kit convention: **Decision / Rationale / Alternatives considered**.

Ground truth for "current state" citations is the 002-landed tree at
HEAD `9f1aa1c4` (branch `003-snapshot-arm-coverage`, master merged
002 at `75072db1`).

---

## R1. Snapshot-tick scheduler call site

**Unknown**: FR-001 requires periodic `StateSnapshot` emission at
configurable cadence. 002 emits a snapshot exactly once per session
(inside `HighBarService::Hello`, consumed by `HelloResponse.static_map`
and forwarded into `StreamState` as the first `StateUpdate`). Nothing
else on the plugin side materialises a snapshot.

**Decision**: Add a new `SnapshotTick` scheduler in
`src/circuit/grpc/SnapshotTick.{h,cpp}` that exposes a single method
`Pump(uint32_t frame, size_t own_units_count)` called from
`CGrpcGatewayModule::OnFrameTick` on the engine thread. `Pump`
decides whether this frame is a snapshot frame by consulting a
running `next_snapshot_frame_` counter; on fire, it invokes the
existing snapshot serialiser (the same one `Hello` uses), wraps the
bytes in a `StateUpdate` with `payload.snapshot = …` and
`send_monotonic_ns = CLOCK_MONOTONIC ns`, and hands the buffer to the
existing fan-out path (`CGrpcGatewayModule::BroadcastStateUpdate`).
No new threads, no new locks, no serialiser duplication.

The `RequestSnapshot` RPC (FR-006) sets a single `std::atomic<bool>
pending_request_` on the module. `Pump` observes the flag at the top
of each frame call and, if set, forces a snapshot this frame
(regardless of cadence), clears the flag, and resets the cadence
counter so the next periodic tick happens `snapshot_cadence_frames`
frames later (not on the frame after the forced one). This is how we
coalesce concurrent `RequestSnapshot` callers: N callers in the same
frame set the same flag; exactly one extra snapshot is emitted.

**Rationale**: The engine thread already owns snapshot serialisation
(Hello takes `state_mutex_` exclusive to build the one-shot). Putting
`SnapshotTick` on the same thread and the same mutex means we pay
zero new concurrency design cost. Pump-from-`OnFrameTick` is the same
surgical-edit shape 002 used for `DrainCommandQueue` — precedent is
clean. Keeping the RPC handler worker-only-sets-atomic preserves
Constitution II: no CircuitAI state ever touched from a gRPC worker.

**Alternatives considered**:

- *Dedicated `std::thread` driving snapshots with its own timer.*
  Rejected: violates Constitution II (mutates serialiser state from
  a non-engine thread) and introduces a new synchronisation surface
  that would interact with 002's `state_mutex_` in ways we'd have to
  re-verify. The engine-thread frame cadence gives us all the timing
  signal we need.
- *Have the gRPC worker serialise snapshots on demand.* Rejected for
  the same Constitution II reason. Workers can read under shared
  lock for the existing Hello resume-out-of-range path because that
  case doesn't mutate anything; a periodic tick that advances
  scheduler state and updates the fan-out ring buffer is a writer,
  not a reader.
- *Wrap in `OnUpdate` (the BARb per-second callback) instead of
  `OnFrameTick` (per-frame).* Rejected: `OnUpdate` fires at ~1Hz,
  too coarse to support the `behavioral-move.sh` 4s / 120-frame
  window reliably. `OnFrameTick` at 30fps lets us take 30× as many
  cadence steps.

---

## R2. Halving-cadence semantics under `own_units > snapshot_max_units`

**Unknown**: Spec clarification Q2 answered "halve the effective
cadence, no truncation, no skip" but left the implementation
semantics of "each subsequent tick while the cap is exceeded" loose.
Does the interval double once and stay doubled? Does it keep halving
on every tick until it's longer than the match? What happens when
unit count drops back under the cap?

**Decision**: The scheduler tracks a single integer
`effective_cadence_frames` that starts at the configured
`snapshot_cadence_frames` (default 30). On each snapshot emission:

- If `own_units.length > snapshot_max_units` AT THE MOMENT of the
  emission, `effective_cadence_frames` doubles for the *next* tick
  (30 → 60 → 120 → 240 …), capped at 1024 frames (~34s at 30fps) so
  a runaway doesn't starve the stream entirely.
- If `own_units.length <= snapshot_max_units` on the emission,
  `effective_cadence_frames` snaps back to the configured base value
  (1024 → 30 in one step, not a symmetric decay).

Each emitted `StateSnapshot` populates the new
`effective_cadence_frames` field with the interval that was in
effect *when this snapshot fired* (not the one that will govern the
next emission) so clients can compute the exact next expected frame
as `frame + effective_cadence_frames`.

**Rationale**: The halving is a safety valve, not a steady-state
control law. Asymmetric recovery — instant return to baseline — is
the simplest behavior that satisfies the spec's "cadence returns to
baseline as soon as the unit count drops back under the cap"
language without introducing a tuning parameter (decay rate) that
nobody will have evidence to set. The 1024-frame cap is a paranoia
guard; in practice BAR matches rarely exceed 200 own units even with
a dense economy, so the halving usually fires zero or one times.

Broadcasting the interval on the snapshot itself (rather than as a
separate `CadenceChangedEvent` delta) means test drivers have a
single source of truth per snapshot and don't need to reconcile
between streams.

**Alternatives considered**:

- *Symmetric decay (halve interval back toward baseline on under-
  cap frames).* Rejected: adds a second tuning parameter (decay
  rate) with no evidence for the right value, and the recovery
  would lag the under-cap observation by multiple snapshots. Snap-
  back is strictly simpler and matches the spec's language.
- *Emit a separate `CadenceChangedEvent`.* Rejected: the cadence is
  a per-snapshot property (the interval until the *next* snapshot
  is a function of this one's effective cadence), so threading it
  through the existing `StateSnapshot` envelope is the natural fit.
  Additional event type = additional proto churn, no benefit.
- *Truncate `own_units[]` at the cap.* Explicitly rejected by the
  clarification answer.

---

## R3. Bootstrap plan capability coverage

**Unknown**: Spec clarification Q1 answered "two-phase bootstrap, no
cheats" and named five example capabilities (`commander`,
`factory_ground`, `factory_air`, `radar`, `mex`, `builder`). The spec
leaves open which BAR unit def IDs realise each capability and how
the commander provisions them deterministically from the
`minimal.startscript` baseline.

**Decision**: The BootstrapPlan consists of an ordered list of
`(capability_tag, def_id, relative_position)` tuples the commander
issues as sequential build orders. For the default
`minimal.startscript` (Avalanche 3.4, two BARb teams, Armada-vs-
Armada), the plan is:

1. `mex` → `armmex` at commander + (+96, 0, 0) — cheapest build,
   proves build pipeline works.
2. `solar` → `armsolar` at commander + (-96, 0, 0) — economy sanity.
3. `factory_ground` → `armvp` (vehicle plant, closest to commander
   spawn on Avalanche) at commander + (+160, 0, +96).
4. `factory_air` → `armap` (aircraft plant) at commander + (-160,
   0, +96).
5. `radar` → `armrad` at commander + (+96, 0, -96).
6. `builder` → assisted-build `armck` from the `armvp` factory (the
   factory itself has `BuildUnit` capability that tests the
   factory-arm path; once it produces `armck`, the ground-constructor
   arms have a target).
7. `cloakable` → `armpeep` from `armap` (Peeper scout; provides the
   `scout`/`cloak`-capable vehicle for arms that need one).

Positions are absolute offsets from the commander's spawn
(read from the first `StateSnapshot.own_units[commander]`), so the
plan is gameseed-deterministic even though the commander spawn
itself varies per start-script.

The plan's step ordering is fixed (mex/solar first so economy
exists, then factories, then radar, then factory-produced units
last). Each step has its own per-capability upper-bound timeout
(`mex`: 10s, `solar`: 10s, `factory_ground`/`factory_air`: 45s,
`radar`: 10s, `armck`/`armpeep`: 30s). The commander queues
steps 1–5 in parallel and the two factories pipeline steps 6–7,
so the wall-clock critical path is `max(45s commander-built) +
max(30s factory-produced) = 75s ≤ 90s` (matches SC-003's
`bootstrap plan ≤ 90s` budget). Completion is signaled by
the corresponding unit appearing in `own_units[]` with
`under_construction=false`; timeout on any step aborts Phase 2 with
`bootstrap_timeout` and the CSV is emitted with all 66 rows marked
`precondition_unmet`.

**Rationale**: The seven-capability set covers every
`required_capability` tag we expect the 66-arm registry to claim, and
it uses only Armada-side unit defs (the `minimal.startscript` pins
Armada on both teams). Relative-offset positions are the
straightforward way to stay gameseed-determinism-compatible across
different maps if we later swap start-scripts — the commander spawn
is the anchor, nothing else.

Using `armvp` + `armap` (vehicle + aircraft plants) rather than the
lab/gantry tier matches what the `minimal.startscript` commander
can afford within the first 60 seconds on default BAR economy; we
don't need heavy factories to exercise factory-arm capabilities, we
just need *any* factory.

**Alternatives considered**:

- *Enable cheats (`/godmode`, `/cheat give`).* Explicitly rejected
  by the clarification answer: cheats-off baseline is the premise of
  the behavioral-coverage suite.
- *Spawn a dedicated "test" start-script with pre-placed prerequisite
  units.* Rejected: pre-placed units bypass the engine's build
  pipeline, which means the bootstrap phase would stop exercising
  the very BuildUnit command the macro driver needs to verify as
  arm #17 (`build_unit`). Using the commander to build the
  prerequisites is itself a behavioral test of the Build arm — the
  bootstrap plan's success is US2's positive signal.
- *Build everything simultaneously instead of sequentially.*
  Rejected: economy throughput doesn't permit it. A commander on
  default BAR economy produces ≈ 2 metal/s; building `armvp`
  (50m) + `armap` (130m) + `armrad` (30m) + `armmex` (16m) in
  parallel exceeds income and stalls the bootstrap. Sequential
  scheduling with explicit dependencies keeps the plan
  deterministically ≤ 90s.

---

## R4. Bootstrap-state reset determinism

**Unknown**: Spec FR-003b requires a bootstrap-state reset between
every arm with per-reset timeout 10s. Clarification Q4 affirmed
"bootstrap-state reset between arms" as the failure-isolation
strategy. How does the reset decide what to reissue, and how does
it stay deterministic given per-gameseed float-jitter in build
timing?

**Decision**: The reset is purely manifest-driven:

1. The BootstrapPlan's seven-step completion snapshot (taken the
   first time Phase 1 finishes) is recorded as the **bootstrap
   manifest**: a sorted list of `(def_id, count)` pairs. (E.g.,
   `(armcom, 1), (armmex, 1), (armsolar, 1), (armvp, 1), (armap,
   1), (armrad, 1), (armck, 1), (armpeep, 1)`.)
2. After each arm's verify-predicate resolves, the reset function
   takes a fresh snapshot, diffs `own_units[]` against the manifest
   by `def_id`-count, and for each missing `(def_id, count_short)`
   pair issues `count_short` `BuildUnit` commands to the nearest
   surviving capability unit (the commander for mex/solar/factories/
   radar; the factory for factory-produced units).
3. The reset blocks on sampled snapshots (at the effective cadence,
   so at default config every 1s) until the manifest re-matches OR
   the 10s timeout elapses. On timeout: `bootstrap_reset_failed`
   for all remaining undispatched arms, digest still emitted.

The digest is stable across runs because:

- The manifest is sorted by `(def_id, count)`, which is a stable
  key.
- The reset issues commands in a deterministic order (ascending
  `def_id`, then by nearest-surviving-capability-unit's smallest
  `unit_id`).
- The verify-predicate's pass/fail decision operates only on
  integer counts and fixed-threshold float comparisons (see R5
  for the float strategy), never on raw float values or wall-clock
  times.

**Rationale**: A manifest-driven reset means the reset logic has
exactly one input (the manifest) and one output (reissued build
orders). Any non-determinism comes from engine-side build timing,
which we contain by bounding the wait on the cadence-locked
snapshot stream rather than on wall-clock.

**Alternatives considered**:

- *Capture the reset state per-arm (diff against the previous
  arm's post-state instead of a fixed manifest).* Rejected: makes
  the reset inherently sequential-dependent and destroys FR-012
  reproducibility if an arm hiccups and the "previous post-state"
  is itself non-deterministic. Fixed manifest is the only way to
  get gameseed-deterministic resets.
- *Skip the reset entirely if the arm's verify-predicate passed.*
  Rejected: a passing verify still mutates state (the move
  happened, the build started) and later arms would observe the
  mutation. The reset is cheap enough (~1-3s) to always run.

---

## R5. Reproducibility-critical vs. evidence columns in the digest

**Unknown**: Spec clarification Q3 specified "bit-exact only for
reproducibility-critical columns" (`arm_name`, `dispatched`,
`verified`, `error`) and excluded the `evidence` column. Q3 also
said the digest is SHA-256 over a canonical serialisation. The spec
does not pin what "canonical" means — CSV escape quoting, boolean
representation, error-string casing, sort key tiebreaker.

**Decision**: Canonical serialisation for the digest:

- Input: the 66 data rows (no header).
- Per row, concatenate the four critical columns with `\x1f` (ASCII
  unit separator, 0x1F) as the field delimiter, and end each row
  with `\n` (0x0A).
- Column values:
  - `arm_name`: the exact string as it appears in the registry key
    (UTF-8, case-sensitive).
  - `dispatched`: `"true"` or `"false"` (lowercase, no quotes in
    the serialisation).
  - `verified`: `"true"`, `"false"`, or `"na"` (lowercase).
  - `error`: empty string if no error, otherwise one of the fixed
    lowercase snake-case tokens: `dispatcher_rejected`,
    `effect_not_observed`, `target_unit_destroyed`, `cheats_required`,
    `precondition_unmet`, `bootstrap_reset_failed`, `timeout`,
    `internal_error`.
- Sort: ascending `arm_name` (UTF-8 byte order, case-sensitive).
- Hash: SHA-256 over the concatenated bytes; output lowercase hex.
- Digest file (`.digest` sidecar): exactly 64 hex chars + LF, no
  leading whitespace, no trailing anything.

The CSV itself (the human-readable artifact at
`build/reports/aicommand-behavioral-coverage.csv`) uses standard
RFC 4180 quoting for cells containing commas or quotes; the `category`
and `evidence` columns are included for humans but excluded from the
digest input. Float values inside `evidence` (e.g., position deltas)
are rendered with fixed `.3f` formatting purely for readability, but
because `evidence` is excluded from the digest, any future change
to the float format does not break reproducibility.

**Rationale**: ASCII unit separator (0x1F) as the canonical field
delimiter eliminates any ambiguity about CSV quoting rules — a
character that will never appear in any of our four critical column
values can't cause a quoting-induced mismatch between runs with
different locale settings. SHA-256 is the obvious hash choice
(stdlib, cryptographic-strength, widely tool-supported for `sha256sum
--check`). The explicit lowercase snake-case error vocabulary means
any refactor of error strings has to update a single enum rather
than risk a digest drift across runs.

**Alternatives considered**:

- *Use RFC 4180 CSV as the canonical format itself (hash the CSV
  bytes directly).* Rejected: locale and library choice affect
  line-ending handling and cell-quoting heuristics in subtle ways
  across Python versions; a hand-rolled canonical format eliminates
  the surface area.
- *Include the `category` column in the digest.* Rejected: category
  is a derived constant from the arm's static metadata, so it
  contributes no information the name doesn't already encode. Keep
  the digest minimal.
- *Hash with SHA-1 (faster).* Rejected: no performance advantage
  at 66 rows (< 1µs on commodity hardware either way), and SHA-256
  is the team default per 002's auth-token hashing.

---

## R6. Gameseed, start-script, and reproducibility topology

**Unknown**: FR-008 specifies `gameseed = 0x42424242`. The existing
`minimal.startscript` does not pin a gameseed. Does the macro driver
mutate the start-script on disk, or inject the seed via command-line
override, or via start-script include?

**Decision**: The macro driver generates a per-run derived
start-script at `build/tmp/behavioral-coverage-run-N.startscript`
that starts from `tests/headless/scripts/minimal.startscript` verbatim
and appends a `[modoptions] gameseed=0x42424242 [/modoptions]` block
(or replaces the existing block if present). The headless script
passes this derived path to `spring-headless` via the same argv
surface `us2-ai-coexist.sh` uses. The original `minimal.startscript`
is not modified in place — it's a shared test asset and other
scripts consume it.

Reproducibility-run numbering: `behavioral-reproducibility.sh`
invokes the macro driver five times with run indices 1..5 appended
to the tmp startscript filename (and to the CSV output paths —
`build/reports/run-1/aicommand-behavioral-coverage.csv`, etc.), so
post-hoc comparison of a single failing run against the other four
is a simple `diff`.

**Rationale**: Generating a derived start-script keeps the baseline
asset unchanged (Constitution I's "surgical edits" principle applied
to test assets too) and makes the gameseed explicit and auditable
per run. The `build/tmp/` location is gitignored; run-indexed output
paths give reproducibility failures a concrete per-run debug trail.

**Alternatives considered**:

- *Pass `gameseed` via `spring-headless` CLI.* Rejected: BAR's
  engine reads gameseed from the start-script `[modoptions]` block,
  not a CLI arg; there is no CLI override that works portably across
  the pinned `recoil_2025.06.19`.
- *Mutate `minimal.startscript` in place.* Rejected: shared asset.
  Other headless scripts would inherit the seed.
- *Require the user to provide a pre-seeded start-script.*
  Rejected: couples the acceptance script to a checked-in asset we
  then have to keep in sync with the coverage script. Derived files
  are cheaper.

---

## R7. Threshold policy and CI ratcheting

**Unknown**: FR-007 defaults the verified-rate threshold to 50% and
states "CI MUST set the threshold to `0.50` initially and ratchet
upward in subsequent commits as more arms gain verification." Spec
doesn't say how the ratchet is enforced — is the threshold a
committed constant, a commit message parser, a PR-review gate?

**Decision**: The threshold lives as a plain-text constant in
`.github/workflows/ci.yml` (a numeric argument to the
`aicommand-behavioral-coverage.sh` invocation:
`HIGHBAR_BEHAVIORAL_THRESHOLD=0.50`). Moving it upward is a one-line
PR diff; there is no separate ratchet-tracking file. A CI job
`threshold-ratchet-check` reads the current `verified_count /
wire_observable_count` from the uploaded CSV artifact of the prior
merged main-branch run and prints a line
`behavioral-coverage: verified=<n>/<w> threshold=<T> — next ratchet opportunity: <suggested T+5pp>`
as a PR comment. Enforcement is social (reviewer sees the comment
and decides whether to bump the threshold in this PR); the CI gate
itself only fails if the current run is below the currently-set
threshold.

**Rationale**: A ratchet encoded in config is the minimum-moving-
parts option. Automatic enforcement of ratcheting (e.g., rejecting
PRs that don't bump the threshold) would couple feature-work PRs
to the coverage number, which is a floor, not a target — some PRs
genuinely won't move it, and failing them would be noise. The
comment makes the ratchet opportunity visible without enforcing it.

**Alternatives considered**:

- *Hard-code threshold in the Python driver instead of CI config.*
  Rejected: makes the threshold un-overridable by the env var the
  spec requires (`HIGHBAR_BEHAVIORAL_THRESHOLD`), and moving it
  becomes a code change instead of a config change.
- *Auto-ratchet: CI writes a new threshold file when the verified-
  rate increases.* Rejected: self-mutating CI state creates a
  regression hazard where a flaky high-water-mark locks the
  threshold above what the steady-state set actually passes.

---

## R8. Python package wiring — `behavioral_coverage` as a submodule

**Unknown**: Spec clarification Q5 specified "extend the existing
`clients/python/highbar_client` package with a new
`behavioral_coverage` submodule exposed as a module entry point."
How does that submodule interact with the existing `commands.py`,
`session.py`, `state_stream.py`? Is there a new runtime dependency?

**Decision**: The submodule layout is:

```
clients/python/highbar_client/behavioral_coverage/
├── __init__.py       # orchestrator: parse args, build session, run phases
├── __main__.py       # `python -m highbar_client.behavioral_coverage` entry
├── registry.py       # 66-row BehavioralTestCase table
├── capabilities.py   # required_capability tag vocabulary
├── bootstrap.py      # BootstrapPlan + manifest + reset logic
├── predicates.py     # shared verify-predicate helpers
└── report.py         # canonical CSV + digest
```

It consumes the existing `highbar_client.commands` (builder helpers
for every `AICommand` oneof arm — 002 wired these), `highbar_client.
session` (channel construction, Hello handshake, AI-role token), and
`highbar_client.state_stream` (StreamState consumer that materialises
snapshots into Python-side `StateSnapshot` protos). It does **not**
add a new dep beyond stdlib:

- `argparse`, `hashlib`, `pathlib`, `time`: stdlib.
- `csv`: stdlib.
- `grpcio` / generated stubs: already in `pyproject.toml`.

The CLI entry point is `python -m highbar_client.behavioral_coverage`
invoked via `uv run --project clients/python …` from the shell
wrapper, matching FR-013 verbatim. Arguments exposed:
`--startscript`, `--gameseed`, `--output-dir`, `--threshold`,
`--run-index` (for reproducibility runs).

**Rationale**: Submodule-not-subpackage matches FR-013's "no new
package, no new lockfile" letter. Reusing the 002-landed command
builders means the arm registry can be one-liners per row
(`(arm="move_unit", build=lambda unit: commands.move_unit(unit.id,
target_pos), …)`) rather than re-implementing proto construction.

**Alternatives considered**:

- *Separate `highbar_tools` package alongside `highbar_client`.*
  Explicitly rejected by the clarification.
- *Standalone script at `tests/headless/behavioral_coverage.py`
  outside the package.* Rejected: loses import access to the
  package's command builders and session helpers; would need to
  duplicate their logic or add a sys.path hack.

---

## R9. Channel C (Lua-only) arm disposition

**Unknown**: Spec FR-005 and §Out of Scope say Channel-C Lua-only
arms (draw-on-minimap, in-game chat, custom widgets) are not
wire-observable in this feature's scope and are deferred to a
follow-up tied to BAR Lua widgets + `InvokeCallback`. How are
those arms represented in the 66-row registry, and what shows up
in their CSV row?

**Decision**: Channel-C arms are present in the registry with
`required_capability = "none"`, `input_builder` that constructs a
minimal-valid command (so we still exercise the dispatch path
serialisation-wise), and `verify_predicate = NotWireObservable` —
a sentinel that causes the driver to:

- Still dispatch the arm (so `dispatched=true` is truthful — the
  gateway acked the batch).
- Skip the verify-predicate and record `verified="na"`,
  `error="not_wire_observable"`.
- Exclude the arm from the success-rate denominator (per FR-005 and
  spec §Out of Scope).
- Emit `evidence` containing the sentinel rationale string
  (e.g., `"draw-on-minimap: no wire signal in this feature; deferred
  to Lua widget follow-up"`).

The header-listed `wire_observable` column is not added; instead
the driver prints a summary line at the end:
`behavioral-coverage: verified=<N>/<W> wire-observable, <C>
channel-c-deferred, <P> precondition-unmet`.

**Rationale**: Keeping every arm in the registry even when it can't
be verified means the 66-row invariant (FR-004: "exactly 66 rows")
is preserved without special-casing. The sentinel-predicate pattern
lets us lift the restriction later (when Lua widgets ship) by
swapping the sentinel for a real predicate — no registry
restructuring.

**Alternatives considered**:

- *Omit Channel-C arms from the registry entirely.* Rejected: FR-
  004's "exactly 66 rows" invariant is explicit.
- *Mark them as `dispatched=false`.* Rejected: dispatching them is
  still useful (serialisation round-trip sanity), and claiming they
  weren't dispatched when they were would be misleading.

---

## R10. Digest reproducibility under `precondition_unmet` arms

**Unknown**: If an arm's `required_capability` is not in the
bootstrap plan (FR-003a sentinel `precondition_unmet`), the arm
contributes to the digest with `dispatched=false, verified=na,
error=precondition_unmet`. If the bootstrap plan's capability set
changes between commits (new capabilities added, existing ones
removed), the digest changes. How do we prevent "the bootstrap plan
changed" from presenting as "reproducibility broke"?

**Decision**: The reproducibility check (FR-008, US6) operates on
**five runs at the same commit** — not across commits. A commit
that changes the bootstrap plan is allowed to change the digest;
the ratchet/regression story for digests is committed + compared
only within a single CI run. The CI artifact retention keeps prior
digests for post-hoc comparison, but no PR gate is attached to
"digest equal to the previous main-branch digest."

**Rationale**: Reproducibility is a *flakiness* gate
(same-commit, same-inputs, same-output), not a *stability* gate
(no-output-ever-changes-across-commits). Mixing the two would make
legitimate feature work (new capabilities, new arms wired) look
like flakiness. Keeping the gate strictly within-run matches the
clarification Q3 scope ("the same gameseed") and the spec's FR-012
wording.

**Alternatives considered**:

- *Hash the registry layout into the digest so changes are
  self-identifying.* Rejected: solves a problem we don't have, and
  makes the digest opaque to the diff-localisation that FR-008
  requires on mismatch.
- *Baseline-compare against main-branch digest as a gate.*
  Rejected for the reason above.

---

## Summary of Decisions

| # | Topic | Decision |
|---|---|---|
| R1 | Snapshot-tick call site | `SnapshotTick::Pump` from `OnFrameTick` on engine thread; `RequestSnapshot` sets atomic flag, engine thread drains. |
| R2 | Halving semantics | Double on over-cap, snap back to baseline on under-cap. Cap at 1024 frames. Emit `effective_cadence_frames` on each snapshot. |
| R3 | Bootstrap plan | 7 steps (mex, solar, factory_ground, factory_air, radar, builder, cloakable) via commander + factory sequential build orders. ≤ 90s. |
| R4 | Reset determinism | Manifest-driven diff, sorted by `(def_id, count)`; reissue in deterministic order; 10s per-reset timeout. |
| R5 | Digest canonical form | ASCII-0x1F field separator, LF row terminator, SHA-256 hex, 4 critical columns only. |
| R6 | Gameseed plumbing | Derived per-run start-script at `build/tmp/`, gameseed `0x42424242` in `[modoptions]`. Run-indexed output paths. |
| R7 | Threshold policy | CI-config constant; social ratchet via CI comment; no auto-ratchet. |
| R8 | Python wiring | `highbar_client.behavioral_coverage` submodule; stdlib-only new deps; `uv run --project clients/python python -m …`. |
| R9 | Channel-C arms | In registry with `required_capability="none"`, sentinel predicate, excluded from success-rate denominator. |
| R10 | Digest vs. commits | Reproducibility gate is within-run; digest is allowed to change across commits. |

All NEEDS CLARIFICATION items from the plan's Technical Context are
resolved. Proceed to Phase 1 (data-model, contracts, quickstart).

# Contract: Bootstrap plan & state-reset protocol

**Feature**: 003-snapshot-arm-coverage
**Consumes**: FR-003a, FR-003b, FR-012; data-model §3; research.md §R3–R4

---

## Static plan definition

Defined in
`clients/python/highbar_client/behavioral_coverage/bootstrap.py` as
a module-level tuple of `BuildStep` dataclass instances. Order
matters and is preserved across runs (tuples are hashable and
iteration-deterministic).

```python
from dataclasses import dataclass
from highbar_client.highbar import Vector3

@dataclass(frozen=True)
class BuildStep:
    step_index: int
    capability: str           # tag from capability vocabulary
    def_id: str               # BAR unit def name (e.g., "armmex")
    builder_capability: str   # "commander", "factory_ground", "factory_air"
    relative_position: Vector3  # relative to commander spawn; n/a for factory-queued
    timeout_seconds: float
```

### Default plan

```python
DEFAULT_BOOTSTRAP_PLAN: tuple[BuildStep, ...] = (
    BuildStep(1, "mex",              "armmex",   "commander",      Vector3(+96, 0,   0), 10.0),
    BuildStep(2, "solar",            "armsolar", "commander",      Vector3(-96, 0,   0), 10.0),
    BuildStep(3, "factory_ground",   "armvp",    "commander",      Vector3(+160, 0, +96), 45.0),
    BuildStep(4, "factory_air",      "armap",    "commander",      Vector3(-160, 0, +96), 45.0),
    BuildStep(5, "radar",            "armrad",   "commander",      Vector3(+96, 0, -96), 10.0),
    BuildStep(6, "builder",          "armck",    "factory_ground", Vector3(0, 0, 0),     30.0),
    BuildStep(7, "cloakable",        "armpeep",  "factory_air",    Vector3(0, 0, 0),     30.0),
)
```

**Wall-clock budget: ≤ 90s end-to-end under the parallel-pipelined
path (SC-003's bootstrap-plan budget).** The commander queues build
orders for steps 1–5 in parallel (its internal build queue
processes them pipelined, not strictly serially), and steps 6–7
overlap at two independent factories once steps 3/4 finish.
Critical path: `max(commander-built step timeouts) +
max(factory-produced step timeouts)` = `45s (factory_ground or
factory_air) + 30s (armck or armpeep)` = **75s ≤ 90s**. The
180s-if-serialised number is a worst-case degenerate path the
plan does not exercise. Per-step `timeout_seconds` is the upper
bound on any one step firing `bootstrap_timeout`, not a
sequential-sum contribution.

### Step legality rules

- No single `timeout_seconds` may exceed 45s for
  `builder_capability == "commander"` steps or 30s for
  factory-produced steps; the plan's critical path
  (`max(commander-step timeouts) + max(factory-produced-step
  timeouts)`) MUST be ≤ 90 seconds (SC-003's bootstrap-plan
  budget). Enforced by unit test
  `test_plan_critical_path_within_90s`.
- Each `capability` tag MUST appear exactly once (bootstrap does
  not provision redundant capabilities; if a Phase-2 arm destroys
  its target, the reset (§3) handles re-provisioning).
- `relative_position` for factory-queued steps is ignored by the
  dispatcher (the factory picks its own rally). Field retained for
  symmetry with commander-built steps.
- `def_id` strings correspond to Armada-side BAR unit defs. If the
  test start-script changes team, the plan must be forked; no
  parameterization is done for this feature (`minimal.startscript`
  is Armada-vs-Armada).

---

## Plan execution protocol (Phase 1)

```
Input:  live session (Hello'd, AI-role token acquired, StreamState open)
Output: BootstrapContext (per data-model §3d)
        OR abort with error=bootstrap_timeout / bootstrap_failed
```

1. **Capture commander spawn.** Read the first `StateSnapshot` on
   the StreamState (already delivered as the Hello one-shot, or
   force via `RequestSnapshot`). Find the `own_units[]` entry with
   `def_id == <armcom def_id>`; record `commander_unit_id` and
   `commander_position`.

2. **Issue steps 1–5 (commander-built).** For each step where
   `builder_capability == "commander"`:
   - Construct `BuildUnitCommand(builder_unit_id=commander_unit_id,
     def_id=<resolved numeric>, target_position=commander_position +
     step.relative_position)`.
   - Issue via `SubmitCommands` in a single `CommandBatch` per
     step (the commander queues them; the driver does not manually
     serialize).
   - Record issue timestamp (wall-clock; used only for timeout
     bookkeeping, not for verification).

3. **Wait for steps 1–5 to complete.** Sampled from each periodic
   snapshot: a step is "complete" when `own_units[]` contains an
   entry with `def_id == step.def_id` AND `under_construction ==
   false`. Per-step timeout: `step.timeout_seconds`. On any step
   timing out → abort with `bootstrap_timeout` and emit a CSV
   where all 66 rows have `dispatched=false, verified=na,
   error=precondition_unmet`. Digest still computed.

4. **Issue steps 6–7 (factory-queued).** For each step where
   `builder_capability == "factory_ground" | "factory_air"`:
   - Look up the factory's `unit_id` from the current snapshot
     (the step 3/4 product, now with `under_construction=false`).
   - Construct `BuildUnitCommand(builder_unit_id=<factory_id>,
     def_id=<resolved numeric>, target_position=…)`. The factory
     handles rally internally; `target_position` is the factory's
     position by default.
   - Issue via `SubmitCommands`.

5. **Wait for steps 6–7.** Same completion criterion as steps 1–5.

6. **Snapshot the manifest.** Once all 7 steps report complete,
   capture a fresh snapshot (via `RequestSnapshot`) and compute
   the BootstrapManifest: `tuple(sorted((def_id, count) for def_id,
   count in own_units_by_def.items()))`. Store on
   BootstrapContext.

7. **Populate `capability_units` dict.** Map each capability tag
   to the `unit_id` of the first (smallest `unit_id`)
   corresponding `own_units[]` entry. This is the unit Phase-2
   arms will target when they declare the tag.

8. **Populate `enemy_seed_id` (best-effort).** Scan
   `visible_enemies[]`; if any entry is present, record the first
   entry's `unit_id`. Otherwise `None` (attack arms will skip with
   `precondition_unmet`).

9. **Transition to BootstrapReady.** Phase 2 begins.

---

## 3. Bootstrap-state reset protocol (between arms)

Executed after each arm's verify-predicate resolves, before the
next arm dispatches. Scoped per-arm; invariant across arms.

### Reset algorithm

```
Input:  BootstrapContext (with frozen manifest)
Output: BootstrapContext with capability_units refreshed
        OR abort with error=bootstrap_reset_failed
```

1. **Force a fresh snapshot.** Call `RequestSnapshot`, await the
   forced snapshot on the open StreamState.

2. **Diff against manifest.** Compute current
   `own_units_by_def[def_id] = count` and diff against
   `context.manifest`. For each `(def_id, expected_count)` pair in
   the manifest:
   - If `current_count >= expected_count`: skip (no reissue).
   - If `current_count < expected_count`: record
     `shortage[def_id] = expected_count - current_count`.

3. **Reissue short-count units in deterministic order.** Iterate
   `shortage` in ascending `def_id` byte order. For each shorted
   def:
   - Look up which BootstrapStep produced that def.
   - Identify the builder: if `step.builder_capability ==
     "commander"`, target the commander (if alive; if the
     commander is missing, this is a fatal run-abort —
     `bootstrap_reset_failed` with detail `commander_lost`). If
     factory-queued, target the factory with the smallest
     `unit_id` matching `factory_*` (if the factory itself is
     missing, first reissue the factory, then the factory-output,
     recursively bounded by the overall 10-second timeout).
   - Issue `BuildUnitCommand` via `SubmitCommands`.
   - Repeat `shortage[def_id]` times.

4. **Wait for manifest re-match.** Sample each periodic snapshot;
   return to BootstrapReady when the manifest diff is empty (no
   shortages). Per-reset timeout: **10.0 seconds** (FR-003b).

5. **On timeout.** Abort the remainder of the run. All arms not
   yet dispatched get `dispatched=false, verified=na,
   error=bootstrap_reset_failed`. The 66-row CSV is still emitted;
   digest is still computed. SC-004 reproducibility depends on
   which arm triggered the reset failure, which is recorded in
   the run's stderr log for post-hoc analysis.

### Determinism invariants

- **Diff sort order.** Shortages are iterated in ascending
  `def_id` byte order (so `"armap"` before `"armck"` before
  `"armcom"` etc.). No dict-iteration-order dependence.
- **Issue order.** Within a `def_id`'s shortage, commands are
  issued in the order of the BootstrapPlan's step_index (which
  matches the deterministic default plan).
- **Completion detection.** Based on snapshot sampling at the
  effective cadence; not wall-clock. This means a run on a
  congested host still produces the same `verified/dispatched/error`
  columns — it just takes longer.
- **No wall-clock in the decision path.** Timeouts are
  wall-clock, but they only fail-close (abort); they never change
  the CSV content for arms that ran successfully before the
  timeout.

---

## 4. Bootstrap manifest serialization

The manifest is internal to the driver and is not persisted.
However, for debugging, each run emits the captured manifest to
stderr under a `bootstrap-manifest:` prefix (JSON-serialized).

Example:

```
bootstrap-manifest: [["armap",1],["armck",1],["armcom",1],["armmex",1],["armpeep",1],["armrad",1],["armsolar",1],["armvp",1]]
```

This line is the first `bootstrap-manifest:` emission in the run
log. If later resets reissue units, they do not log a fresh
manifest (the same manifest is the target throughout Phase 2).

---

## 5. Test coverage

- **Unit tests** (pytest, `clients/python/tests/test_bootstrap.py`):
  - `test_plan_critical_path_within_90s`: critical path
    (max commander-built-step timeout + max factory-produced-step
    timeout) ≤ 90s.
  - `test_plan_capabilities_unique`: every capability tag appears
    exactly once in the plan.
  - `test_manifest_sort_deterministic`: given a synthetic
    `own_units[]`, the computed manifest is a sorted tuple.
  - `test_reset_diff_deterministic`: given a synthetic snapshot
    with a 2-unit shortage, the shortage dict iterates in
    ascending `def_id`.

- **Headless acceptance** (`behavioral-reproducibility.sh`, US6):
  runs the macro driver 5× and asserts the digests match. Any
  non-determinism in bootstrap or reset produces a digest drift
  that this script catches.

- **No integration test needed.** The mock engine does not
  produce a realistic `own_units[]` progression; the reset
  algorithm's behavior is verified in Python unit tests
  against synthetic snapshots.

# Data Model: Snapshot-grounded behavioral verification of AICommand arms

**Feature**: 003-snapshot-arm-coverage
**Date**: 2026-04-21
**Status**: Complete
**Sources**: spec.md §Key Entities, research.md §R1–R10

This document defines every entity introduced or extended by this
feature: the fields they carry, the relationships between them, the
validation rules, and the state transitions where applicable. Wire
encoding for the two proto-level entities (`SnapshotTickConfig`
equivalent on the wire = `StateSnapshot.effective_cadence_frames`;
`RequestSnapshotRequest` / `RequestSnapshotResponse`) lives in
`contracts/`; this file is the authoritative definition the contracts
encode.

---

## 1. BehavioralTestCase

One row in the macro driver's arm registry. There are exactly 66 of
these (FR-004) — one per arm declared in the `AICommand` oneof at
`proto/highbar/commands.proto`.

**Fields:**

| Field | Type | Notes |
|---|---|---|
| `arm_name` | `str` | UTF-8, case-sensitive. The oneof arm name (e.g., `"move_unit"`, `"build_unit"`, `"attack_unit"`, `"set_god_mode"`). Primary key. |
| `category` | `str` | One of `"channel_a_command"`, `"channel_b_query"`, `"channel_c_lua"` (from 002's contracts/aicommand-arm-map.md). Included in the CSV for human readability, excluded from the digest. |
| `required_capability` | `str` | Tag from the capability vocabulary in §2 below, or `"none"` for arms that don't need a target unit (e.g., chat, debug-set). |
| `input_builder` | `Callable[[BootstrapContext], CommandBatch]` | Pure function that takes the live match's BootstrapContext (commander unit, factory outputs, map metadata) and returns a valid `CommandBatch` proto. Must not read wall-clock time or rng. |
| `verify_predicate` | `Callable[[SnapshotPair, DeltaLog], VerificationOutcome]` or sentinel `NotWireObservable` | Takes the SnapshotPair the driver captured around dispatch + any delta events observed in the test window, returns a VerificationOutcome. Pure — same inputs always yield the same outcome. |
| `verify_window_frames` | `int` | Frames to wait between pre- and post-snapshot. Default 120 (4s @ 30fps). Per-arm overridable for arms with known slow effects (Build ≈ 150, Reclaim ≈ 300). |
| `rationale` | `str` | Free text. For arms registered as `NotWireObservable`, this is the sentinel rationale the CSV prints in `evidence`. For normal arms, it's a one-line comment describing the verification approach (not CSV-emitted). |

**Validation rules:**

- `arm_name` MUST match one of the 66 oneof arm names declared in
  `proto/highbar/commands.proto` AICommand. Registry loader asserts
  this at import time; mismatch = `RegistryError`, fail-fast before
  any match boots.
- `required_capability` MUST be a key in the capability vocabulary
  (§2) or the literal `"none"`.
- `verify_window_frames` MUST be in `[30, 900]` (1s to 30s). Outside
  that range suggests the verifier design is wrong (too tight =
  race, too loose = multi-arm overlap).
- If `verify_predicate` is `NotWireObservable`, `required_capability`
  MUST be `"none"` and `category` MUST be `"channel_c_lua"` (the
  sentinel is only legal for Lua-only arms per spec §Out of Scope).

**Relationships:**

- Registry is `dict[arm_name → BehavioralTestCase]` in Python; on
  disk it's the `registry.py` module (one dict literal, not a CSV,
  so Python syntax checkers catch typos at import).
- Each BehavioralTestCase produces exactly one CoverageReport row
  (§5).

---

## 2. Capability Vocabulary

Tag vocabulary used by `BehavioralTestCase.required_capability` and
mirrored by `BootstrapPlan` step outputs (§3). Not a runtime entity
— a closed set of string constants defined in
`capabilities.py`.

| Tag | Meaning | Example unit def (Armada, `minimal.startscript`) |
|---|---|---|
| `commander` | The commander unit. Always provisioned by start-script. | `armcom` |
| `mex` | A metal extractor (economy sanity + reclaimable target for some arms). | `armmex` |
| `solar` | A solar collector (secondary economy target). | `armsolar` |
| `radar` | A radar structure (target for `SetRepeat`, `Guard`-on-structure arms). | `armrad` |
| `factory_ground` | A factory that produces ground units. Target for factory-arm BuildUnit, Repeat, etc. | `armvp` |
| `factory_air` | A factory that produces aircraft. Target for aircraft-specific factory arms. | `armap` |
| `builder` | A mobile constructor (factory output). Target for assisted-build, reclaim, capture arms. | `armck` |
| `cloakable` | A unit with cloak capability (factory output). Target for `SetCloak` arm. | `armpeep` |
| `none` | Arm does not require a target unit (e.g., debug-set, chat). |  |

**Validation rules:**

- Vocabulary is closed. Adding a new tag requires editing
  `capabilities.py` AND adding a corresponding step to the
  BootstrapPlan (§3) so the capability is provisioned.
- Each capability tag SHOULD map to exactly one live unit in the
  bootstrap manifest. Multi-instance capabilities (e.g., two mexes)
  are out of scope for this feature — the macro driver picks the
  first matching unit deterministically.

---

## 3. BootstrapPlan and BootstrapContext

An ordered list of `BuildStep` entries the macro driver issues in
Phase 1 (before any arm-under-test is dispatched). Produced deterministically
from the gameseed and the starting commander position.

### 3a. BuildStep

| Field | Type | Notes |
|---|---|---|
| `step_index` | `int` | 1-based. Determines issue order. |
| `capability` | `str` | Tag from §2. |
| `def_id` | `str` | BAR unit def name (e.g., `"armmex"`). The macro driver resolves this to a numeric `def_id` by consulting the `UnitDefResolver` session helper (a thin wrapper around `HighBarProxy.InvokeCallback` — zero new proto surface). |
| `builder_capability` | `str` | Capability tag whose unit issues this step's build order. Ground/sea structures = `"commander"`; factory outputs = `"factory_ground"` or `"factory_air"`. |
| `relative_position` | `Vector3` | Offset from the commander spawn position, in engine elmos. Step 1's commander-spawn is sourced from the first post-bootstrap snapshot's `own_units[commander].position`. |
| `timeout_seconds` | `float` | Per-step build timeout. On exceed → bootstrap_timeout fault (spec SC-003). |

### 3b. Default BootstrapPlan (from research.md §R3)

| # | capability | def_id | builder | offset (x, 0, z) | timeout |
|---|---|---|---|---|---|
| 1 | `mex` | `armmex` | `commander` | (+96, 0, 0) | 10s |
| 2 | `solar` | `armsolar` | `commander` | (-96, 0, 0) | 10s |
| 3 | `factory_ground` | `armvp` | `commander` | (+160, 0, +96) | 45s |
| 4 | `factory_air` | `armap` | `commander` | (-160, 0, +96) | 45s |
| 5 | `radar` | `armrad` | `commander` | (+96, 0, -96) | 10s |
| 6 | `builder` | `armck` | `factory_ground` | n/a (factory queue) | 30s |
| 7 | `cloakable` | `armpeep` | `factory_air` | n/a (factory queue) | 30s |

**Total budget: ≤90s** (matches SC-003 bootstrap-plan budget).

### 3c. BootstrapManifest

Derived from the plan at first successful completion. A sorted list
of `(def_id, count)` pairs summarising the `own_units[]` contents
Phase 2 expects between arms. For the default plan:

```
[("armap", 1), ("armck", 1), ("armcom", 1), ("armmex", 1),
 ("armpeep", 1), ("armrad", 1), ("armsolar", 1), ("armvp", 1)]
```

Stored as a frozen tuple on the BootstrapContext; used by the reset
loop (§4) to diff the post-arm `own_units[]` and decide what to
reissue.

### 3d. BootstrapContext

Container object the driver threads through input-builder calls and
reset invocations. Populated once Phase 1 completes.

| Field | Type | Notes |
|---|---|---|
| `commander_unit_id` | `int` | Populated from the pre-bootstrap snapshot. Stable for the run unless the commander dies (fatal fault → abort run). |
| `commander_position` | `Vector3` | Engine-elmo coordinates at bootstrap start. Anchors BuildStep offsets. |
| `capability_units` | `dict[str, int]` | Map from capability tag to `unit_id`. Freshened after each reset. |
| `enemy_seed_id` | `int \| None` | For attack-arm predicates: the `unit_id` of the first `visible_enemies[]` entry observed after Phase 1. None if none were visible before Phase 2 began → attack arms skip with `precondition_unmet`. |
| `manifest` | `tuple[tuple[str, int], ...]` | BootstrapManifest (§3c). |

**State transitions:**

```
     Init (driver start)
        │
        ▼
     BootstrapPending ─── (step timeout) ──▶ BootstrapFailed (abort, emit all-precondition_unmet CSV)
        │
        │ all steps complete + manifest matched
        ▼
     BootstrapReady ─── arm dispatched ──▶ ArmVerifying
                                                │
                                                ▼
                                        ArmResolved (outcome recorded)
                                                │
                                                ▼
                                        ResetPending
                                        │      │
                                        │      │ (reset timeout)
                                        │      ▼
                                        │   ResetFailed (abort, mark remaining as bootstrap_reset_failed)
                                        │
                                        │ manifest re-matched
                                        ▼
                                     BootstrapReady ── next arm ─▶ …
                                        │
                                        │ all 66 arms resolved
                                        ▼
                                     ReportEmit (CSV + digest, exit)
```

---

## 4. SnapshotPair

Container for the two snapshots the verify-predicate diffs. Captured
by the macro driver around each arm's dispatch.

| Field | Type | Notes |
|---|---|---|
| `before` | `StateSnapshot` | Snapshot captured immediately before the `SubmitCommands` call. Either delivered via `RequestSnapshot` or by waiting for the next periodic tick, whichever arrives first. |
| `after` | `StateSnapshot` | Snapshot captured `verify_window_frames` frames after the `before` snapshot (sourced from the periodic stream). |
| `dispatched_at_frame` | `uint32` | `before.frame_number` + (frame of dispatch - before's frame), approximately. Used only for evidence strings, not for verification. |
| `delta_log` | `list[DeltaEvent]` | All `DeltaEvent` entries observed between `before` and `after`. Shared with the verify-predicate so arms that verify via events (e.g., `EnemyDestroyed`) can consult it. |

**Validation rules:**

- `before.frame_number < after.frame_number` (strict). If equal or
  reversed, the driver logs a scheduling bug and the verify returns
  `internal_error`.
- `after.frame_number - before.frame_number >= verify_window_frames`
  (snapshot stream ran at or below expected cadence). Less than that
  indicates the halving cadence (FR-001) kicked in; verify-predicates
  tolerate this by reading `after.effective_cadence_frames` and
  extending their patience accordingly.

---

## 5. VerificationOutcome

The return value of a verify-predicate. Small closed-enum types to
keep the digest-critical columns canonicalizable.

| Field | Type | Allowed values |
|---|---|---|
| `verified` | `str` | `"true"`, `"false"`, `"na"` (lowercase). The digest uses the string form; the Python type is `Literal["true", "false", "na"]`. |
| `evidence` | `str` | Human-readable. Format varies per predicate family — e.g., `"position dx=503.2 dz=0.0 (threshold 100)"`, `"unit_count_delta=+1 def=armmex under_construction=true"`. Excluded from digest. |
| `error` | `str` | Empty or one of the fixed lowercase tokens: `dispatcher_rejected`, `effect_not_observed`, `target_unit_destroyed`, `cheats_required`, `precondition_unmet`, `bootstrap_reset_failed`, `not_wire_observable`, `timeout`, `internal_error`. |

**Consistency rules:**

- `verified="true"` ⇒ `error=""`.
- `verified="false"` ⇒ `error` ∈ {`effect_not_observed`,
  `target_unit_destroyed`, `timeout`, `internal_error`}.
- `verified="na"` ⇒ `error` ∈ {`dispatcher_rejected`,
  `cheats_required`, `precondition_unmet`,
  `bootstrap_reset_failed`, `not_wire_observable`}.

`na` rows do not count in the success-rate denominator (FR-007).
`false` rows do (they're wire-observable attempts that didn't
verify, and thus honest failures to include in the metric).

---

## 6. CoverageReport

The final CSV artifact. One row per BehavioralTestCase; exactly 66
data rows plus a header.

**Header:**

```
arm_name,category,dispatched,verified,evidence,error
```

**Per-row columns:**

| Column | Source | Digest? |
|---|---|---|
| `arm_name` | `BehavioralTestCase.arm_name` | ✓ |
| `category` | `BehavioralTestCase.category` | ✗ |
| `dispatched` | `"true"` iff the driver called `SubmitCommands` with the arm's batch and the gateway acked; `"false"` otherwise. | ✓ |
| `verified` | `VerificationOutcome.verified` | ✓ |
| `evidence` | `VerificationOutcome.evidence` | ✗ |
| `error` | `VerificationOutcome.error` | ✓ |

**Sort:** ascending `arm_name`, UTF-8 byte order, case-sensitive.

**Quoting:** RFC 4180 CSV quoting for the readable artifact
(`evidence` may contain commas). The digest serialisation uses
0x1F separators and is not CSV-escaped.

**Output paths:**

- Artifact CSV: `build/reports/aicommand-behavioral-coverage.csv`
- Digest sidecar: `build/reports/aicommand-behavioral-coverage.digest`
  (64 lowercase hex chars + LF).
- Reproducibility-run outputs: `build/reports/run-<N>/
  aicommand-behavioral-coverage.{csv,digest}` for N ∈ [1..5].

---

## 7. SnapshotTickConfig

Plugin-side configuration for the snapshot tick. Defined once in
`data/config/grpc.json`, loaded by the gateway module at startup,
immutable for the lifetime of the plugin instance.

**JSON schema (embedded in `grpc.json`):**

```json
{
  "snapshot_tick": {
    "snapshot_cadence_frames": 30,
    "snapshot_max_units": 1000
  }
}
```

| Field | Type | Default | Range |
|---|---|---|---|
| `snapshot_cadence_frames` | `uint32` | 30 | [1, 1024] |
| `snapshot_max_units` | `uint32` | 1000 | [1, 100000] |

**Defaults rationale:** 30 frames ≈ 1s at 30fps headless (spec
FR-001); 1000 units chosen per clarification Q2 as the raised cap
from the earlier 500-unit baseline.

**Back-compat:** missing `snapshot_tick` object in `grpc.json` ⇒ all
defaults applied. No version-bump required.

**Validation rules:**

- `snapshot_cadence_frames` out of range ⇒ plugin refuses to load
  with a structured `[hb-gateway] fault cfg_invalid` log line. Same
  failure mode 002 established for malformed UDS paths.
- `snapshot_max_units` out of range ⇒ same.

**State the scheduler maintains at runtime (not on disk):**

| Field | Type | Notes |
|---|---|---|
| `next_snapshot_frame` | `uint32` | When `current_frame >= next_snapshot_frame` AND gateway is Healthy, emit a snapshot. Updated after every emission. |
| `effective_cadence_frames` | `uint32` | Current interval. Starts at config value; doubles on over-cap emissions (up to 1024); snaps back to config value on under-cap emissions. |
| `pending_request` | `std::atomic<bool>` | Set by `RequestSnapshot` worker handlers; drained by engine-thread tick. At most one extra snapshot per frame regardless of caller count (FR-006). |

---

## 8. Entity Relationships (summary)

```
Registry (dict[str, BehavioralTestCase])
  │
  ├── 66 × BehavioralTestCase
  │       ├── .required_capability ──▶ Capability Vocabulary (§2)
  │       │                              │
  │       │                              ▼
  │       │                           BootstrapPlan (§3) produces:
  │       │                             ├── BuildStep × 7
  │       │                             ├── BootstrapManifest
  │       │                             └── BootstrapContext
  │       │
  │       ├── .input_builder ──(consumes)──▶ BootstrapContext
  │       │
  │       └── .verify_predicate ──(consumes)──▶ SnapshotPair (§4)
  │                                 │
  │                                 ▼
  │                           VerificationOutcome (§5)
  │
  └── collated into ──▶ CoverageReport (§6)
                          │
                          ├── CSV (build/reports/…csv)
                          └── digest sidecar (…digest)

Plugin-side:
  data/config/grpc.json
       │
       ▼
  SnapshotTickConfig (§7) ──▶ SnapshotTick scheduler ──▶ StateSnapshot.effective_cadence_frames
                                            │                       │
                                            └── triggered by ──▶ OnFrameTick (engine thread)
                                            │
                                            └── forced by ──▶ RequestSnapshot RPC (contracts/request-snapshot.md)
```

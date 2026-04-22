# Contract: Behavioral arm registry

**Feature**: 003-snapshot-arm-coverage
**Consumes**: FR-003, FR-005, FR-013; data-model §1–§2; research.md §R8–§R9
**Scope**: Python-internal format consumed by the macro driver.

---

## File location

```
clients/python/highbar_client/behavioral_coverage/registry.py
```

Single dict literal mapping arm names to `BehavioralTestCase`
dataclass instances. Module-level, top-of-file; no dynamic
registration. Registry completeness is validated at import time
(the module raises `RegistryError` if the arm set does not exactly
equal the 66 oneof arm names declared in
`proto/highbar/commands.proto` `AICommand`).

---

## `BehavioralTestCase` dataclass

```python
from dataclasses import dataclass
from typing import Callable, Literal, Union

from highbar_client.highbar import StateSnapshot, DeltaEvent, CommandBatch

Verified = Literal["true", "false", "na"]
ErrorCode = Literal[
    "",
    "dispatcher_rejected",
    "effect_not_observed",
    "target_unit_destroyed",
    "cheats_required",
    "precondition_unmet",
    "bootstrap_reset_failed",
    "not_wire_observable",
    "timeout",
    "internal_error",
]

@dataclass(frozen=True)
class VerificationOutcome:
    verified: Verified
    evidence: str
    error: ErrorCode = ""

InputBuilder = Callable[["BootstrapContext"], CommandBatch]
VerifyPredicate = Union[
    Callable[["SnapshotPair", "DeltaLog"], VerificationOutcome],
    "NotWireObservable",  # sentinel type
]

@dataclass(frozen=True)
class BehavioralTestCase:
    arm_name: str                     # e.g. "move_unit"
    category: Literal["channel_a_command", "channel_b_query", "channel_c_lua"]
    required_capability: str          # from capability vocabulary (below)
    input_builder: InputBuilder
    verify_predicate: VerifyPredicate
    verify_window_frames: int = 120
    rationale: str = ""
```

### Field semantics

- **`arm_name`**: UTF-8, case-sensitive. Must match the oneof arm
  name exactly (e.g., `"move_unit"`, not `"MoveUnit"` or
  `"MoveUnitCommand"`).
- **`category`**: one of `channel_a_command`, `channel_b_query`,
  `channel_c_lua` (mirrors 002's taxonomy).
- **`required_capability`**: key from the closed vocabulary below.
- **`input_builder`**: pure function that returns a `CommandBatch`
  proto. Does not read wall-clock time, does not call rng.
- **`verify_predicate`**: pure function, OR the `NotWireObservable`
  sentinel (Channel-C only).
- **`verify_window_frames`**: integer in `[30, 900]`; default 120.
- **`rationale`**: free text; surfaces in the CSV `evidence` column
  only when the sentinel predicate fires.

### Pure-function discipline

Both `input_builder` and `verify_predicate` MUST be pure:

- No wall-clock reads (`time.time()`, `time.monotonic()`).
- No rng (`random`, `secrets`).
- No filesystem / network I/O.
- No mutation of global state or captured variables.
- Same inputs → same outputs, always.

This is what FR-012's digest-stability invariant demands. The
driver enforces it socially (code review), not mechanically —
there is no interpreter sandbox here. Reviewers flag any time /
rng / I/O import inside `registry.py` or `predicates.py`.

---

## Required-capability vocabulary

Closed set. Defined in
`clients/python/highbar_client/behavioral_coverage/capabilities.py`
as a frozen enum-equivalent (Python `Literal` union backed by a
tuple constant).

```python
CAPABILITY_TAGS = (
    "commander",
    "mex",
    "solar",
    "radar",
    "factory_ground",
    "factory_air",
    "builder",
    "cloakable",
    "none",
)
```

| Tag | Provisioned by (bootstrap step) | Typical arm examples |
|---|---|---|
| `commander` | start-script (always present) | `move_unit`, `self_destruct`, `stop`, `guard` |
| `mex` | BootstrapStep 1 (`armmex`) | `reclaim_unit` (targets a mex for reclaim), `repair_unit` |
| `solar` | BootstrapStep 2 (`armsolar`) | `capture_unit` (captures a solar — cross-team would need enemy LOS; same-team sanity) |
| `radar` | BootstrapStep 5 (`armrad`) | `set_repeat` on structure, `guard` on structure |
| `factory_ground` | BootstrapStep 3 (`armvp`) | `build_unit` (factory builds the unit), `set_repeat` on factory, `wait` |
| `factory_air` | BootstrapStep 4 (`armap`) | same family, aircraft-specific |
| `builder` | BootstrapStep 6 (`armck`) | `assist_build`, `patrol`, `area_attack` |
| `cloakable` | BootstrapStep 7 (`armpeep`) | `set_cloak`, `set_stealth` |
| `none` | n/a | Channel-C Lua arms, debug-set arms, chat arms |

Additions to this vocabulary are allowed but require a
corresponding new BootstrapStep in `bootstrap-plan.md`. A new tag
without provisioning is a registry validation error
(`RegistryError: unprovisioned_capability`).

---

## `NotWireObservable` sentinel

```python
class NotWireObservable:
    """Sentinel predicate for Channel-C Lua-only arms.

    The macro driver recognizes instances of this class by type,
    not by value. Instantiate with a rationale string that will
    appear in the CSV `evidence` column.
    """
    def __init__(self, rationale: str):
        self.rationale = rationale
```

When the driver encounters a `BehavioralTestCase.verify_predicate`
that is an instance of `NotWireObservable`:

1. It still runs `input_builder` and dispatches the command batch
   (so the `dispatched` column is accurate).
2. It skips snapshot capture entirely for this arm (saves ~4s per
   Channel-C row of wall-clock time).
3. It records `VerificationOutcome(verified="na",
   evidence=<sentinel.rationale>, error="not_wire_observable")`.
4. It excludes the arm from the success-rate denominator
   (FR-005).

### Sentinel legality

Only `category="channel_c_lua"` arms may use the sentinel.
`required_capability` MUST be `"none"` for sentinel arms.
Violations raise `RegistryError` at import time.

---

## Import-time validation rules

The registry module, on import, asserts the following:

1. **Completeness.** `set(registry.keys())` exactly equals the set
   of 66 oneof arm names from `proto/highbar/commands.proto`
   `AICommand`. Extraction is done by parsing the compiled
   `highbar_client.highbar.commands_pb2.AICommand.DESCRIPTOR.fields_by_name`.
   Mismatch → `RegistryError: arm_set_mismatch`.
2. **Capability validity.** Every `required_capability` is in
   `CAPABILITY_TAGS`. Unknown → `RegistryError:
   unknown_capability`.
3. **Sentinel legality.** See above — sentinel arms are
   Channel-C + `required_capability="none"` only.
4. **Window bounds.** `verify_window_frames` ∈ `[30, 900]`.
5. **Unique arm names.** (Trivially true for a dict, but asserted
   against the discovered oneof set to catch typos like
   `"moveunit"` vs. `"move_unit"`.)

All assertions happen at `import highbar_client.behavioral_coverage`
time — failures crash the driver before any match boots. This
means a misconfigured registry is caught in unit tests and
pre-flight rather than silently mis-reporting coverage.

---

## Extension workflow

To add behavioral coverage for a newly-wired arm:

1. Write the input-builder function in `predicates.py` (or inline
   if one-liner).
2. Write the verify-predicate function, also in `predicates.py`.
3. Add the `BehavioralTestCase` entry to `registry.py`, keyed by
   the arm name.
4. If the arm needs a new capability, add the tag to
   `capabilities.py` AND a new step to `bootstrap-plan.md`'s plan.
5. Run `pytest clients/python/tests/test_behavioral_registry.py`
   to confirm all import-time validations pass.
6. Ratchet `HIGHBAR_BEHAVIORAL_THRESHOLD` in CI if this bumps the
   verified rate above the next 5pp step (per research.md §R7).

No changes to the macro driver's orchestrator are needed — all
arm-specific logic lives in the registry entry.

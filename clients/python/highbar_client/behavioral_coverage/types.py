# SPDX-License-Identifier: GPL-2.0-only
"""Shared dataclass types for the behavioral-coverage submodule.

Lives in its own module to keep cross-imports (registry.py <->
predicates.py <-> bootstrap.py) from looping through the heavier
registry dict literal.

Source: contracts/arm-registry.md §BehavioralTestCase dataclass;
data-model.md §§1, 4, 5.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Literal, Optional, Union

Verified = Literal["true", "false", "na"]

# Fixed vocabulary per contracts/behavioral-coverage-csv.md §1.
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
    """Return value from a verify-predicate (data-model §5).

    Consistency rules (enforced at CSV emit time, not here):
      verified='true'   → error=''
      verified='false'  → error ∈ {effect_not_observed, target_unit_destroyed,
                                    timeout, internal_error}
      verified='na'     → error ∈ {dispatcher_rejected, cheats_required,
                                    precondition_unmet, bootstrap_reset_failed,
                                    not_wire_observable}
    """

    verified: Verified
    evidence: str
    error: ErrorCode = ""


class NotWireObservable:
    """Sentinel predicate for Channel-C Lua-only arms.

    When the driver sees an instance of this class as a test case's
    `verify_predicate`, it:
      - dispatches the command batch normally (so `dispatched` is
        truthful);
      - records verified='na', error='not_wire_observable', with the
        rationale string surfaced in the CSV `evidence` column;
      - excludes the row from the success-rate denominator (FR-005).
    """

    __slots__ = ("rationale",)

    def __init__(self, rationale: str):
        self.rationale = rationale


@dataclass(frozen=True)
class SnapshotPair:
    """Container the driver threads into verify-predicates.

    `before` is captured immediately before dispatch (via
    RequestSnapshot when available, else the most recent periodic
    snapshot). `after` is captured at `before.frame_number +
    verify_window_frames` or later, also sourced from the periodic
    stream.
    """

    before: Any                      # highbar.v1.StateSnapshot
    after: Any                       # highbar.v1.StateSnapshot
    dispatched_at_frame: int
    delta_log: list[Any] = field(default_factory=list)


# Signatures kept as plain `Any` so registry.py's import-time validator
# doesn't drag in proto types at module-load (they load lazily via
# `from highbar_client.highbar import commands_pb2` inside the
# builder/predicate bodies).
InputBuilder = Callable[[Any], Any]                   # (BootstrapContext) -> CommandBatch
VerifyPredicate = Union[Callable[[SnapshotPair, list], VerificationOutcome],
                         NotWireObservable]


@dataclass(frozen=True)
class BehavioralTestCase:
    """One row in the arm registry (contracts/arm-registry.md)."""

    arm_name: str
    category: Literal["channel_a_command", "channel_b_query", "channel_c_lua"]
    required_capability: str
    input_builder: InputBuilder
    verify_predicate: VerifyPredicate
    verify_window_frames: int = 120
    rationale: str = ""


class RegistryError(RuntimeError):
    """Raised on import-time registry-validation failures."""


class CoverageReportError(RuntimeError):
    """Raised when the CSV emitter detects a consistency-rule violation."""


class GatewayNotHealthyError(RuntimeError):
    """Raised when RequestSnapshot returns scheduled_frame=0."""

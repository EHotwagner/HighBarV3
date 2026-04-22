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
from pathlib import Path
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
    audit_channel: Optional["AuditChannel"] = None
    audit_observability: "EvidenceShape" = "snapshot_diff"
    audit_phase_default: Literal["phase1", "phase2"] = "phase1"


class RegistryError(RuntimeError):
    """Raised on import-time registry-validation failures."""


class CoverageReportError(RuntimeError):
    """Raised when the CSV emitter detects a consistency-rule violation."""


class GatewayNotHealthyError(RuntimeError):
    """Raised when RequestSnapshot returns scheduled_frame=0."""


OutcomeBucket = Literal["verified", "dispatched-only", "blocked", "broken"]
EvidenceShape = Literal[
    "snapshot_diff",
    "engine_log",
    "not_wire_observable",
    "dispatch_ack_only",
]
AuditChannel = Literal[
    "channel_a_command",
    "channel_b_query",
    "channel_c_lua",
    "team_global",
    "drawer_only",
]
HypothesisClass = Literal[
    "phase1_reissuance",
    "effect_not_snapshotable",
    "target_missing",
    "cross_team_rejection",
    "cheats_required",
    "dispatcher_defect",
    "intended_noop",
    "engine_version_drift",
]


@dataclass(frozen=True)
class AuditRow:
    """One rendered row in the 004 gateway-command audit."""

    row_id: str
    kind: Literal["aicommand", "rpc"]
    arm_or_rpc_name: str
    category: str
    outcome: OutcomeBucket
    dispatch_citation: str
    evidence_shape: EvidenceShape
    gametype_pin: str
    engine_pin: str
    evidence_excerpt: str = ""
    reproduction_recipe: str = ""
    hypothesis_class: Optional[HypothesisClass] = None
    hypothesis_summary: str = ""
    falsification_test: str = ""
    channel: Optional[AuditChannel] = None
    notes: str = ""


@dataclass(frozen=True)
class HypothesisCandidate:
    rank: int
    hypothesis_class: HypothesisClass
    hypothesis_summary: str
    predicted_confirmed_evidence: str
    predicted_falsified_evidence: str
    test_command: str


@dataclass(frozen=True)
class HypothesisPlanEntry:
    arm_name: str
    related_audit_row_id: str
    candidates: tuple[HypothesisCandidate, ...]


@dataclass(frozen=True)
class V2V3LedgerRow:
    pathology_id: str
    pathology_name: str
    v2_source_citation: str
    v2_excerpt: str
    v3_status: Literal["fixed", "partial", "not-addressed"]
    v3_source_citation: str
    v3_mechanism: str
    audit_row_reference: str = ""
    hypothesis_plan_reference: str = ""
    residual_risk: str = ""


@dataclass(frozen=True)
class AuditArtifacts:
    """Filesystem destinations for the checked-in 004 deliverables."""

    repo_root: Path
    audit_dir: Path
    reports_dir: Path

# SPDX-License-Identifier: GPL-2.0-only
"""T020 — Bootstrap plan & state-reset determinism tests.

Contract: contracts/bootstrap-plan.md §5 Test coverage.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

import pytest

from highbar_client.behavioral_coverage.bootstrap import (
    DEFAULT_BOOTSTRAP_PLAN,
    BuildStep,
    Vector3,
    compute_manifest,
    critical_path_seconds,
    manifest_shortages,
    validate_plan,
)
from highbar_client.behavioral_coverage.types import RegistryError


@dataclass(frozen=True)
class FakeOwnUnit:
    """Shape-compatible stand-in for highbar.v1.OwnUnit so the tests
    don't need the proto runtime."""
    unit_id: int
    def_id: int


# ---- plan structure ------------------------------------------------------


def test_plan_critical_path_within_90s():
    """(max commander-built timeout) + (max factory-produced timeout) ≤ 90s."""
    assert critical_path_seconds(DEFAULT_BOOTSTRAP_PLAN) <= 90.0


def test_plan_capabilities_unique():
    """Each capability appears exactly once in the plan."""
    caps = [s.capability for s in DEFAULT_BOOTSTRAP_PLAN]
    assert len(caps) == len(set(caps))


def test_validate_plan_rejects_long_critical_path():
    bad = (
        BuildStep(1, "mex",           "armmex",  "commander",      Vector3(0,0,0), 60.0),
        BuildStep(2, "factory_ground", "armvp",  "commander",      Vector3(0,0,0), 60.0),
        BuildStep(3, "builder",        "armck",  "factory_ground", Vector3(0,0,0), 40.0),
    )
    with pytest.raises(RegistryError):
        validate_plan(bad)


def test_validate_plan_rejects_duplicate_capability():
    bad = (
        BuildStep(1, "mex", "armmex", "commander", Vector3(0,0,0), 10.0),
        BuildStep(2, "mex", "armmex", "commander", Vector3(0,0,0), 10.0),
    )
    with pytest.raises(RegistryError):
        validate_plan(bad)


# ---- manifest computation ------------------------------------------------


def test_manifest_sort_deterministic():
    """From a synthetic own_units[], compute_manifest yields a sorted tuple."""
    def_id_by_name = {
        "armcom": 1, "armmex": 2, "armsolar": 3, "armvp": 4,
        "armrad": 5, "armap": 6, "armck": 7, "armpeep": 8,
    }
    units: list[FakeOwnUnit] = [
        FakeOwnUnit(unit_id=100, def_id=1),   # armcom
        FakeOwnUnit(unit_id=101, def_id=2),   # armmex
        FakeOwnUnit(unit_id=102, def_id=4),   # armvp
        FakeOwnUnit(unit_id=103, def_id=3),   # armsolar
        FakeOwnUnit(unit_id=104, def_id=5),   # armrad
        FakeOwnUnit(unit_id=105, def_id=6),   # armap
        FakeOwnUnit(unit_id=106, def_id=7),   # armck
        FakeOwnUnit(unit_id=107, def_id=8),   # armpeep
    ]
    manifest = compute_manifest(units, def_id_by_name)
    # Expected: sorted tuple of (name, count), byte-order ascending.
    expected = (
        ("armap", 1), ("armck", 1), ("armcom", 1), ("armmex", 1),
        ("armpeep", 1), ("armrad", 1), ("armsolar", 1), ("armvp", 1),
    )
    assert manifest == expected

    # Deterministic re-computation produces the exact same tuple.
    units_reordered = list(reversed(units))
    assert compute_manifest(units_reordered, def_id_by_name) == expected


def test_reset_diff_deterministic():
    """Given a synthetic snapshot with 2-unit shortage, the shortage dict
    iterates in ascending def_name order."""
    def_id_by_name = {
        "armcom": 1, "armmex": 2, "armsolar": 3, "armvp": 4,
        "armrad": 5, "armap": 6, "armck": 7, "armpeep": 8,
    }
    target = (
        ("armap", 1), ("armck", 1), ("armcom", 1), ("armmex", 1),
        ("armpeep", 1), ("armrad", 1), ("armsolar", 1), ("armvp", 1),
    )
    current = (
        ("armap", 1), ("armcom", 1),        # missing armck, armmex, armpeep, armrad, armsolar, armvp
    )
    shortages = manifest_shortages(current, target)
    # Missing six def_ids, each with shortage 1.
    assert shortages == {
        "armck": 1, "armmex": 1, "armpeep": 1,
        "armrad": 1, "armsolar": 1, "armvp": 1,
    }
    # Iteration order is insertion order == sorted ascending.
    assert list(shortages.keys()) == sorted(shortages.keys())

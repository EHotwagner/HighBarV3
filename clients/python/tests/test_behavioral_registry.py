# SPDX-License-Identifier: GPL-2.0-only
"""T019 — Import-time validation of the behavioral arm registry.

Contract: contracts/arm-registry.md §Import-time validation rules.
"""

from __future__ import annotations

import pytest

from highbar_client.behavioral_coverage import REGISTRY
from highbar_client.behavioral_coverage import (
    _simplified_bootstrap_precondition_message,
)
from highbar_client.behavioral_coverage.bootstrap import BootstrapContext
from highbar_client.behavioral_coverage.capabilities import CAPABILITY_TAGS
from highbar_client.behavioral_coverage.registry import (
    _build_registry,
    _expected_arm_names,
    validate_registry,
)
from highbar_client.behavioral_coverage.types import (
    BehavioralTestCase,
    NotWireObservable,
    RegistryError,
)


def test_registry_completeness():
    """Every AICommand oneof arm has an entry; no extras."""
    expected = _expected_arm_names()
    assert len(expected) == 66, (
        f"proto/commands.proto AICommand oneof has {len(expected)} arms, "
        f"expected 66")
    assert set(REGISTRY.keys()) == expected


def test_registry_capability_vocab():
    """Every required_capability is in the closed vocabulary."""
    for name, case in REGISTRY.items():
        assert case.required_capability in CAPABILITY_TAGS, (
            f"{name}: unknown capability {case.required_capability!r}")


def test_sentinel_legality():
    """NotWireObservable is only used on channel_c_lua + required_capability=none."""
    for name, case in REGISTRY.items():
        if isinstance(case.verify_predicate, NotWireObservable):
            assert case.category == "channel_c_lua", (
                f"{name}: sentinel requires category=channel_c_lua, "
                f"got {case.category!r}")
            assert case.required_capability == "none", (
                f"{name}: sentinel requires required_capability=none, "
                f"got {case.required_capability!r}")


def test_window_bounds():
    """verify_window_frames ∈ [30, 900]."""
    for name, case in REGISTRY.items():
        assert 30 <= case.verify_window_frames <= 900, (
            f"{name}: verify_window_frames={case.verify_window_frames} "
            f"outside [30, 900]")


def test_registry_unique_arm_names():
    """Trivially true for a dict, but catch typos like 'moveunit' vs
    'move_unit' via the expected-set comparison."""
    expected = _expected_arm_names()
    assert set(REGISTRY.keys()) == expected


def test_registry_rejects_extra_entries():
    """If we add a spurious entry, validate_registry rejects it."""
    broken = dict(REGISTRY)
    broken["nonexistent_arm"] = BehavioralTestCase(
        arm_name="nonexistent_arm",
        category="channel_a_command",
        required_capability="commander",
        input_builder=lambda ctx: None,
        verify_predicate=lambda pair, deltas: None,
    )
    with pytest.raises(RegistryError):
        validate_registry(broken)


def test_registry_rejects_missing_entries():
    """If we drop an arm, validate_registry rejects it."""
    broken = dict(REGISTRY)
    some_name = next(iter(broken))
    del broken[some_name]
    with pytest.raises(RegistryError):
        validate_registry(broken)


def test_registry_validates_on_rebuild():
    """_build_registry's output is re-validatable."""
    built = _build_registry()
    validate_registry(built)  # should not raise


def test_simplified_bootstrap_blocks_target_missing_capture_area():
    ctx = BootstrapContext(
        commander_unit_id=42,
        capability_units={"commander": 42},
    )

    message = _simplified_bootstrap_precondition_message(
        "capture_area",
        REGISTRY["capture_area"],
        ctx,
    )

    assert message == (
        "simplified bootstrap does not provision the target fixture required for this arm"
    )


def test_simplified_bootstrap_keeps_safe_attack_dispatchable():
    ctx = BootstrapContext(
        commander_unit_id=42,
        capability_units={"commander": 42},
    )

    message = _simplified_bootstrap_precondition_message(
        "attack",
        REGISTRY["attack"],
        ctx,
    )

    assert message is None

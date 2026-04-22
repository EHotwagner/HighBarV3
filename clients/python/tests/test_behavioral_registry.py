# SPDX-License-Identifier: GPL-2.0-only
"""T019 — Import-time validation of the behavioral arm registry.

Contract: contracts/arm-registry.md §Import-time validation rules.
"""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from highbar_client.behavioral_coverage import REGISTRY
from highbar_client.behavioral_coverage import (
    _refresh_bootstrap_context,
    _simplified_bootstrap_precondition_message,
)
from highbar_client.behavioral_coverage.bootstrap import BootstrapContext, Vector3
from highbar_client.behavioral_coverage.capabilities import CAPABILITY_TAGS
from highbar_client.behavioral_coverage.registry import (
    _build_registry,
    _expected_arm_names,
    exact_custom_command_ids_for_arm,
    validate_registry,
)
from highbar_client.behavioral_coverage.types import (
    BehavioralTestCase,
    NotWireObservable,
    RegistryError,
)


@dataclass(frozen=True)
class FakePosition:
    x: float
    y: float
    z: float


@dataclass(frozen=True)
class FakeOwnUnit:
    unit_id: int
    def_id: int
    position: FakePosition
    health: float
    max_health: float


@dataclass(frozen=True)
class FakeEnemyUnit:
    unit_id: int
    def_id: int
    position: FakePosition
    health: float
    max_health: float


@dataclass(frozen=True)
class FakeFeature:
    feature_id: int
    def_id: int
    position: FakePosition
    reclaim_value_metal: float
    reclaim_value_energy: float


@dataclass(frozen=True)
class FakeSnapshot:
    own_units: tuple[FakeOwnUnit, ...]
    visible_enemies: tuple[FakeEnemyUnit, ...]
    map_features: tuple[FakeFeature, ...]
    frame_number: int = 0


@dataclass(frozen=True)
class FakeFeatureCreated:
    feature_id: int
    position: FakePosition


class FakeDeltaEvent:
    def __init__(self, feature_id: int, position: FakePosition):
        self.feature_created = FakeFeatureCreated(feature_id=feature_id, position=position)

    def WhichOneof(self, _name: str) -> str:
        return "feature_created"


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


def test_authoritative_fixture_preconditions_block_missing_capture_fixture():
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
        "live fixture dependency unavailable for this arm (capturable_target)"
    )


def test_simplified_bootstrap_keeps_attack_dispatchable_with_hostile_target():
    ctx = BootstrapContext(
        commander_unit_id=42,
        capability_units={"commander": 42},
        fixture_unit_ids={"hostile_target": 99},
        fixture_positions={"hostile_target": Vector3(5.0, 0.0, 6.0)},
        enemy_seed_id=99,
    )

    message = _simplified_bootstrap_precondition_message(
        "attack",
        REGISTRY["attack"],
        ctx,
    )

    assert message is None


def test_refresh_bootstrap_context_tracks_native_fixture_candidates():
    commander = FakeOwnUnit(
        unit_id=42,
        def_id=1,
        position=FakePosition(10.0, 0.0, 20.0),
        health=3250.0,
        max_health=3250.0,
    )
    builder = FakeOwnUnit(
        unit_id=77,
        def_id=2,
        position=FakePosition(12.0, 0.0, 24.0),
        health=690.0,
        max_health=690.0,
    )
    cloakable = FakeOwnUnit(
        unit_id=88,
        def_id=3,
        position=FakePosition(14.0, 0.0, 26.0),
        health=89.0,
        max_health=89.0,
    )
    transport = FakeOwnUnit(
        unit_id=99,
        def_id=4,
        position=FakePosition(16.0, 0.0, 28.0),
        health=265.0,
        max_health=265.0,
    )
    enemy = FakeEnemyUnit(
        unit_id=123,
        def_id=5,
        position=FakePosition(50.0, 0.0, 60.0),
        health=100.0,
        max_health=100.0,
    )
    feature = FakeFeature(
        feature_id=200,
        def_id=6,
        position=FakePosition(30.0, 0.0, 40.0),
        reclaim_value_metal=10.0,
        reclaim_value_energy=5.0,
    )
    snapshot = FakeSnapshot(
        own_units=(commander, builder, cloakable, transport),
        visible_enemies=(enemy,),
        map_features=(feature,),
    )
    ctx = BootstrapContext(
        commander_unit_id=42,
        commander_position=Vector3(10.0, 0.0, 20.0),
        capability_units={"commander": 42},
    )

    refreshed = _refresh_bootstrap_context(
        {"snapshots": [snapshot], "deltas": [FakeDeltaEvent(200, feature.position)]},
        ctx,
    )

    assert refreshed.capability_units["builder"] == 77
    assert refreshed.capability_units["cloakable"] == 88
    assert refreshed.fixture_unit_ids["transport_unit"] == 99
    assert refreshed.fixture_unit_ids["payload_unit"] == 77
    assert refreshed.fixture_unit_ids["capturable_target"] == 123
    assert refreshed.fixture_feature_ids["reclaim_target"] == 200
    assert refreshed.fixture_feature_ids["wreck_target"] == 200


def test_authoritative_fixture_preconditions_allow_capture_with_native_target():
    ctx = BootstrapContext(
        commander_unit_id=42,
        capability_units={"commander": 42},
        fixture_unit_ids={"capturable_target": 55},
        fixture_positions={"capturable_target": Vector3(1.0, 0.0, 2.0)},
    )

    message = _simplified_bootstrap_precondition_message(
        "capture_area",
        REGISTRY["capture_area"],
        ctx,
    )

    assert message is None


def test_refresh_bootstrap_context_falls_back_to_secondary_reclaimable_feature_for_wreck():
    commander = FakeOwnUnit(
        unit_id=42,
        def_id=1,
        position=FakePosition(10.0, 0.0, 20.0),
        health=3250.0,
        max_health=3250.0,
    )
    reclaim_feature = FakeFeature(
        feature_id=200,
        def_id=9,
        position=FakePosition(30.0, 0.0, 40.0),
        reclaim_value_metal=25.0,
        reclaim_value_energy=0.0,
    )
    wreck_feature = FakeFeature(
        feature_id=250,
        def_id=10,
        position=FakePosition(35.0, 0.0, 45.0),
        reclaim_value_metal=80.0,
        reclaim_value_energy=10.0,
    )
    snapshot = FakeSnapshot(
        own_units=(commander,),
        visible_enemies=(),
        map_features=(reclaim_feature, wreck_feature),
    )
    ctx = BootstrapContext(commander_unit_id=42)

    refreshed = _refresh_bootstrap_context({"snapshots": [snapshot], "deltas": []}, ctx)

    assert refreshed.fixture_feature_ids["reclaim_target"] == 200
    assert refreshed.fixture_feature_ids["wreck_target"] == 250


def test_custom_builder_prefers_native_cloak_command_when_cloakable_exists():
    ctx = BootstrapContext(
        commander_unit_id=42,
        capability_units={"commander": 42, "cloakable": 88},
        fixture_unit_ids={"cloakable": 88},
    )

    batch = REGISTRY["custom"].input_builder(ctx)

    assert batch.target_unit_id == 88
    assert batch.commands[0].custom.unit_id == 88
    assert batch.commands[0].custom.command_id == 37382
    assert list(batch.commands[0].custom.params) == [1.0]


def test_load_units_builder_uses_transport_and_payload_fixture_ids():
    ctx = BootstrapContext(
        commander_unit_id=42,
        capability_units={"commander": 42},
        fixture_unit_ids={"transport_unit": 99, "payload_unit": 77},
    )

    batch = REGISTRY["load_units"].input_builder(ctx)

    assert batch.target_unit_id == 99
    assert batch.commands[0].load_units.unit_id == 99
    assert list(batch.commands[0].load_units.to_load_unit_ids) == [77]


def test_load_units_precondition_only_reports_truly_missing_composite_fixture():
    ctx = BootstrapContext(
        commander_unit_id=42,
        capability_units={"commander": 42, "builder": 77},
        fixture_unit_ids={"payload_unit": 77},
    )

    message = _simplified_bootstrap_precondition_message(
        "load_units",
        REGISTRY["load_units"],
        ctx,
    )

    assert message is not None
    assert "transport_unit" in message
    assert "payload_unit" not in message


def test_self_destruct_precondition_accepts_builder_as_disposable_fixture():
    ctx = BootstrapContext(
        commander_unit_id=42,
        capability_units={"commander": 42, "builder": 77},
        fixture_unit_ids={"builder": 77},
    )

    message = _simplified_bootstrap_precondition_message(
        "self_destruct",
        REGISTRY["self_destruct"],
        ctx,
    )

    assert message is None


def test_self_destruct_builder_targets_builder_before_commander():
    ctx = BootstrapContext(
        commander_unit_id=42,
        capability_units={"commander": 42, "builder": 77},
        fixture_unit_ids={"builder": 77},
    )

    batch = REGISTRY["self_destruct"].input_builder(ctx)

    assert batch.target_unit_id == 77
    assert batch.commands[0].self_destruct.unit_id == 77


def test_self_destruct_builder_prefers_builder_over_cloakable():
    ctx = BootstrapContext(
        commander_unit_id=42,
        capability_units={"commander": 42, "builder": 77, "cloakable": 88},
        fixture_unit_ids={"builder": 77, "cloakable": 88},
    )

    batch = REGISTRY["self_destruct"].input_builder(ctx)

    assert batch.target_unit_id == 77
    assert batch.commands[0].self_destruct.unit_id == 77


def test_self_destruct_precondition_accepts_payload_as_disposable_fixture():
    ctx = BootstrapContext(
        commander_unit_id=42,
        capability_units={"commander": 42},
        fixture_unit_ids={"payload_unit": 99},
    )

    message = _simplified_bootstrap_precondition_message(
        "self_destruct",
        REGISTRY["self_destruct"],
        ctx,
    )

    assert message is None


def test_self_destruct_builder_targets_payload_before_commander():
    ctx = BootstrapContext(
        commander_unit_id=42,
        capability_units={"commander": 42},
        fixture_unit_ids={"payload_unit": 99},
    )

    batch = REGISTRY["self_destruct"].input_builder(ctx)

    assert batch.target_unit_id == 99
    assert batch.commands[0].self_destruct.unit_id == 99


def test_custom_arm_exposes_exact_bar_command_inventory_ids():
    assert exact_custom_command_ids_for_arm("custom") == (
        32102,
        34571,
        34922,
        34923,
        34924,
        34925,
        37382,
    )
    assert exact_custom_command_ids_for_arm("attack") == ()

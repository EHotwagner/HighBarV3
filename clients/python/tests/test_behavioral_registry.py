# SPDX-License-Identifier: GPL-2.0-only
"""T019 — Import-time validation of the behavioral arm registry.

Contract: contracts/arm-registry.md §Import-time validation rules.
"""

from __future__ import annotations

from dataclasses import dataclass

import pytest

import highbar_client.behavioral_coverage as behavioral_coverage
from highbar_client.behavioral_coverage import REGISTRY
from highbar_client.behavioral_coverage import (
    _assess_bootstrap_readiness,
    _attempt_enemy_fixture_provisioning,
    _attempt_transport_provisioning,
    _can_skip_bootstrap_step_failure,
    _economy_obviously_starved,
    _execute_live_bootstrap,
    _issue_bootstrap_seed_step,
    _position_for_bootstrap_step,
    _refresh_bootstrap_context,
    _reset_live_context_to_manifest,
    _seed_position_for_bootstrap_step,
    _simplified_bootstrap_precondition_message,
)
from highbar_client.behavioral_coverage.bootstrap import (
    BootstrapContext,
    DEFAULT_BOOTSTRAP_PLAN,
    Vector3,
    compute_bootstrap_manifest,
)
from highbar_client.behavioral_coverage.capabilities import CAPABILITY_TAGS
from highbar_client.behavioral_coverage.registry import (
    _build_registry,
    _expected_arm_names,
    exact_custom_command_ids_for_arm,
    transport_compatibility_for_command,
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
    under_construction: bool = False
    build_progress: float = 1.0


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
    economy: object | None = None


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


def test_attempt_enemy_fixture_provisioning_spawns_enemy_when_missing(monkeypatch):
    commander = FakeOwnUnit(
        unit_id=42,
        def_id=1,
        position=FakePosition(10.0, 0.0, 20.0),
        health=3250.0,
        max_health=3250.0,
    )
    enemy = FakeEnemyUnit(
        unit_id=123,
        def_id=99,
        position=FakePosition(458.0, 0.0, 116.0),
        health=600.0,
        max_health=600.0,
    )
    current = FakeSnapshot(
        own_units=(commander,),
        visible_enemies=(),
        map_features=(),
        frame_number=10,
    )
    spawned = FakeSnapshot(
        own_units=(commander,),
        visible_enemies=(enemy,),
        map_features=(),
        frame_number=11,
    )
    shared = {"snapshots": [current], "deltas": []}
    dispatched = []

    monkeypatch.setattr(
        "highbar_client.behavioral_coverage._refreshing_snapshot",
        lambda _stub, _shared, token=None, timeout_s=5.0: shared["snapshots"][-1],
    )

    def fake_request_snapshot(_stub, token=None):
        del token
        return spawned.frame_number

    def fake_wait_for_snapshot(_shared, min_frame, timeout_s):
        del timeout_s
        if shared["snapshots"][-1].frame_number < spawned.frame_number:
            shared["snapshots"].append(spawned)
        latest = shared["snapshots"][-1]
        if latest.frame_number >= min_frame:
            return latest
        return None

    def fake_dispatch(_stub, batch, token=None):
        del token
        dispatched.append(batch)
        return None

    monkeypatch.setattr(
        "highbar_client.behavioral_coverage._request_snapshot",
        fake_request_snapshot,
    )
    monkeypatch.setattr(
        "highbar_client.behavioral_coverage._wait_for_snapshot",
        fake_wait_for_snapshot,
    )
    monkeypatch.setattr("highbar_client.behavioral_coverage._dispatch", fake_dispatch)

    ctx = BootstrapContext(
        commander_unit_id=42,
        commander_position=Vector3(10.0, 0.0, 20.0),
        capability_units={"commander": 42},
    )

    refreshed = _attempt_enemy_fixture_provisioning(object(), shared, ctx, token="tok")

    assert len(dispatched) == 1
    assert dispatched[0].commands[0].call_lua_rules.data.startswith("highbar_spawn_enemy:corck:")
    assert refreshed.enemy_seed_id == 123
    assert refreshed.fixture_unit_ids["hostile_target"] == 123
    assert refreshed.fixture_unit_ids["capturable_target"] == 123


def test_attempt_enemy_fixture_provisioning_skips_spawn_when_enemy_visible(monkeypatch):
    commander = FakeOwnUnit(
        unit_id=42,
        def_id=1,
        position=FakePosition(10.0, 0.0, 20.0),
        health=3250.0,
        max_health=3250.0,
    )
    enemy = FakeEnemyUnit(
        unit_id=123,
        def_id=99,
        position=FakePosition(50.0, 0.0, 60.0),
        health=600.0,
        max_health=600.0,
    )
    snapshot = FakeSnapshot(
        own_units=(commander,),
        visible_enemies=(enemy,),
        map_features=(),
        frame_number=10,
    )
    shared = {"snapshots": [snapshot], "deltas": []}

    monkeypatch.setattr(
        "highbar_client.behavioral_coverage._dispatch",
        lambda *_args, **_kwargs: pytest.fail("enemy spawn dispatch should be skipped"),
    )

    ctx = BootstrapContext(
        commander_unit_id=42,
        commander_position=Vector3(10.0, 0.0, 20.0),
        capability_units={"commander": 42},
    )

    refreshed = _attempt_enemy_fixture_provisioning(object(), shared, ctx, token="tok")

    assert refreshed.enemy_seed_id == 123
    assert refreshed.fixture_unit_ids["custom_target"] == 123


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


def test_transport_compatibility_helper_flags_payload_incompatibility():
    ctx = BootstrapContext(
        commander_unit_id=42,
        capability_units={"commander": 42},
        fixture_unit_ids={"transport_unit": 99, "payload_unit": 99},
    )

    result, detail = transport_compatibility_for_command("cmd-load-units", ctx)

    assert result == "payload_incompatible"
    assert detail is not None


def test_refresh_bootstrap_context_prefers_runtime_resolved_transport_variant():
    commander = FakeOwnUnit(
        unit_id=42,
        def_id=1,
        position=FakePosition(10.0, 0.0, 20.0),
        health=3250.0,
        max_health=3250.0,
    )
    heavy_transport = FakeOwnUnit(
        unit_id=109,
        def_id=777,
        position=FakePosition(12.0, 0.0, 22.0),
        health=1800.0,
        max_health=1800.0,
    )
    snapshot = FakeSnapshot(
        own_units=(commander, heavy_transport),
        visible_enemies=(),
        map_features=(),
    )
    ctx = BootstrapContext(
        commander_unit_id=42,
        capability_units={"commander": 42},
        def_id_by_name={"armhvytrans": 777},
    )

    refreshed = _refresh_bootstrap_context({"snapshots": [snapshot], "deltas": []}, ctx)

    assert refreshed.fixture_unit_ids["transport_unit"] == 109


def test_refresh_bootstrap_context_clears_stale_transport_fixture_when_missing():
    commander = FakeOwnUnit(
        unit_id=42,
        def_id=1,
        position=FakePosition(10.0, 0.0, 20.0),
        health=3250.0,
        max_health=3250.0,
    )
    snapshot = FakeSnapshot(
        own_units=(commander,),
        visible_enemies=(),
        map_features=(),
    )
    ctx = BootstrapContext(
        commander_unit_id=42,
        capability_units={"commander": 42},
        fixture_unit_ids={"transport_unit": 109, "payload_unit": 110},
        fixture_positions={
            "transport_unit": Vector3(12.0, 0.0, 22.0),
            "payload_unit": Vector3(13.0, 0.0, 23.0),
        },
    )

    refreshed = _refresh_bootstrap_context({"snapshots": [snapshot], "deltas": []}, ctx)

    assert "transport_unit" not in refreshed.fixture_unit_ids
    assert "payload_unit" not in refreshed.fixture_unit_ids


def test_refresh_bootstrap_context_prefers_builder_payload_over_cloakable():
    commander = FakeOwnUnit(
        unit_id=42,
        def_id=1,
        position=FakePosition(10.0, 0.0, 20.0),
        health=3250.0,
        max_health=3250.0,
    )
    cloakable = FakeOwnUnit(
        unit_id=88,
        def_id=3,
        position=FakePosition(14.0, 0.0, 26.0),
        health=89.0,
        max_health=89.0,
    )
    builder = FakeOwnUnit(
        unit_id=77,
        def_id=2,
        position=FakePosition(12.0, 0.0, 24.0),
        health=690.0,
        max_health=690.0,
    )
    transport = FakeOwnUnit(
        unit_id=99,
        def_id=4,
        position=FakePosition(16.0, 0.0, 28.0),
        health=265.0,
        max_health=265.0,
    )
    snapshot = FakeSnapshot(
        own_units=(commander, cloakable, builder, transport),
        visible_enemies=(),
        map_features=(),
    )
    ctx = BootstrapContext(
        commander_unit_id=42,
        capability_units={"commander": 42},
    )

    refreshed = _refresh_bootstrap_context({"snapshots": [snapshot], "deltas": []}, ctx)

    assert refreshed.fixture_unit_ids["payload_unit"] == 77


def test_refresh_bootstrap_context_tracks_factory_ground_from_runtime_def_id():
    commander = FakeOwnUnit(
        unit_id=42,
        def_id=1,
        position=FakePosition(10.0, 0.0, 20.0),
        health=3250.0,
        max_health=3250.0,
    )
    replacement_factory_ground = FakeOwnUnit(
        unit_id=303,
        def_id=13,
        position=FakePosition(270.0, 0.0, 216.0),
        health=2050.0,
        max_health=2050.0,
    )
    snapshot = FakeSnapshot(
        own_units=(commander, replacement_factory_ground),
        visible_enemies=(),
        map_features=(),
        frame_number=10,
    )
    ctx = BootstrapContext(
        commander_unit_id=42,
        commander_position=Vector3(10.0, 0.0, 20.0),
        capability_units={"commander": 42, "factory_ground": 103},
        def_id_by_name={"armvp": 13},
        observed_own_units={42: commander},
    )

    refreshed = _refresh_bootstrap_context({"snapshots": [snapshot], "deltas": []}, ctx)

    assert refreshed.capability_units["factory_ground"] == 303


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


def test_transport_compatibility_helper_flags_transport_under_construction():
    transport = FakeOwnUnit(
        unit_id=99,
        def_id=4,
        position=FakePosition(16.0, 0.0, 28.0),
        health=265.0,
        max_health=265.0,
        under_construction=True,
        build_progress=0.5,
    )
    payload = FakeOwnUnit(
        unit_id=77,
        def_id=2,
        position=FakePosition(12.0, 0.0, 24.0),
        health=690.0,
        max_health=690.0,
    )
    ctx = BootstrapContext(
        commander_unit_id=42,
        capability_units={"commander": 42},
        fixture_unit_ids={"transport_unit": 99, "payload_unit": 77},
        observed_own_units={99: transport, 77: payload},
    )

    result, detail = transport_compatibility_for_command("cmd-load-units", ctx)

    assert result == "candidate_unusable"
    assert "under construction" in (detail or "")


def test_transport_compatibility_helper_flags_payload_under_construction():
    transport = FakeOwnUnit(
        unit_id=99,
        def_id=4,
        position=FakePosition(16.0, 0.0, 28.0),
        health=265.0,
        max_health=265.0,
    )
    payload = FakeOwnUnit(
        unit_id=77,
        def_id=2,
        position=FakePosition(12.0, 0.0, 24.0),
        health=690.0,
        max_health=690.0,
        under_construction=True,
        build_progress=0.5,
    )
    ctx = BootstrapContext(
        commander_unit_id=42,
        capability_units={"commander": 42},
        fixture_unit_ids={"transport_unit": 99, "payload_unit": 77},
        observed_own_units={99: transport, 77: payload},
    )

    result, detail = transport_compatibility_for_command("cmd-load-units", ctx)

    assert result == "payload_incompatible"
    assert "payload" in (detail or "")


def test_attempt_transport_provisioning_dispatches_natural_build(monkeypatch):
    commander = FakeOwnUnit(
        unit_id=42,
        def_id=1,
        position=FakePosition(10.0, 0.0, 20.0),
        health=3250.0,
        max_health=3250.0,
    )
    factory_air = FakeOwnUnit(
        unit_id=51,
        def_id=100,
        position=FakePosition(30.0, 0.0, 40.0),
        health=2050.0,
        max_health=2050.0,
    )
    builder = FakeOwnUnit(
        unit_id=77,
        def_id=2,
        position=FakePosition(12.0, 0.0, 24.0),
        health=690.0,
        max_health=690.0,
    )
    shared = {
        "snapshots": [
            FakeSnapshot(
                own_units=(commander, factory_air, builder),
                visible_enemies=(),
                map_features=(),
            )
        ],
        "deltas": [],
    }
    ctx = BootstrapContext(
        commander_unit_id=42,
        capability_units={"commander": 42},
        def_id_by_name={"armap": 100, "armatlas": 200},
    )
    dispatched = []

    def fake_dispatch(_stub, batch, token=None):
        dispatched.append((batch, token))
        return None

    monkeypatch.setattr("highbar_client.behavioral_coverage._dispatch", fake_dispatch)

    refreshed = _attempt_transport_provisioning(object(), shared, ctx, wait_timeout_s=0.0)

    assert refreshed.capability_units["factory_air"] == 51
    assert len(dispatched) == 1
    batch = dispatched[0][0]
    assert batch.target_unit_id == 51
    assert batch.commands[0].build_unit.unit_id == 51
    assert batch.commands[0].build_unit.to_build_unit_def_id == 200


def test_attempt_transport_provisioning_does_not_duplicate_pending_build(monkeypatch):
    commander = FakeOwnUnit(
        unit_id=42,
        def_id=1,
        position=FakePosition(10.0, 0.0, 20.0),
        health=3250.0,
        max_health=3250.0,
    )
    factory_air = FakeOwnUnit(
        unit_id=51,
        def_id=100,
        position=FakePosition(30.0, 0.0, 40.0),
        health=2050.0,
        max_health=2050.0,
    )
    pending_transport = FakeOwnUnit(
        unit_id=99,
        def_id=200,
        position=FakePosition(35.0, 0.0, 45.0),
        health=100.0,
        max_health=265.0,
        under_construction=True,
        build_progress=0.5,
    )
    shared = {
        "snapshots": [
            FakeSnapshot(
                own_units=(commander, factory_air, pending_transport),
                visible_enemies=(),
                map_features=(),
            )
        ],
        "deltas": [],
    }
    ctx = BootstrapContext(
        commander_unit_id=42,
        capability_units={"commander": 42},
        def_id_by_name={"armap": 100, "armatlas": 200},
    )

    def fail_dispatch(*_args, **_kwargs):
        raise AssertionError("dispatch should not be called while a transport build is already pending")

    monkeypatch.setattr("highbar_client.behavioral_coverage._dispatch", fail_dispatch)

    refreshed = _attempt_transport_provisioning(object(), shared, ctx, wait_timeout_s=0.0)

    assert "transport_unit" not in refreshed.fixture_unit_ids


def test_self_destruct_builder_targets_payload_before_commander():
    ctx = BootstrapContext(
        commander_unit_id=42,
        capability_units={"commander": 42},
        fixture_unit_ids={"payload_unit": 99},
    )

    batch = REGISTRY["self_destruct"].input_builder(ctx)

    assert batch.target_unit_id == 99
    assert batch.commands[0].self_destruct.unit_id == 99


def test_execute_live_bootstrap_builds_full_plan(monkeypatch):
    commander = FakeOwnUnit(
        unit_id=42,
        def_id=1,
        position=FakePosition(10.0, 0.0, 20.0),
        health=3250.0,
        max_health=3250.0,
    )
    mex = FakeOwnUnit(
        unit_id=101,
        def_id=11,
        position=FakePosition(106.0, 0.0, 20.0),
        health=100.0,
        max_health=100.0,
    )
    solar = FakeOwnUnit(
        unit_id=102,
        def_id=12,
        position=FakePosition(-86.0, 0.0, 20.0),
        health=100.0,
        max_health=100.0,
    )
    factory_ground = FakeOwnUnit(
        unit_id=103,
        def_id=13,
        position=FakePosition(170.0, 0.0, 116.0),
        health=2050.0,
        max_health=2050.0,
    )
    factory_air = FakeOwnUnit(
        unit_id=104,
        def_id=14,
        position=FakePosition(-150.0, 0.0, 116.0),
        health=2050.0,
        max_health=2050.0,
    )
    radar = FakeOwnUnit(
        unit_id=105,
        def_id=15,
        position=FakePosition(106.0, 0.0, -76.0),
        health=100.0,
        max_health=100.0,
    )
    builder = FakeOwnUnit(
        unit_id=106,
        def_id=16,
        position=FakePosition(172.0, 0.0, 118.0),
        health=690.0,
        max_health=690.0,
    )
    cloakable = FakeOwnUnit(
        unit_id=107,
        def_id=17,
        position=FakePosition(-148.0, 0.0, 118.0),
        health=89.0,
        max_health=89.0,
    )
    shared = {
        "snapshots": [
            FakeSnapshot(own_units=(commander,), visible_enemies=(), map_features=(), frame_number=0)
        ],
        "deltas": [],
    }
    produced_by_def_id = {
        11: mex,
        12: solar,
        13: factory_ground,
        14: factory_air,
        15: radar,
        16: builder,
        17: cloakable,
    }
    pending_snapshots = []
    dispatched = []
    wait_call_count = 0
    request_call_count = 0

    def fake_resolve_bootstrap_defs(_stub, ctx, token=None):
        del token
        ctx.def_id_by_name.update(
            {
                "armmex": 11,
                "armsolar": 12,
                "armvp": 13,
                "armap": 14,
                "armrad": 15,
                "armck": 16,
                "armpeep": 17,
                "armatlas": 18,
            }
        )

    def fake_resolve_transport_defs(_stub, ctx, token=None):
        del token
        ctx.transport_resolution_trace = ()

    def fake_request_snapshot(_stub, token=None):
        nonlocal request_call_count
        del token
        request_call_count += 1
        return 0

    def fake_wait_for_snapshot(_shared, min_frame, timeout_s):
        nonlocal wait_call_count
        del timeout_s
        wait_call_count += 1
        if wait_call_count == 1:
            return None
        if not pending_snapshots:
            return None
        for index, snapshot in enumerate(pending_snapshots):
            if snapshot.frame_number < min_frame:
                continue
            del pending_snapshots[index]
            shared["snapshots"].append(snapshot)
            return snapshot
        return None

    def fake_dispatch(_stub, batch, token=None):
        del token
        dispatched.append(batch)
        build_def_id = batch.commands[0].build_unit.to_build_unit_def_id
        produced_unit = produced_by_def_id[build_def_id]
        latest_snapshot = shared["snapshots"][-1]
        next_units = tuple(getattr(latest_snapshot, "own_units", ())) + (produced_unit,)
        pending_snapshots.append(
            FakeSnapshot(
                own_units=next_units,
                visible_enemies=(),
                map_features=(),
                frame_number=getattr(latest_snapshot, "frame_number", 0) + len(pending_snapshots) + 1,
            )
        )
        return None

    monkeypatch.setattr("highbar_client.behavioral_coverage._resolve_bootstrap_defs", fake_resolve_bootstrap_defs)
    monkeypatch.setattr("highbar_client.behavioral_coverage._resolve_supported_transport_defs", fake_resolve_transport_defs)
    monkeypatch.setattr("highbar_client.behavioral_coverage._request_snapshot", fake_request_snapshot)
    monkeypatch.setattr("highbar_client.behavioral_coverage._wait_for_snapshot", fake_wait_for_snapshot)
    monkeypatch.setattr("highbar_client.behavioral_coverage._dispatch", fake_dispatch)
    monkeypatch.setattr(
        "highbar_client.behavioral_coverage._attempt_transport_provisioning",
        lambda _stub, _shared, ctx, wait_timeout_s=0.0, token=None: ctx,
    )
    monkeypatch.setattr(
        "highbar_client.behavioral_coverage._attempt_enemy_fixture_provisioning",
        lambda _stub, _shared, ctx, token=None, timeout_s=6.0: ctx,
    )

    static_map = type(
        "FakeStaticMap",
        (),
        {
            "metal_spots": (
                FakePosition(200.0, 0.0, 300.0),
                FakePosition(106.0, 0.0, 20.0),
            )
        },
    )()

    ctx = _execute_live_bootstrap(object(), shared, token="tok", static_map=static_map)

    assert len(dispatched) == 7
    assert [batch.target_unit_id for batch in dispatched[:5]] == [42, 42, 42, 42, 42]
    assert [batch.target_unit_id for batch in dispatched[5:]] == [103, 104]
    assert request_call_count >= 7
    assert dispatched[0].commands[0].build_unit.build_position.x == 106.0
    assert dispatched[0].commands[0].build_unit.build_position.z == 20.0
    assert ctx.capability_units["factory_ground"] == 103
    assert ctx.capability_units["factory_air"] == 104
    assert ctx.capability_units["builder"] == 106
    assert ctx.capability_units["cloakable"] == 107
    assert dict(ctx.manifest)["armap"] == 1
    assert dict(ctx.manifest)["armck"] == 1
    assert dict(ctx.manifest)["armpeep"] == 1


def test_seed_position_for_bootstrap_step_prefers_preserved_bootstrap_position():
    factory_ground = FakeOwnUnit(
        unit_id=103,
        def_id=13,
        position=FakePosition(170.0, 0.0, 116.0),
        health=2050.0,
        max_health=2050.0,
    )
    blocker = FakeOwnUnit(
        unit_id=999,
        def_id=77,
        position=FakePosition(268.0, 0.0, 214.0),
        health=100.0,
        max_health=100.0,
    )
    snapshot = FakeSnapshot(
        own_units=(factory_ground, blocker),
        visible_enemies=(),
        map_features=(),
        frame_number=10,
    )
    ctx = BootstrapContext(
        capability_units={"factory_ground": 103},
        observed_own_units={103: factory_ground, 999: blocker},
        bootstrap_positions={"builder": Vector3(268.0, 0.0, 214.0)},
    )

    position = _seed_position_for_bootstrap_step(
        DEFAULT_BOOTSTRAP_PLAN[5],
        ctx,
        snapshot=snapshot,
    )

    assert (position.x, position.y, position.z) != (266.0, 0.0, 212.0)
    assert (position.x, position.y, position.z) != (268.0, 0.0, 214.0)


def test_seed_position_for_bootstrap_step_reuses_preserved_commander_position():
    step = DEFAULT_BOOTSTRAP_PLAN[0]
    blocker = FakeOwnUnit(
        unit_id=999,
        def_id=77,
        position=FakePosition(201.0, 0.0, 300.0),
        health=100.0,
        max_health=100.0,
    )
    snapshot = FakeSnapshot(
        own_units=(blocker,),
        visible_enemies=(),
        map_features=(),
        frame_number=10,
    )
    ctx = BootstrapContext(
        commander_unit_id=42,
        commander_position=Vector3(10.0, 0.0, 20.0),
        bootstrap_positions={"mex": Vector3(200.0, 0.0, 300.0)},
    )

    position = _seed_position_for_bootstrap_step(step, ctx, snapshot=snapshot)

    assert (position.x, position.y, position.z) != (200.0, 0.0, 300.0)


def test_issue_bootstrap_seed_step_retries_alternate_mex_positions(monkeypatch):
    ctx = BootstrapContext(
        commander_unit_id=42,
        commander_position=Vector3(10.0, 0.0, 20.0),
        def_id_by_name={"armmex": 11},
    )
    snapshot = FakeSnapshot(
        own_units=(),
        visible_enemies=(),
        map_features=(),
        frame_number=10,
    )
    static_map = type(
        "FakeStaticMap",
        (),
        {
            "metal_spots": (
                FakePosition(106.0, 0.0, 20.0),
                FakePosition(200.0, 0.0, 300.0),
                FakePosition(300.0, 0.0, 400.0),
            )
        },
    )()
    dispatched_positions = []
    attempt_count = 0
    completed_unit = FakeOwnUnit(
        unit_id=101,
        def_id=11,
        position=FakePosition(200.0, 0.0, 300.0),
        health=100.0,
        max_health=100.0,
    )

    monkeypatch.setattr(
        "highbar_client.behavioral_coverage._dispatch",
        lambda _stub, batch, token=None: dispatched_positions.append(
            (
                batch.commands[0].give_me_new_unit.position.x,
                batch.commands[0].give_me_new_unit.position.y,
                batch.commands[0].give_me_new_unit.position.z,
            )
        ),
    )

    def fake_wait_for_new_ready_unit(
        _shared,
        *,
        def_id,
        baseline_ids,
        timeout_s,
        stub=None,
        token=None,
    ):
        nonlocal attempt_count
        del _shared, def_id, baseline_ids, timeout_s, stub, token
        attempt_count += 1
        if attempt_count == 1:
            raise RuntimeError("timeout waiting for new ready unit def_id=11 saw_new_candidate=0")
        return completed_unit

    monkeypatch.setattr(
        "highbar_client.behavioral_coverage._wait_for_new_ready_unit",
        fake_wait_for_new_ready_unit,
    )

    completed = _issue_bootstrap_seed_step(
        object(),
        {"snapshots": [snapshot], "deltas": []},
        ctx,
        DEFAULT_BOOTSTRAP_PLAN[0],
        baseline_ids=set(),
        token="tok",
        static_map=static_map,
        snapshot=snapshot,
    )

    assert attempt_count == 2
    assert len(dispatched_positions) == 2
    assert dispatched_positions[0] != dispatched_positions[1]
    assert completed.unit_id == 101


def test_position_for_bootstrap_step_skips_occupied_metal_spot():
    commander = FakeOwnUnit(
        unit_id=42,
        def_id=1,
        position=FakePosition(10.0, 0.0, 20.0),
        health=3250.0,
        max_health=3250.0,
    )
    occupied = FakeOwnUnit(
        unit_id=77,
        def_id=11,
        position=FakePosition(106.0, 0.0, 20.0),
        health=100.0,
        max_health=100.0,
    )
    step = DEFAULT_BOOTSTRAP_PLAN[0]
    static_map = type(
        "FakeStaticMap",
        (),
        {
            "metal_spots": (
                FakePosition(106.0, 0.0, 20.0),
                FakePosition(200.0, 0.0, 300.0),
            )
        },
    )()
    snapshot = FakeSnapshot(
        own_units=(commander, occupied),
        visible_enemies=(),
        map_features=(),
        frame_number=0,
    )

    position = _position_for_bootstrap_step(
        step,
        Vector3(10.0, 0.0, 20.0),
        static_map=static_map,
        snapshot=snapshot,
        ignore_unit_ids={42},
    )

    assert position.x == 200.0
    assert position.z == 300.0


def test_position_for_bootstrap_step_relocates_blocked_factory_site():
    commander = FakeOwnUnit(
        unit_id=42,
        def_id=1,
        position=FakePosition(10.0, 0.0, 20.0),
        health=3250.0,
        max_health=3250.0,
    )
    blocker = FakeOwnUnit(
        unit_id=77,
        def_id=99,
        position=FakePosition(170.0, 0.0, 116.0),
        health=1000.0,
        max_health=1000.0,
    )
    step = DEFAULT_BOOTSTRAP_PLAN[2]
    snapshot = FakeSnapshot(
        own_units=(commander, blocker),
        visible_enemies=(),
        map_features=(),
        frame_number=0,
    )

    position = _position_for_bootstrap_step(
        step,
        Vector3(10.0, 0.0, 20.0),
        snapshot=snapshot,
        ignore_unit_ids={42},
    )

    assert (position.x, position.z) != (170.0, 116.0)


def test_economy_obviously_starved_requires_no_metal_and_no_income():
    starved_snapshot = FakeSnapshot(
        own_units=(),
        visible_enemies=(),
        map_features=(),
        frame_number=0,
        economy=type(
            "Economy",
            (),
            {
                "metal": 0.1,
                "metal_income": 0.0,
                "metal_storage": 1500.0,
                "energy": 6000.0,
                "energy_income": 0.0,
                "energy_storage": 8000.0,
            },
        )(),
    )
    healthy_snapshot = FakeSnapshot(
        own_units=(),
        visible_enemies=(),
        map_features=(),
        frame_number=0,
        economy=type(
            "Economy",
            (),
            {
                "metal": 25.0,
                "metal_income": 2.0,
                "metal_storage": 1500.0,
                "energy": 6000.0,
                "energy_income": 20.0,
                "energy_storage": 8000.0,
            },
        )(),
    )

    assert _economy_obviously_starved(starved_snapshot)
    assert not _economy_obviously_starved(healthy_snapshot)


def test_assess_bootstrap_readiness_ignores_optional_missing_steps_when_downstream_units_exist():
    commander = FakeOwnUnit(
        unit_id=42,
        def_id=1,
        position=FakePosition(10.0, 0.0, 20.0),
        health=3250.0,
        max_health=3250.0,
    )
    mex = FakeOwnUnit(101, 11, FakePosition(106.0, 0.0, 20.0), 100.0, 100.0)
    builder = FakeOwnUnit(106, 16, FakePosition(172.0, 0.0, 118.0), 690.0, 690.0)
    cloakable = FakeOwnUnit(107, 17, FakePosition(-148.0, 0.0, 118.0), 89.0, 89.0)
    snapshot = FakeSnapshot(
        own_units=(commander, mex, builder, cloakable),
        visible_enemies=(),
        map_features=(),
        frame_number=0,
        economy=type(
            "Economy",
            (),
            {
                "metal": 0.0,
                "metal_income": 0.0,
                "metal_storage": 1725.0,
                "energy": 6462.2,
                "energy_income": 0.0,
                "energy_storage": 8408.5,
            },
        )(),
    )
    ctx = BootstrapContext(
        capability_units={"commander": 42, "builder": 106, "cloakable": 107},
        fixture_unit_ids={"builder": 106, "cloakable": 107},
        def_id_by_name={
            "armmex": 11,
            "armsolar": 12,
            "armvp": 13,
            "armap": 14,
            "armrad": 15,
            "armck": 16,
            "armpeep": 17,
        },
    )

    status, path, first_required_step, reason = _assess_bootstrap_readiness(snapshot, ctx)

    assert status == "natural_ready"
    assert path == "prepared_state"
    assert first_required_step == "armsolar"
    assert "optional commander-built gaps" in reason


def test_assess_bootstrap_readiness_keeps_armmex_as_first_required_step_when_start_is_starved():
    commander = FakeOwnUnit(
        unit_id=42,
        def_id=1,
        position=FakePosition(10.0, 0.0, 20.0),
        health=3250.0,
        max_health=3250.0,
    )
    snapshot = FakeSnapshot(
        own_units=(commander,),
        visible_enemies=(),
        map_features=(),
        frame_number=0,
        economy=type(
            "Economy",
            (),
            {
                "metal": 0.0,
                "metal_income": 0.0,
                "metal_storage": 1500.0,
                "energy": 6000.0,
                "energy_income": 0.0,
                "energy_storage": 8000.0,
            },
        )(),
    )
    ctx = BootstrapContext(
        capability_units={"commander": 42},
        def_id_by_name={
            "armmex": 11,
            "armsolar": 12,
            "armvp": 13,
            "armap": 14,
            "armrad": 15,
        },
    )

    status, path, first_required_step, reason = _assess_bootstrap_readiness(snapshot, ctx)

    assert status == "resource_starved"
    assert path == "unavailable"
    assert first_required_step == "armmex"
    assert "resource-starved state" in reason


def test_execute_live_bootstrap_records_resource_starved_readiness(monkeypatch):
    commander = FakeOwnUnit(
        unit_id=42,
        def_id=1,
        position=FakePosition(10.0, 0.0, 20.0),
        health=3250.0,
        max_health=3250.0,
    )
    starved_snapshot = FakeSnapshot(
        own_units=(commander,),
        visible_enemies=(),
        map_features=(),
        frame_number=0,
        economy=type(
            "Economy",
            (),
            {
                "metal": 0.1,
                "metal_income": 0.0,
                "metal_storage": 1500.0,
                "energy": 6000.0,
                "energy_income": 0.0,
                "energy_storage": 8000.0,
            },
        )(),
    )
    shared = {"snapshots": [starved_snapshot], "deltas": []}

    def fake_resolve_bootstrap_defs(_stub, ctx, token=None):
        del token
        ctx.def_id_by_name.update(
            {
                "armmex": 11,
                "armsolar": 12,
                "armvp": 13,
                "armap": 14,
                "armrad": 15,
            }
        )

    monkeypatch.setattr(
        behavioral_coverage,
        "_resolve_bootstrap_defs",
        fake_resolve_bootstrap_defs,
    )
    monkeypatch.setattr(
        behavioral_coverage,
        "_resolve_supported_transport_defs",
        lambda _stub, _ctx, token=None: None,
    )
    monkeypatch.setattr(
        behavioral_coverage,
        "_refreshing_snapshot",
        lambda _stub, _shared, token=None, timeout_s=5.0: starved_snapshot,
    )

    with pytest.raises(behavioral_coverage.BootstrapExecutionError) as exc_info:
        _execute_live_bootstrap(object(), shared)

    err = exc_info.value
    assert err.ctx is not None
    assert err.ctx.bootstrap_readiness is not None
    assert err.ctx.bootstrap_readiness["readiness_status"] == "resource_starved"
    assert err.ctx.bootstrap_readiness["first_required_step"] == "armmex"
    assert err.ctx.prerequisite_resolution_records[0]["prerequisite_name"] == "armmex"
    assert err.ctx.runtime_capability_profile is not None
    assert 47 in err.ctx.runtime_capability_profile["supported_callbacks"]
    assert 40 in err.ctx.runtime_capability_profile["supported_callbacks"]
    assert err.ctx.map_source_decisions[0]["selected_source"] == "missing"


def test_execute_live_bootstrap_reuses_existing_ready_plan_units(monkeypatch):
    commander = FakeOwnUnit(
        unit_id=42,
        def_id=1,
        position=FakePosition(10.0, 0.0, 20.0),
        health=3250.0,
        max_health=3250.0,
    )
    mex = FakeOwnUnit(101, 11, FakePosition(106.0, 0.0, 20.0), 100.0, 100.0)
    solar = FakeOwnUnit(102, 12, FakePosition(-86.0, 0.0, 20.0), 100.0, 100.0)
    factory_ground = FakeOwnUnit(103, 13, FakePosition(170.0, 0.0, 116.0), 2050.0, 2050.0)
    factory_air = FakeOwnUnit(104, 14, FakePosition(-150.0, 0.0, 116.0), 2050.0, 2050.0)
    radar = FakeOwnUnit(105, 15, FakePosition(106.0, 0.0, -76.0), 100.0, 100.0)
    builder = FakeOwnUnit(106, 16, FakePosition(172.0, 0.0, 118.0), 690.0, 690.0)
    cloakable = FakeOwnUnit(107, 17, FakePosition(-148.0, 0.0, 118.0), 89.0, 89.0)
    shared = {
        "snapshots": [
            FakeSnapshot(
                own_units=(commander, mex, solar, factory_ground, factory_air, radar, builder, cloakable),
                visible_enemies=(),
                map_features=(),
                frame_number=0,
            )
        ],
        "deltas": [],
    }
    dispatched = []

    def fake_resolve_bootstrap_defs(_stub, ctx, token=None):
        del token
        ctx.def_id_by_name.update(
            {
                "armmex": 11,
                "armsolar": 12,
                "armvp": 13,
                "armap": 14,
                "armrad": 15,
                "armck": 16,
                "armpeep": 17,
                "armatlas": 18,
            }
        )

    monkeypatch.setattr("highbar_client.behavioral_coverage._resolve_bootstrap_defs", fake_resolve_bootstrap_defs)
    monkeypatch.setattr(
        "highbar_client.behavioral_coverage._resolve_supported_transport_defs",
        lambda _stub, ctx, token=None: setattr(ctx, "transport_resolution_trace", ()),
    )
    monkeypatch.setattr("highbar_client.behavioral_coverage._request_snapshot", lambda _stub, token=None: 0)
    monkeypatch.setattr(
        "highbar_client.behavioral_coverage._wait_for_snapshot",
        lambda _shared, min_frame, timeout_s: None,
    )
    monkeypatch.setattr(
        "highbar_client.behavioral_coverage._dispatch",
        lambda _stub, batch, token=None: dispatched.append(batch),
    )
    monkeypatch.setattr(
        "highbar_client.behavioral_coverage._attempt_transport_provisioning",
        lambda _stub, _shared, ctx, wait_timeout_s=0.0, token=None: ctx,
    )
    monkeypatch.setattr(
        "highbar_client.behavioral_coverage._attempt_enemy_fixture_provisioning",
        lambda _stub, _shared, ctx, token=None, timeout_s=6.0: ctx,
    )

    ctx = _execute_live_bootstrap(object(), shared, token="tok")

    assert dispatched == []
    assert ctx.capability_units["mex"] == 101
    assert ctx.capability_units["factory_ground"] == 103
    assert ctx.capability_units["factory_air"] == 104
    assert ctx.capability_units["builder"] == 106
    assert ctx.capability_units["cloakable"] == 107


def test_execute_live_bootstrap_uses_explicit_seed_path(monkeypatch):
    commander = FakeOwnUnit(
        unit_id=42,
        def_id=1,
        position=FakePosition(10.0, 0.0, 20.0),
        health=3250.0,
        max_health=3250.0,
    )
    economy = type(
        "FakeEconomy",
        (),
        {
            "metal": 0.0,
            "metal_income": 0.0,
            "metal_storage": 1500.0,
            "energy": 0.0,
            "energy_income": 0.0,
            "energy_storage": 1200.0,
        },
    )()
    shared = {
        "snapshots": [
            FakeSnapshot(
                own_units=(commander,),
                visible_enemies=(),
                map_features=(),
                frame_number=0,
                economy=economy,
            )
        ],
        "deltas": [],
    }
    pending_snapshots = []
    dispatched = []
    produced_by_def_id = {
        11: FakeOwnUnit(101, 11, FakePosition(106.0, 0.0, 20.0), 100.0, 100.0),
        12: FakeOwnUnit(102, 12, FakePosition(-86.0, 0.0, 20.0), 100.0, 100.0),
        13: FakeOwnUnit(103, 13, FakePosition(170.0, 0.0, 116.0), 2050.0, 2050.0),
        14: FakeOwnUnit(104, 14, FakePosition(-150.0, 0.0, 116.0), 2050.0, 2050.0),
        15: FakeOwnUnit(105, 15, FakePosition(106.0, 0.0, -76.0), 100.0, 100.0),
        16: FakeOwnUnit(106, 16, FakePosition(172.0, 0.0, 118.0), 690.0, 690.0),
        17: FakeOwnUnit(107, 17, FakePosition(-148.0, 0.0, 118.0), 89.0, 89.0),
    }

    def fake_resolve_bootstrap_defs(_stub, ctx, token=None):
        del token
        ctx.def_id_by_name.update(
            {
                "armmex": 11,
                "armsolar": 12,
                "armvp": 13,
                "armap": 14,
                "armrad": 15,
                "armck": 16,
                "armpeep": 17,
                "armatlas": 18,
            }
        )

    def fake_request_snapshot(_stub, token=None):
        del token
        return 0

    def fake_wait_for_snapshot(_shared, min_frame, timeout_s):
        del timeout_s
        if not pending_snapshots:
            return None
        for index, snapshot in enumerate(pending_snapshots):
            if snapshot.frame_number < min_frame:
                continue
            del pending_snapshots[index]
            shared["snapshots"].append(snapshot)
            return snapshot
        return None

    def fake_dispatch(_stub, batch, token=None):
        del token
        dispatched.append(batch)
        command = batch.commands[0]
        if command.build_unit.to_build_unit_def_id:
            raise AssertionError("explicit seed path should not use natural build dispatch")
        if command.give_me_new_unit.unit_def_id:
            produced_unit = produced_by_def_id[command.give_me_new_unit.unit_def_id]
            latest_snapshot = shared["snapshots"][-1]
            pending_snapshots.append(
                FakeSnapshot(
                    own_units=tuple(getattr(latest_snapshot, "own_units", ())) + (produced_unit,),
                    visible_enemies=(),
                    map_features=(),
                    frame_number=getattr(latest_snapshot, "frame_number", 0) + len(pending_snapshots) + 1,
                    economy=economy,
                )
            )
        return None

    monkeypatch.setattr(
        "highbar_client.behavioral_coverage._resolve_bootstrap_defs",
        fake_resolve_bootstrap_defs,
    )
    monkeypatch.setattr(
        "highbar_client.behavioral_coverage._resolve_supported_transport_defs",
        lambda _stub, ctx, token=None: setattr(ctx, "transport_resolution_trace", ()),
    )
    monkeypatch.setattr("highbar_client.behavioral_coverage._request_snapshot", fake_request_snapshot)
    monkeypatch.setattr("highbar_client.behavioral_coverage._wait_for_snapshot", fake_wait_for_snapshot)
    monkeypatch.setattr("highbar_client.behavioral_coverage._dispatch", fake_dispatch)
    monkeypatch.setattr(
        "highbar_client.behavioral_coverage._attempt_transport_provisioning",
        lambda _stub, _shared, ctx, wait_timeout_s=0.0, token=None: ctx,
    )
    monkeypatch.setattr(
        "highbar_client.behavioral_coverage._attempt_enemy_fixture_provisioning",
        lambda _stub, _shared, ctx, token=None, timeout_s=6.0: ctx,
    )

    ctx = _execute_live_bootstrap(object(), shared, token="tok", enable_seeded_path=True)

    seed_def_ids = [
        batch.commands[0].give_me_new_unit.unit_def_id
        for batch in dispatched
        if batch.commands[0].give_me_new_unit.unit_def_id
    ]

    assert ctx.cheats_enabled is True
    assert ctx.bootstrap_readiness is not None
    assert ctx.bootstrap_readiness["readiness_status"] == "seeded_ready"
    assert ctx.bootstrap_readiness["readiness_path"] == "explicit_seed"
    assert seed_def_ids == [11, 12, 13, 14, 15, 16, 17]
    assert any(batch.commands[0].give_me.amount == 5000.0 for batch in dispatched)
    assert any(batch.commands[0].give_me.amount == 20000.0 for batch in dispatched)
    assert ctx.capability_units["factory_ground"] == 103
    assert ctx.capability_units["factory_air"] == 104
    assert ctx.capability_units["builder"] == 106
    assert ctx.capability_units["cloakable"] == 107


def test_execute_live_bootstrap_provisions_enemy_fixture_after_transport(monkeypatch):
    commander = FakeOwnUnit(
        unit_id=42,
        def_id=1,
        position=FakePosition(10.0, 0.0, 20.0),
        health=3250.0,
        max_health=3250.0,
    )
    shared = {
        "snapshots": [
            FakeSnapshot(
                own_units=(commander,),
                visible_enemies=(),
                map_features=(),
                frame_number=0,
            )
        ],
        "deltas": [],
    }
    provisioned_ctx = BootstrapContext(
        commander_unit_id=42,
        commander_position=Vector3(10.0, 0.0, 20.0),
        capability_units={
            "commander": 42,
            "factory_ground": 103,
            "factory_air": 104,
            "builder": 106,
            "cloakable": 107,
        },
        fixture_unit_ids={
            "hostile_target": 123,
            "capturable_target": 123,
            "custom_target": 123,
        },
        fixture_positions={"hostile_target": Vector3(50.0, 0.0, 60.0)},
        enemy_seed_id=123,
        manifest=(("armap", 1), ("armck", 1), ("armpeep", 1), ("armvp", 1)),
        def_id_by_name={
            "armmex": 11,
            "armsolar": 12,
            "armvp": 13,
            "armap": 14,
            "armrad": 15,
            "armck": 16,
            "armpeep": 17,
        },
    )

    monkeypatch.setattr(
        "highbar_client.behavioral_coverage._resolve_bootstrap_defs",
        lambda _stub, ctx, token=None: ctx.def_id_by_name.update(
            {
                "armmex": 11,
                "armsolar": 12,
                "armvp": 13,
                "armap": 14,
                "armrad": 15,
                "armck": 16,
                "armpeep": 17,
            }
        ),
    )
    monkeypatch.setattr(
        "highbar_client.behavioral_coverage._resolve_supported_transport_defs",
        lambda _stub, ctx, token=None: setattr(ctx, "transport_resolution_trace", ()),
    )
    monkeypatch.setattr(
        "highbar_client.behavioral_coverage._refreshing_snapshot",
        lambda _stub, _shared, token=None, timeout_s=5.0: shared["snapshots"][-1],
    )
    monkeypatch.setattr(
        "highbar_client.behavioral_coverage._assess_bootstrap_readiness",
        lambda _snapshot, _ctx: ("resource_starved", "natural", "mex", "fixture gap"),
    )
    monkeypatch.setattr(
        "highbar_client.behavioral_coverage._attempt_seeded_bootstrap",
        lambda _stub, _shared, ctx, token=None, static_map=None, starting_snapshot=None: (
            BootstrapContext(
                commander_unit_id=ctx.commander_unit_id,
                commander_position=ctx.commander_position,
                capability_units={
                    "commander": 42,
                    "factory_ground": 103,
                    "factory_air": 104,
                    "builder": 106,
                    "cloakable": 107,
                },
                def_id_by_name=dict(ctx.def_id_by_name),
            ),
            ("armmex", "armvp"),
        ),
    )
    monkeypatch.setattr(
        "highbar_client.behavioral_coverage._capture_callback_diagnostic",
        lambda _stub, _shared, _ctx, capture_stage, token=None: None,
    )
    monkeypatch.setattr(
        "highbar_client.behavioral_coverage._attempt_transport_provisioning",
        lambda _stub, _shared, ctx, wait_timeout_s=0.0, token=None: ctx,
    )
    monkeypatch.setattr(
        "highbar_client.behavioral_coverage._attempt_enemy_fixture_provisioning",
        lambda _stub, _shared, ctx, token=None, timeout_s=6.0: provisioned_ctx,
    )

    ctx = _execute_live_bootstrap(object(), shared, token="tok", enable_seeded_path=True)

    assert ctx.enemy_seed_id == 123
    assert ctx.fixture_unit_ids["hostile_target"] == 123


def test_compute_bootstrap_manifest_excludes_non_bootstrap_units():
    units = (
        FakeOwnUnit(101, 11, FakePosition(106.0, 0.0, 20.0), 100.0, 100.0),
        FakeOwnUnit(102, 12, FakePosition(-86.0, 0.0, 20.0), 100.0, 100.0),
        FakeOwnUnit(103, 13, FakePosition(170.0, 0.0, 116.0), 2050.0, 2050.0),
        FakeOwnUnit(104, 999, FakePosition(200.0, 0.0, 200.0), 50.0, 50.0),
    )

    manifest = compute_bootstrap_manifest(
        units,
        {
            "armmex": 11,
            "armsolar": 12,
            "armvp": 13,
            "armap": 14,
            "armrad": 15,
            "armck": 16,
            "armpeep": 17,
        },
    )

    assert manifest == (("armmex", 1), ("armsolar", 1), ("armvp", 1))


def test_execute_live_bootstrap_skips_commander_built_factories_when_downstream_units_preexist(
    monkeypatch,
):
    commander = FakeOwnUnit(
        unit_id=42,
        def_id=1,
        position=FakePosition(10.0, 0.0, 20.0),
        health=3250.0,
        max_health=3250.0,
    )
    mex = FakeOwnUnit(101, 11, FakePosition(106.0, 0.0, 20.0), 100.0, 100.0)
    solar = FakeOwnUnit(102, 12, FakePosition(-86.0, 0.0, 20.0), 100.0, 100.0)
    radar = FakeOwnUnit(105, 15, FakePosition(106.0, 0.0, -76.0), 100.0, 100.0)
    builder = FakeOwnUnit(106, 16, FakePosition(172.0, 0.0, 118.0), 690.0, 690.0)
    cloakable = FakeOwnUnit(107, 17, FakePosition(-148.0, 0.0, 118.0), 89.0, 89.0)
    shared = {
        "snapshots": [
            FakeSnapshot(
                own_units=(commander, mex, solar, radar, builder, cloakable),
                visible_enemies=(),
                map_features=(),
                frame_number=0,
            )
        ],
        "deltas": [],
    }
    attempted_defs = []

    def fake_resolve_bootstrap_defs(_stub, ctx, token=None):
        del token
        ctx.def_id_by_name.update(
            {
                "armmex": 11,
                "armsolar": 12,
                "armvp": 13,
                "armap": 14,
                "armrad": 15,
                "armck": 16,
                "armpeep": 17,
                "armatlas": 18,
            }
        )

    def fake_issue_bootstrap_build_step(
        _stub,
        _shared,
        _ctx,
        step,
        *,
        builder_unit_id,
        target_position,
        baseline_ids,
        token=None,
        static_map=None,
        failure_snapshot=None,
    ):
        del builder_unit_id, target_position, baseline_ids, token, static_map, failure_snapshot
        attempted_defs.append(step.def_id)
        raise RuntimeError(
            f"{step.capability}/{step.def_id} timeout waiting for new ready unit "
            f"def_id=999 saw_new_candidate=0"
        )

    monkeypatch.setattr(
        "highbar_client.behavioral_coverage._resolve_bootstrap_defs",
        fake_resolve_bootstrap_defs,
    )
    monkeypatch.setattr(
        "highbar_client.behavioral_coverage._resolve_supported_transport_defs",
        lambda _stub, ctx, token=None: setattr(ctx, "transport_resolution_trace", ()),
    )
    monkeypatch.setattr(
        "highbar_client.behavioral_coverage._refreshing_snapshot",
        lambda _stub, _shared, token=None, timeout_s=5.0: shared["snapshots"][-1],
    )
    monkeypatch.setattr(
        "highbar_client.behavioral_coverage._request_snapshot",
        lambda _stub, token=None: 0,
    )
    monkeypatch.setattr(
        "highbar_client.behavioral_coverage._wait_for_snapshot",
        lambda _shared, min_frame, timeout_s: None,
    )
    monkeypatch.setattr(
        "highbar_client.behavioral_coverage._issue_bootstrap_build_step",
        fake_issue_bootstrap_build_step,
    )
    monkeypatch.setattr(
        "highbar_client.behavioral_coverage._attempt_transport_provisioning",
        lambda _stub, _shared, ctx, wait_timeout_s=0.0, token=None: ctx,
    )
    monkeypatch.setattr(
        "highbar_client.behavioral_coverage._attempt_enemy_fixture_provisioning",
        lambda _stub, _shared, ctx, token=None, timeout_s=6.0: ctx,
    )

    ctx = _execute_live_bootstrap(object(), shared, token="tok")

    assert attempted_defs == ["armvp", "armap"]
    assert ctx.capability_units["builder"] == 106
    assert ctx.capability_units["cloakable"] == 107
    assert "factory_ground" not in ctx.capability_units
    assert "factory_air" not in ctx.capability_units


def test_can_skip_bootstrap_step_failure_only_for_optional_no_candidate_steps():
    assert _can_skip_bootstrap_step_failure(
        DEFAULT_BOOTSTRAP_PLAN[0],
        RuntimeError("timeout waiting for new ready unit def_id=149 saw_new_candidate=0"),
    )
    assert _can_skip_bootstrap_step_failure(
        DEFAULT_BOOTSTRAP_PLAN[1],
        RuntimeError("timeout waiting for new ready unit def_id=209 saw_new_candidate=0"),
    )
    assert _can_skip_bootstrap_step_failure(
        DEFAULT_BOOTSTRAP_PLAN[4],
        RuntimeError("timeout waiting for new ready unit def_id=333 saw_new_candidate=0"),
    )
    assert not _can_skip_bootstrap_step_failure(
        DEFAULT_BOOTSTRAP_PLAN[0],
        RuntimeError("timeout waiting for new ready unit def_id=149 saw_new_candidate=1"),
    )
    assert not _can_skip_bootstrap_step_failure(
        DEFAULT_BOOTSTRAP_PLAN[2],
        RuntimeError("timeout waiting for new ready unit def_id=150 saw_new_candidate=0"),
    )


def test_can_skip_bootstrap_factory_failure_when_prepared_state_already_has_downstream_units():
    ctx = BootstrapContext(
        capability_units={"builder": 106, "cloakable": 107},
        fixture_unit_ids={},
    )
    assert _can_skip_bootstrap_step_failure(
        DEFAULT_BOOTSTRAP_PLAN[2],
        RuntimeError("timeout waiting for new ready unit def_id=150 saw_new_candidate=0"),
        ctx,
    )
    assert _can_skip_bootstrap_step_failure(
        DEFAULT_BOOTSTRAP_PLAN[3],
        RuntimeError("timeout waiting for new ready unit def_id=151 saw_new_candidate=0"),
        ctx,
    )


def test_cannot_skip_bootstrap_factory_failure_without_downstream_units():
    ctx = BootstrapContext(capability_units={}, fixture_unit_ids={})
    assert not _can_skip_bootstrap_step_failure(
        DEFAULT_BOOTSTRAP_PLAN[2],
        RuntimeError("timeout waiting for new ready unit def_id=150 saw_new_candidate=0"),
        ctx,
    )
    assert not _can_skip_bootstrap_step_failure(
        DEFAULT_BOOTSTRAP_PLAN[3],
        RuntimeError("timeout waiting for new ready unit def_id=151 saw_new_candidate=0"),
        ctx,
    )


def test_reset_live_context_to_manifest_reissues_missing_builder(monkeypatch):
    commander = FakeOwnUnit(
        unit_id=42,
        def_id=1,
        position=FakePosition(10.0, 0.0, 20.0),
        health=3250.0,
        max_health=3250.0,
    )
    factory_ground = FakeOwnUnit(
        unit_id=103,
        def_id=13,
        position=FakePosition(170.0, 0.0, 116.0),
        health=2050.0,
        max_health=2050.0,
    )
    builder = FakeOwnUnit(
        unit_id=106,
        def_id=16,
        position=FakePosition(172.0, 0.0, 118.0),
        health=690.0,
        max_health=690.0,
    )
    current = FakeSnapshot(
        own_units=(commander, factory_ground),
        visible_enemies=(),
        map_features=(),
        frame_number=10,
    )
    restored = FakeSnapshot(
        own_units=(commander, factory_ground, builder),
        visible_enemies=(),
        map_features=(),
        frame_number=11,
    )
    shared = {"snapshots": [current], "deltas": []}
    pending_snapshots = [restored]
    dispatched = []
    wait_call_count = 0
    ctx = BootstrapContext(
        commander_unit_id=42,
        commander_position=Vector3(10.0, 0.0, 20.0),
        capability_units={"commander": 42, "factory_ground": 103},
        manifest=(("armck", 1), ("armvp", 1)),
        def_id_by_name={"armcom": 1, "armvp": 13, "armck": 16},
        observed_own_units={42: commander, 103: factory_ground},
    )

    def fake_request_snapshot(_stub, token=None):
        del token
        return 0

    def fake_wait_for_snapshot(_shared, min_frame, timeout_s):
        nonlocal wait_call_count
        del timeout_s
        wait_call_count += 1
        if wait_call_count == 1:
            return None
        if not pending_snapshots:
            return None
        snapshot = pending_snapshots.pop(0)
        if snapshot.frame_number < min_frame:
            return None
        shared["snapshots"].append(snapshot)
        return snapshot

    def fake_dispatch(_stub, batch, token=None):
        del token
        dispatched.append(batch)
        return None

    monkeypatch.setattr("highbar_client.behavioral_coverage._request_snapshot", fake_request_snapshot)
    monkeypatch.setattr("highbar_client.behavioral_coverage._wait_for_snapshot", fake_wait_for_snapshot)
    monkeypatch.setattr("highbar_client.behavioral_coverage._dispatch", fake_dispatch)
    monkeypatch.setattr(
        "highbar_client.behavioral_coverage._attempt_transport_provisioning",
        lambda _stub, _shared, ctx, wait_timeout_s=0.0, token=None: ctx,
    )
    monkeypatch.setattr(
        "highbar_client.behavioral_coverage._attempt_enemy_fixture_provisioning",
        lambda _stub, _shared, ctx, token=None, timeout_s=6.0: ctx,
    )

    refreshed = _reset_live_context_to_manifest(object(), shared, ctx, timeout_s=10.0, token="tok")

    assert len(dispatched) == 1
    assert dispatched[0].target_unit_id == 103
    assert dispatched[0].commands[0].build_unit.to_build_unit_def_id == 16
    assert refreshed.capability_units["builder"] == 106


def test_reset_live_context_to_manifest_uses_seeded_reissue_when_cheats_enabled(monkeypatch):
    commander = FakeOwnUnit(
        unit_id=42,
        def_id=1,
        position=FakePosition(10.0, 0.0, 20.0),
        health=3250.0,
        max_health=3250.0,
    )
    factory_ground = FakeOwnUnit(
        unit_id=103,
        def_id=13,
        position=FakePosition(170.0, 0.0, 116.0),
        health=2050.0,
        max_health=2050.0,
    )
    current = FakeSnapshot(
        own_units=(commander, factory_ground),
        visible_enemies=(),
        map_features=(),
        frame_number=10,
    )
    restored_builder = FakeOwnUnit(
        unit_id=106,
        def_id=16,
        position=FakePosition(172.0, 0.0, 118.0),
        health=690.0,
        max_health=690.0,
    )
    restored = FakeSnapshot(
        own_units=(commander, factory_ground, restored_builder),
        visible_enemies=(),
        map_features=(),
        frame_number=11,
    )
    shared = {"snapshots": [current], "deltas": []}
    pending_snapshots = [restored]
    seeded_steps = []
    ctx = BootstrapContext(
        commander_unit_id=42,
        commander_position=Vector3(10.0, 0.0, 20.0),
        capability_units={"commander": 42, "factory_ground": 103},
        manifest=(("armck", 1), ("armvp", 1)),
        cheats_enabled=True,
        def_id_by_name={"armvp": 13, "armck": 16},
        observed_own_units={42: commander, 103: factory_ground},
    )

    monkeypatch.setattr(
        "highbar_client.behavioral_coverage._refreshing_snapshot",
        lambda _stub, _shared, token=None, timeout_s=3.0: shared["snapshots"][-1],
    )

    def fake_issue_bootstrap_seed_step(
        _stub,
        _shared,
        _ctx,
        step,
        *,
        baseline_ids,
        token=None,
        static_map=None,
        snapshot=None,
    ):
        del baseline_ids, token, static_map, snapshot
        seeded_steps.append(step.def_id)
        shared["snapshots"].append(pending_snapshots.pop(0))
        return restored_builder

    monkeypatch.setattr(
        "highbar_client.behavioral_coverage._issue_bootstrap_seed_step",
        fake_issue_bootstrap_seed_step,
    )
    monkeypatch.setattr(
        "highbar_client.behavioral_coverage._attempt_transport_provisioning",
        lambda _stub, _shared, refreshed_ctx, wait_timeout_s=0.0, token=None: refreshed_ctx,
    )
    monkeypatch.setattr(
        "highbar_client.behavioral_coverage._attempt_enemy_fixture_provisioning",
        lambda _stub, _shared, refreshed_ctx, token=None, timeout_s=6.0: refreshed_ctx,
    )

    refreshed = _reset_live_context_to_manifest(object(), shared, ctx, timeout_s=10.0, token="tok")

    assert seeded_steps == ["armck"]
    assert refreshed.capability_units["builder"] == 106


def test_reset_live_context_to_manifest_requests_snapshot_while_waiting_for_restore(
    monkeypatch,
):
    commander = FakeOwnUnit(
        unit_id=42,
        def_id=1,
        position=FakePosition(10.0, 0.0, 20.0),
        health=3250.0,
        max_health=3250.0,
    )
    factory_ground = FakeOwnUnit(
        unit_id=103,
        def_id=13,
        position=FakePosition(170.0, 0.0, 116.0),
        health=2050.0,
        max_health=2050.0,
    )
    current = FakeSnapshot(
        own_units=(commander, factory_ground),
        visible_enemies=(),
        map_features=(),
        frame_number=10,
    )
    restored_builder = FakeOwnUnit(
        unit_id=106,
        def_id=16,
        position=FakePosition(172.0, 0.0, 118.0),
        health=690.0,
        max_health=690.0,
    )
    restored = FakeSnapshot(
        own_units=(commander, factory_ground, restored_builder),
        visible_enemies=(),
        map_features=(),
        frame_number=11,
    )
    shared = {"snapshots": [current], "deltas": []}
    request_count = 0
    ctx = BootstrapContext(
        commander_unit_id=42,
        commander_position=Vector3(10.0, 0.0, 20.0),
        capability_units={"commander": 42, "factory_ground": 103},
        manifest=(("armck", 1), ("armvp", 1)),
        def_id_by_name={"armvp": 13, "armck": 16},
        observed_own_units={42: commander, 103: factory_ground},
    )

    monkeypatch.setattr(
        "highbar_client.behavioral_coverage._refreshing_snapshot",
        lambda _stub, _shared, token=None, timeout_s=3.0: shared["snapshots"][-1],
    )
    monkeypatch.setattr(
        "highbar_client.behavioral_coverage._reissue_manifest_shortages",
        lambda _stub, _shared, refreshed_ctx, shortages, token=None: refreshed_ctx,
    )

    def fake_request_snapshot(_stub, token=None):
        nonlocal request_count
        del token
        request_count += 1
        return restored.frame_number

    def fake_wait_for_snapshot(_shared, min_frame, timeout_s):
        del timeout_s
        if request_count <= 0:
            return None
        if shared["snapshots"][-1].frame_number < restored.frame_number:
            shared["snapshots"].append(restored)
        latest = shared["snapshots"][-1]
        if latest.frame_number >= min_frame:
            return latest
        return None

    monkeypatch.setattr(
        "highbar_client.behavioral_coverage._request_snapshot",
        fake_request_snapshot,
    )
    monkeypatch.setattr(
        "highbar_client.behavioral_coverage._wait_for_snapshot",
        fake_wait_for_snapshot,
    )
    monkeypatch.setattr(
        "highbar_client.behavioral_coverage._attempt_transport_provisioning",
        lambda _stub, _shared, refreshed_ctx, wait_timeout_s=0.0, token=None: refreshed_ctx,
    )
    monkeypatch.setattr(
        "highbar_client.behavioral_coverage._attempt_enemy_fixture_provisioning",
        lambda _stub, _shared, refreshed_ctx, token=None, timeout_s=6.0: refreshed_ctx,
    )

    refreshed = _reset_live_context_to_manifest(object(), shared, ctx, timeout_s=0.5, token="tok")

    assert request_count >= 1
    assert refreshed.capability_units["builder"] == 106


def test_reset_live_context_to_manifest_falls_back_to_seeded_bootstrap_after_wait_timeout(
    monkeypatch,
):
    commander = FakeOwnUnit(
        unit_id=42,
        def_id=1,
        position=FakePosition(10.0, 0.0, 20.0),
        health=3250.0,
        max_health=3250.0,
    )
    factory_ground = FakeOwnUnit(
        unit_id=103,
        def_id=13,
        position=FakePosition(170.0, 0.0, 116.0),
        health=2050.0,
        max_health=2050.0,
    )
    factory_air = FakeOwnUnit(
        unit_id=104,
        def_id=14,
        position=FakePosition(-150.0, 0.0, 116.0),
        health=2050.0,
        max_health=2050.0,
    )
    restored_builder = FakeOwnUnit(
        unit_id=106,
        def_id=16,
        position=FakePosition(172.0, 0.0, 118.0),
        health=690.0,
        max_health=690.0,
    )
    restored_cloakable = FakeOwnUnit(
        unit_id=107,
        def_id=17,
        position=FakePosition(-148.0, 0.0, 118.0),
        health=89.0,
        max_health=89.0,
    )
    current = FakeSnapshot(
        own_units=(commander, factory_ground, factory_air),
        visible_enemies=(),
        map_features=(),
        frame_number=10,
    )
    restored = FakeSnapshot(
        own_units=(
            commander,
            factory_ground,
            factory_air,
            restored_builder,
            restored_cloakable,
        ),
        visible_enemies=(),
        map_features=(),
        frame_number=11,
    )
    shared = {"snapshots": [current], "deltas": []}
    wait_call_count = 0
    fallback_calls = []
    ctx = BootstrapContext(
        commander_unit_id=42,
        commander_position=Vector3(10.0, 0.0, 20.0),
        capability_units={"commander": 42, "factory_ground": 103, "factory_air": 104},
        manifest=(("armap", 1), ("armck", 1), ("armpeep", 1), ("armvp", 1)),
        cheats_enabled=True,
        def_id_by_name={"armvp": 13, "armap": 14, "armck": 16, "armpeep": 17},
        observed_own_units={42: commander, 103: factory_ground, 104: factory_air},
    )

    monkeypatch.setattr(
        "highbar_client.behavioral_coverage._refreshing_snapshot",
        lambda _stub, _shared, token=None, timeout_s=5.0: shared["snapshots"][-1],
    )
    monkeypatch.setattr(
        "highbar_client.behavioral_coverage._reissue_manifest_shortages",
        lambda _stub, _shared, refreshed_ctx, shortages, token=None: refreshed_ctx,
    )

    def fake_wait_for_manifest_match(
        _shared,
        _ctx,
        *,
        timeout_s,
        stub=None,
        token=None,
    ):
        nonlocal wait_call_count
        del timeout_s, stub, token
        wait_call_count += 1
        if wait_call_count == 1:
            raise RuntimeError("timeout waiting for bootstrap manifest to be restored")
        return restored

    def fake_attempt_seeded_bootstrap(
        _stub,
        _shared,
        fallback_ctx,
        *,
        token=None,
        static_map=None,
        starting_snapshot=None,
    ):
        del token, static_map
        fallback_calls.append(starting_snapshot)
        shared["snapshots"].append(restored)
        return fallback_ctx, ("armck", "armpeep")

    monkeypatch.setattr(
        "highbar_client.behavioral_coverage._wait_for_manifest_match",
        fake_wait_for_manifest_match,
    )
    monkeypatch.setattr(
        "highbar_client.behavioral_coverage._attempt_seeded_bootstrap",
        fake_attempt_seeded_bootstrap,
    )
    monkeypatch.setattr(
        "highbar_client.behavioral_coverage._attempt_transport_provisioning",
        lambda _stub, _shared, refreshed_ctx, wait_timeout_s=0.0, token=None: refreshed_ctx,
    )
    monkeypatch.setattr(
        "highbar_client.behavioral_coverage._attempt_enemy_fixture_provisioning",
        lambda _stub, _shared, refreshed_ctx, token=None, timeout_s=6.0: refreshed_ctx,
    )

    refreshed = _reset_live_context_to_manifest(object(), shared, ctx, timeout_s=10.0, token="tok")

    assert wait_call_count == 2
    assert fallback_calls == [current]
    assert refreshed.capability_units["builder"] == 106
    assert refreshed.capability_units["cloakable"] == 107


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

# SPDX-License-Identifier: GPL-2.0-only
from __future__ import annotations

import sys
from pathlib import Path

import pytest

from highbar_client.ai_plugins import (
    MoveOnceAI,
    Turtle1AI,
    client_id_for_plugin,
    load_ai_plugin,
    parse_plugin_config,
)
from highbar_client.highbar import callbacks_pb2, common_pb2, state_pb2


def test_builtin_idle_loads_and_client_id_includes_safe_name_addon():
    plugin = load_ai_plugin("idle")

    assert plugin.name == "idle"
    assert client_id_for_plugin(plugin, name_addon="left flank / test") == (
        "hb-python-ai/idle/0.1.0/left-flank-test"
    )


def test_move_once_emits_one_batch_from_first_snapshot():
    plugin = MoveOnceAI({"target_unit": 42, "move_to": "100,0,200"})
    update = state_pb2.StateUpdate(seq=1)
    update.frame = 10
    update.snapshot.frame_number = 10

    first = list(plugin.on_state(None, update))  # type: ignore[arg-type]
    second = list(plugin.on_state(None, update))  # type: ignore[arg-type]

    assert len(first) == 1
    assert first[0].target_unit_id == 42
    assert first[0].commands[0].move_unit.to_position.x == 100.0
    assert first[0].commands[0].move_unit.to_position.z == 200.0
    assert second == []


def test_parse_plugin_config_requires_json_object():
    assert parse_plugin_config('{"target_unit":7}') == {"target_unit": 7}
    with pytest.raises(ValueError, match="must decode to an object"):
        parse_plugin_config("[1, 2, 3]")


def test_load_module_factory_plugin(tmp_path: Path, monkeypatch):
    module_path = tmp_path / "custom_policy.py"
    module_path.write_text(
        """
from highbar_client.ai_plugins import BaseAIPlugin

class CustomPolicy(BaseAIPlugin):
    name = "custom"
    version = "1.2.3"

def create(config):
    policy = CustomPolicy()
    policy.extra = config["extra"]
    return policy
""",
        encoding="utf-8",
    )
    monkeypatch.syspath_prepend(str(tmp_path))
    sys.modules.pop("custom_policy", None)

    plugin = load_ai_plugin("custom_policy:create", config={"extra": "ok"})

    assert plugin.name == "custom"
    assert plugin.version == "1.2.3"
    assert plugin.extra == "ok"


def test_load_rejects_unknown_short_name():
    with pytest.raises(ValueError, match="module:attribute"):
        load_ai_plugin("not-installed")


def test_plugin_contract_validation(tmp_path: Path, monkeypatch):
    module_path = tmp_path / "bad_policy.py"
    module_path.write_text("bad = object()\n", encoding="utf-8")
    monkeypatch.syspath_prepend(str(tmp_path))
    sys.modules.pop("bad_policy", None)

    with pytest.raises(TypeError, match="missing required attribute"):
        load_ai_plugin("bad_policy:bad")


class _FakeHandshake:
    def __init__(self, static_map: state_pb2.StaticMap):
        self.static_map = static_map


class _FakeTurtleContext:
    def __init__(self, static_map: state_pb2.StaticMap):
        self.handshake = _FakeHandshake(static_map)
        self.build_options = {
            1: {11, 12, 13, 14},
            13: {30, 31, 32},
        }

    def invoke_callback(self, callback_id, *, request_id=1, params=(), timeout=5.0):
        assert callback_id == callbacks_pb2.CALLBACK_UNITDEF_GET_BUILD_OPTIONS
        def_id = tuple(params)[0].int_value
        response = callbacks_pb2.CallbackResponse(request_id=request_id, success=True)
        response.result.int_array_value.values.extend(sorted(self.build_options.get(def_id, ())))
        return response

    def resolve_unit_def_ids(self, wanted_names, *, timeout=5.0):
        raise AssertionError("test supplies def_id_by_name directly")


def _unit(unit_id: int, def_id: int, x: float, z: float):
    return state_pb2.OwnUnit(
        unit_id=unit_id,
        def_id=def_id,
        position=common_pb2.Vector3(x=x, y=0.0, z=z),
        health=1000.0,
        max_health=1000.0,
        under_construction=False,
    )


def _left_side_map():
    static_map = state_pb2.StaticMap(width_cells=1024, height_cells=1024)
    static_map.start_positions.extend(
        (
            common_pb2.Vector3(x=1024.0, y=0.0, z=4096.0),
            common_pb2.Vector3(x=7168.0, y=0.0, z=4096.0),
        )
    )
    static_map.metal_spots.extend(
        (
            common_pb2.Vector3(x=900.0, y=0.0, z=3900.0),
            common_pb2.Vector3(x=6900.0, y=0.0, z=3900.0),
        )
    )
    return static_map


def test_turtle1_loads_as_builtin():
    plugin = load_ai_plugin(
        "turtle1",
        config={
            "def_id_by_name": {
                "armcom": 1,
                "armmex": 11,
            }
        },
    )

    assert plugin.name == "turtle1"
    assert client_id_for_plugin(plugin, name_addon="north base") == (
        "hb-python-ai/turtle1/0.1.0/north-base"
    )


def test_turtle1_macros_without_enemy_seeking_and_stays_on_own_side():
    static_map = _left_side_map()
    plugin = Turtle1AI(
        {
            "max_batches_per_update": 4,
            "build_interval_frames": 1,
            "def_id_by_name": {
                "armcom": 1,
                "armmex": 11,
                "armsolar": 12,
                "armvp": 13,
                "armlab": 14,
                "armfav": 30,
                "armstump": 31,
                "armrock": 32,
            },
        }
    )
    context = _FakeTurtleContext(static_map)
    update = state_pb2.StateUpdate(seq=1, frame=100)
    update.snapshot.frame_number = 100
    update.snapshot.static_map.CopyFrom(static_map)
    update.snapshot.own_units.append(_unit(101, 1, 1024.0, 4096.0))
    update.snapshot.economy.metal_income = 3.0
    update.snapshot.economy.energy_income = 30.0

    batches = list(plugin.on_state(context, update))

    assert batches
    for batch in batches:
        for command in batch.commands:
            assert command.WhichOneof("command") == "build_unit"
            assert command.build_unit.build_position.x <= 4096.0 - plugin.side_padding

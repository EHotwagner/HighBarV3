# SPDX-License-Identifier: GPL-2.0-only
from __future__ import annotations

import sys
from pathlib import Path

import pytest

from highbar_client.ai_plugins import (
    MoveOnceAI,
    client_id_for_plugin,
    load_ai_plugin,
    parse_plugin_config,
)
from highbar_client.highbar import state_pb2


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

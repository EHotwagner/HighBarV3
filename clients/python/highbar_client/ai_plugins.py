# SPDX-License-Identifier: GPL-2.0-only
"""Python-side AI policy plugin support.

The native Spring skirmish AI remains the stable ``highBar`` proxy.
Plugins loaded here are external Python policies that connect through
HighBarProxy as ROLE_AI clients and decide which command batches to
submit from state updates.
"""

from __future__ import annotations

import importlib
import inspect
import json
import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Any, Protocol

import grpc

from . import commands
from .highbar import commands_pb2, service_pb2, state_pb2
from .session import Handshake


CLIENT_ID_PREFIX = "hb-python-ai"
_SAFE_CLIENT_ID_PART = re.compile(r"[^A-Za-z0-9_.-]+")


class AIPlugin(Protocol):
    """External Python AI policy contract."""

    name: str
    version: str

    def on_start(self, context: "AIPluginContext") -> None:
        """Called after the ROLE_AI Hello succeeds."""

    def on_state(
        self,
        context: "AIPluginContext",
        update: state_pb2.StateUpdate,
    ) -> Iterable[commands_pb2.CommandBatch]:
        """Return command batches to submit for a state update."""

    def on_stop(self, context: "AIPluginContext") -> None:
        """Called before runner shutdown."""


@dataclass(slots=True)
class AIPluginContext:
    channel: grpc.Channel
    token: str
    handshake: Handshake
    client_id: str
    name_addon: str = ""

    def submit(
        self,
        batch: commands_pb2.CommandBatch,
        *,
        timeout: float | None = None,
    ) -> service_pb2.CommandAck:
        return commands.submit_one(self.channel, self.token, batch, timeout=timeout)


class BaseAIPlugin:
    """Convenience base class for simple Python policies."""

    name = "base"
    version = "0.1.0"

    def on_start(self, context: AIPluginContext) -> None:
        return None

    def on_state(
        self,
        context: AIPluginContext,
        update: state_pb2.StateUpdate,
    ) -> Iterable[commands_pb2.CommandBatch]:
        return ()

    def on_stop(self, context: AIPluginContext) -> None:
        return None


class IdleAI(BaseAIPlugin):
    name = "idle"
    version = "0.1.0"

    def __init__(self, config: Mapping[str, Any] | None = None):
        _ = config


class MoveOnceAI(BaseAIPlugin):
    """Tiny built-in policy useful for smoke tests."""

    name = "move-once"
    version = "0.1.0"

    def __init__(self, config: Mapping[str, Any] | None = None):
        cfg = dict(config or {})
        self.target_unit = int(cfg.get("target_unit", 1))
        raw_move_to = cfg.get("move_to", (1024.0, 0.0, 1024.0))
        if isinstance(raw_move_to, str):
            move_to = tuple(float(part) for part in raw_move_to.split(","))
        else:
            move_to = tuple(float(part) for part in raw_move_to)
        if len(move_to) != 3:
            raise ValueError("move-once move_to must contain x,y,z")
        self.move_to = move_to
        self._submitted = False

    def on_state(
        self,
        context: AIPluginContext,
        update: state_pb2.StateUpdate,
    ) -> Iterable[commands_pb2.CommandBatch]:
        if self._submitted or not update.HasField("snapshot"):
            return ()
        self._submitted = True
        x, y, z = self.move_to
        return (
            commands.batch(
                target_unit=self.target_unit,
                batch_seq=1,
                orders=[commands.move_to(x, y, z)],
            ),
        )


BUILTIN_PLUGINS = {
    "idle": IdleAI,
    "move-once": MoveOnceAI,
}


def parse_plugin_config(raw: str | None) -> dict[str, Any]:
    if raw in (None, ""):
        return {}
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"plugin config JSON is invalid: {exc.msg}") from exc
    if not isinstance(payload, dict):
        raise ValueError("plugin config JSON must decode to an object")
    return dict(payload)


def sanitize_client_id_part(value: str) -> str:
    stripped = value.strip()
    if not stripped:
        return ""
    sanitized = _SAFE_CLIENT_ID_PART.sub("-", stripped).strip("-")
    return sanitized[:64]


def client_id_for_plugin(plugin: AIPlugin, *, name_addon: str = "") -> str:
    plugin_name = sanitize_client_id_part(getattr(plugin, "name", "plugin")) or "plugin"
    plugin_version = sanitize_client_id_part(getattr(plugin, "version", "0.0.0")) or "0.0.0"
    addon = sanitize_client_id_part(name_addon)
    base = f"{CLIENT_ID_PREFIX}/{plugin_name}/{plugin_version}"
    return f"{base}/{addon}" if addon else base


def _instantiate_plugin(candidate: object, config: Mapping[str, Any]) -> AIPlugin:
    if inspect.isclass(candidate):
        instance = candidate(config)
    elif callable(candidate):
        instance = candidate(config)
    else:
        instance = candidate
    for attr in ("name", "version", "on_start", "on_state", "on_stop"):
        if not hasattr(instance, attr):
            raise TypeError(f"AI plugin is missing required attribute {attr!r}")
    return instance  # type: ignore[return-value]


def load_ai_plugin(
    spec: str,
    *,
    config: Mapping[str, Any] | None = None,
) -> AIPlugin:
    """Load a built-in plugin name or ``module:attribute`` plugin spec."""

    normalized = (spec or "idle").strip() or "idle"
    cfg = dict(config or {})
    if normalized in BUILTIN_PLUGINS:
        return BUILTIN_PLUGINS[normalized](cfg)
    if ":" not in normalized:
        known = ", ".join(sorted(BUILTIN_PLUGINS))
        raise ValueError(
            f"unknown AI plugin {normalized!r}; use one of {known} or module:attribute"
        )
    module_name, attr_name = normalized.split(":", 1)
    if not module_name or not attr_name:
        raise ValueError("AI plugin spec must be '<module>:<attribute>'")
    module = importlib.import_module(module_name)
    candidate = getattr(module, attr_name)
    return _instantiate_plugin(candidate, cfg)

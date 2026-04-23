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
from dataclasses import dataclass, field
from typing import Any, Protocol

import grpc

from . import commands
from .highbar import (
    callbacks_pb2,
    commands_pb2,
    common_pb2,
    service_pb2,
    service_pb2_grpc,
    state_pb2,
)
from .session import TOKEN_HEADER, Handshake


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
    _callback_stub: service_pb2_grpc.HighBarProxyStub | None = field(
        default=None,
        init=False,
        repr=False,
    )

    def submit(
        self,
        batch: commands_pb2.CommandBatch,
        *,
        timeout: float | None = None,
    ) -> service_pb2.CommandAck:
        return commands.submit_one(self.channel, self.token, batch, timeout=timeout)

    def invoke_callback(
        self,
        callback_id: int,
        *,
        request_id: int = 1,
        params: Iterable[callbacks_pb2.CallbackParam] = (),
        timeout: float | None = 5.0,
    ) -> callbacks_pb2.CallbackResponse:
        if self._callback_stub is None:
            self._callback_stub = service_pb2_grpc.HighBarProxyStub(self.channel)
        return self._callback_stub.InvokeCallback(
            callbacks_pb2.CallbackRequest(
                request_id=request_id,
                callback_id=callback_id,
                params=tuple(params),
            ),
            metadata=[(TOKEN_HEADER, self.token)],
            timeout=timeout,
        )

    def resolve_unit_def_ids(
        self,
        wanted_names: Iterable[str],
        *,
        timeout: float | None = 5.0,
    ) -> dict[str, int]:
        wanted = set(wanted_names)
        if not wanted:
            return {}
        bulk = self.invoke_callback(
            callbacks_pb2.CALLBACK_GET_UNIT_DEFS,
            request_id=1,
            timeout=timeout,
        )
        if not bulk.success or not bulk.result.HasField("int_array_value"):
            raise RuntimeError(bulk.error_message or "unit-def callback returned no ids")
        resolved: dict[str, int] = {}
        for index, def_id in enumerate(bulk.result.int_array_value.values, start=2):
            name_resp = self.invoke_callback(
                callbacks_pb2.CALLBACK_UNITDEF_GET_NAME,
                request_id=index,
                params=(callbacks_pb2.CallbackParam(int_value=int(def_id)),),
                timeout=timeout,
            )
            if not name_resp.success or not name_resp.result.HasField("string_value"):
                continue
            def_name = name_resp.result.string_value
            if def_name in wanted:
                resolved[def_name] = int(def_id)
        return resolved


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


class Turtle1AI(BaseAIPlugin):
    """Defensive macro policy that builds economy, tech, and a mixed army."""

    name = "turtle1"
    version = "0.1.0"

    DEFAULT_UNIT_NAMES = {
        "commanders": (
            "armcom",
            "corcom",
        ),
        "economy": (
            "armmex",
            "cormex",
            "armsolar",
            "corsolar",
            "armwin",
            "corwin",
            "armestor",
            "corestor",
            "armmstor",
            "cormstor",
        ),
        "factories": (
            "armvp",
            "corvp",
            "armlab",
            "corlab",
            "armap",
            "corap",
        ),
        "advanced_factories": (
            "armavp",
            "coravp",
            "armalab",
            "coralab",
            "armaap",
            "coraap",
        ),
        "builders": (
            "armck",
            "corck",
            "armcv",
            "corcv",
            "armca",
            "corca",
            "armacv",
            "coracv",
            "armack",
            "corack",
        ),
        "defense": (
            "armllt",
            "corllt",
            "armrl",
            "corrl",
            "armrad",
            "corrad",
            "armjamt",
            "coreyes",
        ),
        "army": (
            "armfav",
            "corfav",
            "armpw",
            "corak",
            "armrock",
            "corstorm",
            "armham",
            "corthud",
            "armstump",
            "corgator",
            "armjanus",
            "corraid",
            "armart",
            "corwolv",
            "armpeep",
            "corfink",
            "armfig",
            "corveng",
        ),
        "advanced_army": (
            "armbull",
            "correap",
            "armmav",
            "cormort",
            "armyork",
            "corsent",
            "armhawk",
            "corvamp",
        ),
    }

    def __init__(self, config: Mapping[str, Any] | None = None):
        cfg = dict(config or {})
        self.max_batches_per_update = int(cfg.get("max_batches_per_update", 4))
        self.build_interval_frames = int(cfg.get("build_interval_frames", 180))
        self.base_radius = float(cfg.get("base_radius", 950.0))
        self.side_padding = float(cfg.get("side_padding", 256.0))
        self.target_mex = int(cfg.get("target_mex", 5))
        self.target_energy = int(cfg.get("target_energy", 7))
        self.target_factories = int(cfg.get("target_factories", 3))
        self.target_builders = int(cfg.get("target_builders", 5))
        self.target_defense = int(cfg.get("target_defense", 8))
        self.target_army = int(cfg.get("target_army", 45))
        self.target_advanced_factories = int(cfg.get("target_advanced_factories", 1))
        self.enable_advanced = _config_bool(cfg.get("enable_advanced", True))
        self.queue_macro_orders = _config_bool(cfg.get("queue_macro_orders", False))
        self.unit_names = {
            key: tuple(cfg.get(key, default))
            for key, default in self.DEFAULT_UNIT_NAMES.items()
        }
        self.def_id_by_name = {
            str(key): int(value)
            for key, value in dict(cfg.get("def_id_by_name", {})).items()
        }
        self.name_by_def_id: dict[int, str] = {
            def_id: name for name, def_id in self.def_id_by_name.items()
        }
        self.build_options_by_def_id: dict[int, set[int]] = {}
        self.batch_seq = 1
        self.last_build_frame = -self.build_interval_frames
        self.resolution_attempted = False
        self._army_cursor = 0
        self._advanced_army_cursor = 0
        self._build_site_cursor = 0

    def on_start(self, context: AIPluginContext) -> None:
        # Runtime callback relay can appear after Hello in client-mode runs.
        # Resolve lazily from the first usable state update instead of
        # blocking startup before the state stream is open.
        return None

    def on_state(
        self,
        context: AIPluginContext,
        update: state_pb2.StateUpdate,
    ) -> Iterable[commands_pb2.CommandBatch]:
        if not update.HasField("snapshot"):
            return ()
        if not self.resolution_attempted:
            self._resolve_defs(context)
        if update.frame < self.last_build_frame + self.build_interval_frames:
            return ()
        snapshot = update.snapshot
        ready_units = [unit for unit in snapshot.own_units if self._is_ready(unit)]
        if not ready_units:
            return ()

        static_map = (
            snapshot.static_map
            if snapshot.HasField("static_map")
            else context.handshake.static_map
        )
        anchor = self._base_anchor(snapshot, static_map)
        batches: list[commands_pb2.CommandBatch] = []
        self._append_hold_position_batches(ready_units, batches)
        self._append_macro_batches(context, snapshot, ready_units, static_map, anchor, batches)
        if batches:
            self.last_build_frame = int(update.frame)
        return tuple(batches[: self.max_batches_per_update])

    def _resolve_defs(self, context: AIPluginContext) -> None:
        self.resolution_attempted = True
        wanted = {
            name
            for names in self.unit_names.values()
            for name in names
            if name not in self.def_id_by_name
        }
        if not wanted:
            return
        try:
            self.def_id_by_name.update(context.resolve_unit_def_ids(wanted))
        except Exception:
            return
        self.name_by_def_id = {
            def_id: name for name, def_id in self.def_id_by_name.items()
        }

    def _build_options_for_unit(
        self,
        context: AIPluginContext,
        unit: state_pb2.OwnUnit,
    ) -> set[int]:
        if unit.def_id in self.build_options_by_def_id:
            return self.build_options_by_def_id[unit.def_id]
        try:
            response = context.invoke_callback(
                callbacks_pb2.CALLBACK_UNITDEF_GET_BUILD_OPTIONS,
                request_id=10_000 + int(unit.def_id),
                params=(callbacks_pb2.CallbackParam(int_value=int(unit.def_id)),),
            )
        except Exception:
            self.build_options_by_def_id[unit.def_id] = set()
            return set()
        if not response.success or not response.result.HasField("int_array_value"):
            self.build_options_by_def_id[unit.def_id] = set()
            return set()
        options = {int(value) for value in response.result.int_array_value.values}
        self.build_options_by_def_id[unit.def_id] = options
        return options

    def _append_macro_batches(
        self,
        context: AIPluginContext,
        snapshot: state_pb2.StateSnapshot,
        ready_units: list[state_pb2.OwnUnit],
        static_map: state_pb2.StaticMap,
        anchor: common_pb2.Vector3,
        batches: list[commands_pb2.CommandBatch],
    ) -> None:
        counts = self._counts_by_group(snapshot)
        plan: list[tuple[str, tuple[str, ...]]] = []
        if counts["mex"] < self.target_mex:
            plan.append(("mex", self._names("armmex", "cormex")))
        if counts["energy"] < self.target_energy:
            plan.append(("energy", self._names("armsolar", "corsolar", "armwin", "corwin")))
        if counts["factories"] < self.target_factories:
            plan.append(("factory", self.unit_names["factories"]))
        if counts["builders"] < self.target_builders:
            plan.append(("builder", self.unit_names["builders"]))
        if counts["defense"] < self.target_defense:
            plan.append(("defense", self.unit_names["defense"]))
        if (
            self.enable_advanced
            and counts["factories"] >= 1
            and counts["advanced_factories"] < self.target_advanced_factories
            and snapshot.economy.metal_income >= 2.0
            and snapshot.economy.energy_income >= 20.0
        ):
            plan.append(("advanced_factory", self.unit_names["advanced_factories"]))
        if counts["army"] < self.target_army:
            plan.append(("army", self._rotated_army_names(advanced=False)))
        if counts["advanced_factories"] > 0 and counts["army"] < self.target_army:
            plan.append(("advanced_army", self._rotated_army_names(advanced=True)))

        for category, names in plan:
            if len(batches) >= self.max_batches_per_update:
                return
            target_name = self._first_resolved(names)
            if target_name is None:
                continue
            target_def_id = self.def_id_by_name[target_name]
            builder = self._find_builder(context, ready_units, target_def_id, category)
            if builder is None:
                continue
            position = self._position_for_category(
                category,
                snapshot,
                static_map,
                anchor,
                builder,
                target_name,
            )
            batches.append(
                commands.batch(
                    target_unit=int(builder.unit_id),
                    batch_seq=self._next_batch_seq(),
                    orders=[
                        commands.build(
                            target_def_id,
                            position.x,
                            position.y,
                            position.z,
                        )
                    ],
                    opts=(
                        commands.OptionBits.SHIFT
                        if self.queue_macro_orders
                        else commands.OptionBits.NONE
                    ),
                )
            )

    def _append_hold_position_batches(
        self,
        ready_units: list[state_pb2.OwnUnit],
        batches: list[commands_pb2.CommandBatch],
    ) -> None:
        army_def_ids = self._def_ids_for(
            (*self.unit_names["army"], *self.unit_names["advanced_army"])
        )
        for unit in ready_units:
            if len(batches) >= 1:
                return
            if int(unit.def_id) not in army_def_ids:
                continue
            batches.append(
                commands.batch(
                    target_unit=int(unit.unit_id),
                    batch_seq=self._next_batch_seq(),
                    orders=[commands.move_state(0), commands.fire_state(2)],
                )
            )

    def _counts_by_group(self, snapshot: state_pb2.StateSnapshot) -> dict[str, int]:
        counts = {
            "mex": 0,
            "energy": 0,
            "factories": 0,
            "advanced_factories": 0,
            "builders": 0,
            "defense": 0,
            "army": 0,
        }
        groups = {
            "mex": self._names("armmex", "cormex"),
            "energy": self._names("armsolar", "corsolar", "armwin", "corwin", "armestor", "corestor"),
            "factories": self.unit_names["factories"],
            "advanced_factories": self.unit_names["advanced_factories"],
            "builders": self.unit_names["builders"],
            "defense": self.unit_names["defense"],
            "army": (*self.unit_names["army"], *self.unit_names["advanced_army"]),
        }
        group_ids = {key: self._def_ids_for(names) for key, names in groups.items()}
        for unit in snapshot.own_units:
            if unit.health <= 0:
                continue
            def_id = int(unit.def_id)
            for key, def_ids in group_ids.items():
                if def_id in def_ids:
                    counts[key] += 1
        return counts

    def _find_builder(
        self,
        context: AIPluginContext,
        ready_units: list[state_pb2.OwnUnit],
        target_def_id: int,
        category: str,
    ) -> state_pb2.OwnUnit | None:
        for unit in ready_units:
            build_options = self._build_options_for_unit(context, unit)
            if target_def_id in build_options:
                return unit
            if not build_options and self._can_fallback_build(unit, category):
                return unit
        return None

    def _can_fallback_build(self, unit: state_pb2.OwnUnit, category: str) -> bool:
        def_id = int(unit.def_id)
        if category in {"mex", "energy", "factory", "defense", "advanced_factory"}:
            base_builders = self._def_ids_for(
                (*self.unit_names["commanders"], *self.unit_names["builders"])
            )
            if base_builders:
                return def_id in base_builders
            non_base_builders = self._def_ids_for(
                (
                    *self.unit_names["factories"],
                    *self.unit_names["advanced_factories"],
                    *self.unit_names["army"],
                    *self.unit_names["advanced_army"],
                    *self.unit_names["economy"],
                    *self.unit_names["defense"],
                )
            )
            return def_id not in non_base_builders
        if category in {"builder", "army", "advanced_army"}:
            return def_id in self._def_ids_for(
                (*self.unit_names["factories"], *self.unit_names["advanced_factories"])
            )
        return False

    def _position_for_category(
        self,
        category: str,
        snapshot: state_pb2.StateSnapshot,
        static_map: state_pb2.StaticMap,
        anchor: common_pb2.Vector3,
        builder: state_pb2.OwnUnit,
        target_name: str,
    ) -> common_pb2.Vector3:
        if category == "mex":
            return self._next_metal_spot(snapshot, static_map, anchor)
        if category in {"army", "advanced_army", "builder"}:
            return commands.vec3(builder.position.x, builder.position.y, builder.position.z)
        return self._next_base_site(static_map, anchor, target_name)

    def _next_metal_spot(
        self,
        snapshot: state_pb2.StateSnapshot,
        static_map: state_pb2.StaticMap,
        anchor: common_pb2.Vector3,
    ) -> common_pb2.Vector3:
        mex_ids = self._def_ids_for(self._names("armmex", "cormex"))
        existing = [
            unit.position
            for unit in snapshot.own_units
            if int(unit.def_id) in mex_ids
        ]
        candidates = sorted(
            (
                spot
                for spot in static_map.metal_spots
                if self._on_own_side(spot, static_map, anchor)
                and self._distance2(spot, anchor) <= self.base_radius * self.base_radius * 4
                and all(self._distance2(spot, pos) > 140.0 * 140.0 for pos in existing)
            ),
            key=lambda spot: self._distance2(spot, anchor),
        )
        if candidates:
            spot = candidates[0]
            return commands.vec3(spot.x, spot.y, spot.z)
        return self._next_base_site(static_map, anchor, "mex")

    def _next_base_site(
        self,
        static_map: state_pb2.StaticMap,
        anchor: common_pb2.Vector3,
        target_name: str,
    ) -> common_pb2.Vector3:
        ring = (
            (-220.0, -180.0),
            (220.0, -180.0),
            (-260.0, 180.0),
            (260.0, 180.0),
            (-420.0, 0.0),
            (420.0, 0.0),
            (0.0, -360.0),
            (0.0, 360.0),
        )
        idx = self._build_site_cursor % len(ring)
        self._build_site_cursor += 1
        dx, dz = ring[idx]
        if target_name in self.unit_names["defense"]:
            dx *= 1.7
            dz *= 1.7
        pos = commands.vec3(anchor.x + dx, anchor.y, anchor.z + dz)
        return self._clamp_to_own_side(pos, static_map, anchor)

    def _base_anchor(
        self,
        snapshot: state_pb2.StateSnapshot,
        static_map: state_pb2.StaticMap,
    ) -> common_pb2.Vector3:
        ready = [unit for unit in snapshot.own_units if self._is_ready(unit)]
        if ready:
            x = sum(unit.position.x for unit in ready) / len(ready)
            y = sum(unit.position.y for unit in ready) / len(ready)
            z = sum(unit.position.z for unit in ready) / len(ready)
            return commands.vec3(x, y, z)
        if static_map.start_positions:
            pos = static_map.start_positions[0]
            return commands.vec3(pos.x, pos.y, pos.z)
        return commands.vec3(0.0, 0.0, 0.0)

    def _on_own_side(
        self,
        pos: common_pb2.Vector3,
        static_map: state_pb2.StaticMap,
        anchor: common_pb2.Vector3,
    ) -> bool:
        max_x = self._map_max_x(static_map, anchor)
        if max_x <= 0:
            return self._distance2(pos, anchor) <= self.base_radius * self.base_radius * 4
        middle = max_x / 2.0
        if anchor.x <= middle:
            return pos.x <= middle + self.side_padding
        return pos.x >= middle - self.side_padding

    def _clamp_to_own_side(
        self,
        pos: common_pb2.Vector3,
        static_map: state_pb2.StaticMap,
        anchor: common_pb2.Vector3,
    ) -> common_pb2.Vector3:
        max_x = self._map_max_x(static_map, anchor)
        if max_x <= 0:
            return pos
        middle = max_x / 2.0
        x = pos.x
        if anchor.x <= middle:
            x = min(max(pos.x, self.side_padding), middle - self.side_padding)
        else:
            x = max(min(pos.x, max_x - self.side_padding), middle + self.side_padding)
        return commands.vec3(x, pos.y, max(pos.z, self.side_padding))

    def _map_max_x(
        self,
        static_map: state_pb2.StaticMap,
        anchor: common_pb2.Vector3,
    ) -> float:
        start_x = [pos.x for pos in static_map.start_positions]
        if start_x:
            return max(max(start_x) * 1.25, anchor.x * 1.5, 1.0)
        if static_map.width_cells:
            return float(static_map.width_cells) * 8.0
        return 0.0

    def _rotated_army_names(self, *, advanced: bool) -> tuple[str, ...]:
        names = self.unit_names["advanced_army" if advanced else "army"]
        if not names:
            return ()
        cursor = self._advanced_army_cursor if advanced else self._army_cursor
        rotated = tuple(names[cursor:] + names[:cursor])
        if advanced:
            self._advanced_army_cursor = (self._advanced_army_cursor + 1) % len(names)
        else:
            self._army_cursor = (self._army_cursor + 1) % len(names)
        return rotated

    def _first_resolved(self, names: Iterable[str]) -> str | None:
        return next((name for name in names if self.def_id_by_name.get(name)), None)

    def _def_ids_for(self, names: Iterable[str]) -> set[int]:
        return {
            int(self.def_id_by_name[name])
            for name in names
            if self.def_id_by_name.get(name)
        }

    def _names(self, *names: str) -> tuple[str, ...]:
        return tuple(names)

    def _next_batch_seq(self) -> int:
        value = self.batch_seq
        self.batch_seq += 1
        return value

    @staticmethod
    def _is_ready(unit: state_pb2.OwnUnit) -> bool:
        return (
            unit.health > 0
            and not unit.under_construction
            and (unit.max_health <= 0 or unit.health >= unit.max_health * 0.35)
        )

    @staticmethod
    def _distance2(
        left: common_pb2.Vector3,
        right: common_pb2.Vector3,
    ) -> float:
        return (left.x - right.x) ** 2 + (left.z - right.z) ** 2


BUILTIN_PLUGINS = {
    "idle": IdleAI,
    "move-once": MoveOnceAI,
    "turtle1": Turtle1AI,
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


def _config_bool(value: object) -> bool:
    if isinstance(value, str):
        return value.strip().lower() not in {"0", "false", "no", "off"}
    return bool(value)


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

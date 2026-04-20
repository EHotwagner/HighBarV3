# SPDX-License-Identifier: GPL-2.0-only
"""SubmitCommands wrapper (T089).

Python-ergonomic builders for the most common unit commands plus a
``submit`` helper that opens the client-stream, writes N CommandBatch
messages, and awaits the final CommandAck. Attacher routes the AI
token through the ``x-highbar-ai-token`` metadata.

For the 80+ AICommand arms not listed here (drawing, chat, groups,
pathfinding, lua, figures, etc.), callers should build the protobuf
AICommand directly and wrap it in their own CommandBatch — same
principle as the F# client's ``Commands.Raw``.
"""

from __future__ import annotations

import sys
from typing import Iterable

import grpc

from highbar.v1 import commands_pb2, common_pb2, service_pb2_grpc


def _v3(x: float, y: float, z: float) -> common_pb2.Vector3:
    v = common_pb2.Vector3()
    v.x, v.y, v.z = x, y, z
    return v


def move_to(unit_id: int, x: float, y: float, z: float) -> commands_pb2.AICommand:
    cmd = commands_pb2.AICommand()
    cmd.move_unit.unit_id = unit_id
    cmd.move_unit.timeout = sys.maxsize
    cmd.move_unit.to_position.CopyFrom(_v3(x, y, z))
    return cmd


def stop(unit_id: int) -> commands_pb2.AICommand:
    cmd = commands_pb2.AICommand()
    cmd.stop.unit_id = unit_id
    cmd.stop.timeout = sys.maxsize
    return cmd


def patrol_to(unit_id: int, x: float, y: float, z: float) -> commands_pb2.AICommand:
    cmd = commands_pb2.AICommand()
    cmd.patrol.unit_id = unit_id
    cmd.patrol.timeout = sys.maxsize
    cmd.patrol.to_position.CopyFrom(_v3(x, y, z))
    return cmd


def fight_to(unit_id: int, x: float, y: float, z: float) -> commands_pb2.AICommand:
    cmd = commands_pb2.AICommand()
    cmd.fight.unit_id = unit_id
    cmd.fight.timeout = sys.maxsize
    cmd.fight.to_position.CopyFrom(_v3(x, y, z))
    return cmd


def attack_area(
    unit_id: int, x: float, y: float, z: float, radius: float
) -> commands_pb2.AICommand:
    cmd = commands_pb2.AICommand()
    cmd.attack_area.unit_id = unit_id
    cmd.attack_area.timeout = sys.maxsize
    cmd.attack_area.attack_position.CopyFrom(_v3(x, y, z))
    cmd.attack_area.radius = radius
    return cmd


def build(
    unit_id: int,
    to_build_def_id: int,
    x: float,
    y: float,
    z: float,
    facing: int = 0,
) -> commands_pb2.AICommand:
    cmd = commands_pb2.AICommand()
    cmd.build_unit.unit_id = unit_id
    cmd.build_unit.timeout = sys.maxsize
    cmd.build_unit.to_build_unit_def_id = to_build_def_id
    cmd.build_unit.build_position.CopyFrom(_v3(x, y, z))
    cmd.build_unit.facing = facing
    return cmd


def repair(unit_id: int, target_unit_id: int) -> commands_pb2.AICommand:
    cmd = commands_pb2.AICommand()
    cmd.repair.unit_id = unit_id
    cmd.repair.timeout = sys.maxsize
    cmd.repair.repair_unit_id = target_unit_id
    return cmd


def reclaim_unit(unit_id: int, target_unit_id: int) -> commands_pb2.AICommand:
    cmd = commands_pb2.AICommand()
    cmd.reclaim_unit.unit_id = unit_id
    cmd.reclaim_unit.timeout = sys.maxsize
    cmd.reclaim_unit.reclaim_unit_id = target_unit_id
    return cmd


def batch(
    batch_seq: int, target_unit_id: int, *commands: commands_pb2.AICommand
) -> commands_pb2.CommandBatch:
    b = commands_pb2.CommandBatch()
    b.batch_seq = batch_seq
    b.target_unit_id = target_unit_id
    b.commands.extend(commands)
    return b


def submit(
    channel: grpc.Channel,
    token: str,
    batches: Iterable[commands_pb2.CommandBatch],
):
    """Open SubmitCommands, stream batches, return the final CommandAck."""
    stub = service_pb2_grpc.HighBarProxyStub(channel)
    metadata = (("x-highbar-ai-token", token),)
    return stub.SubmitCommands(iter(batches), metadata=metadata)

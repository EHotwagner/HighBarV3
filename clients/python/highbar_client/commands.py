# SPDX-License-Identifier: GPL-2.0-only
"""Command helpers + SubmitCommands client stream (T089).

Mirrors the coverage in clients/fsharp/src/Commands.fs — 15 unit-order
arms. The raw AICommand proto is still accessible for the long tail.
"""

from __future__ import annotations

import enum
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from typing import Optional

from .highbar import (  # type: ignore
    commands_pb2,
    common_pb2,
    service_pb2,
)
TOKEN_HEADER = "x-highbar-ai-token"


def vec3(x: float, y: float, z: float) -> common_pb2.Vector3:
    return common_pb2.Vector3(x=x, y=y, z=z)


class OptionBits(enum.IntFlag):
    NONE = 0
    SHIFT = 1  # queued
    CTRL = 2
    ALT = 4


@dataclass(frozen=True, slots=True)
class Order:
    """Internal sum type — use the builder functions below."""

    kind: str
    payload: dict


def move_to(x: float, y: float, z: float) -> Order:
    return Order("move_to", {"pos": vec3(x, y, z)})


def patrol_to(x: float, y: float, z: float) -> Order:
    return Order("patrol_to", {"pos": vec3(x, y, z)})


def fight_to(x: float, y: float, z: float) -> Order:
    return Order("fight_to", {"pos": vec3(x, y, z)})


def attack_area(x: float, y: float, z: float, radius: float) -> Order:
    return Order("attack_area", {"pos": vec3(x, y, z), "radius": radius})


def stop() -> Order:
    return Order("stop", {})


def wait() -> Order:
    return Order("wait", {})


def build(def_id: int, x: float, y: float, z: float, facing: int = 0) -> Order:
    return Order(
        "build",
        {"def_id": def_id, "pos": vec3(x, y, z), "facing": facing},
    )


def repair(repair_unit_id: int) -> Order:
    return Order("repair", {"repair_unit_id": repair_unit_id})


def reclaim_unit(reclaim_unit_id: int) -> Order:
    return Order("reclaim_unit", {"reclaim_unit_id": reclaim_unit_id})


def reclaim_area(x: float, y: float, z: float, radius: float) -> Order:
    return Order("reclaim_area", {"pos": vec3(x, y, z), "radius": radius})


def resurrect_area(x: float, y: float, z: float, radius: float) -> Order:
    return Order("resurrect_area", {"pos": vec3(x, y, z), "radius": radius})


def self_destruct() -> Order:
    return Order("self_destruct", {})


def wanted_speed(speed: float) -> Order:
    return Order("wanted_speed", {"speed": speed})


def fire_state(state: int) -> Order:
    return Order("fire_state", {"state": state})


def move_state(state: int) -> Order:
    return Order("move_state", {"state": state})


def _to_proto(
    order: Order, unit_id: int, opts: OptionBits
) -> commands_pb2.AICommand:
    cmd = commands_pb2.AICommand()
    bits = int(opts)
    k = order.kind
    p = order.payload
    if k == "move_to":
        cmd.move_unit.unit_id = unit_id
        cmd.move_unit.options = bits
        cmd.move_unit.to_position.CopyFrom(p["pos"])
    elif k == "patrol_to":
        cmd.patrol.unit_id = unit_id
        cmd.patrol.options = bits
        cmd.patrol.to_position.CopyFrom(p["pos"])
    elif k == "fight_to":
        cmd.fight.unit_id = unit_id
        cmd.fight.options = bits
        cmd.fight.to_position.CopyFrom(p["pos"])
    elif k == "attack_area":
        cmd.attack_area.unit_id = unit_id
        cmd.attack_area.options = bits
        cmd.attack_area.attack_position.CopyFrom(p["pos"])
        cmd.attack_area.radius = p["radius"]
    elif k == "stop":
        cmd.stop.unit_id = unit_id
        cmd.stop.options = bits
    elif k == "wait":
        cmd.wait.unit_id = unit_id
        cmd.wait.options = bits
    elif k == "build":
        cmd.build_unit.unit_id = unit_id
        cmd.build_unit.options = bits
        cmd.build_unit.to_build_unit_def_id = p["def_id"]
        cmd.build_unit.build_position.CopyFrom(p["pos"])
        cmd.build_unit.facing = p["facing"]
    elif k == "repair":
        cmd.repair.unit_id = unit_id
        cmd.repair.options = bits
        cmd.repair.repair_unit_id = p["repair_unit_id"]
    elif k == "reclaim_unit":
        cmd.reclaim_unit.unit_id = unit_id
        cmd.reclaim_unit.options = bits
        cmd.reclaim_unit.reclaim_unit_id = p["reclaim_unit_id"]
    elif k == "reclaim_area":
        cmd.reclaim_area.unit_id = unit_id
        cmd.reclaim_area.options = bits
        cmd.reclaim_area.position.CopyFrom(p["pos"])
        cmd.reclaim_area.radius = p["radius"]
    elif k == "resurrect_area":
        cmd.resurrect_in_area.unit_id = unit_id
        cmd.resurrect_in_area.options = bits
        cmd.resurrect_in_area.position.CopyFrom(p["pos"])
        cmd.resurrect_in_area.radius = p["radius"]
    elif k == "self_destruct":
        cmd.self_destruct.unit_id = unit_id
        cmd.self_destruct.options = bits
    elif k == "wanted_speed":
        cmd.set_wanted_max_speed.unit_id = unit_id
        cmd.set_wanted_max_speed.options = bits
        cmd.set_wanted_max_speed.wanted_max_speed = p["speed"]
    elif k == "fire_state":
        cmd.set_fire_state.unit_id = unit_id
        cmd.set_fire_state.options = bits
        cmd.set_fire_state.fire_state = p["state"]
    elif k == "move_state":
        cmd.set_move_state.unit_id = unit_id
        cmd.set_move_state.options = bits
        cmd.set_move_state.move_state = p["state"]
    else:
        raise ValueError(f"unknown order kind: {k}")
    return cmd


def batch(
    target_unit: int,
    batch_seq: int,
    orders: Iterable[Order],
    opts: OptionBits = OptionBits.NONE,
    client_command_id: int | None = None,
    based_on_frame: int | None = None,
    based_on_state_seq: int | None = None,
    conflict_policy: int | None = None,
) -> commands_pb2.CommandBatch:
    b = commands_pb2.CommandBatch(batch_seq=batch_seq, target_unit_id=target_unit)
    if client_command_id is not None:
        b.client_command_id = client_command_id
    if based_on_frame is not None:
        b.based_on_frame = based_on_frame
    if based_on_state_seq is not None:
        b.based_on_state_seq = based_on_state_seq
    if conflict_policy is not None:
        b.conflict_policy = conflict_policy
    for ord_ in orders:
        b.commands.append(_to_proto(ord_, target_unit, opts))
    return b


def issue_summary(
    result: commands_pb2.CommandBatchResult,
) -> list[tuple[str, int, str, str]]:
    return [
        (
            commands_pb2.CommandIssueCode.Name(issue.code),
            issue.command_index,
            issue.field_path,
            commands_pb2.RetryHint.Name(issue.retry_hint),
        )
        for issue in result.issues
    ]


def submit_one(
    channel_,
    token: str,
    batch_: commands_pb2.CommandBatch,
    timeout: Optional[float] = None,
) -> service_pb2.CommandAck:
    """One-shot SubmitCommands: send a single batch and await the ack."""

    def _batches() -> Iterator[commands_pb2.CommandBatch]:
        yield batch_

    from .highbar import service_pb2_grpc  # type: ignore

    stub = service_pb2_grpc.HighBarProxyStub(channel_)
    metadata = [(TOKEN_HEADER, token)]
    return stub.SubmitCommands(_batches(), metadata=metadata, timeout=timeout)


def validate_batch(
    channel_,
    token: str,
    batch_: commands_pb2.CommandBatch,
    timeout: Optional[float] = None,
) -> commands_pb2.CommandBatchResult:
    from .highbar import service_pb2_grpc  # type: ignore

    stub = service_pb2_grpc.HighBarProxyStub(channel_)
    metadata = [(TOKEN_HEADER, token)]
    return stub.ValidateCommandBatch(batch_, metadata=metadata, timeout=timeout)

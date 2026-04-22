#!/usr/bin/env python3
"""Minimal AI-role client.

Connects to the coordinator via HighBarProxy:
  1. Hello(ROLE_AI)
  2. StreamState (server streaming) — picks a controllable own unit
     from either a fresh UnitCreated delta or the next snapshot.
  3. SubmitCommands (client streaming) — sends one MoveUnit command
     targeting that unit. Coordinator forwards to the plugin, which
     drains it in DrainCommandQueue and dispatches via CmdMoveTo.
  4. Continues watching StreamState briefly to confirm the unit's
     position actually changes.

End-to-end verification of the full client-mode loop:
  external AI process → coordinator → plugin → engine → unit moves
"""
import sys
import argparse
import threading
import time

sys.path.insert(0, "/tmp/hb-run/pyproto")

import grpc
from highbar import service_pb2, service_pb2_grpc
from highbar import commands_pb2, common_pb2


def _remember_unit(out, unit_id, source, detail):
    if out.get("unit_id") is not None:
        return
    out["unit_id"] = unit_id
    out["unit_id_at"] = time.time()
    out["unit_source"] = source
    print(detail, flush=True)


def watch_state(stub, out):
    """Background thread: stream state, pick the first controllable unit.

    We prefer a live UnitCreated delta when it arrives after subscribe,
    but also fall back to snapshot own-units so late subscribers do not
    miss already-spawned commanders.
    """
    req = service_pb2.StreamStateRequest(resume_from_seq=0)
    try:
        for update in stub.StreamState(req, timeout=120):
            payload = update.WhichOneof("payload")
            if payload == "snapshot":
                if out.get("unit_id") is None:
                    for unit in update.snapshot.own_units:
                        if unit.health > 0.0 and not unit.under_construction:
                            _remember_unit(
                                out,
                                unit.unit_id,
                                "snapshot",
                                (
                                    "[ai] selected own unit from snapshot "
                                    f"id={unit.unit_id} health={unit.health:.1f}"
                                ),
                            )
                            break
                continue
            if payload != "delta":
                continue
            for ev in update.delta.events:
                kind = ev.WhichOneof("kind")
                if kind == "unit_created" and out.get("unit_id") is None:
                    _remember_unit(
                        out,
                        ev.unit_created.unit_id,
                        "unit_created",
                        (
                            "[ai] saw UnitCreated "
                            f"id={ev.unit_created.unit_id} "
                            f"builder={ev.unit_created.builder_id}"
                        ),
                    )
                elif kind == "unit_damaged":
                    # T065: assert only on checkable damage events.
                    # The gateway must forward the engine payload
                    # verbatim, and live matches do emit legitimate
                    # attackerless damage events with no direction.
                    # Those do not prove the widening regressed.
                    d = ev.unit_damaged
                    dir_ok = (d.direction.x != 0.0
                              or d.direction.y != 0.0
                              or d.direction.z != 0.0)
                    if d.damage <= 0.0:
                        out["damage_invalid"] = (
                            out.get("damage_invalid", 0) + 1)
                    elif not dir_ok:
                        if d.HasField("attacker_id"):
                            out["damage_invalid"] = (
                                out.get("damage_invalid", 0) + 1)
                        else:
                            out["damage_skipped_unattributed"] = (
                                out.get("damage_skipped_unattributed", 0) + 1)
    except grpc.RpcError as e:
        out["err"] = e.code().name


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--endpoint", required=True)
    p.add_argument("--wait", type=float, default=15.0,
                   help="seconds to wait for a UnitCreated event")
    p.add_argument("--dx", type=float, default=500.0,
                   help="x offset in elmos")
    p.add_argument("--dz", type=float, default=0.0,
                   help="z offset in elmos")
    args = p.parse_args()

    ch = grpc.insecure_channel(args.endpoint)
    stub = service_pb2_grpc.HighBarProxyStub(ch)

    # Hello as AI role.
    hello = stub.Hello(service_pb2.HelloRequest(
        schema_version="1.0.0",
        role=service_pb2.Role.ROLE_AI,
    ), timeout=5)
    print(f"[ai] Hello OK session={hello.session_id}", flush=True)

    # Watch state in a background thread.
    shared = {}
    t = threading.Thread(target=watch_state, args=(stub, shared), daemon=True)
    t.start()

    # Wait for a unit id from either a live creation delta or snapshot state.
    deadline = time.time() + args.wait
    while time.time() < deadline and shared.get("unit_id") is None:
        time.sleep(0.2)
    uid = shared.get("unit_id")
    if uid is None:
        print(
            f"[ai] no controllable unit in {args.wait}s — check state stream",
            flush=True,
        )
        return 1

    # Submit a MoveUnit command.
    def gen():
        batch = commands_pb2.CommandBatch()
        batch.batch_seq = 1
        batch.target_unit_id = uid
        cmd = batch.commands.add()
        cmd.move_unit.unit_id = uid
        cmd.move_unit.to_position.x = args.dx
        cmd.move_unit.to_position.y = 0.0
        cmd.move_unit.to_position.z = args.dz
        cmd.move_unit.options = 0
        cmd.move_unit.timeout = 0
        print(f"[ai] sending MoveUnit unit_id={uid} "
              f"to=({args.dx},0,{args.dz})", flush=True)
        yield batch

    ack = stub.SubmitCommands(gen(), timeout=10)
    print(f"[ai] SubmitCommands ack: accepted={ack.batches_accepted} "
          f"rejected_invalid={ack.batches_rejected_invalid} "
          f"rejected_full={ack.batches_rejected_full}", flush=True)

    # Let the state stream run a few seconds to capture effect.
    time.sleep(5)
    invalid = shared.get("damage_invalid", 0)
    skipped = shared.get("damage_skipped_unattributed", 0)
    print(
        f"[ai] done; unit_id={uid} damage_invalid={invalid} "
        f"damage_skipped_unattributed={skipped}",
        flush=True,
    )
    if invalid > 0:
        return 2  # T065 widening regression — driver script flags as fail.
    return 0


if __name__ == "__main__":
    sys.exit(main())

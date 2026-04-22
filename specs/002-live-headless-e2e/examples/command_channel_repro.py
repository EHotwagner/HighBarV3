#!/usr/bin/env python3
"""Minimal repro for coordinator command-channel lifetime.

Starts no engine and no plugin. Instead it:
  1. Opens HighBarCoordinator.OpenCommandChannel as a fake plugin.
  2. Optionally streams heartbeats in the background.
  3. Says Hello as an AI-role client on HighBarProxy.
  4. Sends N one-batch SubmitCommands RPCs.
  5. Reports whether the command channel stayed open and how many
     batches arrived on it.

This isolates the Python coordinator relay from the rest of the live
stack so we can tell whether the "disconnect after two batches" bug
exists without spring-headless or the C++ plugin.
"""

from __future__ import annotations

import argparse
import sys
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path

import grpc

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT / "clients/python/highbar_client"))

from highbar import commands_pb2, coordinator_pb2, coordinator_pb2_grpc
from highbar import service_pb2, service_pb2_grpc
from highbar import state_pb2


def _make_channel(endpoint: str) -> grpc.Channel:
    if endpoint.startswith("unix:"):
        return grpc.insecure_channel(endpoint)
    return grpc.insecure_channel(endpoint)


def _make_move_batch(batch_seq: int, unit_id: int) -> commands_pb2.CommandBatch:
    batch = commands_pb2.CommandBatch()
    batch.batch_seq = batch_seq
    batch.target_unit_id = unit_id
    cmd = batch.commands.add()
    cmd.move_unit.unit_id = unit_id
    cmd.move_unit.to_position.x = float(100 * batch_seq)
    cmd.move_unit.to_position.y = 0.0
    cmd.move_unit.to_position.z = 0.0
    cmd.move_unit.options = 0
    cmd.move_unit.timeout = 0
    return batch


@dataclass
class CommandChannelState:
    received_batch_seqs: list[int] = field(default_factory=list)
    read_error: str | None = None
    finished: bool = False


@dataclass
class StateStreamState:
    updates_seen: int = 0
    read_error: str | None = None
    finished: bool = False


def _heartbeat_loop(
    stub: coordinator_pb2_grpc.HighBarCoordinatorStub,
    plugin_id: str,
    stop_event: threading.Event,
    interval_s: float,
) -> None:
    frame = 0
    while not stop_event.is_set():
        frame += 30
        try:
            stub.Heartbeat(
                coordinator_pb2.HeartbeatRequest(
                    plugin_id=plugin_id,
                    frame=frame,
                    engine_sha256="repro",
                    schema_version="1.0.0",
                ),
                timeout=1.0,
            )
        except grpc.RpcError:
            return
        stop_event.wait(interval_s)


def _command_channel_loop(
    stub: coordinator_pb2_grpc.HighBarCoordinatorStub,
    plugin_id: str,
    state: CommandChannelState,
    stop_event: threading.Event,
) -> None:
    try:
        stream = stub.OpenCommandChannel(
            coordinator_pb2.CommandChannelSubscribe(
                plugin_id=plugin_id,
                schema_version="1.0.0",
            ),
            timeout=60.0,
        )
        for batch in stream:
            state.received_batch_seqs.append(batch.batch_seq)
            print(
                "[repro] cmd-channel received "
                f"batch_seq={batch.batch_seq} ncmds={len(batch.commands)}",
                flush=True,
            )
            if stop_event.is_set():
                break
    except grpc.RpcError as exc:
        state.read_error = f"{exc.code().name}: {exc.details()}"
    finally:
        state.finished = True


def _push_state_loop(
    stub: coordinator_pb2_grpc.HighBarCoordinatorStub,
    stop_event: threading.Event,
    interval_s: float,
) -> None:
    def gen():
        seq = 0
        while not stop_event.is_set():
            seq += 1
            update = state_pb2.StateUpdate()
            update.seq = seq
            update.frame = seq * 30
            update.keepalive.SetInParent()
            yield update
            if stop_event.wait(interval_s):
                break

    try:
        ack = stub.PushState(gen(), timeout=60.0)
        print(
            "[repro] PushState closed "
            f"messages_received={ack.messages_received} "
            f"max_seq_seen={ack.max_seq_seen}",
            flush=True,
        )
    except grpc.RpcError as exc:
        print(
            f"[repro] PushState error {exc.code().name}: {exc.details()}",
            flush=True,
        )


def _state_stream_loop(
    stub: service_pb2_grpc.HighBarProxyStub,
    state: StateStreamState,
    stop_event: threading.Event,
) -> None:
    try:
        stream = stub.StreamState(
            service_pb2.StreamStateRequest(resume_from_seq=0),
            timeout=60.0,
        )
        for update in stream:
            state.updates_seen += 1
            print(
                "[repro] state-stream update "
                f"seq={update.seq} payload={update.WhichOneof('payload')}",
                flush=True,
            )
            if stop_event.is_set():
                break
    except grpc.RpcError as exc:
        state.read_error = f"{exc.code().name}: {exc.details()}"
    finally:
        state.finished = True


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--endpoint", required=True)
    parser.add_argument("--plugin-id", default="repro-plugin")
    parser.add_argument("--client-id", default="repro-ai")
    parser.add_argument("--unit-id", type=int, default=1)
    parser.add_argument("--batches", type=int, default=3)
    parser.add_argument("--delay-ms", type=int, default=150)
    parser.add_argument("--post-wait-ms", type=int, default=500)
    parser.add_argument("--disable-heartbeats", action="store_true")
    parser.add_argument("--disable-push-state", action="store_true")
    parser.add_argument("--disable-stream-state", action="store_true")
    args = parser.parse_args()

    channel = _make_channel(args.endpoint)
    coord_stub = coordinator_pb2_grpc.HighBarCoordinatorStub(channel)
    proxy_stub = service_pb2_grpc.HighBarProxyStub(channel)

    stop_event = threading.Event()
    channel_state = CommandChannelState()
    state_stream_state = StateStreamState()

    cmd_thread = threading.Thread(
        target=_command_channel_loop,
        args=(coord_stub, args.plugin_id, channel_state, stop_event),
        daemon=True,
    )
    cmd_thread.start()

    hb_thread = None
    if not args.disable_heartbeats:
        hb_thread = threading.Thread(
            target=_heartbeat_loop,
            args=(coord_stub, args.plugin_id, stop_event, 0.2),
            daemon=True,
        )
        hb_thread.start()

    push_thread = None
    if not args.disable_push_state:
        push_thread = threading.Thread(
            target=_push_state_loop,
            args=(coord_stub, stop_event, 0.2),
            daemon=True,
        )
        push_thread.start()

    state_thread = None
    if not args.disable_stream_state:
        state_thread = threading.Thread(
            target=_state_stream_loop,
            args=(proxy_stub, state_stream_state, stop_event),
            daemon=True,
        )
        state_thread.start()

    # Let the command channel subscribe before sending commands.
    time.sleep(0.3)

    hello = proxy_stub.Hello(
        service_pb2.HelloRequest(
            schema_version="1.0.0",
            client_id=args.client_id,
            role=service_pb2.Role.ROLE_AI,
        ),
        timeout=5.0,
    )
    print(f"[repro] Hello OK session={hello.session_id}", flush=True)

    submit_errors: list[str] = []
    for batch_seq in range(1, args.batches + 1):
        batch = _make_move_batch(batch_seq, args.unit_id)

        def gen():
            yield batch

        try:
            ack = proxy_stub.SubmitCommands(gen(), timeout=5.0)
            print(
                "[repro] SubmitCommands ack "
                f"batch_seq={batch_seq} accepted={ack.batches_accepted}",
                flush=True,
            )
        except grpc.RpcError as exc:
            msg = f"batch_seq={batch_seq} {exc.code().name}: {exc.details()}"
            submit_errors.append(msg)
            print(f"[repro] SubmitCommands error {msg}", flush=True)
        time.sleep(args.delay_ms / 1000.0)

    time.sleep(args.post_wait_ms / 1000.0)
    stop_event.set()
    cmd_thread.join(timeout=2.0)
    if hb_thread is not None:
        hb_thread.join(timeout=1.0)
    if push_thread is not None:
        push_thread.join(timeout=1.0)
    if state_thread is not None:
        state_thread.join(timeout=1.0)

    print(
        "[repro] summary "
        f"received={channel_state.received_batch_seqs} "
        f"finished={channel_state.finished} "
        f"read_error={channel_state.read_error!r} "
        f"state_updates_seen={state_stream_state.updates_seen} "
        f"state_stream_finished={state_stream_state.finished} "
        f"state_stream_error={state_stream_state.read_error!r} "
        f"submit_errors={submit_errors}",
        flush=True,
    )

    expected = list(range(1, args.batches + 1))
    if channel_state.received_batch_seqs != expected:
        return 2
    if submit_errors:
        return 3
    if channel_state.finished and not stop_event.is_set():
        return 4
    return 0


if __name__ == "__main__":
    sys.exit(main())

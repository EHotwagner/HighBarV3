# SPDX-License-Identifier: GPL-2.0-only
"""StreamState consumer with monotonic-seq checker (T087).

Mirrors clients/fsharp/src/StateStream.fs. Emits each StateUpdate to
the caller's handler and enforces the FR-006 monotonicity invariant on
the client side as defense-in-depth — a server bug that regressed seq
would surface here as SeqInvariantError rather than silently downstream
in observer UIs.
"""

from __future__ import annotations

from typing import Callable, Iterator, Optional

import grpc

from highbar.v1 import service_pb2, service_pb2_grpc


class SeqInvariantError(RuntimeError):
    """Raised when the stream violates strict-monotonic ``seq``."""


OnUpdate = Callable[[object], None]  # argument is highbar.v1.StateUpdate


def consume(
    channel: grpc.Channel,
    resume_from_seq: int = 0,
    on_update: Optional[OnUpdate] = None,
) -> Iterator[object]:
    """Open StreamState and yield each StateUpdate.

    ``resume_from_seq=0`` asks for a fresh snapshot; any other value is
    a resume request. Callers may either consume the generator directly
    or pass ``on_update`` to side-effect each message while also getting
    yielded values — both interfaces are provided so scripts can pick
    whichever fits their control flow.
    """
    stub = service_pb2_grpc.HighBarProxyStub(channel)
    req = service_pb2.StreamStateRequest(resume_from_seq=resume_from_seq)
    last_seq: Optional[int] = None
    snapshots_seen = 0

    for upd in stub.StreamState(req):
        if last_seq is not None and upd.seq <= last_seq:
            raise SeqInvariantError(
                f"seq regression: got {upd.seq} after {last_seq}"
            )
        if upd.WhichOneof("payload") == "snapshot":
            snapshots_seen += 1
        last_seq = upd.seq
        if on_update is not None:
            on_update(upd)
        yield upd

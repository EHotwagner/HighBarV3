# SPDX-License-Identifier: GPL-2.0-only
"""StreamState consumer with seq-monotonicity checker (T087).

Port of clients/fsharp/src/StateStream.fs. The invariant checker is
authoritative: any gap, duplicate, or regression raises
``SeqInvariantError`` — equivalent to the F# client's
``SeqInvariantException``, so SC-004's byte-equality claim between
F# and Python clients extends to their error paths too.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Optional

import grpc

from .highbar import service_pb2, service_pb2_grpc, state_pb2  # type: ignore


class SeqInvariantError(RuntimeError):
    """Raised when a StateUpdate has non-monotonic seq."""


def consume(
    channel: grpc.Channel,
    resume_from_seq: int = 0,
    max_wait_seconds: Optional[float] = None,
) -> Iterator[state_pb2.StateUpdate]:
    """Yield StateUpdates from StreamState. Checks monotonic seq.

    The caller iterates and runs their own per-update logic. Cancel
    by closing the channel or breaking out of the loop — grpcio
    sends CANCELLED to the server on iterator close.
    """
    stub = service_pb2_grpc.HighBarProxyStub(channel)
    req = service_pb2.StreamStateRequest(resume_from_seq=resume_from_seq)

    last_seq: Optional[int] = None
    call_kwargs: dict = {}
    if max_wait_seconds is not None:
        call_kwargs["timeout"] = max_wait_seconds

    for update in stub.StreamState(req, **call_kwargs):
        if last_seq is not None and update.seq <= last_seq:
            raise SeqInvariantError(
                f"seq regression: got {update.seq} after {last_seq}"
            )
        last_seq = update.seq
        yield update


def record(
    channel: grpc.Channel,
    resume_from_seq: int = 0,
    max_updates: Optional[int] = None,
    max_wait_seconds: Optional[float] = None,
) -> list[state_pb2.StateUpdate]:
    """Diagnostic: drain up to ``max_updates`` updates into a list.

    Do not use on long-lived streams — the buffer is unbounded except
    for ``max_updates``.
    """
    out: list[state_pb2.StateUpdate] = []
    try:
        for update in consume(channel, resume_from_seq, max_wait_seconds):
            out.append(update)
            if max_updates is not None and len(out) >= max_updates:
                break
    except grpc.RpcError as e:
        # Deadline hits here; callers usually want partial results
        # rather than losing them.
        if e.code() != grpc.StatusCode.DEADLINE_EXCEEDED:
            raise
    return out

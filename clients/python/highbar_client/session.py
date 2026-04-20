# SPDX-License-Identifier: GPL-2.0-only
"""Hello handshake + token loader (T086).

Observer- and AI-role handshakes share the same Hello wire format; the
AI role additionally reads the per-session token file with exponential
backoff (handles the startup race per data-model §7) and attaches
``x-highbar-ai-token`` to the RPC metadata.

Schema version is a compile-time constant on the C++ side; we keep our
own copy and check both against the server's reply (FR-022a defense in
depth — the server already rejects a mismatch with FAILED_PRECONDITION,
but a client-side assert catches the rare case where a test mocks the
server wire).
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass
from typing import Optional

import grpc

from highbar.v1 import service_pb2, service_pb2_grpc
from highbar.v1.service_pb2 import Role


SCHEMA_VERSION = "1.0.0"


@dataclass
class Handshake:
    session_id: str
    static_map: object  # highbar.v1.StaticMap
    current_frame: int
    role: str  # "observer" | "ai"


def read_token_with_backoff(path: str, max_wait_ms: int = 5_000) -> str:
    """Read the token file, retrying with exponential backoff.

    The plugin writes the token file atomically after generating it and
    before ``HighBarService::Bind`` unblocks; clients that race the
    plugin's startup may see the file not-yet-present. Retry up to
    ``max_wait_ms`` with a 25→1000 ms exponential delay.
    """
    deadline = time.monotonic() + max_wait_ms / 1000
    delay_ms = 25
    while not os.path.exists(path):
        if time.monotonic() >= deadline:
            raise FileNotFoundError(
                f"token file not present within {max_wait_ms}ms: {path}"
            )
        time.sleep(delay_ms / 1000)
        delay_ms = min(1000, delay_ms * 2)
    with open(path, "r", encoding="ascii") as f:
        return f.read().strip()


def hello(
    channel: grpc.Channel,
    role: str = "observer",
    client_id: str = "hb-python/0.1.0",
    token: Optional[str] = None,
) -> Handshake:
    """Open a Hello RPC. Returns Handshake on OK.

    FAILED_PRECONDITION from the server bubbles as grpc.RpcError; the
    status detail carries both server and client schema versions so
    callers can surface a meaningful error.
    """
    stub = service_pb2_grpc.HighBarProxyStub(channel)
    req = service_pb2.HelloRequest(
        schema_version=SCHEMA_VERSION,
        client_id=client_id,
        role=Role.ROLE_AI if role == "ai" else Role.ROLE_OBSERVER,
    )
    metadata = ()
    if token is not None:
        metadata = (("x-highbar-ai-token", token),)
    resp = stub.Hello(req, metadata=metadata)

    if resp.schema_version != SCHEMA_VERSION:
        raise RuntimeError(
            f"schema mismatch: server={resp.schema_version} "
            f"client={SCHEMA_VERSION}"
        )

    return Handshake(
        session_id=resp.session_id,
        static_map=resp.static_map,
        current_frame=resp.current_frame,
        role=role,
    )


def hello_ai(
    channel: grpc.Channel,
    client_id: str,
    token_path: str,
    max_token_wait_ms: int = 5_000,
) -> tuple[Handshake, str]:
    """AI-role convenience: read the token with backoff, then Hello."""
    token = read_token_with_backoff(token_path, max_token_wait_ms)
    handshake = hello(channel, role="ai", client_id=client_id, token=token)
    return handshake, token

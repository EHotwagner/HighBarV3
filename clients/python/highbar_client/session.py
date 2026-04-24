# SPDX-License-Identifier: GPL-2.0-only
"""Hello handshake + AI token loader (T086).

Mirrors clients/fsharp/src/Session.fs behavior so SC-004's byte-equal
stream claim holds: both clients ship the same SchemaVersion, both
do strict-equality verification on HelloResponse, both read the token
file with exponential backoff up to 5s.
"""

from __future__ import annotations

import enum
import os
import time
from dataclasses import dataclass
from typing import Optional

import grpc

from . import SCHEMA_VERSION
from .highbar import service_pb2, service_pb2_grpc, state_pb2  # type: ignore

TOKEN_HEADER = "x-highbar-ai-token"


class ClientRole(enum.Enum):
    OBSERVER = service_pb2.Role.ROLE_OBSERVER
    AI = service_pb2.Role.ROLE_AI


@dataclass(slots=True)
class Handshake:
    session_id: str
    schema_version: str
    static_map: state_pb2.StaticMap
    current_frame: int
    role: ClientRole


def read_token_with_backoff(path: str, max_delay_ms: int = 5000) -> str:
    """Read the AI token file, retrying with exponential backoff.

    The plugin writes the token after init but before Bind unblocks —
    a client that starts simultaneously can race it. Matches the F#
    client's 25ms → 1000ms cap; total wait bounded by ``max_delay_ms``.
    """
    deadline = time.monotonic() + (max_delay_ms / 1000.0)
    delay_ms = 25
    while not os.path.isfile(path):
        if time.monotonic() >= deadline:
            raise TimeoutError(
                f"token file not present within {max_delay_ms}ms: {path}"
            )
        time.sleep(delay_ms / 1000.0)
        delay_ms = min(1000, delay_ms * 2)
    with open(path, "r", encoding="utf-8") as f:
        return f.read().strip()


def hello(
    channel: grpc.Channel,
    role: ClientRole,
    client_id: str,
    token: Optional[str] = None,
) -> Handshake:
    """Open a Hello RPC. Raises grpc.RpcError on FAILED_PRECONDITION /
    PERMISSION_DENIED / ALREADY_EXISTS per contracts/README.md §Hello.

    ``token``: required when ``role == AI``. The server's auth
    interceptor does not gate Hello on the token, but a token-carrying
    Hello keeps the metadata handle available for subsequent RPCs on
    the same channel.
    """
    stub = service_pb2_grpc.HighBarProxyStub(channel)
    req = service_pb2.HelloRequest(
        schema_version=SCHEMA_VERSION,
        client_id=client_id,
        role=role.value,
    )
    metadata: list[tuple[str, str]] = []
    if token is not None:
        metadata.append((TOKEN_HEADER, token))

    resp = stub.Hello(req, metadata=metadata)

    # FR-022a defense-in-depth mirror of the F# client: server already
    # rejected mismatch with FAILED_PRECONDITION, but re-verify here so
    # unit tests that stub the server can't silently drift.
    if resp.schema_version != SCHEMA_VERSION:
        raise RuntimeError(
            f"schema mismatch: server={resp.schema_version} "
            f"client={SCHEMA_VERSION}"
        )

    return Handshake(
        session_id=resp.session_id,
        schema_version=resp.schema_version,
        static_map=resp.static_map,
        current_frame=resp.current_frame,
        role=role,
    )


def get_command_schema(
    channel: grpc.Channel,
    token: str,
    timeout: Optional[float] = None,
) -> service_pb2.CommandSchemaResponse:
    stub = service_pb2_grpc.HighBarProxyStub(channel)
    return stub.GetCommandSchema(
        service_pb2.CommandSchemaRequest(),
        metadata=[(TOKEN_HEADER, token)],
        timeout=timeout,
    )


def get_unit_capabilities(
    channel: grpc.Channel,
    token: str,
    unit_id: int,
    timeout: Optional[float] = None,
) -> service_pb2.UnitCapabilitiesResponse:
    stub = service_pb2_grpc.HighBarProxyStub(channel)
    req = service_pb2.UnitCapabilitiesRequest(unit_id=unit_id)
    return stub.GetUnitCapabilities(
        req,
        metadata=[(TOKEN_HEADER, token)],
        timeout=timeout,
    )

# SPDX-License-Identifier: GPL-2.0-only
"""Channel construction for the HighBarV3 gateway (T085).

Mirrors clients/fsharp/src/Channel.fs: UDS channels use the
``unix:PATH`` scheme that grpcio natively supports on Linux; TCP
channels use ``host:port`` against the plain insecure credentials
(loopback-only, FR-013/14 delegate confidentiality to the filesystem
and the loopback bind).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Union

import grpc


@dataclass(frozen=True)
class UdsEndpoint:
    """Unix domain socket endpoint; ``path`` is an absolute filesystem path."""

    path: str


@dataclass(frozen=True)
class TcpEndpoint:
    """Loopback TCP endpoint; ``host_port`` is the ``host:port`` string."""

    host_port: str


Endpoint = Union[UdsEndpoint, TcpEndpoint]


def for_endpoint(endpoint: Endpoint, max_recv_mb: int = 32) -> grpc.Channel:
    """Open an insecure channel for ``endpoint``.

    ``max_recv_mb`` bumps ``grpc.max_receive_message_length`` so that
    late-game snapshots (>4 MiB) don't trip the default 4 MiB ceiling —
    matches ``data/config/grpc.json``'s default.
    """
    options = [
        ("grpc.max_receive_message_length", max_recv_mb * 1024 * 1024),
    ]
    if isinstance(endpoint, UdsEndpoint):
        target = f"unix:{endpoint.path}"
    elif isinstance(endpoint, TcpEndpoint):
        target = endpoint.host_port
    else:
        raise TypeError(f"unknown endpoint type: {type(endpoint).__name__}")
    return grpc.insecure_channel(target, options=options)


def parse(transport: str, uds_path: str, tcp_bind: str) -> Endpoint:
    """Resolve a ``(transport, uds_path, tcp_bind)`` triple into an Endpoint.

    Shapes match ``data/config/grpc.json`` so higher layers stay
    transport-agnostic.
    """
    t = transport.lower()
    if t == "uds":
        return UdsEndpoint(path=uds_path)
    if t == "tcp":
        return TcpEndpoint(host_port=tcp_bind)
    raise ValueError(f"unknown transport {transport!r} (expected uds|tcp)")

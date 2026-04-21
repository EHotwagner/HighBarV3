# SPDX-License-Identifier: GPL-2.0-only
"""gRPC channel construction for HighBarV3 (T085).

UDS uses grpcio's `unix:<path>` target form. TCP uses `host:port`.
Both are InsecureChannel — the same-host trust model applies per
docs/transport.md; there is no TLS on this boundary.
"""

from __future__ import annotations

from dataclasses import dataclass

import grpc

DEFAULT_MAX_RECV_MB = 32


@dataclass(frozen=True, slots=True)
class Endpoint:
    """Transport discriminator — mirrors clients/fsharp/src/Channel.fs."""

    kind: str  # "uds" or "tcp"
    target: str  # for UDS: filesystem path; for TCP: "host:port"

    @classmethod
    def uds(cls, path: str) -> "Endpoint":
        return cls(kind="uds", target=path)

    @classmethod
    def tcp(cls, host_port: str) -> "Endpoint":
        return cls(kind="tcp", target=host_port)


def _channel_options(max_recv_mb: int) -> list[tuple[str, int]]:
    return [
        ("grpc.max_receive_message_length", max_recv_mb * 1024 * 1024),
    ]


def for_endpoint(
    endpoint: Endpoint, max_recv_mb: int = DEFAULT_MAX_RECV_MB
) -> grpc.Channel:
    """Build an insecure grpc.Channel for the given endpoint."""
    opts = _channel_options(max_recv_mb)
    if endpoint.kind == "uds":
        return grpc.insecure_channel(f"unix:{endpoint.target}", options=opts)
    if endpoint.kind == "tcp":
        return grpc.insecure_channel(endpoint.target, options=opts)
    raise ValueError(f"unknown transport: {endpoint.kind}")


def parse(transport: str, uds_path: str, tcp_bind: str) -> Endpoint:
    """Config-shape parse — matches data/config/grpc.json."""
    t = transport.lower()
    if t == "uds":
        return Endpoint.uds(uds_path)
    if t == "tcp":
        return Endpoint.tcp(tcp_bind)
    raise ValueError(f"unknown transport '{transport}' (expected uds|tcp)")

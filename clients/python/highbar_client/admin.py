# SPDX-License-Identifier: GPL-2.0-only
"""HighBarAdmin generated-client helpers."""

from __future__ import annotations

from typing import Optional

import grpc

from .highbar import service_pb2, service_pb2_grpc
from .session import TOKEN_HEADER


def get_capabilities(
    channel: grpc.Channel,
    token: str,
    timeout: Optional[float] = None,
) -> service_pb2.AdminCapabilitiesResponse:
    stub = service_pb2_grpc.HighBarAdminStub(channel)
    return stub.GetAdminCapabilities(
        service_pb2.AdminCapabilitiesRequest(),
        metadata=[(TOKEN_HEADER, token)],
        timeout=timeout,
    )


def validate_action(
    channel: grpc.Channel,
    token: str,
    action: service_pb2.AdminAction,
    timeout: Optional[float] = None,
) -> service_pb2.AdminActionResult:
    stub = service_pb2_grpc.HighBarAdminStub(channel)
    return stub.ValidateAdminAction(
        action,
        metadata=[(TOKEN_HEADER, token)],
        timeout=timeout,
    )


def execute_action(
    channel: grpc.Channel,
    token: str,
    action: service_pb2.AdminAction,
    timeout: Optional[float] = None,
) -> service_pb2.AdminActionResult:
    stub = service_pb2_grpc.HighBarAdminStub(channel)
    return stub.ExecuteAdminAction(
        action,
        metadata=[(TOKEN_HEADER, token)],
        timeout=timeout,
    )

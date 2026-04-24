# SPDX-License-Identifier: GPL-2.0-only
"""HighBarAdmin generated-client helpers.

Admin RPCs use the normal AI token for channel authorization. Mutating
actions also need run-scoped admin metadata so the server can apply the
operator/admin/test-harness role model and lease ownership rules.
"""

from __future__ import annotations

from typing import Optional

import grpc

from .highbar import service_pb2, service_pb2_grpc
from .session import TOKEN_HEADER

ADMIN_ROLE_HEADER = "x-highbar-admin-role"
ADMIN_CLIENT_ID_HEADER = "x-highbar-client-id"


def unit_transfer_action(
    *,
    unit_id: int,
    from_team_id: int,
    to_team_id: int,
    preserve_orders: bool = True,
    action_seq: int = 0,
    client_action_id: int = 0,
    based_on_frame: int = 0,
    based_on_state_seq: int = 0,
    reason: str = "",
) -> service_pb2.AdminAction:
    """Build the additive admin unit-transfer action."""

    return service_pb2.AdminAction(
        action_seq=action_seq,
        client_action_id=client_action_id,
        based_on_frame=based_on_frame,
        based_on_state_seq=based_on_state_seq,
        conflict_policy=service_pb2.ADMIN_CONFLICT_REJECT_IF_CONTROLLED,
        reason=reason,
        unit_transfer=service_pb2.UnitTransferAction(
            unit_id=unit_id,
            from_team_id=from_team_id,
            to_team_id=to_team_id,
            preserve_orders=preserve_orders,
        ),
    )


def _metadata(
    token: str,
    *,
    admin_role: Optional[str] = None,
    client_id: Optional[str] = None,
) -> list[tuple[str, str]]:
    metadata = [(TOKEN_HEADER, token)]
    if admin_role:
        metadata.append((ADMIN_ROLE_HEADER, admin_role))
    if client_id:
        metadata.append((ADMIN_CLIENT_ID_HEADER, client_id))
    return metadata


def get_capabilities(
    channel: grpc.Channel,
    token: str,
    timeout: Optional[float] = None,
    *,
    admin_role: Optional[str] = None,
    client_id: Optional[str] = None,
) -> service_pb2.AdminCapabilitiesResponse:
    """Return the server's available admin roles, actions, and flags.

    Args:
        channel: gRPC channel connected to the HighBar endpoint.
        token: AI token read from the run's token file.
        timeout: Optional per-RPC deadline in seconds.
        admin_role: Optional run-scoped role header, for example
            ``"operator"``, ``"admin"``, or ``"test-harness"``.
        client_id: Optional caller identity used in server logs/audit
            trails when the admin service records a caller.
    """

    stub = service_pb2_grpc.HighBarAdminStub(channel)
    return stub.GetAdminCapabilities(
        service_pb2.AdminCapabilitiesRequest(),
        metadata=_metadata(token, admin_role=admin_role, client_id=client_id),
        timeout=timeout,
    )


def validate_action(
    channel: grpc.Channel,
    token: str,
    action: service_pb2.AdminAction,
    timeout: Optional[float] = None,
    *,
    admin_role: Optional[str] = None,
    client_id: Optional[str] = None,
) -> service_pb2.AdminActionResult:
    """Dry-run an admin action without dispatching it to the engine.

    Pass ``admin_role`` for privileged validation. The server accepts
    ``"operator"``, ``"admin"``, and ``"test-harness"`` for executable
    admin actions; omitted or observer/AI roles are rejected with a
    structured permission issue.
    """

    stub = service_pb2_grpc.HighBarAdminStub(channel)
    return stub.ValidateAdminAction(
        action,
        metadata=_metadata(token, admin_role=admin_role, client_id=client_id),
        timeout=timeout,
    )


def execute_action(
    channel: grpc.Channel,
    token: str,
    action: service_pb2.AdminAction,
    timeout: Optional[float] = None,
    *,
    admin_role: Optional[str] = None,
    client_id: Optional[str] = None,
) -> service_pb2.AdminActionResult:
    """Execute an admin action and return the server's structured result.

    ``client_id`` is used for lease ownership and audit identity. Use a
    stable value per operator/tool instance so repeated actions can renew
    or conflict with leases predictably.
    """

    stub = service_pb2_grpc.HighBarAdminStub(channel)
    return stub.ExecuteAdminAction(
        action,
        metadata=_metadata(token, admin_role=admin_role, client_id=client_id),
        timeout=timeout,
    )

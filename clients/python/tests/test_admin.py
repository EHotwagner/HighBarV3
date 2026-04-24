# SPDX-License-Identifier: GPL-2.0-only

from highbar_client import admin
from highbar_client.highbar import service_pb2
from highbar_client.session import TOKEN_HEADER


class _RecordingAdminStub:
    calls = []

    def __init__(self, channel):
        self.channel = channel

    def GetAdminCapabilities(self, request, *, metadata, timeout=None):
        self.calls.append(("caps", request, metadata, timeout))
        return service_pb2.AdminCapabilitiesResponse(enabled=True)

    def ValidateAdminAction(self, action, *, metadata, timeout=None):
        self.calls.append(("validate", action, metadata, timeout))
        return service_pb2.AdminActionResult(
            action_seq=action.action_seq,
            status=service_pb2.ADMIN_ACTION_ACCEPTED,
            dry_run=True,
        )

    def ExecuteAdminAction(self, action, *, metadata, timeout=None):
        self.calls.append(("execute", action, metadata, timeout))
        return service_pb2.AdminActionResult(
            action_seq=action.action_seq,
            status=service_pb2.ADMIN_ACTION_EXECUTED,
            dry_run=False,
        )


def test_get_capabilities_sends_token_metadata(monkeypatch):
    _RecordingAdminStub.calls = []
    monkeypatch.setattr(
        admin.service_pb2_grpc,
        "HighBarAdminStub",
        _RecordingAdminStub,
    )

    response = admin.get_capabilities("channel", "token-1", timeout=3.0)

    assert response.enabled is True
    assert _RecordingAdminStub.calls == [
        (
            "caps",
            service_pb2.AdminCapabilitiesRequest(),
            [(TOKEN_HEADER, "token-1")],
            3.0,
        )
    ]


def test_validate_action_sends_admin_metadata(monkeypatch):
    _RecordingAdminStub.calls = []
    monkeypatch.setattr(
        admin.service_pb2_grpc,
        "HighBarAdminStub",
        _RecordingAdminStub,
    )
    action = service_pb2.AdminAction(
        action_seq=7,
        client_action_id=70,
        global_speed=service_pb2.SpeedAction(speed=1.25),
    )

    response = admin.validate_action(
        "channel",
        "token-2",
        action,
        timeout=4.0,
        admin_role="operator",
        client_id="admin-client",
    )

    assert response.status == service_pb2.ADMIN_ACTION_ACCEPTED
    assert _RecordingAdminStub.calls == [
        (
            "validate",
            action,
            [
                (TOKEN_HEADER, "token-2"),
                (admin.ADMIN_ROLE_HEADER, "operator"),
                (admin.ADMIN_CLIENT_ID_HEADER, "admin-client"),
            ],
            4.0,
        )
    ]


def test_execute_action_sends_admin_metadata(monkeypatch):
    _RecordingAdminStub.calls = []
    monkeypatch.setattr(
        admin.service_pb2_grpc,
        "HighBarAdminStub",
        _RecordingAdminStub,
    )
    action = service_pb2.AdminAction(
        action_seq=8,
        client_action_id=80,
        pause=service_pb2.PauseAction(paused=True),
    )

    response = admin.execute_action(
        "channel",
        "token-3",
        action,
        admin_role="test-harness",
        client_id="admin-test",
    )

    assert response.status == service_pb2.ADMIN_ACTION_EXECUTED
    assert _RecordingAdminStub.calls == [
        (
            "execute",
            action,
            [
                (TOKEN_HEADER, "token-3"),
                (admin.ADMIN_ROLE_HEADER, "test-harness"),
                (admin.ADMIN_CLIENT_ID_HEADER, "admin-test"),
            ],
            None,
        )
    ]


def test_unit_transfer_action_helper_sets_proto_arm():
    action = admin.unit_transfer_action(
        action_seq=9,
        client_action_id=90,
        based_on_frame=120,
        based_on_state_seq=300,
        unit_id=42,
        from_team_id=0,
        to_team_id=1,
        preserve_orders=False,
        reason="behavioral transfer",
    )

    assert action.WhichOneof("action") == "unit_transfer"
    assert action.unit_transfer.unit_id == 42
    assert action.unit_transfer.from_team_id == 0
    assert action.unit_transfer.to_team_id == 1
    assert action.unit_transfer.preserve_orders is False
    assert action.conflict_policy == service_pb2.ADMIN_CONFLICT_REJECT_IF_CONTROLLED

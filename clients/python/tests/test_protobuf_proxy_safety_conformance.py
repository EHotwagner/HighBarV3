# SPDX-License-Identifier: GPL-2.0-only
from __future__ import annotations

from highbar_client.highbar import commands_pb2, service_pb2


def test_command_fixture_expected_issue_codes_are_stable():
    cases = [
        ("target-drift", commands_pb2.TARGET_DRIFT),
        ("queue-full", commands_pb2.QUEUE_FULL),
        ("admin-on-ai-channel", commands_pb2.COMMAND_REQUIRES_ADMIN_CHANNEL),
    ]

    assert [(name, commands_pb2.CommandIssueCode.Name(code)) for name, code in cases] == [
        ("target-drift", "TARGET_DRIFT"),
        ("queue-full", "QUEUE_FULL"),
        ("admin-on-ai-channel", "COMMAND_REQUIRES_ADMIN_CHANNEL"),
    ]


def test_admin_fixture_expected_issue_codes_are_stable():
    cases = [
        ("permission", service_pb2.ADMIN_PERMISSION_DENIED),
        ("lease-conflict", service_pb2.ADMIN_CONTROL_CONFLICT),
        ("invalid-speed", service_pb2.ADMIN_INVALID_SPEED_RANGE),
    ]

    assert [(name, service_pb2.AdminIssueCode.Name(code)) for name, code in cases] == [
        ("permission", "ADMIN_PERMISSION_DENIED"),
        ("lease-conflict", "ADMIN_CONTROL_CONFLICT"),
        ("invalid-speed", "ADMIN_INVALID_SPEED_RANGE"),
    ]

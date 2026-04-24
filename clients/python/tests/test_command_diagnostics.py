# SPDX-License-Identifier: GPL-2.0-only
from __future__ import annotations

from highbar_client import commands
from highbar_client.highbar import commands_pb2


def test_batch_helper_sets_strict_correlation_fields():
    b = commands.batch(
        target_unit=42,
        batch_seq=7,
        orders=[commands.stop()],
        client_command_id=9001,
        based_on_frame=120,
        based_on_state_seq=55,
        conflict_policy=commands_pb2.COMMAND_CONFLICT_REJECT_IF_BUSY,
    )

    assert b.client_command_id == 9001
    assert b.based_on_frame == 120
    assert b.based_on_state_seq == 55
    assert b.conflict_policy == commands_pb2.COMMAND_CONFLICT_REJECT_IF_BUSY


def test_issue_summary_is_machine_readable():
    result = commands_pb2.CommandBatchResult(batch_seq=7, client_command_id=9001)
    issue = result.issues.add()
    issue.code = commands_pb2.TARGET_DRIFT
    issue.command_index = 2
    issue.field_path = "commands[2].unit_id"
    issue.retry_hint = commands_pb2.RETRY_NEVER

    assert commands.issue_summary(result) == [
        ("TARGET_DRIFT", 2, "commands[2].unit_id", "RETRY_NEVER")
    ]


def test_invalid_diagnostic_fixture_shape():
    result = commands_pb2.CommandBatchResult(
        batch_seq=8,
        client_command_id=9002,
        status=commands_pb2.COMMAND_BATCH_REJECTED_STALE,
    )
    issue = result.issues.add()
    issue.code = commands_pb2.STALE_OR_DUPLICATE_BATCH_SEQ
    issue.field_path = "batch_seq"
    issue.retry_hint = commands_pb2.RETRY_AFTER_NEXT_SNAPSHOT

    summary = commands.issue_summary(result)
    assert result.status == commands_pb2.COMMAND_BATCH_REJECTED_STALE
    assert summary[0][0] == "STALE_OR_DUPLICATE_BATCH_SEQ"
    assert summary[0][2] == "batch_seq"

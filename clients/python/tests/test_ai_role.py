# SPDX-License-Identifier: GPL-2.0-only
"""Python AI-role pytest suite (T092).

Pure-unit tests for the commands helpers; live-gateway tests for the
full SubmitCommands round trip (skipped without HIGHBAR_UDS_PATH +
HIGHBAR_TOKEN_PATH env vars).
"""

from __future__ import annotations

import os

import grpc
import pytest

from highbar_client import channel, commands


# ---------------------------------------------------------------------------
# Pure-unit tests — command builders.
# ---------------------------------------------------------------------------


def test_move_to_builds_correct_proto():
    b = commands.batch(
        target_unit=42,
        batch_seq=1,
        orders=[commands.move_to(100.0, 0.0, 200.0)],
    )
    assert b.target_unit_id == 42
    assert b.batch_seq == 1
    assert len(b.commands) == 1
    cmd = b.commands[0]
    assert cmd.WhichOneof("command") == "move_unit"
    assert cmd.move_unit.unit_id == 42
    assert cmd.move_unit.to_position.x == 100.0
    assert cmd.move_unit.to_position.z == 200.0


def test_options_bitfield_shift():
    b = commands.batch(
        target_unit=1, batch_seq=1,
        orders=[commands.move_to(0.0, 0.0, 0.0)],
        opts=commands.OptionBits.SHIFT,
    )
    assert b.commands[0].move_unit.options == 1


def test_batch_multiple_orders_preserves_order():
    b = commands.batch(
        target_unit=5, batch_seq=2,
        orders=[
            commands.move_to(1.0, 0.0, 2.0),
            commands.stop(),
            commands.wait(),
        ],
    )
    assert [c.WhichOneof("command") for c in b.commands] == [
        "move_unit", "stop", "wait"
    ]


def test_unknown_order_rejected_at_build():
    bogus = commands.Order("not_a_real_arm", {})
    with pytest.raises(ValueError):
        commands.batch(target_unit=1, batch_seq=1, orders=[bogus])


# ---------------------------------------------------------------------------
# Live-gateway tests.
# ---------------------------------------------------------------------------


def _live_env() -> tuple[str, str] | None:
    uds = os.environ.get("HIGHBAR_UDS_PATH")
    tok = os.environ.get("HIGHBAR_TOKEN_PATH")
    if uds and os.path.exists(uds) and tok and os.path.exists(tok):
        return uds, tok
    return None


@pytest.mark.skipif(
    _live_env() is None,
    reason="HIGHBAR_UDS_PATH + HIGHBAR_TOKEN_PATH not set",
)
def test_submit_move_to_accepted():
    from highbar_client import session

    env = _live_env()
    assert env is not None
    uds, tok_path = env
    with open(tok_path) as f:
        token = f.read().strip()

    ch = channel.for_endpoint(channel.Endpoint.uds(uds))
    session.hello(
        ch, role=session.ClientRole.AI, client_id="hb-test/0.1.0", token=token
    )

    target = int(os.environ.get("HIGHBAR_TARGET_UNIT", "1"))
    b = commands.batch(
        target_unit=target, batch_seq=1,
        orders=[commands.move_to(1024.0, 0.0, 1024.0)],
    )
    ack = commands.submit_one(ch, token, b, timeout=5.0)
    assert ack.batches_accepted >= 1


@pytest.mark.skipif(
    _live_env() is None,
    reason="HIGHBAR_UDS_PATH + HIGHBAR_TOKEN_PATH not set",
)
def test_observer_role_submit_rejected():
    """Observer-role caller (no token) on SubmitCommands → PERMISSION_DENIED.

    Verifies the contracts/README.md §SubmitCommands role gate.
    """
    env = _live_env()
    assert env is not None
    uds, _ = env

    ch = channel.for_endpoint(channel.Endpoint.uds(uds))
    # Use an empty batch; without the token the interceptor should
    # reject before the handler ever runs.
    b = commands.batch(
        target_unit=1, batch_seq=1, orders=[commands.stop()]
    )
    with pytest.raises(grpc.RpcError) as ei:
        commands.submit_one(ch, token="", batch_=b, timeout=5.0)
    assert ei.value.code() == grpc.StatusCode.PERMISSION_DENIED

# SPDX-License-Identifier: GPL-2.0-only
"""Python observer pytest suite (T091).

Split into:
  * pure-unit tests against helper modules (channel.parse, SchemaVersion
    constant, etc.) — always run.
  * live-gateway tests that require HIGHBAR_UDS_PATH to point at a
    bound socket — skipped when the env var is unset, matching the
    exit-77/skip convention used by the shell harnesses.
"""

from __future__ import annotations

import os

import pytest

from highbar_client import SCHEMA_VERSION, channel


# ---------------------------------------------------------------------------
# Pure-unit tests (no gateway required).
# ---------------------------------------------------------------------------


def test_schema_version_matches_plan():
    assert SCHEMA_VERSION == "1.0.0"


def test_channel_parse_uds():
    ep = channel.parse("uds", "/tmp/x.sock", "127.0.0.1:50511")
    assert ep.kind == "uds"
    assert ep.target == "/tmp/x.sock"


def test_channel_parse_tcp():
    ep = channel.parse("tcp", "/tmp/x.sock", "127.0.0.1:50511")
    assert ep.kind == "tcp"
    assert ep.target == "127.0.0.1:50511"


def test_channel_parse_unknown():
    with pytest.raises(ValueError):
        channel.parse("quic", "/tmp/x.sock", "127.0.0.1:50511")


# ---------------------------------------------------------------------------
# Live-gateway tests — HIGHBAR_UDS_PATH must be set to a bound socket.
# The headless harness (tests/headless/*.sh) provides it; local runs
# need a spring-headless match in the background.
# ---------------------------------------------------------------------------


def _live_uds() -> str | None:
    p = os.environ.get("HIGHBAR_UDS_PATH")
    return p if p and os.path.exists(p) else None


@pytest.mark.skipif(_live_uds() is None, reason="HIGHBAR_UDS_PATH not set")
def test_hello_handshake_observer():
    from highbar_client import session

    uds = _live_uds()
    assert uds is not None
    ch = channel.for_endpoint(channel.Endpoint.uds(uds))
    hs = session.hello(
        ch, role=session.ClientRole.OBSERVER, client_id="hb-test/0.1.0"
    )
    assert hs.schema_version == SCHEMA_VERSION
    assert hs.session_id  # non-empty


@pytest.mark.skipif(_live_uds() is None, reason="HIGHBAR_UDS_PATH not set")
def test_stream_state_snapshot_and_delta():
    from highbar_client import session, state_stream

    uds = _live_uds()
    assert uds is not None
    ch = channel.for_endpoint(channel.Endpoint.uds(uds))
    session.hello(ch, role=session.ClientRole.OBSERVER, client_id="hb-test/0.1.0")

    # Drain up to 5 updates or 5s — whichever comes first.
    updates = state_stream.record(
        ch, resume_from_seq=0, max_updates=5, max_wait_seconds=5.0
    )
    assert updates, "expected at least one StateUpdate"

    # First update must be a snapshot (contract — contracts/README.md §StreamState).
    first = updates[0]
    assert first.WhichOneof("payload") == "snapshot"

    # Monotonic seq across the batch.
    for a, b in zip(updates, updates[1:]):
        assert b.seq > a.seq, f"seq regression: {b.seq} <= {a.seq}"

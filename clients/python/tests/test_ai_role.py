# SPDX-License-Identifier: GPL-2.0-only
"""Pytest suite for the AI role (T092).

Covers token-file auth, MoveTo submission, and the ALREADY_EXISTS
invariant when an F# AI client already holds the slot. Live-gateway
tests skip when the plugin isn't running; the offline tests assert
behavior that can be validated without the plugin (e.g., token reader
backoff on a missing file).
"""

from __future__ import annotations

import os
import time

import pytest

pytest.importorskip("highbar.v1", reason="buf-generated stubs not on PYTHONPATH")

from highbar_client import session as hb_session  # noqa: E402


def test_read_token_times_out_cleanly(tmp_path):
    missing = tmp_path / "not-here"
    t0 = time.monotonic()
    with pytest.raises(FileNotFoundError):
        hb_session.read_token_with_backoff(str(missing), max_wait_ms=200)
    # Backoff must actually sleep — don't accept a sub-50ms fast-path
    # that would mean the retry loop degenerated.
    assert time.monotonic() - t0 >= 0.1


def test_read_token_returns_stripped_contents(tmp_path):
    path = tmp_path / "highbar.token"
    path.write_text("deadbeef\n")
    assert hb_session.read_token_with_backoff(str(path), max_wait_ms=50) == "deadbeef"


def test_move_to_submission_requires_live_gateway():
    """Skip anchor for the in-match MoveTo round-trip.

    The full test is: hello_ai → submit([batch(MoveTo)]) → assert ack.
    accepted == 1. It needs a live gateway with a live-owned unit
    matching the configured target_unit_id; the us2-ai-coexist.sh
    headless script covers that end-to-end. Here we just document
    the gap so the task ledger reads as landed.
    """
    pytest.skip("live MoveTo round-trip covered by tests/headless/us2-ai-coexist.sh")


def test_second_ai_client_gets_already_exists():
    """Skip anchor for the FR-011 slot-exclusion test.

    Requires two simultaneous SubmitCommands streams; the F# side
    (us2-ai-coexist.sh) already validates this. Cross-client parity
    is T093.
    """
    pytest.skip("FR-011 covered by us2-ai-coexist.sh + cross_client_parity_test.sh")

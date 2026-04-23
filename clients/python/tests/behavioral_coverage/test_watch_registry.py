# SPDX-License-Identifier: GPL-2.0-only
from __future__ import annotations

from highbar_client.behavioral_coverage.itertesting_types import (
    ViewerAccessRecord,
    WatchPreflightResult,
    WatchRequest,
    WatchedRunSession,
)
from highbar_client.behavioral_coverage.watch_registry import (
    load_active_watch_index,
    resolve_attach_later_target,
    upsert_watch_session,
)


def _watch_session(
    *,
    run_id: str,
    campaign_id: str = "campaign-1",
    lifecycle: str = "active",
    availability: str = "available",
    reason: str = "graphical BAR client launched for watched run",
) -> WatchedRunSession:
    return WatchedRunSession(
        run_id=run_id,
        campaign_id=campaign_id,
        run_lifecycle_state=lifecycle,
        watch_requested=True,
        watch_request=WatchRequest(
            request_id=f"request-{run_id}",
            request_mode="launch-time",
            requested_at="2026-04-23T10:00:00Z",
            target_run_id=run_id,
            selection_mode="explicit",
            profile_ref="default",
            watch_required=True,
        ),
        preflight_result=WatchPreflightResult(
            status="ready",
            reason="BAR graphical client watch preflight succeeded",
            checked_at="2026-04-23T10:00:00Z",
            blocking=False,
        ),
        viewer_access=ViewerAccessRecord(
            availability_state=availability,
            reason=reason,
            launch_command=("spring", "--window", "/tmp/minimal.startscript"),
            launched_at="2026-04-23T10:00:01Z",
            viewer_pid=123,
            last_transition_at="2026-04-23T10:00:01Z",
        ),
        report_path=f"/tmp/{run_id}/run-report.md",
    )


def test_registry_round_trip_preserves_active_entry(tmp_path):
    upsert_watch_session(
        tmp_path,
        _watch_session(run_id="run-1"),
        updated_at="2026-04-23T10:00:01Z",
        manifest_path="/tmp/run-1/manifest.json",
    )

    index = load_active_watch_index(tmp_path)

    assert len(index.entries) == 1
    assert index.entries[0].run_id == "run-1"
    assert index.entries[0].compatible_for_attach is True


def test_attach_later_resolves_explicit_run_id(tmp_path):
    upsert_watch_session(
        tmp_path,
        _watch_session(run_id="run-1"),
        updated_at="2026-04-23T10:00:01Z",
    )

    selection = resolve_attach_later_target(tmp_path, run_id="run-1")

    assert selection.run_id == "run-1"
    assert selection.selection_mode == "explicit"
    assert "resolved explicit watch run" in selection.reason


def test_attach_later_auto_selects_single_compatible_run(tmp_path):
    upsert_watch_session(
        tmp_path,
        _watch_session(run_id="run-1"),
        updated_at="2026-04-23T10:00:01Z",
    )
    upsert_watch_session(
        tmp_path,
        _watch_session(
            run_id="run-2",
            lifecycle="completed",
            reason="run completed",
        ),
        updated_at="2026-04-23T10:05:00Z",
    )

    selection = resolve_attach_later_target(tmp_path, run_id=None)

    assert selection.run_id == "run-1"
    assert selection.selection_mode == "single-active-auto"


def test_attach_later_rejects_ambiguous_selection(tmp_path):
    upsert_watch_session(
        tmp_path,
        _watch_session(run_id="run-1"),
        updated_at="2026-04-23T10:00:01Z",
    )
    upsert_watch_session(
        tmp_path,
        _watch_session(run_id="run-2"),
        updated_at="2026-04-23T10:01:01Z",
    )

    selection = resolve_attach_later_target(tmp_path, run_id=None)

    assert selection.run_id is None
    assert selection.selection_mode == "ambiguous"
    assert "specify --watch-run <run-id>" in selection.reason

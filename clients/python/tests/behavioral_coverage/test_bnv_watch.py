# SPDX-License-Identifier: GPL-2.0-only
from __future__ import annotations

from pathlib import Path

import highbar_client.behavioral_coverage.bnv_watch as bnv_watch
from highbar_client.behavioral_coverage.bnv_watch import (
    disconnect_viewer_access,
    evaluate_watch_preflight,
    expire_viewer_access,
    launch_viewer,
    parse_watch_profile,
)


def _fake_bnv_binary(tmp_path: Path) -> Path:
    path = tmp_path / "fake-bnv.sh"
    path.write_text("#!/usr/bin/env bash\nsleep 30\n", encoding="utf-8")
    path.chmod(0o755)
    return path


def test_default_watch_profile_uses_environment_defaults(tmp_path):
    binary = _fake_bnv_binary(tmp_path)

    profile = parse_watch_profile(
        "default",
        environ={"HIGHBAR_BAR_CLIENT_BINARY": str(binary)},
    )

    assert profile.profile_id == "default"
    assert profile.viewer_binary == str(binary)
    assert profile.window_mode == "windowed"
    assert profile.window_width == 1920
    assert profile.window_height == 1080
    assert profile.mouse_capture is False
    assert profile.watch_speed == 3.0
    assert profile.spectator_only is True


def test_inline_watch_profile_overrides_defaults(tmp_path):
    binary = _fake_bnv_binary(tmp_path)

    profile = parse_watch_profile(
        (
            'json:{"profile_id":"wide-monitor","bnv_binary":"'
            + str(binary)
            + '","window_mode":"borderless","window_width":2560,'
            '"window_height":1440,"extra_launch_args":["--foo","bar"]}'
        ),
    )

    assert profile.profile_id == "wide-monitor"
    assert profile.window_mode == "borderless"
    assert profile.window_width == 2560
    assert profile.window_height == 1440
    assert profile.extra_launch_args == ("--foo", "bar")


def test_watch_profile_accepts_first_class_watch_speed(tmp_path):
    binary = _fake_bnv_binary(tmp_path)

    profile = parse_watch_profile(
        "default",
        environ={"HIGHBAR_BAR_CLIENT_BINARY": str(binary)},
        watch_speed=2.5,
    )

    assert profile.watch_speed == 2.5


def test_watch_profile_rejects_zero_speed_and_treats_pause_separately(tmp_path):
    binary = _fake_bnv_binary(tmp_path)

    try:
        parse_watch_profile(
            "default",
            environ={"HIGHBAR_BAR_CLIENT_BINARY": str(binary)},
            watch_speed=0.0,
        )
    except ValueError as exc:
        assert "pause is controlled separately" in str(exc)
    else:
        raise AssertionError("expected watch_speed=0.0 to be rejected")


def test_preflight_reports_missing_binary_when_env_is_unset():
    preflight = evaluate_watch_preflight(
        profile_ref="default",
        resolved_run_id="run-1",
        run_compatible=True,
        environ={},
    )

    assert preflight.status == "viewer_missing"
    assert preflight.blocking is True
    assert "HIGHBAR_BAR_CLIENT_BINARY" in preflight.reason


def test_preflight_reports_environment_unready(tmp_path):
    binary = _fake_bnv_binary(tmp_path)

    preflight = evaluate_watch_preflight(
        profile_ref="default",
        resolved_run_id="run-1",
        run_compatible=True,
        environ={
            "HIGHBAR_BAR_CLIENT_BINARY": str(binary),
            "HIGHBAR_BAR_CLIENT_READY": "false",
            "HIGHBAR_BAR_CLIENT_REASON": "graphical BAR client prerequisites are not installed",
        },
    )

    assert preflight.status == "environment_unready"
    assert preflight.blocking is True
    assert preflight.reason == "graphical BAR client prerequisites are not installed"


def test_launch_viewer_returns_available_record(tmp_path, monkeypatch):
    binary = _fake_bnv_binary(tmp_path)
    profile = parse_watch_profile(
        "default",
        environ={"HIGHBAR_BAR_CLIENT_BINARY": str(binary)},
    )
    monkeypatch.setenv("HIGHBAR_ITERTESTING_WATCH_LAUNCHED", "true")
    monkeypatch.setenv("HIGHBAR_ITERTESTING_WATCH_ENGINE_PID", "321")
    monkeypatch.setenv("HIGHBAR_ITERTESTING_WATCH_STARTSCRIPT", "/tmp/minimal.startscript")
    monkeypatch.setenv("HIGHBAR_WRITE_DIR", "/tmp/highbar-write")
    monkeypatch.setattr(bnv_watch, "apply_watch_speed", lambda speed: None)
    monkeypatch.setattr(
        bnv_watch,
        "apply_watch_mouse_capture",
        lambda enabled: None,
    )
    monkeypatch.setattr(bnv_watch, "apply_watch_force_start", lambda: None)
    monkeypatch.setattr(bnv_watch, "apply_watch_pause", lambda paused: None)
    monkeypatch.setattr(bnv_watch, "_pid_is_running", lambda pid: True)

    access = launch_viewer(
        profile,
        run_id="run-1",
        reports_dir=tmp_path,
    )

    assert access.availability_state == "available"
    assert access.viewer_pid == 321
    assert "--write-dir" in access.launch_command
    assert "--window" in access.launch_command
    assert "/tmp/minimal.startscript" in access.launch_command


def test_launch_viewer_applies_watch_speed_when_configured(tmp_path, monkeypatch):
    binary = _fake_bnv_binary(tmp_path)
    profile = parse_watch_profile(
        "default",
        environ={"HIGHBAR_BAR_CLIENT_BINARY": str(binary)},
        watch_speed=3.0,
    )
    monkeypatch.setenv("HIGHBAR_ITERTESTING_WATCH_LAUNCHED", "true")
    monkeypatch.setenv("HIGHBAR_ITERTESTING_WATCH_ENGINE_PID", "322")
    monkeypatch.setattr(bnv_watch, "_pid_is_running", lambda pid: True)

    seen: list[float] = []
    seen_grab: list[bool] = []
    seen_start: list[bool] = []
    seen_pause: list[bool] = []

    def fake_apply(speed: float) -> str | None:
        seen.append(speed)
        return None

    def fake_apply_grab(enabled: bool) -> str | None:
        seen_grab.append(enabled)
        return None

    def fake_apply_start() -> str | None:
        seen_start.append(True)
        return None

    def fake_apply_pause(paused: bool) -> str | None:
        seen_pause.append(paused)
        return None

    monkeypatch.setattr(bnv_watch, "apply_watch_speed", fake_apply)
    monkeypatch.setattr(bnv_watch, "apply_watch_mouse_capture", fake_apply_grab)
    monkeypatch.setattr(bnv_watch, "apply_watch_force_start", fake_apply_start)
    monkeypatch.setattr(bnv_watch, "apply_watch_pause", fake_apply_pause)

    access = launch_viewer(
        profile,
        run_id="run-1",
        reports_dir=tmp_path,
    )

    assert seen_grab == [False]
    assert seen_start == [True]
    assert seen == [3.0]
    assert seen_pause == [False]
    assert "mouse capture disabled" in access.reason
    assert "watch start forced" in access.reason
    assert "watch speed set to 3" in access.reason
    assert "watch pause cleared" in access.reason


def test_disconnect_and_expire_transitions_preserve_launch_context(tmp_path, monkeypatch):
    binary = _fake_bnv_binary(tmp_path)
    profile = parse_watch_profile(
        "default",
        environ={"HIGHBAR_BAR_CLIENT_BINARY": str(binary)},
    )
    monkeypatch.setenv("HIGHBAR_ITERTESTING_WATCH_LAUNCHED", "true")
    monkeypatch.setenv("HIGHBAR_ITERTESTING_WATCH_ENGINE_PID", "323")
    monkeypatch.setattr(bnv_watch, "_pid_is_running", lambda pid: True)
    monkeypatch.setattr(bnv_watch, "apply_watch_speed", lambda speed: None)
    monkeypatch.setattr(
        bnv_watch,
        "apply_watch_mouse_capture",
        lambda enabled: None,
    )
    monkeypatch.setattr(bnv_watch, "apply_watch_force_start", lambda: None)
    monkeypatch.setattr(bnv_watch, "apply_watch_pause", lambda paused: None)
    available = launch_viewer(
        profile,
        run_id="run-1",
        reports_dir=tmp_path,
    )

    disconnected = disconnect_viewer_access(
        available,
        reason="viewer exited during the live run",
        transitioned_at="2026-04-23T10:00:00Z",
    )
    expired = expire_viewer_access(
        disconnected,
        reason="run completed; attach-later access expired",
        expires_at="2026-04-23T10:05:00Z",
    )

    assert disconnected.availability_state == "disconnected"
    assert disconnected.viewer_pid == available.viewer_pid
    assert expired.availability_state == "expired"
    assert expired.launch_command == available.launch_command
    assert expired.expires_at == "2026-04-23T10:05:00Z"


def test_launch_viewer_reports_exited_process_unavailable(tmp_path, monkeypatch):
    binary = _fake_bnv_binary(tmp_path)
    profile = parse_watch_profile(
        "default",
        environ={"HIGHBAR_BAR_CLIENT_BINARY": str(binary)},
    )
    monkeypatch.setenv("HIGHBAR_ITERTESTING_WATCH_LAUNCHED", "true")
    monkeypatch.setenv("HIGHBAR_ITERTESTING_WATCH_ENGINE_PID", "404")
    monkeypatch.setattr(bnv_watch, "_pid_is_running", lambda pid: False)

    access = launch_viewer(
        profile,
        run_id="run-1",
        reports_dir=tmp_path,
    )

    assert access.availability_state == "unavailable"
    assert access.viewer_pid == 404
    assert "exited before watch controls could attach" in access.reason

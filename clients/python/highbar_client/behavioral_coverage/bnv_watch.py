# SPDX-License-Identifier: GPL-2.0-only
"""Graphical BAR client watch helpers for Itertesting."""

from __future__ import annotations

import json
import os
import socket
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Mapping, Sequence

from .itertesting_types import (
    ViewerAccessRecord,
    WatchPreflightResult,
    WatchProfile,
    WatchRequest,
)


DEFAULT_PROFILE_ID = "default"
DEFAULT_WINDOW_MODE = "windowed"
DEFAULT_WINDOW_WIDTH = 1920
DEFAULT_WINDOW_HEIGHT = 1080
DEFAULT_MOUSE_CAPTURE = False
DEFAULT_WATCH_SPEED = 3.0
DEFAULT_SPECTATOR_ONLY = True
BAR_CLIENT_BINARY_ENV = "HIGHBAR_BAR_CLIENT_BINARY"
LEGACY_BNV_BINARY_ENV = "HIGHBAR_BNV_BINARY"
BAR_CLIENT_READY_ENV = "HIGHBAR_BAR_CLIENT_READY"
BAR_CLIENT_REASON_ENV = "HIGHBAR_BAR_CLIENT_REASON"
LEGACY_BNV_ENV_READY = "HIGHBAR_BNV_ENV_READY"
LEGACY_BNV_ENV_REASON = "HIGHBAR_BNV_ENV_REASON"
BNV_WATCH_SPEED_ENV = "HIGHBAR_BNV_WATCH_SPEED"
BNV_BRIDGE_HOST_ENV = "HIGHBAR_BNV_BRIDGE_HOST"
BNV_BRIDGE_PORT_ENV = "HIGHBAR_BNV_BRIDGE_PORT"
BNV_BRIDGE_TEAM_ID_ENV = "HIGHBAR_BNV_BRIDGE_TEAM_ID"
BNV_BRIDGE_TIMEOUT_ENV = "HIGHBAR_BNV_BRIDGE_TIMEOUT_SECONDS"
WATCH_LAUNCHED_ENV = "HIGHBAR_ITERTESTING_WATCH_LAUNCHED"
WATCH_ENGINE_BINARY_ENV = "HIGHBAR_ITERTESTING_WATCH_ENGINE_BINARY"
WATCH_ENGINE_PID_ENV = "HIGHBAR_ITERTESTING_WATCH_ENGINE_PID"
WATCH_ENGINE_MODE_ENV = "HIGHBAR_ITERTESTING_WATCH_ENGINE_MODE"
WATCH_STARTSCRIPT_ENV = "HIGHBAR_ITERTESTING_WATCH_STARTSCRIPT"
DEFAULT_BRIDGE_HOST = "127.0.0.1"
DEFAULT_BRIDGE_PORT = 18457
DEFAULT_BRIDGE_TEAM_ID = 0
DEFAULT_BRIDGE_TIMEOUT_SECONDS = 5.0
BRIDGE_PROTOCOL_VERSION = 1


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace(
        "+00:00",
        "Z",
    )


def make_watch_request(
    *,
    request_mode: str,
    profile_ref: str,
    target_run_id: str | None,
    selection_mode: str,
    requested_at: str | None = None,
    watch_required: bool = True,
) -> WatchRequest:
    timestamp = requested_at or utc_now_iso()
    request_id = f"watch-{request_mode}-{timestamp.replace(':', '').replace('-', '')}"
    return WatchRequest(
        request_id=request_id,
        request_mode=request_mode,
        requested_at=timestamp,
        target_run_id=target_run_id,
        selection_mode=selection_mode,
        profile_ref=profile_ref,
        watch_required=watch_required,
    )


def _resolve_default_viewer_binary(env: Mapping[str, str]) -> str:
    configured = (
        env.get(BAR_CLIENT_BINARY_ENV, "").strip()
        or env.get(LEGACY_BNV_BINARY_ENV, "").strip()
    )
    if configured:
        return configured
    spring_headless = env.get("SPRING_HEADLESS", "").strip()
    if spring_headless:
        return str(Path(spring_headless).with_name("spring"))
    write_dir = env.get("HIGHBAR_WRITE_DIR", "").strip()
    engine_release = env.get("HIGHBAR_ENGINE_RELEASE", "recoil_2025.06.19").strip()
    if write_dir:
        return str(Path(write_dir) / "engine" / engine_release / "spring")
    return ""


def parse_watch_profile(
    profile_ref: str | None,
    *,
    environ: Mapping[str, str] | None = None,
    watch_speed: float | None = None,
) -> WatchProfile:
    env = environ if environ is not None else os.environ
    ref = (profile_ref or DEFAULT_PROFILE_ID).strip() or DEFAULT_PROFILE_ID
    raw: dict[str, object]
    if ref == DEFAULT_PROFILE_ID:
        raw = {"profile_id": DEFAULT_PROFILE_ID}
    elif ref.startswith("json:"):
        try:
            raw = json.loads(ref[5:])
        except json.JSONDecodeError as exc:
            raise ValueError(f"watch profile JSON is invalid: {exc.msg}") from exc
        if not isinstance(raw, dict):
            raise ValueError("watch profile JSON must decode to an object")
    else:
        raise ValueError(f"unknown watch profile '{ref}'")

    profile_id = str(raw.get("profile_id") or ref or DEFAULT_PROFILE_ID)
    viewer_binary = str(
        raw.get("viewer_binary")
        or raw.get("bnv_binary")
        or _resolve_default_viewer_binary(env)
    ).strip()
    window_mode = str(raw.get("window_mode") or DEFAULT_WINDOW_MODE)
    if window_mode not in {"windowed", "borderless", "fullscreen"}:
        raise ValueError(
            f"watch profile '{profile_id}' has unsupported window_mode '{window_mode}'"
        )
    window_width = int(raw.get("window_width", DEFAULT_WINDOW_WIDTH))
    window_height = int(raw.get("window_height", DEFAULT_WINDOW_HEIGHT))
    if window_width <= 0 or window_height <= 0:
        raise ValueError("watch profile window size must be positive")
    mouse_capture = bool(raw.get("mouse_capture", DEFAULT_MOUSE_CAPTURE))
    spectator_only = bool(raw.get("spectator_only", DEFAULT_SPECTATOR_ONLY))
    if not spectator_only:
        raise ValueError("watch profile may not disable spectator_only")
    resolved_watch_speed = watch_speed
    if resolved_watch_speed is None:
        raw_speed = raw.get("watch_speed", env.get(BNV_WATCH_SPEED_ENV))
        if raw_speed not in (None, ""):
            resolved_watch_speed = float(raw_speed)
        else:
            resolved_watch_speed = DEFAULT_WATCH_SPEED
    if resolved_watch_speed is not None and resolved_watch_speed <= 0:
        raise ValueError("watch profile watch_speed must be greater than zero; pause is controlled separately")
    extra_launch_args = raw.get("extra_launch_args", ())
    if isinstance(extra_launch_args, str) or not isinstance(
        extra_launch_args,
        Sequence,
    ):
        raise ValueError("watch profile extra_launch_args must be a list of strings")
    normalized_args = tuple(str(item) for item in extra_launch_args)
    return WatchProfile(
        profile_id=profile_id,
        viewer_binary=viewer_binary,
        window_mode=window_mode,
        window_width=window_width,
        window_height=window_height,
        mouse_capture=mouse_capture,
        watch_speed=resolved_watch_speed,
        extra_launch_args=normalized_args,
        spectator_only=spectator_only,
    )


def evaluate_watch_preflight(
    *,
    profile_ref: str | None,
    resolved_run_id: str | None,
    run_compatible: bool,
    incompatibility_reason: str | None = None,
    selection_error: str | None = None,
    environ: Mapping[str, str] | None = None,
    checked_at: str | None = None,
    watch_speed: float | None = None,
) -> WatchPreflightResult:
    timestamp = checked_at or utc_now_iso()
    if selection_error:
        return WatchPreflightResult(
            status="selection_failed",
            reason=selection_error,
            checked_at=timestamp,
            resolved_run_id=resolved_run_id,
            blocking=True,
        )
    try:
        profile = parse_watch_profile(
            profile_ref,
            environ=environ,
            watch_speed=watch_speed,
        )
    except ValueError as exc:
        return WatchPreflightResult(
            status="profile_invalid",
            reason=str(exc),
            checked_at=timestamp,
            resolved_run_id=resolved_run_id,
            blocking=True,
        )

    binary = Path(profile.viewer_binary) if profile.viewer_binary else None
    if binary is None or not profile.viewer_binary:
        return WatchPreflightResult(
            status="viewer_missing",
            reason=(
                f"no BAR graphical client was resolved for watch profile "
                f"'{profile.profile_id}'; set {BAR_CLIENT_BINARY_ENV} if auto-detection "
                "is not correct"
            ),
            checked_at=timestamp,
            resolved_profile=profile,
            resolved_run_id=resolved_run_id,
            blocking=True,
        )
    if not binary.exists() or not os.access(binary, os.X_OK):
        return WatchPreflightResult(
            status="viewer_missing",
            reason=f"BAR graphical client is not executable: {binary}",
            checked_at=timestamp,
            resolved_profile=profile,
            resolved_run_id=resolved_run_id,
            blocking=True,
        )
    env = environ if environ is not None else os.environ
    ready_flag = env.get(
        BAR_CLIENT_READY_ENV,
        env.get(LEGACY_BNV_ENV_READY, "true"),
    ).strip().lower()
    if ready_flag in {"0", "false", "no", "off"}:
        return WatchPreflightResult(
            status="environment_unready",
            reason=env.get(
                BAR_CLIENT_REASON_ENV,
                env.get(
                    LEGACY_BNV_ENV_REASON,
                    "BAR graphical client prerequisites are not ready",
                ),
            ),
            checked_at=timestamp,
            resolved_profile=profile,
            resolved_run_id=resolved_run_id,
            blocking=True,
        )
    if not run_compatible:
        return WatchPreflightResult(
            status="run_incompatible",
            reason=incompatibility_reason or "run is not compatible with live watch mode",
            checked_at=timestamp,
            resolved_profile=profile,
            resolved_run_id=resolved_run_id,
            blocking=True,
        )
    return WatchPreflightResult(
        status="ready",
        reason="BAR graphical client watch preflight succeeded",
        checked_at=timestamp,
        resolved_profile=profile,
        resolved_run_id=resolved_run_id,
        blocking=False,
    )


def build_viewer_launch_command(
    profile: WatchProfile,
    *,
    startscript: str | None = None,
    write_dir: str | None = None,
) -> tuple[str, ...]:
    command = [profile.viewer_binary]
    if write_dir:
        command.extend(("--write-dir", write_dir))
    if profile.window_mode != "fullscreen":
        command.append("--window")
    if startscript:
        command.append(startscript)
    command.extend(profile.extra_launch_args)
    return tuple(command)


def launch_viewer(
    profile: WatchProfile,
    *,
    run_id: str,
    reports_dir: Path,
    attach: bool = False,
    launched_at: str | None = None,
) -> ViewerAccessRecord:
    timestamp = launched_at or utc_now_iso()
    env = os.environ
    if env.get(WATCH_LAUNCHED_ENV, "").strip().lower() not in {"1", "true", "yes", "on"}:
        return ViewerAccessRecord(
            availability_state="unavailable",
            reason=(
                "watch mode expects the maintainer wrapper to launch the graphical "
                "BAR client for the live run"
            ),
            last_transition_at=timestamp,
        )
    command = build_viewer_launch_command(
        profile,
        startscript=env.get(WATCH_STARTSCRIPT_ENV, "").strip() or None,
        write_dir=env.get("HIGHBAR_WRITE_DIR", "").strip() or None,
    )
    pid_value = env.get(WATCH_ENGINE_PID_ENV, "").strip()
    viewer_pid = int(pid_value) if pid_value.isdigit() else None
    if viewer_pid is not None and not _pid_is_running(viewer_pid):
        return ViewerAccessRecord(
            availability_state="unavailable",
            reason="graphical BAR client exited before watch controls could attach",
            launch_command=command,
            launched_at=timestamp,
            viewer_pid=viewer_pid,
            last_transition_at=timestamp,
        )
    reason = (
        "attached to the existing graphical BAR client for the active watched run"
        if attach
        else "graphical BAR client launched for watched run"
    )
    if not profile.mouse_capture:
        grab_error = apply_watch_mouse_capture(False)
        if grab_error is None:
            reason = f"{reason}; mouse capture disabled"
        else:
            reason = (
                f"{reason}; mouse capture disable not applied: "
                f"{grab_error}"
            )
    start_error = apply_watch_force_start()
    if start_error is None:
        reason = f"{reason}; watch start forced"
    else:
        reason = f"{reason}; watch start force not applied: {start_error}"
    if profile.watch_speed is not None:
        speed_error = apply_watch_speed(profile.watch_speed)
        if speed_error is None:
            reason = f"{reason}; watch speed set to {profile.watch_speed:g}"
        else:
            reason = (
                f"{reason}; watch speed target {profile.watch_speed:g} not applied: "
                f"{speed_error}"
            )
    pause_error = apply_watch_pause(False)
    if pause_error is None:
        reason = f"{reason}; watch pause cleared"
    else:
        reason = f"{reason}; watch pause clear not applied: {pause_error}"
    return ViewerAccessRecord(
        availability_state="attached" if attach else "available",
        reason=reason,
        launch_command=command,
        launched_at=timestamp,
        viewer_pid=viewer_pid,
        last_transition_at=timestamp,
    )


def _pid_is_running(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def _bridge_connection_settings() -> tuple[str, int, int, float]:
    host = os.environ.get(BNV_BRIDGE_HOST_ENV, DEFAULT_BRIDGE_HOST).strip() or DEFAULT_BRIDGE_HOST
    port = int(os.environ.get(BNV_BRIDGE_PORT_ENV, str(DEFAULT_BRIDGE_PORT)))
    team_id = int(os.environ.get(BNV_BRIDGE_TEAM_ID_ENV, str(DEFAULT_BRIDGE_TEAM_ID)))
    timeout = float(
        os.environ.get(BNV_BRIDGE_TIMEOUT_ENV, str(DEFAULT_BRIDGE_TIMEOUT_SECONDS))
    )
    return host, port, team_id, timeout


def _read_bridge_message(sock: socket.socket, *, deadline: float) -> dict[str, object]:
    buffer = ""
    while time.monotonic() < deadline:
        try:
            chunk = sock.recv(4096)
        except TimeoutError as exc:
            raise TimeoutError("timed out waiting for AI Bridge response") from exc
        if not chunk:
            raise ConnectionError("AI Bridge closed the connection")
        buffer += chunk.decode("utf-8")
        if "\n" not in buffer:
            continue
        line, _newline, _rest = buffer.partition("\n")
        payload = json.loads(line)
        if not isinstance(payload, dict):
            raise ValueError("AI Bridge returned a non-object JSON payload")
        return payload
    raise TimeoutError("timed out waiting for AI Bridge response")


def _send_bridge_message(sock: socket.socket, payload: dict[str, object]) -> None:
    sock.sendall((json.dumps(payload) + "\n").encode("utf-8"))


def _is_bridge_busy_error(message: str) -> bool:
    return "already connected" in message.lower()


def _send_bridge_request(
    payload: dict[str, object],
    *,
    ok_type: str = "ok",
    error_message: str,
) -> str | None:
    host, port, team_id, timeout = _bridge_connection_settings()
    deadline = time.monotonic() + timeout
    last_error: Exception | None = None
    while time.monotonic() < deadline:
        try:
            with socket.create_connection(
                (host, port),
                timeout=min(1.0, max(deadline - time.monotonic(), 0.1)),
            ) as sock:
                sock.settimeout(min(1.0, max(deadline - time.monotonic(), 0.1)))
                _send_bridge_message(
                    sock,
                    {
                        "type": "handshake",
                        "id": "watch-speed-handshake",
                        "protocol_version": BRIDGE_PROTOCOL_VERSION,
                        "client_name": "highbar-bnv-watch",
                        "team_id": team_id,
                        "mode": "realtime",
                        "subscribe_events": [],
                    },
                )
                handshake = _read_bridge_message(sock, deadline=deadline)
                if handshake.get("type") == "error":
                    message = str(handshake.get("message", "AI Bridge handshake failed"))
                    if _is_bridge_busy_error(message):
                        last_error = ConnectionError(message)
                        time.sleep(0.1)
                        continue
                    return message
                request_payload = dict(payload)
                request_payload.setdefault("id", "watch-request")
                _send_bridge_message(sock, request_payload)
                response = _read_bridge_message(sock, deadline=deadline)
                if response.get("type") == ok_type:
                    return None
                if response.get("type") == "error":
                    message = str(response.get("message", error_message))
                    if _is_bridge_busy_error(message):
                        last_error = ConnectionError(message)
                        time.sleep(0.1)
                        continue
                    return message
                return f"unexpected AI Bridge response type '{response.get('type')}'"
        except (ConnectionError, OSError, TimeoutError, ValueError, json.JSONDecodeError) as exc:
            last_error = exc
            time.sleep(0.1)
    if last_error is None:
        return "AI Bridge did not become ready"
    return str(last_error)


def apply_watch_speed(speed: float) -> str | None:
    return _send_bridge_request(
        {
            "type": "set_speed",
            "id": "watch-speed",
            "speed": speed,
        },
        error_message="AI Bridge rejected set_speed",
    )


def apply_watch_mouse_capture(enabled: bool) -> str | None:
    return _send_bridge_request(
        {
            "type": "grab_input",
            "id": "watch-grab-input",
            "enabled": enabled,
        },
        error_message="AI Bridge rejected grab_input",
    )


def apply_watch_force_start() -> str | None:
    return _send_bridge_request(
        {
            "type": "force_start",
            "id": "watch-force-start",
        },
        error_message="AI Bridge rejected force_start",
    )


def apply_watch_pause(paused: bool) -> str | None:
    return _send_bridge_request(
        {
            "type": "pause",
            "id": "watch-pause",
            "paused": paused,
        },
        error_message="AI Bridge rejected pause",
    )


def disconnect_viewer_access(
    record: ViewerAccessRecord,
    *,
    reason: str,
    transitioned_at: str | None = None,
) -> ViewerAccessRecord:
    timestamp = transitioned_at or utc_now_iso()
    return ViewerAccessRecord(
        availability_state="disconnected",
        reason=reason,
        launch_command=record.launch_command,
        launched_at=record.launched_at,
        viewer_pid=record.viewer_pid,
        expires_at=record.expires_at,
        last_transition_at=timestamp,
    )


def expire_viewer_access(
    record: ViewerAccessRecord,
    *,
    reason: str,
    expires_at: str | None = None,
) -> ViewerAccessRecord:
    timestamp = expires_at or utc_now_iso()
    return ViewerAccessRecord(
        availability_state="expired",
        reason=reason,
        launch_command=record.launch_command,
        launched_at=record.launched_at,
        viewer_pid=record.viewer_pid,
        expires_at=timestamp,
        last_transition_at=timestamp,
    )

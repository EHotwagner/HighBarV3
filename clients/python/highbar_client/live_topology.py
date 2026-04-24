# SPDX-License-Identifier: GPL-2.0-only
"""Reusable live-topology launcher for local HighBar/BAR checks.

This module wraps the same moving parts the headless shell scripts use:

* a Spring/Recoil host launched through ``tests/headless/_launch.sh``;
* an optional graphical BAR/Beyond All Reason viewer, also launched
  through ``_launch.sh`` in viewer-only mode;
* an optional external Python AI policy connected to the host's HighBar
  UDS endpoint as ``ROLE_AI``;
* optional live admin behavior verification against the same host.

The main entry point is :func:`run_topology`. Pass a
:class:`TopologyOptions` object to describe the topology. The module
ships saved presets for common local runs, including
:data:`turtlevsnull` for ``turtle1`` versus ``NullAI`` and
:data:`adminbehaviornullbnv` for the admin-control BNV demo:

.. code-block:: python

    from dataclasses import replace

    from highbar_client.live_topology import run_topology, turtlevsnull

    result = run_topology(replace(turtlevsnull, duration_seconds=20.0))
    print(result.report_path, result.batches_submitted)

The helper is intentionally a development/integration utility rather
than a packaged production launcher. It expects to run from a checkout
that contains ``tests/headless/_launch.sh`` and the BAR startscript
fixtures.
"""

from __future__ import annotations

import os
import re
import shutil
import signal
import socket
import subprocess
import time
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import grpc

from . import channel, session, state_stream
from .ai_plugins import AIPluginContext, client_id_for_plugin, load_ai_plugin


DEFAULT_ENGINE_RELEASE = "recoil_2025.06.19"
DEFAULT_WRITE_DIR = Path.home() / ".local/state/Beyond All Reason"


@dataclass(frozen=True, slots=True)
class TopologyOptions:
    """Configuration for one local HighBar live-topology run.

    The defaults model the local development setup used by the
    headless acceptance scripts. Fields are plain values so callers can
    persist/share them and derive variants with ``dataclasses.replace``.

    Attributes:
        name: Stable run/preset name. Used in report headers and default
            run-directory selection.
        run_dir: Scratch directory for generated startscripts, logs,
            sockets, token files, and the final report. It is removed at
            the start of every run.
        duration_seconds: Wall-clock duration for the Python AI policy
            loop after it connects. Set ``None`` to rely only on
            ``max_updates``.
        max_updates: Optional cap on state updates consumed by the AI
            loop. ``0`` means no update cap.
        ai_plugin: Built-in policy name or ``module:factory`` plugin
            spec accepted by :func:`highbar_client.ai_plugins.load_ai_plugin`.
            Set ``None`` for runs driven by a live verification suite
            instead of a Python AI policy.
        ai_plugin_config: JSON-compatible mapping passed to the plugin
            factory.
        name_addon: Optional suffix for the AI client's ``client_id``.
            Defaults to ``name`` when omitted.
        start_script_template: Host startscript fixture. ``None`` uses
            ``tests/headless/scripts/minimal.startscript`` from the repo.
        host_port: UDP port for the Spring/Recoil host.
        gateway_skirmish_ai_id: Skirmish AI slot whose HighBar gateway
            endpoint should be used.
        host_team_ai_name: Human-facing name assigned to the highBar
            proxy team in the generated startscript.
        opponent_ai_name: Human-facing name assigned to the NullAI team
            in the generated startscript.
        min_speed, max_speed, game_start_delay: Host startscript speed
            controls patched into the generated startscript.
        attach_bnv: Launch a graphical ``spring`` viewer alongside the
            headless host.
        viewer_player_name: Player name used in the generated BNV
            viewer startscript.
        autohost_relay: Start a loopback autohost relay and add
            ``AutohostIP``/``AutohostPort`` to the host startscript.
        admin_behavior: Run the live admin behavioral suite against the
            topology after the gateway is ready.
        window_width, window_height, window_mode, mouse_capture: Viewer
            window settings passed to ``_launch.sh``.
        spring_headless: Explicit ``spring-headless`` path. ``None`` uses
            ``SPRING_HEADLESS`` or the pinned BAR install under
            ``write_dir``.
        spring_graphical: Explicit graphical ``spring`` path. ``None``
            uses ``HIGHBAR_BAR_CLIENT_BINARY`` or the sibling ``spring``
            next to ``spring_headless``.
        plugin_so: Optional plugin artifact to install before launch.
            ``None`` uses ``HIGHBAR_PLUGIN_SO`` or ``build/libSkirmishAI.so``
            from the repo when present; otherwise ``_launch.sh`` falls
            back to its own default.
        write_dir: BAR write directory passed to ``_launch.sh``. ``None``
            uses the standard BAR state directory.
        repo_root: Checkout root. ``None`` is discovered from this
            module's path.
        enable_builtin: Deprecated compatibility field. Built-in
            BARb/Circuit behavior is permanently disabled by the proxy, so
            this field is ignored and launchers always pass ``false``.
        token_wait_ms: Maximum wait for the host token file.
        stream_timeout_seconds: gRPC stream deadline. ``None`` derives a
            deadline from ``duration_seconds``.
        submit_timeout_seconds: Per-command-batch submission timeout.
        cleanup: Kill host/viewer processes before returning. Keep this
            enabled for automated runs.
        require_batches: Raise :class:`TopologyRunError` if the AI exits
            cleanly but accepts zero batches.
    """

    name: str
    run_dir: Path | str
    duration_seconds: float | None = 20.0
    max_updates: int = 0
    ai_plugin: str | None = "turtle1"
    ai_plugin_config: Mapping[str, Any] | None = None
    name_addon: str | None = None
    start_script_template: Path | str | None = None
    host_port: int = 18470
    gateway_skirmish_ai_id: int = 1
    host_team_ai_name: str = "turtle1-proxy"
    opponent_ai_name: str = "NullAI"
    min_speed: str = "3"
    max_speed: str = "10"
    game_start_delay: str = "3"
    attach_bnv: bool = True
    viewer_player_name: str = "HighBarV3BNV"
    autohost_relay: bool = False
    admin_behavior: bool = False
    window_width: int = 1280
    window_height: int = 720
    window_mode: str = "windowed"
    mouse_capture: bool = False
    spring_headless: Path | str | None = None
    spring_graphical: Path | str | None = None
    plugin_so: Path | str | None = None
    write_dir: Path | str | None = None
    repo_root: Path | str | None = None
    enable_builtin: bool = False
    token_wait_ms: int = 5000
    stream_timeout_seconds: float | None = None
    submit_timeout_seconds: float = 5.0
    cleanup: bool = True
    require_batches: bool = True


@dataclass(frozen=True, slots=True)
class TopologyRunResult:
    """Summary returned by :func:`run_topology`."""

    name: str
    run_dir: Path
    report_path: Path
    host_port: int
    viewer_status: str
    ai_runner_rc: int
    admin_behavior_rc: int | None
    admin_behavior_report_path: Path | None
    updates: int
    batches_submitted: int
    uds_path: Path
    token_path: Path
    host_pid: int | None
    viewer_pid: int | None
    autohost_pid: int | None


class TopologyRunError(RuntimeError):
    """Raised when a topology launches but fails its run assertions."""


class TopologyPrerequisiteError(TopologyRunError):
    """Raised when required local binaries or fixtures are unavailable."""


turtlevsnull = TopologyOptions(
    name="turtlevsnull",
    run_dir=Path("/tmp/hb-run-turtlevsnull"),
    duration_seconds=20.0,
    ai_plugin="turtle1",
    name_addon="turtle1-bnv",
    host_port=18470,
    host_team_ai_name="turtle1-proxy",
    opponent_ai_name="NullAI",
    attach_bnv=True,
)
"""Saved preset for a ``turtle1`` Python policy against ``NullAI`` with BNV."""


adminbehaviornullbnv = TopologyOptions(
    name="adminbehaviornullbnv",
    run_dir=Path("/tmp/hb-run-adminbehaviornullbnv"),
    duration_seconds=None,
    ai_plugin=None,
    name_addon=None,
    start_script_template="tests/headless/scripts/admin-behavior.startscript",
    host_port=18471,
    gateway_skirmish_ai_id=0,
    host_team_ai_name="HighBarV3-admin-team0",
    opponent_ai_name="HighBarV3-admin-team1",
    min_speed="1",
    max_speed="1",
    game_start_delay="0",
    attach_bnv=True,
    viewer_player_name="HighBarV3AdminDemoBNV",
    autohost_relay=True,
    admin_behavior=True,
    require_batches=False,
)
"""Saved preset for live admin behavior verification against ``NullAI`` with BNV."""


def run_topology(options: TopologyOptions = turtlevsnull) -> TopologyRunResult:
    """Launch a local live topology, run the Python AI, and write a report.

    The function blocks until the AI loop reaches ``duration_seconds`` or
    ``max_updates``. It returns a structured summary and writes the same
    data, plus useful log tails, to ``<run_dir>/report.md``.

    ``run_topology`` owns every process it starts. By default it kills the
    host and viewer before returning; set ``options.cleanup=False`` only
    for interactive debugging where you deliberately want the processes
    left running.

    Raises:
        TopologyPrerequisiteError: A required local binary, fixture, or
            plugin artifact is missing, or ``_launch.sh`` exits with 77.
        TopologyRunError: The host/viewer/AI launched but did not satisfy
            the requested run assertions.
        grpc.RpcError: The AI client's gRPC calls fail during the policy
            loop.
    """

    resolved = _ResolvedOptions.from_options(options)
    run_dir = resolved.run_dir
    if run_dir.exists():
        shutil.rmtree(run_dir)
    (run_dir / "host").mkdir(parents=True, exist_ok=True)
    (run_dir / "viewer").mkdir(parents=True, exist_ok=True)

    host_start = run_dir / f"{options.name}-host.startscript"
    viewer_start = run_dir / f"{options.name}-viewer.startscript"
    token_path = run_dir / "highbar.token"
    host_log = run_dir / "host" / "engine.log"
    viewer_log = run_dir / "viewer" / "viewer.log"
    ai_log = run_dir / "ai.log"
    admin_log = run_dir / "admin-behavior.log"
    admin_behavior_dir = run_dir / "admin-behavior"
    report_path = run_dir / "report.md"
    uds_path = run_dir / "host" / f"highbar-{options.gateway_skirmish_ai_id}.sock"
    host_pid_file = run_dir / "host" / "engine.pid"
    viewer_pid_file = run_dir / "viewer" / "viewer.pid"
    autohost_log = run_dir / "autohost-relay.log"

    host_start.write_text(
        render_host_startscript(
            resolved.start_script_template.read_text(encoding="utf-8"),
            options,
            autohost_port=resolved.autohost_port,
        ),
        encoding="utf-8",
    )
    viewer_start.write_text(
        render_viewer_startscript("127.0.0.1", options.host_port, options.viewer_player_name),
        encoding="utf-8",
    )

    env = os.environ.copy()
    env["HIGHBAR_TOKEN_PATH"] = str(token_path)
    env["HIGHBAR_ENABLE_BUILTIN"] = "false"
    if resolved.autohost_port is not None:
        env["HIGHBAR_AUTOHOST_PORT"] = str(resolved.autohost_port)

    host_pid: int | None = None
    viewer_pid: int | None = None
    autohost_pid: int | None = None
    ai_rc = 1
    admin_behavior_rc: int | None = None
    updates = 0
    batches = 0
    viewer_status = "disabled" if not options.attach_bnv else "pending"

    try:
        if resolved.autohost_port is not None:
            autohost_pid = _start_autohost_relay(
                resolved,
                port=resolved.autohost_port,
                log_path=autohost_log,
            )

        _run_launch(
            [
                str(resolved.launcher),
                "--start-script",
                str(host_start),
                "--engine",
                str(resolved.spring_headless),
                "--runtime-dir",
                str(run_dir / "host"),
                "--log",
                str(host_log),
                "--pid-file",
                str(host_pid_file),
                "--enable-builtin",
                "false",
                *(
                    ["--plugin-so", str(resolved.plugin_so)]
                    if resolved.plugin_so is not None
                    else []
                ),
                "--writedir",
                str(resolved.write_dir),
            ],
            env=env,
        )
        host_pid = _read_pid(host_pid_file)
        _wait_for_log_pattern(
            host_log,
            rf"\[UDPListener\] successfully bound socket on port {options.host_port}",
            host_pid,
            "host UDP listener did not bind",
        )

        if options.attach_bnv:
            _run_launch(
                [
                    str(resolved.launcher),
                    "--start-script",
                    str(viewer_start),
                    "--engine",
                    str(resolved.spring_graphical),
                    "--runtime-dir",
                    str(run_dir / "viewer"),
                    "--log",
                    str(viewer_log),
                    "--pid-file",
                    str(viewer_pid_file),
                    "--window-mode",
                    options.window_mode,
                    "--window-width",
                    str(options.window_width),
                    "--window-height",
                    str(options.window_height),
                    "--mouse-capture",
                    "true" if options.mouse_capture else "false",
                    "--viewer-only",
                    "true",
                    "--writedir",
                    str(resolved.write_dir),
                ],
                env=env,
            )
            viewer_pid = _read_pid(viewer_pid_file)

        _wait_for_path(uds_path, host_pid, "gateway UDS not found", is_socket=True)
        _wait_for_path(token_path, host_pid, "token file not found")

        ai_lines: list[str] = []
        if options.ai_plugin is not None:
            try:
                updates, batches = _run_ai_policy(resolved, token_path, uds_path, ai_lines)
                ai_rc = 0
            finally:
                ai_log.write_text("".join(ai_lines), encoding="utf-8")
        else:
            ai_rc = 0
            ai_log.write_text("ai-topology: no Python AI policy configured\n", encoding="utf-8")

        if options.admin_behavior:
            admin_behavior_rc = _run_admin_behavior_suite(
                resolved,
                endpoint=f"unix:{uds_path}",
                token_path=token_path,
                host_log=host_log,
                output_dir=admin_behavior_dir,
                log_path=admin_log,
            )

        viewer_status = _viewer_status(viewer_log) if options.attach_bnv else "disabled"
        result = TopologyRunResult(
            name=options.name,
            run_dir=run_dir,
            report_path=report_path,
            host_port=options.host_port,
            viewer_status=viewer_status,
            ai_runner_rc=ai_rc,
            admin_behavior_rc=admin_behavior_rc,
            admin_behavior_report_path=(
                admin_behavior_dir / "run-report.md" if options.admin_behavior else None
            ),
            updates=updates,
            batches_submitted=batches,
            uds_path=uds_path,
            token_path=token_path,
            host_pid=host_pid,
            viewer_pid=viewer_pid,
            autohost_pid=autohost_pid,
        )
        _write_report(result, host_log, viewer_log, ai_log, admin_log, autohost_log)

        if options.attach_bnv and viewer_status == "pending":
            raise TopologyRunError(f"viewer did not join; see {report_path}")
        if options.ai_plugin is not None and options.require_batches and batches == 0:
            raise TopologyRunError(f"AI submitted zero accepted batches; see {report_path}")
        if admin_behavior_rc not in (None, 0):
            raise TopologyRunError(f"admin behavior suite failed; see {report_path}")
        return result
    except subprocess.CalledProcessError as exc:
        if exc.returncode == 77:
            raise TopologyPrerequisiteError(exc.stderr or exc.stdout or str(exc)) from exc
        raise TopologyRunError(exc.stderr or exc.stdout or str(exc)) from exc
    finally:
        if options.cleanup:
            _kill_pid(viewer_pid)
            _kill_pid(host_pid)
            _kill_pid(autohost_pid)


def render_host_startscript(
    template: str,
    options: TopologyOptions,
    *,
    autohost_port: int | None = None,
) -> str:
    """Return a host startscript patched for ``options``.

    The fixture keeps the highBar proxy on team 0 and NullAI on team 1.
    This helper only changes stable knobs needed for local topology
    variation: host port, speed/start-delay, and display names.
    """

    text = template
    for key, value in (
        ("HostPort", str(options.host_port)),
        ("MinSpeed", options.min_speed),
        ("MaxSpeed", options.max_speed),
        ("GameStartDelay", options.game_start_delay),
    ):
        text, count = re.subn(
            rf"(^\s*{key}\s*=)\s*[^;]+;",
            rf"\g<1>{value};",
            text,
            flags=re.MULTILINE,
        )
        if count == 0:
            raise ValueError(f"startscript missing {key}")

    text = text.replace("Name=HighBarV3-team0;", f"Name={options.host_team_ai_name};")
    text = text.replace("Name=HighBarV3-team1;", f"Name={options.opponent_ai_name};")
    if autohost_port is not None:
        text = inject_autohost_startscript(text, autohost_port)
    return text


def inject_autohost_startscript(text: str, autohost_port: int) -> str:
    if "AutohostPort=" in text:
        text = re.sub(
            r"(^\s*AutohostIP\s*=)\s*[^;]+;",
            r"\g<1>127.0.0.1;",
            text,
            flags=re.MULTILINE,
        )
        return re.sub(
            r"(^\s*AutohostPort\s*=)\s*[^;]+;",
            rf"\g<1>{autohost_port};",
            text,
            flags=re.MULTILINE,
        )
    return re.sub(
        r"(^\s*HostPort\s*=\s*[^;]+;\n)",
        rf"\1\tAutohostIP=127.0.0.1;\n\tAutohostPort={autohost_port};\n",
        text,
        count=1,
        flags=re.MULTILINE,
    )


def render_viewer_startscript(host: str, port: int, player_name: str = "HighBarV3BNV") -> str:
    """Return a minimal viewer-only startscript for joining a live host."""

    return (
        "[GAME]\n"
        "{\n"
        f"\tHostIP={host};\n"
        f"\tHostPort={port};\n"
        "\tSourcePort=0;\n"
        f"\tMyPlayerName={player_name};\n"
        "\tIsHost=0;\n"
        "}\n"
    )


@dataclass(frozen=True, slots=True)
class _ResolvedOptions:
    options: TopologyOptions
    repo_root: Path
    launcher: Path
    start_script_template: Path
    run_dir: Path
    spring_headless: Path
    spring_graphical: Path
    plugin_so: Path | None
    write_dir: Path
    autohost_port: int | None

    @classmethod
    def from_options(cls, options: TopologyOptions) -> "_ResolvedOptions":
        repo_root = Path(options.repo_root) if options.repo_root else _discover_repo_root()
        launcher = repo_root / "tests/headless/_launch.sh"
        if not launcher.is_file():
            raise TopologyPrerequisiteError(f"_launch.sh not found at {launcher}")

        if options.start_script_template is not None:
            start_script = Path(options.start_script_template)
            if not start_script.is_absolute():
                start_script = repo_root / start_script
        else:
            start_script = repo_root / "tests/headless/scripts/minimal.startscript"
        if not start_script.is_file():
            raise TopologyPrerequisiteError(f"startscript not found at {start_script}")

        write_dir = Path(options.write_dir) if options.write_dir else DEFAULT_WRITE_DIR
        spring_headless = _resolve_spring_headless(options, write_dir)
        if not spring_headless.is_file():
            raise TopologyPrerequisiteError(f"spring-headless not found at {spring_headless}")
        spring_graphical = _resolve_spring_graphical(options, spring_headless)
        if options.attach_bnv and not spring_graphical.is_file():
            raise TopologyPrerequisiteError(f"graphical spring not found at {spring_graphical}")

        plugin_so = _resolve_plugin_so(options, repo_root)
        if plugin_so is not None and not plugin_so.is_file():
            raise TopologyPrerequisiteError(f"plugin artifact not found at {plugin_so}")

        return cls(
            options=options,
            repo_root=repo_root,
            launcher=launcher,
            start_script_template=start_script,
            run_dir=Path(options.run_dir),
            spring_headless=spring_headless,
            spring_graphical=spring_graphical,
            plugin_so=plugin_so,
            write_dir=write_dir,
            autohost_port=_reserve_udp_port() if options.autohost_relay else None,
        )


def _discover_repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _resolve_spring_headless(options: TopologyOptions, write_dir: Path) -> Path:
    if options.spring_headless is not None:
        return Path(options.spring_headless)
    env_path = os.environ.get("SPRING_HEADLESS")
    if env_path:
        return Path(env_path)
    return write_dir / "engine" / DEFAULT_ENGINE_RELEASE / "spring-headless"


def _resolve_spring_graphical(options: TopologyOptions, spring_headless: Path) -> Path:
    if options.spring_graphical is not None:
        return Path(options.spring_graphical)
    env_path = os.environ.get("HIGHBAR_BAR_CLIENT_BINARY")
    if env_path:
        return Path(env_path)
    return spring_headless.parent / "spring"


def _resolve_plugin_so(options: TopologyOptions, repo_root: Path) -> Path | None:
    if options.plugin_so is not None:
        return Path(options.plugin_so)
    env_path = os.environ.get("HIGHBAR_PLUGIN_SO")
    if env_path:
        return Path(env_path)
    default = repo_root / "build/libSkirmishAI.so"
    return default if default.is_file() else None


def _reserve_udp_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _start_autohost_relay(
    resolved: _ResolvedOptions,
    *,
    port: int,
    log_path: Path,
) -> int | None:
    relay = resolved.repo_root / "tests/headless/autohost_relay.py"
    if not relay.is_file():
        raise TopologyPrerequisiteError(f"autohost relay not found at {relay}")
    log_path.parent.mkdir(parents=True, exist_ok=True)
    proc = subprocess.Popen(  # noqa: S603 - local test utility path and args are controlled
        [
            "python3",
            str(relay),
            "--port",
            str(port),
            "--log",
            str(log_path),
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return proc.pid


def _run_admin_behavior_suite(
    resolved: _ResolvedOptions,
    *,
    endpoint: str,
    token_path: Path,
    host_log: Path,
    output_dir: Path,
    log_path: Path,
) -> int:
    output_dir.mkdir(parents=True, exist_ok=True)
    command = [
        "uv",
        "run",
        "--project",
        str(resolved.repo_root / "clients/python"),
        "python",
        "-m",
        "highbar_client.behavioral_coverage",
        "admin",
        "--startscript",
        str(resolved.start_script_template),
        "--output-dir",
        str(output_dir),
        "--endpoint",
        endpoint,
        "--token-file",
        str(token_path),
        "--log-location",
        str(host_log),
        "--timeout-seconds",
        str(resolved.options.stream_timeout_seconds or 30.0),
    ]
    proc = subprocess.run(
        command,
        text=True,
        capture_output=True,
        check=False,
    )
    log_path.write_text((proc.stdout or "") + (proc.stderr or ""), encoding="utf-8")
    return int(proc.returncode)


def _run_launch(command: list[str], *, env: Mapping[str, str]) -> None:
    subprocess.run(
        command,
        env=dict(env),
        check=True,
        text=True,
        capture_output=True,
    )


def _run_ai_policy(
    resolved: _ResolvedOptions,
    token_path: Path,
    uds_path: Path,
    log_lines: list[str],
) -> tuple[int, int]:
    options = resolved.options
    if options.ai_plugin is None:
        return (0, 0)
    plugin = load_ai_plugin(
        options.ai_plugin,
        config=dict(options.ai_plugin_config or {}),
    )
    name_addon = options.name_addon if options.name_addon is not None else options.name
    client_id = client_id_for_plugin(plugin, name_addon=name_addon)
    endpoint = channel.Endpoint.uds(str(uds_path))
    grpc_channel = channel.for_endpoint(endpoint)
    token = session.read_token_with_backoff(str(token_path), options.token_wait_ms)
    handshake = session.hello(
        grpc_channel,
        role=session.ClientRole.AI,
        client_id=client_id,
        token=token,
    )
    context = AIPluginContext(
        channel=grpc_channel,
        token=token,
        handshake=handshake,
        client_id=client_id,
        name_addon=name_addon,
    )
    log_lines.append(
        f"ai-topology: connected client_id={client_id} "
        f"session={handshake.session_id} plugin={plugin.name}/{plugin.version}\n"
    )
    updates = 0
    batches = 0
    deadline = (
        time.monotonic() + options.duration_seconds
        if options.duration_seconds is not None
        else None
    )
    stream_timeout = options.stream_timeout_seconds
    if stream_timeout is None and options.duration_seconds is not None:
        stream_timeout = options.duration_seconds + 10.0

    plugin.on_start(context)
    try:
        for update in state_stream.consume(
            grpc_channel,
            resume_from_seq=0,
            max_wait_seconds=stream_timeout,
        ):
            updates += 1
            for batch in plugin.on_state(context, update):
                ack = context.submit(batch, timeout=options.submit_timeout_seconds)
                batches += ack.batches_accepted
            if options.max_updates > 0 and updates >= options.max_updates:
                break
            if deadline is not None and time.monotonic() >= deadline:
                break
    except grpc.RpcError as exc:
        if exc.code() != grpc.StatusCode.DEADLINE_EXCEEDED:
            raise
    finally:
        plugin.on_stop(context)

    log_lines.append(
        f"ai-topology: stopped updates={updates} batches_submitted={batches}\n"
    )
    return updates, batches


def _wait_for_log_pattern(
    log_path: Path,
    pattern: str,
    pid: int | None,
    failure: str,
    *,
    attempts: int = 80,
    delay_seconds: float = 0.25,
) -> None:
    regex = re.compile(pattern)
    for _ in range(attempts):
        if log_path.is_file() and regex.search(log_path.read_text(errors="ignore")):
            return
        if pid is not None and not _pid_alive(pid):
            raise TopologyRunError(f"{failure}: host exited")
        time.sleep(delay_seconds)
    raise TopologyRunError(failure)


def _wait_for_path(
    path: Path,
    pid: int | None,
    failure: str,
    *,
    is_socket: bool = False,
    attempts: int = 80,
    delay_seconds: float = 0.25,
) -> None:
    for _ in range(attempts):
        if path.exists() and (not is_socket or path.is_socket()):
            return
        if pid is not None and not _pid_alive(pid):
            raise TopologyRunError(f"{failure}: host exited")
        time.sleep(delay_seconds)
    raise TopologyRunError(f"{failure}: {path}")


def _viewer_status(viewer_log: Path) -> str:
    if not viewer_log.is_file():
        return "pending"
    text = viewer_log.read_text(errors="ignore")
    if re.search(r"\[f=[0-9-]+\]", text):
        return "live"
    if "[Game::ClientReadNet] added new player" in text:
        return "joined"
    return "pending"


def _write_report(
    result: TopologyRunResult,
    host_log: Path,
    viewer_log: Path,
    ai_log: Path,
    admin_log: Path,
    autohost_log: Path,
) -> None:
    result.report_path.write_text(
        "\n".join(
            [
                f"# {result.name} live topology run",
                "",
                f"- run_dir: {result.run_dir}",
                f"- host_port: {result.host_port}",
                f"- host_pid: {result.host_pid if result.host_pid is not None else 'unknown'}",
                f"- viewer_pid: {result.viewer_pid if result.viewer_pid is not None else 'unknown'}",
                f"- viewer_status: {result.viewer_status}",
                f"- ai_runner_rc: {result.ai_runner_rc}",
                f"- admin_behavior_rc: {result.admin_behavior_rc if result.admin_behavior_rc is not None else 'not-run'}",
                f"- admin_behavior_report: {result.admin_behavior_report_path or 'not-run'}",
                f"- updates: {result.updates}",
                f"- batches_submitted: {result.batches_submitted}",
                f"- uds: {result.uds_path}",
                f"- token: {result.token_path}",
                f"- autohost_pid: {result.autohost_pid if result.autohost_pid is not None else 'not-run'}",
                "",
                "## AI log tail",
                "```",
                _tail(ai_log),
                "```",
                "",
                "## Admin behavior log tail",
                "```",
                _tail(admin_log),
                "```",
                "",
                "## Autohost relay signals",
                "```",
                _grep_tail(autohost_log, r"relay listening|relay command|drop command"),
                "```",
                "",
                "## Viewer log signals",
                "```",
                _grep_tail(viewer_log, r"added new player|server connection timeout|\[f="),
                "```",
                "",
                "## Engine gateway signals",
                "```",
                _grep_tail(host_log, r"\[hb-gateway\]|CommandDispatch|error|Error|fatal|Fatal"),
                "```",
                "",
            ]
        ),
        encoding="utf-8",
    )


def _tail(path: Path, lines: int = 80) -> str:
    if not path.is_file():
        return ""
    return "\n".join(path.read_text(errors="ignore").splitlines()[-lines:])


def _grep_tail(path: Path, pattern: str, lines: int = 80) -> str:
    if not path.is_file():
        return ""
    regex = re.compile(pattern)
    matches = [line for line in path.read_text(errors="ignore").splitlines() if regex.search(line)]
    return "\n".join(matches[-lines:])


def _read_pid(path: Path) -> int | None:
    try:
        return int(path.read_text(encoding="utf-8").strip())
    except (OSError, ValueError):
        return None


def _pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def _kill_pid(pid: int | None) -> None:
    if pid is None:
        return
    try:
        os.kill(pid, signal.SIGTERM)
    except OSError:
        return

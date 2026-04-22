# SPDX-License-Identifier: GPL-2.0-only
"""Static inventory and source-citation helpers for the 004 audit."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from .registry import REGISTRY
from .types import AuditArtifacts


ENGINE_PIN = "recoil_2025.06.19"
GAMETYPE_PIN = "test-29926"
RPC_METHODS = (
    "Hello",
    "StreamState",
    "SubmitCommands",
    "InvokeCallback",
    "Save",
    "Load",
    "GetRuntimeCounters",
    "RequestSnapshot",
)

_CASE_TO_ARM = {
    "DrawAddPoint": "draw_add_point",
    "DrawAddLine": "draw_add_line",
    "DrawRemovePoint": "draw_remove_point",
    "SendTextMessage": "send_text_message",
    "SetLastPosMessage": "set_last_pos_message",
    "SendResources": "send_resources",
    "SetMyIncomeShareDirect": "set_my_income_share_direct",
    "SetShareLevel": "set_share_level",
    "PauseTeam": "pause_team",
    "GroupAddUnit": "group_add_unit",
    "GroupRemoveUnit": "group_remove_unit",
    "InitPath": "init_path",
    "GetApproxLength": "get_approx_length",
    "GetNextWaypoint": "get_next_waypoint",
    "FreePath": "free_path",
    "GiveMe": "give_me",
    "GiveMeNewUnit": "give_me_new_unit",
    "CallLuaRules": "call_lua_rules",
    "CallLuaUi": "call_lua_ui",
    "CreateSplineFigure": "create_spline_figure",
    "CreateLineFigure": "create_line_figure",
    "SetFigurePosition": "set_figure_position",
    "SetFigureColor": "set_figure_color",
    "RemoveFigure": "remove_figure",
    "DrawUnit": "draw_unit",
    "BuildUnit": "build_unit",
    "Stop": "stop",
    "Wait": "wait",
    "TimedWait": "timed_wait",
    "SquadWait": "squad_wait",
    "DeathWait": "death_wait",
    "GatherWait": "gather_wait",
    "MoveUnit": "move_unit",
    "Patrol": "patrol",
    "Fight": "fight",
    "Attack": "attack",
    "AttackArea": "attack_area",
    "Guard": "guard",
    "Repair": "repair",
    "ReclaimUnit": "reclaim_unit",
    "ReclaimArea": "reclaim_area",
    "ReclaimInArea": "reclaim_in_area",
    "ReclaimFeature": "reclaim_feature",
    "RestoreArea": "restore_area",
    "Resurrect": "resurrect",
    "ResurrectInArea": "resurrect_in_area",
    "Capture": "capture",
    "CaptureArea": "capture_area",
    "SetBase": "set_base",
    "SelfDestruct": "self_destruct",
    "LoadUnits": "load_units",
    "LoadUnitsArea": "load_units_area",
    "LoadOnto": "load_onto",
    "UnloadUnit": "unload_unit",
    "UnloadUnitsArea": "unload_units_area",
    "SetWantedMaxSpeed": "set_wanted_max_speed",
    "Stockpile": "stockpile",
    "Dgun": "dgun",
    "Custom": "custom",
    "SetOnOff": "set_on_off",
    "SetRepeat": "set_repeat",
    "SetMoveState": "set_move_state",
    "SetFireState": "set_fire_state",
    "SetTrajectory": "set_trajectory",
    "SetAutoRepairLevel": "set_auto_repair_level",
    "SetIdleMode": "set_idle_mode",
}


def repo_root() -> Path:
    return Path(__file__).resolve().parents[4]


def artifacts() -> AuditArtifacts:
    root = repo_root()
    return AuditArtifacts(
        repo_root=root,
        audit_dir=root / "audit",
        reports_dir=root / "build" / "reports",
    )


def command_dispatch_citations() -> dict[str, str]:
    path = repo_root() / "src/circuit/grpc/CommandDispatch.cpp"
    lines = path.read_text(encoding="utf-8").splitlines()
    citations: dict[str, str] = {}
    current_case: str | None = None
    start_line: int | None = None
    for idx, line in enumerate(lines, start=1):
        match = re.match(r"\s*case C::k([A-Za-z0-9]+):", line)
        if match:
            if current_case and start_line is not None:
                arm = _CASE_TO_ARM.get(current_case)
                if arm and arm not in citations:
                    citations[arm] = f"src/circuit/grpc/CommandDispatch.cpp:{start_line}-{idx - 1}"
            current_case = match.group(1)
            start_line = idx
    if current_case and start_line is not None:
        arm = _CASE_TO_ARM.get(current_case)
        if arm and arm not in citations:
            citations[arm] = f"src/circuit/grpc/CommandDispatch.cpp:{start_line}-{len(lines)}"
    return citations


def service_citations() -> dict[str, str]:
    path = repo_root() / "src/circuit/grpc/HighBarService.cpp"
    lines = path.read_text(encoding="utf-8").splitlines()
    targets = {
        "Hello": "RequestHello",
        "GetRuntimeCounters": "GetRuntimeCountersCallData",
        "StreamState": "StreamStateCallData",
        "SubmitCommands": "SubmitCommandsCallData",
        "InvokeCallback": "InvokeCallback",
        "Save": "Save",
        "Load": "Load",
        "RequestSnapshot": "RequestSnapshotCallData",
    }
    citations: dict[str, str] = {}
    for rpc_name, token in targets.items():
        start = next(
            (idx for idx, line in enumerate(lines, start=1) if token in line),
            None,
        )
        if start is None:
            citations[rpc_name] = "src/circuit/grpc/HighBarService.cpp:1-1"
            continue
        end = min(len(lines), start + 24)
        citations[rpc_name] = f"src/circuit/grpc/HighBarService.cpp:{start}-{end}"
    return citations


def row_category_for_arm(arm_name: str) -> str:
    case = REGISTRY[arm_name]
    if arm_name in {"give_me", "give_me_new_unit"}:
        return "cheats-gated"
    return case.category


def sorted_arm_names() -> list[str]:
    return sorted(REGISTRY.keys())


@dataclass(frozen=True)
class V2PathologySource:
    pathology_id: str
    pathology_name: str
    v2_source_citation: str
    v2_excerpt: str


V2_PATHOLOGIES: tuple[V2PathologySource, ...] = (
    V2PathologySource(
        "callback-frame-interleaving",
        "Callback frame interleaving",
        "/home/developer/projects/HighBarV2/docs/known-issues.md:40-62",
        "Callback requests could receive the next Frame instead of a CallbackResponse, desynchronizing the protocol.",
    ),
    V2PathologySource(
        "client-recvbytes-infinite-loop",
        "Client recvBytes infinite loop",
        "/home/developer/projects/HighBarV2/reports/017-fix-client-socket-hang.md:33-40",
        "The F# framed-socket reader added zero bytes on peer close and looped forever.",
    ),
    V2PathologySource(
        "max-message-size-8mb",
        "8 MB max-message-size insufficient",
        "/home/developer/projects/HighBarV2/docs/known-issues.md:64-74",
        "The default 8 MB framing limit was too small for large-map payloads.",
    ),
    V2PathologySource(
        "single-connection-lockout",
        "Single-connection lockout, no auto-reconnect",
        "/home/developer/projects/HighBarV2/docs/known-issues.md:76-78",
        "The proxy supported one client connection and had no structured reconnect path.",
    ),
    V2PathologySource(
        "frame-budget-timeout",
        "Frame-budget timeout and AI removal",
        "/home/developer/projects/HighBarV2/docs/known-issues.md:80-82",
        "Slow client-side processing could violate the frame budget and get the AI removed.",
    ),
    V2PathologySource(
        "save-load-todos",
        "Save / Load proxy-side TODO stubs",
        "/home/developer/projects/HighBarV2/docs/known-issues.md:84-92",
        "Save and Load handling remained stubbed or incomplete in the proxy.",
    ),
)

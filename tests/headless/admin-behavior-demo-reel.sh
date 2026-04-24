#!/usr/bin/env bash
# Generate an operator-facing live demo reel for admin behavioral controls with BNV context.

set -euo pipefail

STARTSCRIPT="tests/headless/scripts/admin-behavior.startscript"
OUTPUT_DIR="build/reports/admin-behavior-demo"
EVIDENCE_REPLAY=""
WATCH_PROFILE="default"
ALLOW_MISSING_BNV="false"
LAUNCH_BNV="false"
HOLD_SECONDS="10"
TIMEOUT_SECONDS="30"

while [[ $# -gt 0 ]]; do
    case "$1" in
        --startscript) STARTSCRIPT="$2"; shift 2 ;;
        --output-dir) OUTPUT_DIR="$2"; shift 2 ;;
        --evidence-replay) EVIDENCE_REPLAY="$2"; shift 2 ;;
        --watch-profile) WATCH_PROFILE="$2"; shift 2 ;;
        --allow-missing-bnv) ALLOW_MISSING_BNV="true"; shift ;;
        --launch-bnv) LAUNCH_BNV="true"; shift ;;
        --hold-seconds) HOLD_SECONDS="$2"; shift 2 ;;
        --timeout-seconds) TIMEOUT_SECONDS="$2"; shift 2 ;;
        -h|--help)
            sed -n '1,120p' "$0"
            exit 0
            ;;
        *) echo "admin-behavior-demo-reel.sh: unknown arg: $1" >&2; exit 2 ;;
    esac
done

REPO_ROOT="$(cd "$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")/../.." && pwd)"
cd "$REPO_ROOT"

if [[ ! -f "$STARTSCRIPT" ]]; then
    echo "admin-behavior-demo-reel.sh: startscript missing at $STARTSCRIPT" >&2
    exit 77
fi
if [[ -n "$EVIDENCE_REPLAY" && ! -f "$EVIDENCE_REPLAY" ]]; then
    echo "admin-behavior-demo-reel.sh: evidence replay missing at $EVIDENCE_REPLAY" >&2
    exit 77
fi
if [[ ! -x tests/headless/admin-behavioral-control.sh ]]; then
    echo "admin-behavior-demo-reel.sh: admin behavioral harness is not executable" >&2
    exit 77
fi
if [[ ! -x tests/headless/_launch.sh ]]; then
    echo "admin-behavior-demo-reel.sh: headless launcher is not executable" >&2
    exit 77
fi
if ! command -v uv >/dev/null 2>&1; then
    echo "admin-behavior-demo-reel.sh: uv is required" >&2
    exit 77
fi

mkdir -p "$OUTPUT_DIR"
OUTPUT_DIR="$(cd "$OUTPUT_DIR" && pwd)"

DISPLAY_JSON="$OUTPUT_DIR/display.json"
PREFLIGHT_JSON="$OUTPUT_DIR/bnv-preflight.json"
EVIDENCE_DIR="$OUTPUT_DIR/evidence"
REEL_MD="$OUTPUT_DIR/demo-reel.md"
BNV_LOG="$OUTPUT_DIR/bnv-launch.log"
BNV_PID_FILE="$OUTPUT_DIR/bnv-launch.pid"
BNV_RUNTIME_DIR="$OUTPUT_DIR/bnv-runtime"
HOST_LOG="$OUTPUT_DIR/host.log"
HOST_PID_FILE="$OUTPUT_DIR/host.pid"
HOST_RUNTIME_DIR="$OUTPUT_DIR/runtime"
HOST_STARTSCRIPT="$OUTPUT_DIR/admin-behavior-demo-host.startscript"
VIEWER_STARTSCRIPT="$OUTPUT_DIR/admin-behavior-demo-viewer.startscript"
AUTOHOST_PID_FILE="$OUTPUT_DIR/autohost-relay.pid"
AUTOHOST_LOG="$OUTPUT_DIR/autohost-relay.log"
TOKEN_FILE="$OUTPUT_DIR/highbar.token"

cleanup_pid_file() {
    local pid_file="$1"
    if [[ -f "$pid_file" ]]; then
        local pid
        pid="$(cat "$pid_file" 2>/dev/null || true)"
        if [[ -n "${pid:-}" ]] && kill -0 "$pid" 2>/dev/null; then
            kill "$pid" 2>/dev/null || true
            wait "$pid" 2>/dev/null || true
        fi
    fi
}

cleanup() {
    cleanup_pid_file "$BNV_PID_FILE"
    cleanup_pid_file "$HOST_PID_FILE"
    cleanup_pid_file "$AUTOHOST_PID_FILE"
}
trap cleanup EXIT

reserve_tcp_port() {
    python3 - <<'PY'
import socket
with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
    sock.bind(("127.0.0.1", 0))
    print(sock.getsockname()[1])
PY
}

reserve_udp_port() {
    python3 - <<'PY'
import socket
with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
    sock.bind(("127.0.0.1", 0))
    print(sock.getsockname()[1])
PY
}

prepare_host_startscript() {
    local source_startscript="$1"
    local target_startscript="$2"
    local host_port="$3"
    local autohost_port="$4"

    python3 - "$source_startscript" "$target_startscript" "$host_port" "$autohost_port" <<'PY'
from pathlib import Path
import re
import sys

source = Path(sys.argv[1])
target = Path(sys.argv[2])
host_port = sys.argv[3]
autohost_port = sys.argv[4]
text = source.read_text(encoding="utf-8")

text, count = re.subn(
    r"(^\s*HostPort\s*=)\s*[^;]+;",
    rf"\g<1>{host_port};",
    text,
    count=1,
    flags=re.MULTILINE,
)
if count == 0:
    raise SystemExit(f"missing HostPort in {source}")

if "AutohostPort=" not in text:
    text = re.sub(
        r"(^\s*HostPort\s*=\s*[^;]+;\n)",
        rf"\1\tAutohostIP=127.0.0.1;\n\tAutohostPort={autohost_port};\n",
        text,
        count=1,
        flags=re.MULTILINE,
    )
else:
    text = re.sub(r"(^\s*AutohostIP\s*=)\s*[^;]+;", r"\g<1>127.0.0.1;", text, flags=re.MULTILINE)
    text = re.sub(r"(^\s*AutohostPort\s*=)\s*[^;]+;", rf"\g<1>{autohost_port};", text, flags=re.MULTILINE)

target.write_text(text, encoding="utf-8")
PY
}

prepare_viewer_startscript() {
    local target_startscript="$1"
    local host_port="$2"

    python3 - "$target_startscript" "$host_port" <<'PY'
from pathlib import Path
import sys

target = Path(sys.argv[1])
host_port = sys.argv[2]
target.write_text(
    f"""[GAME]
{{
\tHostIP=127.0.0.1;
\tHostPort={host_port};
\tSourcePort=0;
\tMyPlayerName=HighBarV3AdminDemoBNV;
\tIsHost=0;
}}
""",
    encoding="utf-8",
)
PY
}

echo "Current display:"
printf 'DISPLAY=%s\nWAYLAND_DISPLAY=%s\nXDG_SESSION_TYPE=%s\n' \
    "${DISPLAY-}" "${WAYLAND_DISPLAY-}" "${XDG_SESSION_TYPE-}"

DISPLAY_JSON="$DISPLAY_JSON" \
PREFLIGHT_JSON="$PREFLIGHT_JSON" \
STARTSCRIPT="$STARTSCRIPT" \
WATCH_PROFILE="$WATCH_PROFILE" \
uv run --project clients/python python - <<'PY'
import json
import os
from dataclasses import asdict
from pathlib import Path

from highbar_client.behavioral_coverage.bnv_watch import (
    build_viewer_launch_command,
    evaluate_watch_preflight,
)

display = {
    "DISPLAY": os.environ.get("DISPLAY", ""),
    "WAYLAND_DISPLAY": os.environ.get("WAYLAND_DISPLAY", ""),
    "XDG_SESSION_TYPE": os.environ.get("XDG_SESSION_TYPE", ""),
}
Path(os.environ["DISPLAY_JSON"]).write_text(
    json.dumps(display, indent=2, sort_keys=True) + "\n",
    encoding="utf-8",
)

preflight = evaluate_watch_preflight(
    profile_ref=os.environ["WATCH_PROFILE"],
    resolved_run_id="admin-behavior-demo",
    run_compatible=True,
)
payload = asdict(preflight)
if preflight.resolved_profile is not None:
    payload["launch_command"] = list(
        build_viewer_launch_command(
            preflight.resolved_profile,
            startscript=os.environ["STARTSCRIPT"],
            write_dir=os.environ.get("HIGHBAR_WRITE_DIR", "").strip() or None,
        )
    )
else:
    payload["launch_command"] = []
Path(os.environ["PREFLIGHT_JSON"]).write_text(
    json.dumps(payload, indent=2, sort_keys=True) + "\n",
    encoding="utf-8",
)

print(f"BNV preflight: {preflight.status}")
print(preflight.reason)
if payload["launch_command"]:
    print("BNV launch command:")
    print(" ".join(payload["launch_command"]))
PY

BNV_STATUS="$(
    PREFLIGHT_JSON="$PREFLIGHT_JSON" uv run --project clients/python python - <<'PY'
import json
import os
from pathlib import Path

payload = json.loads(Path(os.environ["PREFLIGHT_JSON"]).read_text(encoding="utf-8"))
print(payload["status"])
PY
)"
if [[ "$BNV_STATUS" != "ready" && "$ALLOW_MISSING_BNV" != "true" ]]; then
    echo "admin-behavior-demo-reel.sh: BNV preflight is $BNV_STATUS; pass --allow-missing-bnv to generate the evidence-only reel" >&2
    exit 77
fi

if [[ -n "$EVIDENCE_REPLAY" ]]; then
    tests/headless/admin-behavioral-control.sh \
        --skip-launch \
        --evidence-replay "$EVIDENCE_REPLAY" \
        --output-dir "$EVIDENCE_DIR" \
        --timeout-seconds "$TIMEOUT_SECONDS"
else
    mkdir -p "$HOST_RUNTIME_DIR" "$BNV_RUNTIME_DIR" "$EVIDENCE_DIR"
    HOST_PORT="$(reserve_tcp_port)"
    AUTOHOST_PORT="$(reserve_udp_port)"
    prepare_host_startscript "$STARTSCRIPT" "$HOST_STARTSCRIPT" "$HOST_PORT" "$AUTOHOST_PORT"
    prepare_viewer_startscript "$VIEWER_STARTSCRIPT" "$HOST_PORT"

    python3 tests/headless/autohost_relay.py \
        --port "$AUTOHOST_PORT" \
        --log "$AUTOHOST_LOG" &
    echo "$!" > "$AUTOHOST_PID_FILE"

    HIGHBAR_TOKEN_PATH="$TOKEN_FILE" HIGHBAR_AUTOHOST_PORT="$AUTOHOST_PORT" tests/headless/_launch.sh \
        --start-script "$HOST_STARTSCRIPT" \
        --log "$HOST_LOG" \
        --pid-file "$HOST_PID_FILE" \
        --runtime-dir "$HOST_RUNTIME_DIR" \
        --phase 2 \
        --enable-builtin false >/dev/null

    if [[ "$LAUNCH_BNV" == "true" ]]; then
        if [[ "$BNV_STATUS" != "ready" ]]; then
            echo "admin-behavior-demo-reel.sh: cannot launch BNV because preflight is $BNV_STATUS" >&2
            exit 77
        fi
        for _ in $(seq 1 300); do
            if grep -q "successfully bound socket" "$HOST_LOG" 2>/dev/null; then
                break
            fi
            sleep 0.05
        done
        if ! grep -q "successfully bound socket" "$HOST_LOG" 2>/dev/null; then
            echo "admin-behavior-demo-reel.sh: host UDP listener did not bind before BNV launch" >&2
            tail -n 120 "$HOST_LOG" >&2 || true
            exit 1
        fi
        mapfile -t BNV_PROFILE < <(
            PREFLIGHT_JSON="$PREFLIGHT_JSON" uv run --project clients/python python - <<'PY'
import json
import os
from pathlib import Path

payload = json.loads(Path(os.environ["PREFLIGHT_JSON"]).read_text(encoding="utf-8"))
profile = payload.get("resolved_profile") or {}
print(profile.get("viewer_binary", ""))
print(profile.get("window_mode", "windowed"))
print(profile.get("window_width", 1920))
print(profile.get("window_height", 1080))
print(str(profile.get("mouse_capture", False)).lower())
PY
        )
        BNV_BINARY="${BNV_PROFILE[0]}"
        BNV_WINDOW_MODE="${BNV_PROFILE[1]}"
        BNV_WINDOW_WIDTH="${BNV_PROFILE[2]}"
        BNV_WINDOW_HEIGHT="${BNV_PROFILE[3]}"
        BNV_MOUSE_CAPTURE="${BNV_PROFILE[4]}"
        echo "Launching BNV on DISPLAY=${DISPLAY-}:"
        tests/headless/_launch.sh \
            --start-script "$VIEWER_STARTSCRIPT" \
            --engine "$BNV_BINARY" \
            --runtime-dir "$BNV_RUNTIME_DIR" \
            --log "$BNV_LOG" \
            --pid-file "$BNV_PID_FILE" \
            --window-mode "$BNV_WINDOW_MODE" \
            --window-width "$BNV_WINDOW_WIDTH" \
            --window-height "$BNV_WINDOW_HEIGHT" \
            --mouse-capture "$BNV_MOUSE_CAPTURE" \
            --viewer-only true >/dev/null
        BNV_PID="$(cat "$BNV_PID_FILE")"
        sleep 2
        if ! kill -0 "$BNV_PID" 2>/dev/null; then
            echo "admin-behavior-demo-reel.sh: BNV exited during startup; log tail follows" >&2
            tail -n 120 "$BNV_LOG" >&2 || true
            exit 1
        fi
        echo "BNV launched: pid=$BNV_PID log=$BNV_LOG startscript=$VIEWER_STARTSCRIPT"
    fi

    for _ in $(seq 1 600); do
        sockets=("$HOST_RUNTIME_DIR"/highbar-*.sock)
        if [[ -S "${sockets[0]}" ]]; then
            break
        fi
        sleep 0.05
    done
    if [[ ! -S "$HOST_RUNTIME_DIR/highbar-0.sock" ]]; then
        echo "admin-behavior-demo-reel.sh: host gRPC socket did not appear" >&2
        tail -n 120 "$HOST_LOG" >&2 || true
        exit 1
    fi

    tests/headless/admin-behavioral-control.sh \
        --skip-launch \
        --output-dir "$EVIDENCE_DIR" \
        --endpoint "unix:$HOST_RUNTIME_DIR/highbar-0.sock" \
        --token-file "$TOKEN_FILE" \
        --log-location "$HOST_LOG" \
        --timeout-seconds "$TIMEOUT_SECONDS"
fi

DISPLAY_JSON="$DISPLAY_JSON" \
PREFLIGHT_JSON="$PREFLIGHT_JSON" \
SUMMARY_CSV="$EVIDENCE_DIR/summary.csv" \
RUN_REPORT="$EVIDENCE_DIR/run-report.md" \
REEL_MD="$REEL_MD" \
EVIDENCE_REPLAY="$EVIDENCE_REPLAY" \
STARTSCRIPT="$STARTSCRIPT" \
HOST_STARTSCRIPT="$HOST_STARTSCRIPT" \
VIEWER_STARTSCRIPT="$VIEWER_STARTSCRIPT" \
HOST_LOG="$HOST_LOG" \
BNV_LOG="$BNV_LOG" \
AUTOHOST_LOG="$AUTOHOST_LOG" \
LAUNCH_BNV="$LAUNCH_BNV" \
uv run --project clients/python python - <<'PY'
import csv
import json
import os
from pathlib import Path

display = json.loads(Path(os.environ["DISPLAY_JSON"]).read_text(encoding="utf-8"))
preflight = json.loads(Path(os.environ["PREFLIGHT_JSON"]).read_text(encoding="utf-8"))
summary_path = Path(os.environ["SUMMARY_CSV"])
rows = list(csv.DictReader(summary_path.open(encoding="utf-8", newline="")))
passed = sum(row["passed"] == "true" for row in rows)
mode = "replay" if os.environ["EVIDENCE_REPLAY"] else "live"

cue_copy = {
    "pause_match": "Freeze the live match; BNV should stop frame progression while the state stream proves no frame advance.",
    "resume_match": "Resume play; BNV should show motion again while the state stream proves frames advance.",
    "set_speed_fast": "Increase global simulation speed; BNV should visibly accelerate while the engine log proves Recoil set speed to 2.0.",
    "grant_resource": "Grant team resources; BNV should show the controlled economy bump while the resource snapshot changes.",
    "spawn_enemy_unit": "Spawn an enemy fixture unit near the active unit; BNV should show the new opposing unit appear.",
    "transfer_unit": "Transfer a unit to the opposing team; BNV should show allegiance change while the unit remains in place.",
    "reject_unauthorized": "Attempt an unauthorized admin action; BNV should remain unchanged and the audit result must be permission denied.",
    "reject_invalid_speed": "Attempt an invalid speed; BNV should remain at the prior speed.",
    "reject_invalid_resource": "Attempt an invalid resource target; BNV should show no economy mutation.",
    "reject_invalid_spawn": "Attempt an invalid spawn; BNV should show no new unit.",
    "reject_invalid_transfer": "Attempt an invalid transfer; BNV should show ownership unchanged.",
    "reject_lease_conflict": "Attempt a conflicting leased pause action; BNV should remain in the leased state.",
}

lines = [
    "# Admin Behavioral Demo Reel",
    "",
    "## Current Display",
    f"- DISPLAY: `{display.get('DISPLAY', '')}`",
    f"- WAYLAND_DISPLAY: `{display.get('WAYLAND_DISPLAY', '')}`",
    f"- XDG_SESSION_TYPE: `{display.get('XDG_SESSION_TYPE', '')}`",
    "",
    "## BNV Setup",
    f"- Preflight status: `{preflight['status']}`",
    f"- Reason: {preflight['reason']}",
    f"- Launch requested: `{os.environ['LAUNCH_BNV']}`",
    f"- Source startscript: `{os.environ['STARTSCRIPT']}`",
    f"- Host startscript: `{os.environ['HOST_STARTSCRIPT']}`",
    f"- Viewer startscript: `{os.environ['VIEWER_STARTSCRIPT']}`",
    f"- Host log: `{os.environ['HOST_LOG']}`",
    f"- BNV log: `{os.environ['BNV_LOG']}`",
    f"- Autohost relay log: `{os.environ['AUTOHOST_LOG']}`",
]
launch_command = preflight.get("launch_command") or []
if launch_command:
    lines.extend(["- Profile launch command template:", "```sh", " ".join(launch_command), "```"])
else:
    lines.append("- Profile launch command template: unavailable until a graphical BAR client binary is configured.")

lines.extend(
    [
        "",
        "## Evidence Gate",
        f"- Evidence mode: `{mode}`",
        f"- Evidence records: {len(rows)}",
        f"- Passed records: {passed}",
        f"- Failed records: {len(rows) - passed}",
        f"- Summary CSV: `{summary_path}`",
        f"- Full report: `{os.environ['RUN_REPORT']}`",
        "",
        "## Reel Sequence",
        "| Shot | Scenario | Function | BNV cue | Behavioral evidence | Result |",
        "|---:|---|---|---|---|---|",
    ]
)
for index, row in enumerate(rows, start=1):
    scenario = row["scenario_id"]
    action = row["action_name"]
    evidence = f"{row['evidence_source']} / observed={row['observed']}"
    result = "PASS" if row["passed"] == "true" else f"FAIL {row['failure_class']}"
    lines.append(
        f"| {index} | `{scenario}` | `{action}` | {cue_copy.get(scenario, 'Show the action in BNV.')} | {evidence} | {result} |"
    )

lines.extend(
    [
        "",
        "## Acceptance Rule",
        "The reel is accepted only when every shot has behavioral evidence from the live state stream, live snapshot delta, or live engine log, and every expected rejection proves no mutation.",
        "",
    ]
)
Path(os.environ["REEL_MD"]).write_text("\n".join(lines), encoding="utf-8")
PY

echo
echo "Demo reel written to $REEL_MD"
if [[ "$LAUNCH_BNV" == "true" ]]; then
    echo "BNV log written to $BNV_LOG"
    echo "Holding BNV for ${HOLD_SECONDS}s"
    sleep "$HOLD_SECONDS"
fi
echo
sed -n '1,240p' "$REEL_MD"

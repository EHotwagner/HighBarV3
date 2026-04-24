#!/usr/bin/env bash
# Stable entry point for the admin behavioral control suite.

set -euo pipefail

STARTSCRIPT="tests/headless/scripts/admin-behavior.startscript"
OUTPUT_DIR="build/reports/admin-behavior"
TIMEOUT_SECONDS="10"
REPEAT_INDEX="0"
SKIP_LAUNCH="false"
EVIDENCE_REPLAY=""
ENDPOINT_OVERRIDE=""
TOKEN_FILE_OVERRIDE=""
LOG_LOCATION_OVERRIDE=""

while [[ $# -gt 0 ]]; do
    case "$1" in
        --startscript) STARTSCRIPT="$2"; shift 2 ;;
        --output-dir) OUTPUT_DIR="$2"; shift 2 ;;
        --timeout-seconds) TIMEOUT_SECONDS="$2"; shift 2 ;;
        --repeat-index) REPEAT_INDEX="$2"; shift 2 ;;
        --skip-launch) SKIP_LAUNCH="true"; shift ;;
        --evidence-replay) EVIDENCE_REPLAY="$2"; shift 2 ;;
        --endpoint) ENDPOINT_OVERRIDE="$2"; shift 2 ;;
        --token-file) TOKEN_FILE_OVERRIDE="$2"; shift 2 ;;
        --log-location) LOG_LOCATION_OVERRIDE="$2"; shift 2 ;;
        -h|--help)
            sed -n '1,80p' "$0"
            exit 0
            ;;
        *) echo "admin-behavioral-control.sh: unknown arg: $1" >&2; exit 2 ;;
    esac
done

REPO_ROOT="$(cd "$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")/../.." && pwd)"
cd "$REPO_ROOT"

if [[ ! -f "$STARTSCRIPT" ]]; then
    echo "admin-behavioral-control.sh: startscript missing at $STARTSCRIPT" >&2
    exit 77
fi
if [[ ! -f tests/fixtures/admin_behavior/fixture.yaml ]]; then
    echo "admin-behavioral-control.sh: fixture metadata missing" >&2
    exit 77
fi
if ! command -v uv >/dev/null 2>&1; then
    echo "admin-behavioral-control.sh: uv is required" >&2
    exit 77
fi

mkdir -p "$OUTPUT_DIR"
OUTPUT_DIR="$(cd "$OUTPUT_DIR" && pwd)"
mkdir -p "$OUTPUT_DIR/logs"
ENGINE_LOG="$OUTPUT_DIR/logs/engine.log"
COORDINATOR_LOG="$OUTPUT_DIR/logs/coordinator.log"
: > "$ENGINE_LOG"
: > "$COORDINATOR_LOG"

PID_FILE="$OUTPUT_DIR/admin-behavior.pid"
RUNTIME_DIR="$OUTPUT_DIR/runtime"
TOKEN_FILE="$OUTPUT_DIR/highbar.token"
SOCKET_PATH="$RUNTIME_DIR/highbar-0.sock"
if [[ -n "$TOKEN_FILE_OVERRIDE" ]]; then
    TOKEN_FILE="$TOKEN_FILE_OVERRIDE"
fi
AUTOHOST_PID_FILE="$OUTPUT_DIR/autohost-relay.pid"
cleanup() {
    if [[ -f "$PID_FILE" ]]; then
        pid="$(cat "$PID_FILE" 2>/dev/null || true)"
        if [[ -n "${pid:-}" ]] && kill -0 "$pid" 2>/dev/null; then
            kill "$pid" 2>/dev/null || true
            wait "$pid" 2>/dev/null || true
        fi
    fi
    if [[ -f "$AUTOHOST_PID_FILE" ]]; then
        relay_pid="$(cat "$AUTOHOST_PID_FILE" 2>/dev/null || true)"
        if [[ -n "${relay_pid:-}" ]] && kill -0 "$relay_pid" 2>/dev/null; then
            kill "$relay_pid" 2>/dev/null || true
            wait "$relay_pid" 2>/dev/null || true
        fi
    fi
}
trap cleanup EXIT

if [[ "$SKIP_LAUNCH" != "true" ]]; then
    if [[ ! -x tests/headless/_launch.sh ]]; then
        echo "admin-behavioral-control.sh: headless launcher missing" >&2
        exit 77
    fi
    mkdir -p "$RUNTIME_DIR"
    AUTOHOST_PORT="$(python3 - <<'PY'
import socket
with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
    s.bind(("127.0.0.1", 0))
    print(s.getsockname()[1])
PY
)"
    python3 tests/headless/autohost_relay.py \
        --port "$AUTOHOST_PORT" \
        --log "$OUTPUT_DIR/logs/autohost-relay.log" &
    echo "$!" > "$AUTOHOST_PID_FILE"

    AUTOHOST_STARTSCRIPT="$RUNTIME_DIR/admin-behavior-autohost.startscript"
    awk -v port="$AUTOHOST_PORT" '
        { print }
        /^[[:space:]]*HostPort=/ {
            print "\tAutohostIP=127.0.0.1;"
            print "\tAutohostPort=" port ";"
        }
    ' "$STARTSCRIPT" > "$AUTOHOST_STARTSCRIPT"

    if HIGHBAR_TOKEN_PATH="$TOKEN_FILE" HIGHBAR_AUTOHOST_PORT="$AUTOHOST_PORT" tests/headless/_launch.sh \
        --start-script "$AUTOHOST_STARTSCRIPT" \
        --log "$ENGINE_LOG" \
        --pid-file "$PID_FILE" \
        --runtime-dir "$RUNTIME_DIR" \
        --phase 2 \
        --enable-builtin false; then
        :
    else
        code=$?
        [[ "$code" -eq 77 ]] && exit 77
        exit "$code"
    fi

    for _ in $(seq 1 600); do
        sockets=("$RUNTIME_DIR"/highbar-*.sock)
        if [[ -S "${sockets[0]}" ]]; then
            SOCKET_PATH="${sockets[0]}"
            break
        fi
        sleep 0.05
    done
fi

ENDPOINT="unix:$SOCKET_PATH"
if [[ -n "$ENDPOINT_OVERRIDE" ]]; then
    ENDPOINT="$ENDPOINT_OVERRIDE"
fi

ARGS=(
    --startscript "$STARTSCRIPT"
    --output-dir "$OUTPUT_DIR"
    --endpoint "$ENDPOINT"
    --token-file "$TOKEN_FILE"
    --timeout-seconds "$TIMEOUT_SECONDS"
    --repeat-index "$REPEAT_INDEX"
)
if [[ -n "$EVIDENCE_REPLAY" ]]; then
    ARGS+=(--evidence-replay "$EVIDENCE_REPLAY")
fi
if [[ -n "$LOG_LOCATION_OVERRIDE" ]]; then
    ARGS+=(--log-location "$LOG_LOCATION_OVERRIDE")
fi

uv run --project clients/python python -m highbar_client.behavioral_coverage admin "${ARGS[@]}"

#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-2.0-only

# Shared coordinator bootstrap helper for client-mode headless tests.
# Prefer Unix sockets, but fall back to loopback TCP when the local gRPC
# runtime cannot bind a unix: endpoint.

HIGHBAR_COORDINATOR_ENDPOINT=""
HIGHBAR_COORDINATOR_PID=""
HIGHBAR_COORDINATOR_TRANSPORT=""

highbar_pick_loopback_port() {
    python3 - <<'PY'
import socket

try:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
except OSError:
    raise SystemExit(1)
sock.bind(("127.0.0.1", 0))
print(sock.getsockname()[1])
sock.close()
PY
}

highbar_wait_for_tcp_listener() {
    local host="$1"
    local port="$2"

    for _ in $(seq 1 20); do
        if python3 - "$host" "$port" <<'PY'
import socket
import sys

host = sys.argv[1]
port = int(sys.argv[2])
try:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
except OSError:
    raise SystemExit(1)
sock.settimeout(0.2)
try:
    sock.connect((host, port))
except OSError:
    raise SystemExit(1)
finally:
    sock.close()
PY
        then
            return 0
        fi
        sleep 0.2
    done

    return 1
}

highbar_start_coordinator() {
    local examples_dir="$1"
    local run_dir="$2"
    local coord_id="$3"
    local coord_log="$4"
    local coord_sock="$run_dir/hb-coord.sock"
    local tcp_port=""

    HIGHBAR_COORDINATOR_ENDPOINT=""
    HIGHBAR_COORDINATOR_PID=""
    HIGHBAR_COORDINATOR_TRANSPORT=""

    rm -f "$coord_sock"
    python3 "$examples_dir/coordinator.py" \
        --endpoint "unix:$coord_sock" --id "$coord_id" > "$coord_log" 2>&1 &
    HIGHBAR_COORDINATOR_PID=$!
    for _ in $(seq 1 20); do
        if [[ -S "$coord_sock" ]]; then
            HIGHBAR_COORDINATOR_ENDPOINT="unix:$coord_sock"
            HIGHBAR_COORDINATOR_TRANSPORT="uds"
            return 0
        fi
        if ! kill -0 "$HIGHBAR_COORDINATOR_PID" 2>/dev/null; then
            break
        fi
        sleep 0.2
    done
    wait "$HIGHBAR_COORDINATOR_PID" 2>/dev/null || true

    tcp_port="$(highbar_pick_loopback_port)" || return 1
    printf '%s\n' \
        "coordinator-helper: unix bind unavailable, retrying with tcp 127.0.0.1:$tcp_port" \
        >> "$coord_log"
    python3 "$examples_dir/coordinator.py" \
        --endpoint "127.0.0.1:$tcp_port" --id "$coord_id" >> "$coord_log" 2>&1 &
    HIGHBAR_COORDINATOR_PID=$!
    if ! highbar_wait_for_tcp_listener "127.0.0.1" "$tcp_port"; then
        wait "$HIGHBAR_COORDINATOR_PID" 2>/dev/null || true
        HIGHBAR_COORDINATOR_PID=""
        return 1
    fi

    HIGHBAR_COORDINATOR_ENDPOINT="127.0.0.1:$tcp_port"
    HIGHBAR_COORDINATOR_TRANSPORT="tcp"
    return 0
}

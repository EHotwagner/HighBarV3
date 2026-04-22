#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-2.0-only

# Shared coordinator bootstrap helper for client-mode headless tests.
# Prefer Unix sockets, but fall back to loopback TCP when the local gRPC
# runtime cannot bind a unix: endpoint.
#
# Set HIGHBAR_COORDINATOR_FORCE_TRANSPORT=uds|tcp|auto to override the
# default "prefer uds, fall back to tcp" selection.

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

highbar_start_coordinator_uds() {
    local examples_dir="$1"
    local coord_sock="$2"
    local coord_id="$3"
    local coord_log="$4"

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
    HIGHBAR_COORDINATOR_PID=""
    return 1
}

highbar_start_coordinator_tcp() {
    local examples_dir="$1"
    local coord_id="$2"
    local coord_log="$3"
    local tcp_port="$4"

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

highbar_start_coordinator() {
    local examples_dir="$1"
    local run_dir="$2"
    local coord_id="$3"
    local coord_log="$4"
    local coord_sock="$run_dir/hb-coord.sock"
    local tcp_port=""
    local transport_mode="${HIGHBAR_COORDINATOR_FORCE_TRANSPORT:-auto}"

    HIGHBAR_COORDINATOR_ENDPOINT=""
    HIGHBAR_COORDINATOR_PID=""
    HIGHBAR_COORDINATOR_TRANSPORT=""

    case "$transport_mode" in
        auto|uds|tcp)
            ;;
        *)
            printf '%s\n' \
                "coordinator-helper: invalid HIGHBAR_COORDINATOR_FORCE_TRANSPORT=$transport_mode (expected auto|uds|tcp)" \
                > "$coord_log"
            return 1
            ;;
    esac

    if [[ "$transport_mode" != "tcp" ]]; then
        if highbar_start_coordinator_uds "$examples_dir" "$coord_sock" "$coord_id" "$coord_log"; then
            return 0
        fi
        if [[ "$transport_mode" == "uds" ]]; then
            printf '%s\n' \
                "coordinator-helper: forced uds failed to bind at $coord_sock" \
                >> "$coord_log"
            return 1
        fi
    fi

    tcp_port="$(highbar_pick_loopback_port)" || return 1
    if [[ "$transport_mode" == "auto" ]]; then
        printf '%s\n' \
            "coordinator-helper: unix bind unavailable, retrying with tcp 127.0.0.1:$tcp_port" \
            >> "$coord_log"
    else
        printf '%s\n' \
            "coordinator-helper: forcing tcp 127.0.0.1:$tcp_port" \
            > "$coord_log"
    fi
    highbar_start_coordinator_tcp "$examples_dir" "$coord_id" "$coord_log" "$tcp_port"
}

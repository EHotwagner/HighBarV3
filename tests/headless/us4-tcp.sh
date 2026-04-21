#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-2.0-only
# arm-covered: (none — 001-era skip stub; no arms dispatched)
#
# HighBarV3 — US4 TCP acceptance (T077).
#
# Runs us1-observer + us2-ai-coexist flows over loopback TCP. Confirms
# the config-toggle claim in SC-008: one-line change in grpc.json
# swaps transport, identical client code works end-to-end.

set -euo pipefail

# T030/T031 — FR-024 fault-aware exit policy. Source the helper
# unconditionally; `fault_status` returns 0=healthy, 2=disabled,
# 77=indeterminate. Acceptance scripts MUST upgrade `disabled` to
# exit 1, never 77.
source "$(dirname "$0")/_fault-assert.sh"

repo_root="$(cd "$(dirname "$0")/../.." && pwd)"
plugin_lib="${repo_root}/build/libSkirmishAI.so"
observer_bin="${repo_root}/clients/fsharp/samples/Observer/bin/Debug/net8.0/hb-observer"
ai_bin="${repo_root}/clients/fsharp/samples/AiClient/bin/Debug/net8.0/hb-ai-client"

if [[ ! -x "${SPRING_HEADLESS:-}" ]]; then
    echo "us4-tcp: SPRING_HEADLESS not set — skip." >&2
    exit 77
fi
if [[ ! -f "${plugin_lib}" || ! -x "${observer_bin}" || ! -x "${ai_bin}" ]]; then
    echo "us4-tcp: plugin / clients not built — skip." >&2
    exit 77
fi

tcp_bind="${HIGHBAR_TCP_BIND:-127.0.0.1:50513}"
log_dir="${repo_root}/build/tmp/us4-tcp"
mkdir -p "${log_dir}"
engine_log="${log_dir}/engine.log"
observer_log="${log_dir}/observer.log"
ai_log="${log_dir}/ai.log"
token_path="${log_dir}/highbar.token"

# TCP-mode grpc.json — SC-008's "exactly one configuration-file change"
# claim: we set transport="tcp" and keep every other value at its
# default. An operator swapping UDS → TCP flips exactly this line.
cfg_dir="${log_dir}/cfg"
mkdir -p "${cfg_dir}"
cat > "${cfg_dir}/grpc.json" <<EOF
{
  "transport": "tcp",
  "tcp_bind": "${tcp_bind}",
  "ai_token_path": "${token_path}",
  "max_recv_mb": 32,
  "ring_size": 2048
}
EOF

HIGHBAR_CONFIG_DIR="${cfg_dir}" \
"${SPRING_HEADLESS}" --ai HighBarV3 --config us4-tcp.sdd \
    > "${engine_log}" 2>&1 &
engine_pid=$!
cleanup() { kill "${engine_pid}" 2>/dev/null || true; }
trap cleanup EXIT

# Wait for TCP bind.
for _ in {1..100}; do
    if (exec 3<>"/dev/tcp/${tcp_bind%:*}/${tcp_bind##*:}") 2>/dev/null; then
        exec 3<&-; exec 3>&-; break
    fi
    sleep 0.1
done
(exec 3<>"/dev/tcp/${tcp_bind%:*}/${tcp_bind##*:}") 2>/dev/null \
    || { echo "us4-tcp: TCP not bound after 10s"; exit 1; }
exec 3<&-; exec 3>&- 2>/dev/null || true

# Wait for token file.
for _ in {1..100}; do
    [[ -f "${token_path}" ]] && break
    sleep 0.1
done
[[ -f "${token_path}" ]] || { echo "us4-tcp: token file not created"; exit 1; }

# -- Observer over TCP --
timeout 10 "${observer_bin}" --transport tcp --tcp-bind "${tcp_bind}" \
    > "${observer_log}" 2>&1 || true
grep -q "SNAPSHOT" "${observer_log}" \
    || { echo "us4-tcp: no SNAPSHOT via TCP"; exit 1; }

# -- AI submit over TCP --
target_unit="${HIGHBAR_TARGET_UNIT:-1}"
move_to="${HIGHBAR_MOVE_TO:-1024,0,1024}"
"${ai_bin}" --transport tcp --tcp-bind "${tcp_bind}" \
    --token-file "${token_path}" \
    --target-unit "${target_unit}" \
    --move-to "${move_to}" \
    > "${ai_log}" 2>&1
grep -q "ack" "${ai_log}" \
    || { echo "us4-tcp: no ACK from AI submit over TCP"; exit 1; }

echo "us4-tcp: PASS — observer + AI submit work over loopback TCP"

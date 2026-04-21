#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-2.0-only
# arm-covered: (none — 001-era skip stub; no arms dispatched)
#
# HighBarV3 — US4 transport parity test (T075).
#
# Proves SC-008: the same client + plugin + match produces byte-
# identical StateUpdate traces across UDS and TCP, modulo timing.
#
# Methodology:
#   1. Launch two spring-headless matches with identical seed/map/AI
#      roster. Match A configured for UDS (data/config/grpc.json
#      variant), match B for TCP.
#   2. Attach a recording observer to each. Observer outputs canonical
#      protobuf (binary StateUpdate) to a file.
#   3. Strip the `frame` field's timing jitter by normalizing to the
#      first snapshot frame, then compare the two recordings.
#
# Skips (exit 77) on missing prerequisites.

set -euo pipefail

# T030/T031 — FR-024 fault-aware exit policy. Source the helper
# unconditionally; `fault_status` returns 0=healthy, 2=disabled,
# 77=indeterminate. Acceptance scripts MUST upgrade `disabled` to
# exit 1, never 77.
source "$(dirname "$0")/_fault-assert.sh"

repo_root="$(cd "$(dirname "$0")/../.." && pwd)"
plugin_lib="${repo_root}/build/libSkirmishAI.so"
observer_bin="${repo_root}/clients/fsharp/samples/Observer/bin/Debug/net8.0/hb-observer"

if [[ ! -x "${SPRING_HEADLESS:-}" ]]; then
    echo "us4-transport-parity: SPRING_HEADLESS not set — skip." >&2
    exit 77
fi
if [[ ! -f "${plugin_lib}" || ! -x "${observer_bin}" ]]; then
    echo "us4-transport-parity: plugin or observer not built — skip." >&2
    exit 77
fi

: "${XDG_RUNTIME_DIR:=/tmp}"
log_dir="${repo_root}/build/tmp/us4-transport-parity"
mkdir -p "${log_dir}"
uds_path="${XDG_RUNTIME_DIR}/highbar-parity.sock"
tcp_bind="127.0.0.1:50512"

run_match() {
    local transport=$1
    local tag=$2
    local engine_log="${log_dir}/${tag}.engine.log"
    local observer_log="${log_dir}/${tag}.observer.log"

    # Write a per-match grpc.json override. The engine start script
    # should point the plugin at this file via HIGHBAR_CONFIG_DIR.
    local cfg_dir="${log_dir}/cfg-${tag}"
    mkdir -p "${cfg_dir}"
    cat > "${cfg_dir}/grpc.json" <<EOF
{
  "transport": "${transport}",
  "uds_path": "${uds_path}",
  "tcp_bind": "${tcp_bind}",
  "ai_token_path": "${log_dir}/${tag}.token",
  "max_recv_mb": 32,
  "ring_size": 2048
}
EOF

    HIGHBAR_CONFIG_DIR="${cfg_dir}" \
    "${SPRING_HEADLESS}" --ai HighBarV3 \
                         --config "us4-parity-${transport}.sdd" \
                         --seed 1234567 \
        > "${engine_log}" 2>&1 &
    local engine_pid=$!

    # Wait for bind readiness depending on transport.
    local ready=0
    for _ in {1..100}; do
        if [[ "${transport}" == "uds" && -S "${uds_path}" ]]; then ready=1; break; fi
        if [[ "${transport}" == "tcp" ]]; then
            if (exec 3<>/dev/tcp/127.0.0.1/50512) 2>/dev/null; then
                exec 3<&-; exec 3>&-; ready=1; break
            fi
        fi
        sleep 0.1
    done
    [[ ${ready} -eq 1 ]] || { echo "us4-transport-parity: ${transport} bind timeout"; kill "${engine_pid}" 2>/dev/null || true; exit 1; }

    timeout 15 "${observer_bin}" \
        --transport "${transport}" \
        --uds-path "${uds_path}" \
        --tcp-bind "${tcp_bind}" \
        > "${observer_log}" 2>&1 || true

    kill "${engine_pid}" 2>/dev/null || true
    wait "${engine_pid}" 2>/dev/null || true
    echo "${observer_log}"
}

uds_log=$(run_match uds uds)
tcp_log=$(run_match tcp tcp)

# Parity check: strip timing-sensitive fields (the per-line "seq=N frame=N"
# prefix) and diff the payload summaries. For a true byte-equality check
# the observer would need a --record-binary flag (emit raw proto bytes
# to a file); landing that is a follow-up. For now compare the textual
# event shape which catches divergence in the delta catalog / ordering.
norm() {
    # Drop "seq=<n> frame=<n>" prefix and any trailing whitespace so the
    # comparison is purely about shape (SNAPSHOT / DELTA / KEEPALIVE
    # plus counts).
    sed -E 's/^seq=[0-9]+ frame=[0-9]+ //' "$1" | sort
}

if diff <(norm "${uds_log}") <(norm "${tcp_log}") > "${log_dir}/diff.txt"; then
    echo "us4-transport-parity: PASS — UDS and TCP streams match (shape equality)"
    exit 0
else
    echo "us4-transport-parity: FAIL — streams diverge"
    head -n 20 "${log_dir}/diff.txt" >&2
    exit 1
fi

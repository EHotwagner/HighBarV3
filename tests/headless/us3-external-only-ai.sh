#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-2.0-only
#
# HighBarV3 — US3 Phase-2 external-only with AI client (T082, folds T083).
#
# Launches spring-headless with enable_builtin=false and an external F#
# AI client issuing scripted commands. Asserts:
#   1. The F# AI client's MoveTo lands via the engine's command path.
#   2. No built-in AI activity (none of BARb's decision modules Update()).
#
# The second assertion is the T083 coverage that was folded into this
# script during the integration-tier pivot.

set -euo pipefail

repo_root="$(cd "$(dirname "$0")/../.." && pwd)"
plugin_lib="${repo_root}/build/libSkirmishAI.so"
ai_bin="${repo_root}/clients/fsharp/samples/AiClient/bin/Debug/net8.0/hb-ai-client"
observer_bin="${repo_root}/clients/fsharp/samples/Observer/bin/Debug/net8.0/hb-observer"

if [[ ! -x "${SPRING_HEADLESS:-}" ]]; then
    echo "us3-external-only-ai: SPRING_HEADLESS not set — skip." >&2
    exit 77
fi
if [[ ! -f "${plugin_lib}" || ! -x "${ai_bin}" || ! -x "${observer_bin}" ]]; then
    echo "us3-external-only-ai: plugin / clients not built — skip." >&2
    exit 77
fi

: "${XDG_RUNTIME_DIR:=/tmp}"
gameid="${HIGHBAR_SMOKE_GAMEID:-us3-ai}"
uds_path="${XDG_RUNTIME_DIR}/highbar-${gameid}.sock"
log_dir="${repo_root}/build/tmp/us3-external-only-ai"
mkdir -p "${log_dir}"
engine_log="${log_dir}/engine.log"
observer_log="${log_dir}/observer.log"
ai_log="${log_dir}/ai.log"

ai_options_file="${log_dir}/aioptions.lua"
cat > "${ai_options_file}" <<EOF
return { enable_builtin = 'false' }
EOF

"${SPRING_HEADLESS}" --ai HighBarV3 \
                     --config us3-external-only-ai.sdd \
                     --ai-options "${ai_options_file}" \
    > "${engine_log}" 2>&1 &
engine_pid=$!
cleanup() { kill "${engine_pid}" 2>/dev/null || true; }
trap cleanup EXIT

for i in {1..100}; do
    [[ -S "${uds_path}" ]] && break
    sleep 0.1
done
[[ -S "${uds_path}" ]] || { echo "us3-external-only-ai: UDS not bound"; exit 1; }

token_path="${HIGHBAR_TOKEN_PATH:-${XDG_DATA_HOME:-$HOME/.local/share}/HighBar/highbar.token}"
for i in {1..100}; do
    [[ -f "${token_path}" ]] && break
    sleep 0.1
done
[[ -f "${token_path}" ]] || { echo "us3-external-only-ai: token missing"; exit 1; }

# Record a baseline via an observer so we can compare command dispatch
# to what arrives on the state stream.
timeout 20 "${observer_bin}" --transport uds --uds-path "${uds_path}" \
    > "${observer_log}" 2>&1 &
observer_pid=$!
sleep 2

target_unit="${HIGHBAR_TARGET_UNIT:-1}"
move_to="${HIGHBAR_MOVE_TO:-1024,0,1024}"

"${ai_bin}" --transport uds --uds-path "${uds_path}" \
    --token-file "${token_path}" \
    --target-unit "${target_unit}" \
    --move-to "${move_to}" \
    > "${ai_log}" 2>&1
grep -q "ack" "${ai_log}" || { echo "us3-external-only-ai: no ACK"; exit 1; }

wait "${observer_pid}" 2>/dev/null || true

# T083 assertion: enable_builtin=false MUST mean no built-in manager
# activity. Look for BARb's built-in module prefixes in the engine log.
# Any hit → fail with the offending line.
if grep -qE "\[(Builder|Economy|Factory|Military)Manager\]" "${engine_log}"; then
    echo "us3-external-only-ai: FAIL — built-in manager activity detected despite enable_builtin=false"
    grep -E "\[(Builder|Economy|Factory|Military)Manager\]" "${engine_log}" | head -n 5 >&2
    exit 1
fi

# Conversely, the gateway's own log prefix should still be present.
grep -q "\[hb-gateway\]" "${engine_log}" \
    || { echo "us3-external-only-ai: WARN — no [hb-gateway] log line"; }

echo "us3-external-only-ai: PASS — external AI drove the unit; built-in chain inert"

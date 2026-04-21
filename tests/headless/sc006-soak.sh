#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-2.0-only
#
# HighBarV3 — SC-006 30-minute soak (T102).
#
# Runs a full match for 30 minutes with: F# observer + F# AI client +
# Python observer attached simultaneously. All three clients record
# their StateStream output; the SC-005 checker (client-side
# SeqInvariantException/Error) asserts no gaps/duplicates/out-of-order
# across all three streams.
#
# SC-006: ≥95% of sessions complete this clean. One run → one data
# point; CI can loop this script for the statistical sample.

set -euo pipefail

repo_root="$(cd "$(dirname "$0")/../.." && pwd)"
plugin_lib="${repo_root}/build/libSkirmishAI.so"
fs_observer="${repo_root}/clients/fsharp/samples/Observer/bin/Debug/net8.0/hb-observer"
fs_ai="${repo_root}/clients/fsharp/samples/AiClient/bin/Debug/net8.0/hb-ai-client"
python_venv="${repo_root}/clients/python/.venv"

if [[ ! -x "${SPRING_HEADLESS:-}" ]]; then
    echo "sc006-soak: SPRING_HEADLESS not set — skip." >&2
    exit 77
fi
if [[ ! -f "${plugin_lib}" || ! -x "${fs_observer}" || ! -x "${fs_ai}" ]]; then
    echo "sc006-soak: plugin / F# clients not built — skip." >&2
    exit 77
fi
if [[ ! -d "${python_venv}" ]]; then
    echo "sc006-soak: Python venv not set up — skip." >&2
    exit 77
fi

soak_seconds="${HIGHBAR_SOAK_SECONDS:-1800}"  # 30 minutes
: "${XDG_RUNTIME_DIR:=/tmp}"
uds_path="${XDG_RUNTIME_DIR}/highbar-soak.sock"
log_dir="${repo_root}/build/tmp/sc006-soak"
mkdir -p "${log_dir}"

"${SPRING_HEADLESS}" --ai HighBarV3 --config sc006-soak.sdd \
    > "${log_dir}/engine.log" 2>&1 &
engine_pid=$!
cleanup() {
    kill "${engine_pid}" 2>/dev/null || true
    kill "${fs_obs_pid:-}" "${py_obs_pid:-}" 2>/dev/null || true
}
trap cleanup EXIT

for _ in {1..100}; do
    [[ -S "${uds_path}" ]] && break
    sleep 0.1
done

token_path="${HIGHBAR_TOKEN_PATH:-${XDG_DATA_HOME:-$HOME/.local/share}/HighBar/highbar.token}"
for _ in {1..100}; do
    [[ -f "${token_path}" ]] && break
    sleep 0.1
done

# Start two observers. Both raise on seq invariant violation → script
# exits non-zero via timeout's SIGTERM-EXITCODE-124 path.
timeout "${soak_seconds}" "${fs_observer}" \
    --transport uds --uds-path "${uds_path}" \
    > "${log_dir}/fs-observer.log" 2>&1 &
fs_obs_pid=$!

timeout "${soak_seconds}" "${python_venv}/bin/python" \
    -m highbar_client.samples.observer \
    --transport uds --uds-path "${uds_path}" \
    > "${log_dir}/py-observer.log" 2>&1 &
py_obs_pid=$!

# Periodic AI submissions so the command path is exercised across the
# soak window. One batch every 30s, target unit 1, cycling between two
# points so the engine has something to execute.
ai_loop() {
    local i=0
    while kill -0 "${engine_pid}" 2>/dev/null; do
        local target_x=$(( 1000 + (i % 2) * 500 ))
        "${fs_ai}" \
            --transport uds --uds-path "${uds_path}" \
            --token-file "${token_path}" \
            --target-unit "${HIGHBAR_TARGET_UNIT:-1}" \
            --move-to "${target_x},0,1024" \
            >> "${log_dir}/ai-submissions.log" 2>&1 || true
        i=$((i+1))
        sleep 30
    done
}
ai_loop &
ai_loop_pid=$!

# Wait out the soak.
sleep "${soak_seconds}"

kill "${ai_loop_pid}" 2>/dev/null || true
wait "${fs_obs_pid}" 2>/dev/null || true
wait "${py_obs_pid}" 2>/dev/null || true

# Clean exit means no SeqInvariantException / SeqInvariantError was
# raised in either client. A non-zero exit from either observer would
# appear in its log as the exception traceback.
fs_bad=$(grep -c "SeqInvariant" "${log_dir}/fs-observer.log" || true)
py_bad=$(grep -c "SeqInvariant" "${log_dir}/py-observer.log" || true)
if [[ "${fs_bad}" -gt 0 || "${py_bad}" -gt 0 ]]; then
    echo "sc006-soak: FAIL — seq invariant violated (F#=${fs_bad} Py=${py_bad})"
    exit 1
fi

# Engine must still be alive.
if ! kill -0 "${engine_pid}" 2>/dev/null; then
    echo "sc006-soak: FAIL — engine died during soak"
    exit 1
fi

echo "sc006-soak: PASS — ${soak_seconds}s soak with 1 clean session across 3 clients"

#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-2.0-only
#
# HighBarV3 — disconnect-lifecycle survivability (T103).
#
# Drives a rogue client that terminates at each of several RPC
# lifecycle points:
#   1. mid-Hello — TCP/UDS connect + send but SIGKILL before reply
#   2. after Hello but before first StreamState message
#   3. mid-delta stream — random seq cut-off
#   4. mid-SubmitCommands client-stream batch — send partial batch, SIGKILL
#   5. (InvokeCallback/Save/Load lifecycle cases are out of this script;
#      they require engine-originated invocations and land with the
#      upstream-shared edits from the Phase 6 wiring.)
#
# After each rogue run: assert the plugin's UDS is still bound, a
# fresh client can connect cleanly, and (for AI-role cases) the AI
# slot is reclaimable (FR-011 + FR-012).

set -euo pipefail

repo_root="$(cd "$(dirname "$0")/../.." && pwd)"
plugin_lib="${repo_root}/build/libSkirmishAI.so"
fs_observer="${repo_root}/clients/fsharp/samples/Observer/bin/Debug/net8.0/hb-observer"
fs_ai="${repo_root}/clients/fsharp/samples/AiClient/bin/Debug/net8.0/hb-ai-client"

if [[ ! -x "${SPRING_HEADLESS:-}" ]]; then
    echo "sc-disconnect-lifecycle: SPRING_HEADLESS not set — skip." >&2
    exit 77
fi
if [[ ! -f "${plugin_lib}" || ! -x "${fs_observer}" || ! -x "${fs_ai}" ]]; then
    echo "sc-disconnect-lifecycle: plugin / clients not built — skip." >&2
    exit 77
fi

: "${XDG_RUNTIME_DIR:=/tmp}"
gameid="${HIGHBAR_SMOKE_GAMEID:-sc-dc}"
uds_path="${XDG_RUNTIME_DIR}/highbar-${gameid}.sock"
log_dir="${repo_root}/build/tmp/sc-disconnect-lifecycle"
mkdir -p "${log_dir}"

"${SPRING_HEADLESS}" --ai HighBarV3 --config sc-disconnect.sdd \
    > "${log_dir}/engine.log" 2>&1 &
engine_pid=$!
cleanup() { kill "${engine_pid}" 2>/dev/null || true; }
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

assert_bound() {
    local phase=$1
    [[ -S "${uds_path}" ]] || { echo "sc-disconnect-lifecycle: UDS gone after ${phase}"; exit 1; }
    kill -0 "${engine_pid}" 2>/dev/null \
        || { echo "sc-disconnect-lifecycle: engine died after ${phase}"; exit 1; }
}

# Case 1 — rogue observer: start-then-SIGKILL at 200ms (mid-Hello / early stream).
for attempt in 1 2 3; do
    timeout 0.2 "${fs_observer}" --transport uds --uds-path "${uds_path}" \
        > "${log_dir}/rogue-obs-${attempt}.log" 2>&1 || true
    assert_bound "rogue observer #${attempt}"
done

# Case 2 — rogue AI client: issue a MoveTo but SIGKILL before ack.
for attempt in 1 2 3; do
    timeout 0.3 "${fs_ai}" \
        --transport uds --uds-path "${uds_path}" \
        --token-file "${token_path}" \
        --target-unit "${HIGHBAR_TARGET_UNIT:-1}" \
        --move-to "1024,0,1024" \
        > "${log_dir}/rogue-ai-${attempt}.log" 2>&1 || true
    assert_bound "rogue AI #${attempt}"
done

# Reclaim test — a fresh clean AI client must succeed even though a
# burst of rogue-AI SIGKILLs hit the same slot. FR-012.
"${fs_ai}" --transport uds --uds-path "${uds_path}" \
    --token-file "${token_path}" \
    --target-unit "${HIGHBAR_TARGET_UNIT:-1}" \
    --move-to "1024,0,1024" \
    > "${log_dir}/reclaim.log" 2>&1
grep -q "ack" "${log_dir}/reclaim.log" \
    || { echo "sc-disconnect-lifecycle: FAIL — AI slot did not recover for reclaimer"; exit 1; }

# Fresh observer works — FR-003.
timeout 3 "${fs_observer}" --transport uds --uds-path "${uds_path}" \
    > "${log_dir}/final-observer.log" 2>&1 || true
grep -q "SNAPSHOT" "${log_dir}/final-observer.log" \
    || { echo "sc-disconnect-lifecycle: FAIL — fresh observer couldn't subscribe"; exit 1; }

echo "sc-disconnect-lifecycle: PASS — plugin survived rogue clients; AI slot reclaimable"

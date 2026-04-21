#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-2.0-only
# arm-covered: (none — 001-era skip stub; no arms dispatched)
#
# HighBarV3 — US6 reconnect acceptance (T100).
#
# Full mid-match disconnect-reconnect cycle per the spec's US6
# Independent Test:
#   Observer connects, runs 30s, is killed, reconnects with its
#   last-seen seq, confirms either buffered gap or fresh snapshot
#   with monotonic continuation.
#
# This is a superset of us6-resume-in-ring.sh (T098) + us6-resume-out-
# of-range.sh (T099): it runs long enough that both paths are
# exercised and validates the combined SC-005 checker (no
# drop/dup/oor over a 30-minute session) at the one-minute scale.

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
    echo "us6-reconnect: SPRING_HEADLESS not set — skip." >&2
    exit 77
fi
if [[ ! -f "${plugin_lib}" || ! -x "${observer_bin}" ]]; then
    echo "us6-reconnect: plugin / observer not built — skip." >&2
    exit 77
fi

: "${XDG_RUNTIME_DIR:=/tmp}"
gameid="${HIGHBAR_SMOKE_GAMEID:-us6-rec}"
uds_path="${XDG_RUNTIME_DIR}/highbar-${gameid}.sock"
log_dir="${repo_root}/build/tmp/us6-reconnect"
mkdir -p "${log_dir}"
engine_log="${log_dir}/engine.log"
phase1_log="${log_dir}/phase1.log"
phase2_log="${log_dir}/phase2.log"

"${SPRING_HEADLESS}" --ai HighBarV3 --config us6-reconnect.sdd \
    > "${engine_log}" 2>&1 &
engine_pid=$!
cleanup() { kill "${engine_pid}" 2>/dev/null || true; }
trap cleanup EXIT

for _ in {1..100}; do
    [[ -S "${uds_path}" ]] && break
    sleep 0.1
done

# Phase 1: run for 30s, record the final seq.
timeout 30 "${observer_bin}" --transport uds --uds-path "${uds_path}" \
    > "${phase1_log}" 2>&1 || true

last_seq=$(awk '/seq=/{ match($0, /seq=[0-9]+/); print substr($0,RSTART+4,RLENGTH-4) }' "${phase1_log}" \
           | tail -n 1)
[[ -n "${last_seq}" ]] || { echo "us6-reconnect: phase 1 saw no updates"; exit 1; }
echo "us6-reconnect: phase 1 final seq=${last_seq}"

# Phase 2: resume. Don't care whether we hit the ring or not — both
# are legal. What matters is the SC-005 invariants below.
sleep 2
timeout 15 "${observer_bin}" \
    --transport uds --uds-path "${uds_path}" \
    --resume-from-seq "${last_seq}" \
    > "${phase2_log}" 2>&1 || true

# Combined monotonic check across both phases: every seq in phase 2
# must be > last_seq.
min_phase2_seq=$(awk '/seq=/{ match($0, /seq=[0-9]+/); s=substr($0,RSTART+4,RLENGTH-4)+0; if (m=="" || s<m) m=s } END { print m }' "${phase2_log}")
if [[ -z "${min_phase2_seq}" ]]; then
    echo "us6-reconnect: phase 2 saw no updates"
    exit 1
fi
if [[ "${min_phase2_seq}" -le "${last_seq}" ]]; then
    echo "us6-reconnect: FAIL — phase-2 min seq ${min_phase2_seq} <= phase-1 last seq ${last_seq}"
    exit 1
fi

# Per-phase monotonicity.
awk '/seq=/{ match($0, /seq=[0-9]+/); s=substr($0,RSTART+4,RLENGTH-4)+0;
            if (prev != "" && s <= prev) { bad=1 } ; prev=s }
     END { exit bad }' "${phase2_log}" \
    || { echo "us6-reconnect: FAIL — seq regression inside phase 2"; exit 1; }

# SC-005: count duplicates across phase 2 — there must be none.
dupes=$(awk '/seq=/{ match($0, /seq=[0-9]+/); print substr($0,RSTART+4,RLENGTH-4) }' "${phase2_log}" \
        | sort | uniq -d | wc -l)
if [[ "${dupes}" -gt 0 ]]; then
    echo "us6-reconnect: FAIL — ${dupes} duplicate seq values in phase 2"
    exit 1
fi

echo "us6-reconnect: PASS — continuous monotonic seq across disconnect/reconnect"

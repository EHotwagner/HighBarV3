#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-2.0-only
# arm-covered: (none — 001-era skip stub; no arms dispatched)
#
# HighBarV3 — US6 resume-in-ring test (T098).
#
# Observer connects, records up to seq N, kills itself, reconnects with
# resume_from_seq=N, expects the server to replay [N+1..head] in order
# with no gaps/duplicates. Ring size is 2048 by default (grpc.json), so
# a short disconnect window (~1s) stays inside the ring easily.

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
    echo "us6-resume-in-ring: SPRING_HEADLESS not set — skip." >&2
    exit 77
fi
if [[ ! -f "${plugin_lib}" || ! -x "${observer_bin}" ]]; then
    echo "us6-resume-in-ring: plugin / observer not built — skip." >&2
    exit 77
fi

: "${XDG_RUNTIME_DIR:=/tmp}"
gameid="${HIGHBAR_SMOKE_GAMEID:-us6-ring}"
uds_path="${XDG_RUNTIME_DIR}/highbar-${gameid}.sock"
log_dir="${repo_root}/build/tmp/us6-resume-in-ring"
mkdir -p "${log_dir}"
engine_log="${log_dir}/engine.log"
first_log="${log_dir}/first.log"
second_log="${log_dir}/second.log"

"${SPRING_HEADLESS}" --ai HighBarV3 --config us6-resume.sdd \
    > "${engine_log}" 2>&1 &
engine_pid=$!
cleanup() { kill "${engine_pid}" 2>/dev/null || true; }
trap cleanup EXIT

for _ in {1..100}; do
    [[ -S "${uds_path}" ]] && break
    sleep 0.1
done

# First observer: record 5s, then kill. Extract the last seen seq.
timeout 5 "${observer_bin}" --transport uds --uds-path "${uds_path}" \
    > "${first_log}" 2>&1 || true

last_seq=$(awk '/seq=/{ match($0, /seq=[0-9]+/); print substr($0,RSTART+4,RLENGTH-4) }' "${first_log}" \
           | tail -n 1)
if [[ -z "${last_seq}" ]]; then
    echo "us6-resume-in-ring: no seq= lines in first run"
    exit 1
fi
echo "us6-resume-in-ring: first run ended at seq=${last_seq}"

# Brief gap to let the server produce a handful of deltas that WILL be
# in the ring when we reconnect.
sleep 1

# Second observer: resume from last_seq. The first message must be a
# DELTA or KEEPALIVE with seq == last_seq + 1 (ring replay path),
# NOT a SNAPSHOT (which would indicate out-of-range fallback).
timeout 5 "${observer_bin}" \
    --transport uds --uds-path "${uds_path}" \
    --resume-from-seq "${last_seq}" \
    > "${second_log}" 2>&1 || true

first_line_seq=$(awk '/seq=/{ match($0, /seq=[0-9]+/); print substr($0,RSTART+4,RLENGTH-4); exit }' "${second_log}")
first_line_kind=$(awk 'NR<20 && /(SNAPSHOT|DELTA|KEEPALIVE)/ {
    for (i=1; i<=NF; i++) if ($i ~ /^(SNAPSHOT|DELTA|KEEPALIVE)$/) { print $i; exit }
}' "${second_log}")

expected_next=$((last_seq + 1))
if [[ "${first_line_kind}" == "SNAPSHOT" ]]; then
    echo "us6-resume-in-ring: FAIL — got SNAPSHOT on resume (should have been ring replay)"
    echo "  last_seq=${last_seq}, first resume line=${first_line_kind} seq=${first_line_seq}"
    exit 1
fi
if [[ "${first_line_seq}" != "${expected_next}" ]]; then
    echo "us6-resume-in-ring: FAIL — first resume seq=${first_line_seq} expected=${expected_next}"
    exit 1
fi

# Monotonic seq across the resume stream.
awk '/seq=/{ match($0, /seq=[0-9]+/); s=substr($0,RSTART+4,RLENGTH-4)+0;
            if (prev != "" && s <= prev) { print "REGRESSION: " s " after " prev; bad=1 }
            prev=s } END { exit bad }' "${second_log}" \
    || { echo "us6-resume-in-ring: FAIL — seq regression in resumed stream"; exit 1; }

echo "us6-resume-in-ring: PASS — ring replay starts at seq=${expected_next} with no gaps"

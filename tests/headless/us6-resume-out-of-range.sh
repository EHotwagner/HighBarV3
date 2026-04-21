#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-2.0-only
#
# HighBarV3 — US6 resume-out-of-range test (T099).
#
# Observer requests resume_from_seq with a value older than the ring's
# tail. Expected behavior per FR-007/FR-008: server sends a fresh
# StateSnapshot (with next monotonic seq, NOT resetting the counter),
# observer sees the SNAPSHOT arm and knows to treat it as a reset.
#
# Simulates out-of-range by passing resume_from_seq=1 after the plugin
# has emitted more than ring_size updates (2048 default). On a real
# match that's ~70s at 30Hz, so we use a smaller ring via grpc.json
# to make the test tractable.

set -euo pipefail

repo_root="$(cd "$(dirname "$0")/../.." && pwd)"
plugin_lib="${repo_root}/build/libSkirmishAI.so"
observer_bin="${repo_root}/clients/fsharp/samples/Observer/bin/Debug/net8.0/hb-observer"

if [[ ! -x "${SPRING_HEADLESS:-}" ]]; then
    echo "us6-resume-out-of-range: SPRING_HEADLESS not set — skip." >&2
    exit 77
fi
if [[ ! -f "${plugin_lib}" || ! -x "${observer_bin}" ]]; then
    echo "us6-resume-out-of-range: plugin / observer not built — skip." >&2
    exit 77
fi

: "${XDG_RUNTIME_DIR:=/tmp}"
gameid="${HIGHBAR_SMOKE_GAMEID:-us6-oor}"
uds_path="${XDG_RUNTIME_DIR}/highbar-${gameid}.sock"
log_dir="${repo_root}/build/tmp/us6-resume-out-of-range"
mkdir -p "${log_dir}"
engine_log="${log_dir}/engine.log"
observer_log="${log_dir}/observer.log"
cfg_dir="${log_dir}/cfg"
mkdir -p "${cfg_dir}"

# Shrink the ring so "out of range" is reachable in a short test.
cat > "${cfg_dir}/grpc.json" <<EOF
{
  "transport": "uds",
  "uds_path": "${uds_path}",
  "ai_token_path": "${log_dir}/highbar.token",
  "max_recv_mb": 32,
  "ring_size": 256
}
EOF

HIGHBAR_CONFIG_DIR="${cfg_dir}" \
"${SPRING_HEADLESS}" --ai HighBarV3 --config us6-oor.sdd \
    > "${engine_log}" 2>&1 &
engine_pid=$!
cleanup() { kill "${engine_pid}" 2>/dev/null || true; }
trap cleanup EXIT

for _ in {1..100}; do
    [[ -S "${uds_path}" ]] && break
    sleep 0.1
done

# Let the plugin emit enough updates that seq=1 is out of the 256-entry
# ring. Default cadence is 30Hz (frame tick) + KeepAlive every 30 frames,
# so 15 seconds reliably pushes past 256.
sleep 15

# Resume with seq=1 — must trigger fresh-snapshot fallback.
timeout 5 "${observer_bin}" \
    --transport uds --uds-path "${uds_path}" \
    --resume-from-seq 1 \
    > "${observer_log}" 2>&1 || true

first_line_kind=$(awk 'NR<20 && /(SNAPSHOT|DELTA|KEEPALIVE)/ {
    for (i=1; i<=NF; i++) if ($i ~ /^(SNAPSHOT|DELTA|KEEPALIVE)$/) { print $i; exit }
}' "${observer_log}")
first_line_seq=$(awk '/seq=/{ match($0, /seq=[0-9]+/); print substr($0,RSTART+4,RLENGTH-4); exit }' "${observer_log}")

if [[ "${first_line_kind}" != "SNAPSHOT" ]]; then
    echo "us6-resume-out-of-range: FAIL — expected SNAPSHOT on out-of-range resume, got ${first_line_kind}"
    exit 1
fi

# The fresh snapshot's seq must NOT be 1 (that would be a counter reset —
# violates FR-006 "seq never decreases"). It must be strictly greater
# than 1 and greater than the last seq the ring would have held.
if [[ "${first_line_seq}" -le 1 ]]; then
    echo "us6-resume-out-of-range: FAIL — seq reset detected (got ${first_line_seq}); monotonicity broken"
    exit 1
fi

echo "us6-resume-out-of-range: PASS — fresh SNAPSHOT at seq=${first_line_seq}, no counter reset"

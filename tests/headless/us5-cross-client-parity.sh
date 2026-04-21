#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-2.0-only
#
# HighBarV3 — US5 cross-client parity (T093).
#
# F# and Python observers attach to the same spring-headless match for
# 60s. Both record their StreamState output. Assertion: byte-equality
# on the canonical event shape (SC-004).
#
# Canonical shape ≠ raw line-by-line match — the two clients format
# their summary lines differently. We normalize to a common tuple per
# update (seq, payload_case, event_count) and diff that, which is
# what SC-004 actually guarantees: the same server-side sequence of
# updates lands on both clients.

set -euo pipefail

repo_root="$(cd "$(dirname "$0")/../.." && pwd)"
plugin_lib="${repo_root}/build/libSkirmishAI.so"
fsharp_bin="${repo_root}/clients/fsharp/samples/Observer/bin/Debug/net8.0/hb-observer"
python_venv="${repo_root}/clients/python/.venv"

if [[ ! -x "${SPRING_HEADLESS:-}" ]]; then
    echo "us5-cross-client-parity: SPRING_HEADLESS not set — skip." >&2
    exit 77
fi
if [[ ! -f "${plugin_lib}" || ! -x "${fsharp_bin}" ]]; then
    echo "us5-cross-client-parity: plugin / F# observer not built — skip." >&2
    exit 77
fi
if [[ ! -d "${python_venv}" ]]; then
    echo "us5-cross-client-parity: Python venv not set up at ${python_venv} — skip." >&2
    echo "  cd clients/python && python -m venv .venv && .venv/bin/pip install -e '.[dev]'" >&2
    exit 77
fi

: "${XDG_RUNTIME_DIR:=/tmp}"
gameid="${HIGHBAR_SMOKE_GAMEID:-us5-parity}"
uds_path="${XDG_RUNTIME_DIR}/highbar-${gameid}.sock"
log_dir="${repo_root}/build/tmp/us5-cross-client-parity"
mkdir -p "${log_dir}"
engine_log="${log_dir}/engine.log"
fs_log="${log_dir}/fsharp.log"
py_log="${log_dir}/python.log"
fs_norm="${log_dir}/fsharp.tuples"
py_norm="${log_dir}/python.tuples"

"${SPRING_HEADLESS}" --ai HighBarV3 --config us5-parity.sdd \
    > "${engine_log}" 2>&1 &
engine_pid=$!
cleanup() { kill "${engine_pid}" 2>/dev/null || true; }
trap cleanup EXIT

for _ in {1..100}; do
    [[ -S "${uds_path}" ]] && break
    sleep 0.1
done
[[ -S "${uds_path}" ]] || { echo "us5-cross-client-parity: UDS not bound"; exit 1; }

# Run both clients concurrently for 60s.
timeout 60 "${fsharp_bin}" --transport uds --uds-path "${uds_path}" \
    > "${fs_log}" 2>&1 &
fs_pid=$!
timeout 60 "${python_venv}/bin/python" -m highbar_client.samples.observer \
    --transport uds --uds-path "${uds_path}" \
    > "${py_log}" 2>&1 &
py_pid=$!
wait "${fs_pid}" "${py_pid}" 2>/dev/null || true

# Normalize both to (seq, kind, count) tuples. Each observer prints a
# line per update; the formats differ, so match on the common fields.
fs_to_tuple() {
    # F# line shape: "seq=12 frame=34 SNAPSHOT own=5 enemies=2"
    #                "seq=12 frame=34 DELTA events=3"
    #                "seq=12 frame=34 KEEPALIVE"
    awk '
      /SNAPSHOT/ { match($0, /seq=[0-9]+/); s=substr($0,RSTART+4,RLENGTH-4); printf "%s snapshot\n", s; next }
      /DELTA/    { match($0, /seq=[0-9]+/); s=substr($0,RSTART+4,RLENGTH-4);
                   match($0, /events=[0-9]+/); n=substr($0,RSTART+7,RLENGTH-7);
                   printf "%s delta %s\n", s, n; next }
      /KEEPALIVE/{ match($0, /seq=[0-9]+/); s=substr($0,RSTART+4,RLENGTH-4); printf "%s keepalive\n", s; next }
    ' "$1"
}
py_to_tuple() {
    # Python line shape is identical to F# by construction — samples/observer.py
    # prints the same "seq=N frame=N CASE ..." format.
    fs_to_tuple "$1"
}

fs_to_tuple "${fs_log}" | sort -n > "${fs_norm}"
py_to_tuple "${py_log}" | sort -n > "${py_norm}"

if diff "${fs_norm}" "${py_norm}" > "${log_dir}/diff.txt"; then
    echo "us5-cross-client-parity: PASS — F# and Python clients saw the same stream"
    exit 0
else
    echo "us5-cross-client-parity: FAIL — divergence between F# and Python streams"
    head -n 20 "${log_dir}/diff.txt" >&2
    exit 1
fi

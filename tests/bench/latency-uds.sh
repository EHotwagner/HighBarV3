#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-2.0-only
#
# HighBarV3 — UDS latency gate (T072).
#
# Constitution V gate: p99 round-trip UnitDamaged → F# OnEvent must
# stay ≤ 500µs on UDS over a 30-second sample window (SC-002).
#
# Drives the F# bench binary built from clients/fsharp/bench/Latency/.
# Exits:
#   0  — bench ran and p99 within budget.
#   1  — bench ran but p99 exceeded budget (Constitution V fail).
#   77 — prerequisites missing (skip).

set -euo pipefail

repo_root="$(cd "$(dirname "$0")/../.." && pwd)"
plugin_lib="${repo_root}/build/libSkirmishAI.so"
bench_bin="${repo_root}/clients/fsharp/bench/Latency/bin/Release/net8.0/hb-latency-bench"

if [[ ! -x "${SPRING_HEADLESS:-}" ]]; then
    echo "latency-uds: SPRING_HEADLESS not set/executable — skip." >&2
    exit 77
fi
if [[ ! -f "${plugin_lib}" ]]; then
    echo "latency-uds: plugin .so not built — skip." >&2
    exit 77
fi
if [[ ! -x "${bench_bin}" ]]; then
    echo "latency-uds: F# bench not built at ${bench_bin} — skip." >&2
    echo "  cd clients/fsharp/bench/Latency && dotnet build -c Release" >&2
    exit 77
fi

: "${XDG_RUNTIME_DIR:=/tmp}"
gameid="${HIGHBAR_BENCH_GAMEID:-bench-uds}"
uds_path="${XDG_RUNTIME_DIR}/highbar-${gameid}.sock"
log_dir="${repo_root}/build/tmp/latency-uds"
mkdir -p "${log_dir}"
engine_log="${log_dir}/engine.log"
bench_log="${log_dir}/bench.log"
rm -f "${uds_path}" "${engine_log}" "${bench_log}"

"${SPRING_HEADLESS}" --ai HighBarV3 --config bench-uds.sdd \
    > "${engine_log}" 2>&1 &
engine_pid=$!
cleanup() { kill "${engine_pid}" 2>/dev/null || true; }
trap cleanup EXIT

for i in {1..100}; do
    [[ -S "${uds_path}" ]] && break
    sleep 0.1
done
[[ -S "${uds_path}" ]] || { echo "latency-uds: UDS not bound"; exit 1; }

# The bench exits 0 within budget, 1 on budget breach, 77 on unreachable.
set +e
"${bench_bin}" --transport uds --uds-path "${uds_path}" \
    --duration-sec 30 --samples 1000 \
    > "${bench_log}" 2>&1
rc=$?
set -e

cat "${bench_log}"

case ${rc} in
    0)  echo "latency-uds: PASS — p99 within 500µs budget" ;;
    1)  echo "latency-uds: FAIL — Constitution V breach"; exit 1 ;;
    77) echo "latency-uds: SKIP — bench reported unreachable"; exit 77 ;;
    *)  echo "latency-uds: unexpected exit ${rc}"; exit "${rc}" ;;
esac

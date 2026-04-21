#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-2.0-only
#
# HighBarV3 — loopback TCP latency gate (T076).
#
# Constitution V gate: p99 round-trip UnitDamaged → F# OnEvent must
# stay ≤ 1.5ms on loopback TCP over a 30-second sample (SC-002).
#
# Exit codes: 0 pass · 1 budget breach · 77 skip (prereqs missing).

set -euo pipefail

repo_root="$(cd "$(dirname "$0")/../.." && pwd)"
plugin_lib="${repo_root}/build/libSkirmishAI.so"
bench_bin="${repo_root}/clients/fsharp/bench/Latency/bin/Release/net8.0/hb-latency-bench"

if [[ ! -x "${SPRING_HEADLESS:-}" ]]; then
    echo "latency-tcp: SPRING_HEADLESS not set — skip." >&2
    exit 77
fi
if [[ ! -f "${plugin_lib}" ]]; then
    echo "latency-tcp: plugin .so not built — skip." >&2
    exit 77
fi
if [[ ! -x "${bench_bin}" ]]; then
    echo "latency-tcp: F# bench not built — skip." >&2
    echo "  cd clients/fsharp/bench/Latency && dotnet build -c Release" >&2
    exit 77
fi

: "${XDG_RUNTIME_DIR:=/tmp}"
tcp_bind="${HIGHBAR_TCP_BIND:-127.0.0.1:50511}"
log_dir="${repo_root}/build/tmp/latency-tcp"
mkdir -p "${log_dir}"
engine_log="${log_dir}/engine.log"
bench_log="${log_dir}/bench.log"
cfg_dir="${log_dir}/cfg"
mkdir -p "${cfg_dir}"
cat > "${cfg_dir}/grpc.json" <<EOF
{
  "transport": "tcp",
  "tcp_bind": "${tcp_bind}",
  "ai_token_path": "${log_dir}/highbar.token",
  "max_recv_mb": 32,
  "ring_size": 2048
}
EOF

HIGHBAR_CONFIG_DIR="${cfg_dir}" \
"${SPRING_HEADLESS}" --ai HighBarV3 --config bench-tcp.sdd \
    > "${engine_log}" 2>&1 &
engine_pid=$!
cleanup() { kill "${engine_pid}" 2>/dev/null || true; }
trap cleanup EXIT

for _ in {1..100}; do
    if (exec 3<>"/dev/tcp/${tcp_bind%:*}/${tcp_bind##*:}") 2>/dev/null; then
        exec 3<&-; exec 3>&-; break
    fi
    sleep 0.1
done

set +e
"${bench_bin}" --transport tcp --tcp-bind "${tcp_bind}" \
    --duration-sec 30 --samples 1000 \
    > "${bench_log}" 2>&1
rc=$?
set -e

cat "${bench_log}"

case ${rc} in
    0)  echo "latency-tcp: PASS — p99 within 1.5ms budget" ;;
    1)  echo "latency-tcp: FAIL — Constitution V breach"; exit 1 ;;
    77) echo "latency-tcp: SKIP — bench reported unreachable"; exit 77 ;;
    *)  echo "latency-tcp: unexpected exit ${rc}"; exit "${rc}" ;;
esac

#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-2.0-only
#
# HighBarV3 — UDS latency CI gate (T072).
#
# Runs the F# latency microbench against a live plugin, enforcing the
# Constitution V budget: p99 round-trip ≤ 500µs on Unix-domain socket
# transport. Exits:
#   0  — budget met
#   1  — budget exceeded (or other failure)
#   77 — skip (plugin not running / binaries missing)

set -euo pipefail

repo_root="$(cd "$(dirname "$0")/../.." && pwd)"
bench_bin="${repo_root}/clients/fsharp/bench/Latency/bin/Release/net8.0/hb-latency"

: "${XDG_RUNTIME_DIR:=/tmp}"
uds_path="${UDS_PATH:-$XDG_RUNTIME_DIR/highbar-1.sock}"

if [[ ! -x "${bench_bin}" ]]; then
    echo "latency-uds: bench not built at ${bench_bin} — skip." >&2
    echo "  cd clients/fsharp/bench/Latency && dotnet build -c Release" >&2
    exit 77
fi
if [[ ! -S "${uds_path}" ]]; then
    echo "latency-uds: plugin socket not listening at ${uds_path} — skip." >&2
    exit 77
fi

# hb-latency exits 77 itself if the initial probe Hello fails; we
# pass through that exit code so CI skips uniformly.
"${bench_bin}" \
    --transport uds \
    --uds-path "${uds_path}" \
    --samples "${LATENCY_SAMPLES:-5000}" \
    --warmup 500 \
    --gate-p99-us "${LATENCY_P99_GATE_US:-500}"

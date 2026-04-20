#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-2.0-only
#
# HighBarV3 — loopback TCP latency CI gate (T076).
#
# Constitution V budget: p99 round-trip ≤ 1.5ms on loopback TCP.
# Exits:
#   0  — budget met
#   1  — budget exceeded (or other failure)
#   77 — skip (plugin not listening on TCP / binaries missing)

set -euo pipefail

repo_root="$(cd "$(dirname "$0")/../.." && pwd)"
bench_bin="${repo_root}/clients/fsharp/bench/Latency/bin/Release/net8.0/hb-latency"
tcp_bind="${TCP_BIND:-127.0.0.1:50511}"

if [[ ! -x "${bench_bin}" ]]; then
    echo "latency-tcp: bench not built at ${bench_bin} — skip." >&2
    echo "  cd clients/fsharp/bench/Latency && dotnet build -c Release" >&2
    exit 77
fi

# hb-latency's probe Hello returns exit 77 on connection failure; pass
# through so CI skips when the TCP port isn't listening.
"${bench_bin}" \
    --transport tcp \
    --tcp-bind "${tcp_bind}" \
    --samples "${LATENCY_SAMPLES:-5000}" \
    --warmup 500 \
    --gate-p99-us "${LATENCY_P99_GATE_US:-1500}"

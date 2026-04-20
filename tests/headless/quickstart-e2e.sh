#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-2.0-only
#
# HighBarV3 — full-quickstart end-to-end run (T107).
#
# Walks through every section of specs/001-grpc-gateway/quickstart.md
# (§1 → §12) against a fresh checkout. Final validation gate before
# cutting a release. Exit 77 until T104 launch helper lands.

set -euo pipefail

repo_root="$(cd "$(dirname "$0")/../.." && pwd)"

if [[ ! -x "${SPRING_HEADLESS:-}" ]]; then
    echo "quickstart-e2e: SPRING_HEADLESS not set — skip." >&2
    exit 77
fi

echo "quickstart-e2e: launch helper not wired (T104) — skip." >&2
# Shape when T104 lands — sequential gating of the quickstart path:
#   §1 build plugin
#   §2 verify symbol visibility
#   §3 render data/config/grpc.json from template
#   §4 launch engine with plugin; wait for UDS bind
#   §5 connect hb-observer; assert StateSnapshot + 5 seconds of deltas
#   §6 connect hb-ai; MoveTo a live unit; assert ack.accepted=1
#   §7 connect Python observer; assert matching snapshot
#   §8 kill hb-observer; reconnect with --resume-from-seq; assert no gap
#   §9 toggle grpc.json → tcp; restart; repeat §5–§8 over loopback TCP
#   §10 set enable_builtin=false; verify only external commands dispatched
#   §11 run latency benches (UDS + TCP); assert gates met
#   §12 run 30-minute soak; assert SC-005 / SC-006 pass
exit 77

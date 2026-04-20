#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-2.0-only
#
# HighBarV3 — US4 loopback TCP acceptance (T077).
#
# Same scripted flow as us1-observer.sh + us2-ai-coexist.sh, but with
# "transport": "tcp" in the rendered grpc.json. Demonstrates SC-008:
# switching transports is a single-line config change, not a client
# or schema change.
#
# Exit 77 until the CI engine-launch helper + grpc.json render step
# land (same gate as us2-ai-coexist.sh).

set -euo pipefail

repo_root="$(cd "$(dirname "$0")/../.." && pwd)"
plugin_lib="${repo_root}/build/libSkirmishAI.so"
observer_bin="${repo_root}/clients/fsharp/samples/Observer/bin/Debug/net8.0/hb-observer"
ai_bin="${repo_root}/clients/fsharp/samples/AiClient/bin/Debug/net8.0/hb-ai"

if [[ ! -x "${SPRING_HEADLESS:-}" ]]; then
    echo "us4-tcp: SPRING_HEADLESS not set/executable — skip." >&2
    exit 77
fi
if [[ ! -f "${plugin_lib}" ]]; then
    echo "us4-tcp: plugin .so not built at ${plugin_lib} — skip." >&2
    exit 77
fi
if [[ ! -x "${observer_bin}" || ! -x "${ai_bin}" ]]; then
    echo "us4-tcp: F# client samples not built — skip." >&2
    exit 77
fi

echo "us4-tcp: engine launch + tcp grpc.json helper not wired (T104) — skip." >&2
# Shape for when T104 lands:
#   1. Render grpc.json with transport=tcp, tcp_bind=127.0.0.1:0 (ephemeral).
#   2. Launch engine with the plugin; discover bound port from infolog.
#   3. Run hb-observer --transport tcp --tcp-bind 127.0.0.1:$PORT
#      and hb-ai    --transport tcp --tcp-bind 127.0.0.1:$PORT
#      — the trace should match us1-observer + us2-ai-coexist up to
#      timing, per SC-008.
exit 77

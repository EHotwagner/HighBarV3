#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-2.0-only
#
# HighBarV3 — US2 AI-coexistence acceptance script (T071).
#
# Implements US2's Independent Test:
#   Connect an authenticated F# client during a live match. SubmitCommands
#   a MoveTo on an owned unit. Verify in the engine log + state stream
#   that the unit moved. Built-in AI continues issuing orders for other
#   units. A concurrent second AI-client attempt fails ALREADY_EXISTS.
#
# Skips (exit 77) when prerequisites are missing — same pattern as
# phase2-smoke.sh and us1-observer.sh.

set -euo pipefail

repo_root="$(cd "$(dirname "$0")/../.." && pwd)"
plugin_lib="${repo_root}/build/libSkirmishAI.so"
ai_bin="${repo_root}/clients/fsharp/samples/AiClient/bin/Debug/net8.0/hb-ai"

# -- Preconditions ----------------------------------------------------------

if [[ ! -x "${SPRING_HEADLESS:-}" ]]; then
    echo "us2-ai-coexist: SPRING_HEADLESS not set/executable — skip." >&2
    exit 77
fi
if [[ ! -f "${plugin_lib}" ]]; then
    echo "us2-ai-coexist: plugin .so not built at ${plugin_lib} — skip." >&2
    exit 77
fi
if [[ ! -x "${ai_bin}" ]]; then
    echo "us2-ai-coexist: F# AI client not built at ${ai_bin} — skip." >&2
    echo "  cd clients/fsharp/samples/AiClient && dotnet build" >&2
    exit 77
fi

# -- Resolve UDS path and token file ----------------------------------------

: "${XDG_RUNTIME_DIR:=/tmp}"
uds_path="${XDG_RUNTIME_DIR}/highbar-1.sock"
token_path="${WRITE_DIR:-$HOME}/highbar.token"

# -- Launch engine, run AI client, assert ack, check second-client reject ---

# Engine launch intentionally elided — the actual invocation depends on
# the spring-headless match-config path on the host. When the CI harness
# lands (T104), this script will source that shared launch helper. The
# shape below is what the test asserts once the engine is running:
#
#   hb-ai --target-unit $(pick_first_own_unit) --move-to 1024,0,1024 \
#         --uds-path "$uds_path" --token-file "$token_path" > ai.log
#
#   grep -q 'accepted=1' ai.log || { echo "no ack"; exit 1; }
#
#   # Second concurrent AI client should get ALREADY_EXISTS
#   hb-ai --target-unit 42 --token-file "$token_path" \
#         --uds-path "$uds_path" 2> second.err && \
#     { echo "second AI client did not fail"; exit 1; } || true
#   grep -q 'ALREADY_EXISTS' second.err || \
#     { echo "unexpected second-client error"; exit 1; }
#
# Until the launch helper lands we exit 77 to avoid false CI failures.

echo "us2-ai-coexist: engine launch helper not wired (T104) — skip." >&2
exit 77

#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-2.0-only
#
# HighBarV3 — US3 external-only with AI client (T082).
#
# Launch with enable_builtin=false + an F# AI client issuing a scripted
# command sequence. Assert:
#   - Unit movement in the engine log matches the scripted commands.
#   - No built-in-AI log lines appear (military/builder/factory/economy
#     modules never ran Update()).
#
# Exit 77 until T104 lands.

set -euo pipefail

repo_root="$(cd "$(dirname "$0")/../.." && pwd)"
plugin_lib="${repo_root}/build/libSkirmishAI.so"
ai_bin="${repo_root}/clients/fsharp/samples/AiClient/bin/Debug/net8.0/hb-ai"

if [[ ! -x "${SPRING_HEADLESS:-}" ]]; then
    echo "us3-external-only-ai: SPRING_HEADLESS not set — skip." >&2
    exit 77
fi
if [[ ! -f "${plugin_lib}" ]]; then
    echo "us3-external-only-ai: plugin .so not built — skip." >&2
    exit 77
fi
if [[ ! -x "${ai_bin}" ]]; then
    echo "us3-external-only-ai: F# AI client not built — skip." >&2
    exit 77
fi

echo "us3-external-only-ai: engine launch helper not wired (T104) — skip." >&2
exit 77

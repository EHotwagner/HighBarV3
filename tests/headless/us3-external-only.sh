#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-2.0-only
#
# HighBarV3 — US3 external-only survivability (T081).
#
# Launch with enable_builtin=false and NO external client. The AI
# slot must stay alive for 60s without crashing (SC-007, FR-017).
# The plugin's delta stream is still flushing (empty deltas + keepalives);
# the built-in decision modules are not registered so no Cmd* orders
# fire from the AI side.
#
# Exit 77 until the CI engine-launch helper (T104) lands.

set -euo pipefail

repo_root="$(cd "$(dirname "$0")/../.." && pwd)"
plugin_lib="${repo_root}/build/libSkirmishAI.so"

if [[ ! -x "${SPRING_HEADLESS:-}" ]]; then
    echo "us3-external-only: SPRING_HEADLESS not set — skip." >&2
    exit 77
fi
if [[ ! -f "${plugin_lib}" ]]; then
    echo "us3-external-only: plugin .so not built — skip." >&2
    exit 77
fi

echo "us3-external-only: engine launch helper not wired (T104) — skip." >&2
# Shape when T104 lands:
#   1. Write a start-script or Lua override setting AIOptions.enable_builtin=false.
#   2. Launch spring-headless with the plugin; no client connects.
#   3. Watch plugin infolog for "fail-closed" lines; absence + process
#      staying alive for 60s == pass.
#   4. grep infolog for any built-in-AI decision log lines — presence == fail.
exit 77

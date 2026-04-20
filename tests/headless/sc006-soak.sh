#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-2.0-only
#
# HighBarV3 — 30-minute soak for SC-006 (T102).
#
# Full match (or as close as the headless harness allows) with:
#   - F# observer (read-only)
#   - F# AI client (one AI slot, drives a small scripted loop)
#   - Python observer (cross-client-parity witness)
#
# SC-005 invariant checker asserts no dropped / duplicated /
# out-of-order state messages over the 30-minute window; SC-006
# requires ≥95% of sessions to meet this bar — CI runs this script
# 20+ times and counts green.
#
# Exit 77 until T104 lands the launch helper.

set -euo pipefail

repo_root="$(cd "$(dirname "$0")/../.." && pwd)"
plugin_lib="${repo_root}/build/libSkirmishAI.so"

if [[ ! -x "${SPRING_HEADLESS:-}" ]]; then
    echo "sc006-soak: SPRING_HEADLESS not set — skip." >&2
    exit 77
fi
if [[ ! -f "${plugin_lib}" ]]; then
    echo "sc006-soak: plugin .so not built — skip." >&2
    exit 77
fi

echo "sc006-soak: engine launch helper not wired (T104) — skip." >&2
# Shape when T104 lands:
#   1. Launch engine with the plugin, 30-min match timer.
#   2. Start hb-observer --record obs.bin in background.
#   3. Start hb-python-observer --record py.bin in background.
#   4. Start hb-ai running a scripted MoveTo/Stop loop.
#   5. Wait 1800s.
#   6. Stop all; run resume_gap_check on obs.bin and py.bin; assert OK.
#   7. Verify obs.bin == py.bin (cross-client parity within the
#      same run; SC-004 belongs to a separate script but a cheap
#      bonus assertion here).
exit 77

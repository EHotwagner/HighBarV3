#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-2.0-only
#
# HighBarV3 — US6 reconnect acceptance (T100).
#
# Implements US6's Independent Test: observer connects, runs 30s,
# is killed, reconnects with last-seen seq. Receipt of the buffered
# gap or a fresh snapshot with monotonic continuation is verified
# through the SC-005 checker.
#
# Exit 77 until T104 lands the engine-launch helper.

set -euo pipefail

repo_root="$(cd "$(dirname "$0")/../.." && pwd)"
plugin_lib="${repo_root}/build/libSkirmishAI.so"
observer_bin="${repo_root}/clients/fsharp/samples/Observer/bin/Debug/net8.0/hb-observer"

if [[ ! -x "${SPRING_HEADLESS:-}" ]]; then
    echo "us6-reconnect: SPRING_HEADLESS not set — skip." >&2
    exit 77
fi
if [[ ! -f "${plugin_lib}" ]]; then
    echo "us6-reconnect: plugin .so not built — skip." >&2
    exit 77
fi
if [[ ! -x "${observer_bin}" ]]; then
    echo "us6-reconnect: hb-observer not built — skip." >&2
    exit 77
fi

echo "us6-reconnect: engine launch helper not wired (T104) — skip." >&2
# Shape when T104 lands:
#   1. Launch engine with the plugin + built-in AI.
#   2. hb-observer --record phase1.bin & obs_pid=$!
#   3. sleep 30
#   4. kill $obs_pid; wait $obs_pid
#   5. last_seq=$(tail -n1 phase1.bin | extract-seq)
#   6. hb-observer --resume-from-seq $last_seq --record phase2.bin
#   7. resume_gap_check phase1.bin phase2.bin → exit nonzero on
#      any dup/gap across the reconnect boundary.
exit 77

#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-2.0-only
#
# HighBarV3 — US1 framerate budget (T054).
#
# SC-003 / FR-015: with 4 observers attached, the engine's frame
# advance rate must be within 5% of the observer-free baseline.
#
# Methodology:
#   1. Baseline: run a fixed-length headless match (e.g. 30 game
#      seconds) with no observers, measure wall-clock elapsed.
#   2. Loaded:   run the same match with 4 observers attached,
#      measure the same quantity.
#   3. Assert loaded <= baseline * 1.05.
#
# STATUS: scaffolded as a skip-on-missing-prereqs regression anchor.
# The actual timing methodology (stable match seed, warm-up period,
# shared-memory frame counter from the plugin) belongs in its own PR
# once the engine harness matures. Flagging this as a Constitution V
# gate — failing a real run is a blocker, not a flake.

set -euo pipefail

repo_root="$(cd "$(dirname "$0")/../.." && pwd)"

if [[ -z "${SPRING_HEADLESS:-}" ]]; then
    echo "us1-framerate: SPRING_HEADLESS not set — skip." >&2
    exit 77
fi
if [[ ! -f "${repo_root}/build/libSkirmishAI.so" ]]; then
    echo "us1-framerate: plugin .so not built — skip." >&2
    exit 77
fi

echo "us1-framerate: harness TODO — see comment block above."
exit 77

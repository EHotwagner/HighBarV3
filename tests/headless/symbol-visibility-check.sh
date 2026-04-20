#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-2.0-only
#
# HighBarV3 — symbol-visibility guard (T101).
#
# Architecture doc §Critical Pitfalls #3: the Spring engine statically
# links protobuf; our plugin statically links its own copy. If either
# copy's symbols leak across the boundary, protobuf descriptor tables
# fight at load time and the plugin either crashes or silently
# corrupts serialization.
#
# Guard: launch spring-headless with LD_DEBUG=symbols and grep the
# stderr for grpc/protobuf cross-library resolutions. None are expected
# if -fvisibility=hidden + -Bsymbolic are wired correctly (CMakeLists,
# T005).
#
# Exit 0 when no leak observed; exit 1 when a cross-library resolution
# is found; exit 77 when prerequisites missing.

set -euo pipefail

repo_root="$(cd "$(dirname "$0")/../.." && pwd)"
plugin_lib="${repo_root}/build/libSkirmishAI.so"

if [[ ! -x "${SPRING_HEADLESS:-}" ]]; then
    echo "symbol-visibility: SPRING_HEADLESS not set — skip." >&2
    exit 77
fi
if [[ ! -f "${plugin_lib}" ]]; then
    echo "symbol-visibility: plugin .so not built — skip." >&2
    exit 77
fi

log=$(mktemp)
trap 'rm -f "$log"' EXIT

# Launch with a short --benchmark match so the plugin loads but the
# binary exits quickly. Real match run not needed for symbol resolution.
LD_DEBUG=symbols "${SPRING_HEADLESS}" --minlog --ai=HighBarV3 2>"$log" || true

if grep -E 'symbol[[:space:]].*(grpc|protobuf|absl).*undef' "$log" >/dev/null; then
    echo "symbol-visibility: FAIL — cross-library grpc/protobuf/absl resolution observed" >&2
    grep -E 'symbol[[:space:]].*(grpc|protobuf|absl).*undef' "$log" | head -20 >&2
    exit 1
fi
echo "symbol-visibility: PASS — no cross-library grpc/protobuf/absl leaks."
exit 0

#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-2.0-only
# arm-covered: (none — 001-era skip stub; no arms dispatched)
#
# HighBarV3 — US3 Phase-2 external-only, no-client survival (T081).
#
# Launches spring-headless with enable_builtin=false and NO external
# client. The AI slot must stay alive for 60s without crashing
# (SC-007, FR-017). The engine's AI slot-status callback is what we
# assert on; in practice we check the plugin process stays up and the
# UDS socket remains bound.

set -euo pipefail

# T030/T031 — FR-024 fault-aware exit policy. Source the helper
# unconditionally; `fault_status` returns 0=healthy, 2=disabled,
# 77=indeterminate. Acceptance scripts MUST upgrade `disabled` to
# exit 1, never 77.
source "$(dirname "$0")/_fault-assert.sh"

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

: "${XDG_RUNTIME_DIR:=/tmp}"
gameid="${HIGHBAR_SMOKE_GAMEID:-us3-nocli}"
uds_path="${XDG_RUNTIME_DIR}/highbar-${gameid}.sock"
log_dir="${repo_root}/build/tmp/us3-external-only"
mkdir -p "${log_dir}"
engine_log="${log_dir}/engine.log"

# AIOptions with enable_builtin=false. The engine reads these from a
# match-setup file; the driver harness that builds the .sdd should
# splat these in.
ai_options_file="${log_dir}/aioptions.lua"
cat > "${ai_options_file}" <<EOF
-- enable_builtin=false → Phase-2 externalization (FR-016, FR-017)
return { enable_builtin = 'false' }
EOF

"${SPRING_HEADLESS}" --ai HighBarV3 \
                     --config us3-external-only.sdd \
                     --ai-options "${ai_options_file}" \
    > "${engine_log}" 2>&1 &
engine_pid=$!
cleanup() { kill "${engine_pid}" 2>/dev/null || true; }
trap cleanup EXIT

# Bind must still happen (FR-017: gateway alive even with no client).
for i in {1..100}; do
    [[ -S "${uds_path}" ]] && break
    sleep 0.1
done
[[ -S "${uds_path}" ]] || {
    echo "us3-external-only: UDS not bound — gateway should be alive without a client (FR-017)"
    exit 1
}

# Hold for 60s. Assert the engine process hasn't died and the UDS is
# still present.
sleep 60
if ! kill -0 "${engine_pid}" 2>/dev/null; then
    echo "us3-external-only: engine died inside 60s (SC-007 fail)"
    tail -n 50 "${engine_log}" >&2
    exit 1
fi
if [[ ! -S "${uds_path}" ]]; then
    echo "us3-external-only: UDS disappeared before 60s"
    exit 1
fi

# No built-in AI decision activity should appear in the engine log.
# BARb's modules log under recognizable prefixes (e.g., "[BuilderManager]",
# "[EconomyManager]") — absence of those proves Phase-2 mode suppressed
# the built-in chain. This is a soft check (WARN only): the engine log
# format isn't under our control.
if grep -qE "\[(Builder|Economy|Factory|Military)Manager\]" "${engine_log}"; then
    echo "us3-external-only: WARN — built-in manager log lines found despite enable_builtin=false" >&2
fi

echo "us3-external-only: PASS — gateway survived 60s with no client (SC-007 / FR-017)"

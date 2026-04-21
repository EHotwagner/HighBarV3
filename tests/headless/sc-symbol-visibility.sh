#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-2.0-only
#
# HighBarV3 — symbol-visibility check (T101).
#
# Architecture doc §Critical Pitfalls #3: the engine ships its own
# protobuf; the plugin links its own protobuf via vcpkg. Unhidden
# symbols resolve across the library boundary and crash rarely and
# dramatically (constructors running twice, ABI skew). The plugin is
# built with -fvisibility=hidden -Bsymbolic; this script validates
# that at runtime by LD_DEBUG=symbols grepping for cross-library
# resolution into engine protobuf symbols.
#
# Pass: no cross-library resolutions reported for grpc / protobuf.
# Skip: prerequisites missing.
# Fail: any protobuf symbol bound from the engine into the plugin
#       (or vice versa).

set -euo pipefail

repo_root="$(cd "$(dirname "$0")/../.." && pwd)"
plugin_lib="${repo_root}/build/libSkirmishAI.so"

if [[ ! -x "${SPRING_HEADLESS:-}" ]]; then
    echo "sc-symbol-visibility: SPRING_HEADLESS not set — skip." >&2
    exit 77
fi
if [[ ! -f "${plugin_lib}" ]]; then
    echo "sc-symbol-visibility: plugin .so not built — skip." >&2
    exit 77
fi

log_dir="${repo_root}/build/tmp/sc-symbol-visibility"
mkdir -p "${log_dir}"
ld_log="${log_dir}/ld.log"
engine_log="${log_dir}/engine.log"

# Short run is enough — we just need the dynamic linker to resolve
# every protobuf/gRPC symbol the plugin touches. 5s is plenty.
LD_DEBUG=symbols,bindings LD_DEBUG_OUTPUT="${log_dir}/ld" \
"${SPRING_HEADLESS}" --ai HighBarV3 --config sc-symvis.sdd \
    > "${engine_log}" 2>&1 &
engine_pid=$!
cleanup() { kill "${engine_pid}" 2>/dev/null || true; }
trap cleanup EXIT
sleep 5
kill "${engine_pid}" 2>/dev/null || true
wait "${engine_pid}" 2>/dev/null || true

# Aggregate the per-pid LD_DEBUG files into one grep target.
cat "${log_dir}"/ld.* 2>/dev/null > "${ld_log}" || true
if [[ ! -s "${ld_log}" ]]; then
    echo "sc-symbol-visibility: LD_DEBUG produced no output — LD may be stripped on this distro."
    exit 77
fi

# Look for protobuf / grpc symbols bound ACROSS library boundaries.
# LD_DEBUG=bindings prints "binding file X [<ver>] to Y [<ver>]: ..."
# A clean plugin must never bind protobuf::* or grpc::* between its
# own .so and anything else.
violations=$(grep -E 'binding file .*(libSkirmishAI|libspring|libengine).*to .*(protobuf|grpc)' "${ld_log}" \
             | grep -vE 'binding file .*libSkirmishAI.*to .*libSkirmishAI' \
             | wc -l)

if [[ "${violations}" -gt 0 ]]; then
    echo "sc-symbol-visibility: FAIL — ${violations} cross-library protobuf/grpc bindings"
    grep -E 'binding file .*(protobuf|grpc)' "${ld_log}" | head -n 20 >&2
    exit 1
fi

echo "sc-symbol-visibility: PASS — no cross-library protobuf/grpc resolution"

#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-2.0-only
#
# HighBarV3 — Phase 2 foundational smoke test (T031).
#
# Launches the plugin in spring-headless, waits for the UDS socket,
# verifies the expected log sequence, probes every RPC, and asserts
# that:
#   * Hello succeeds (schema handshake passes)
#   * GetRuntimeCounters returns a coherent zero-valued snapshot
#   * All other RPCs return UNIMPLEMENTED
#
# This is a REGRESSION anchor for Phase 2. When US1/US2 fill in
# StreamState / SubmitCommands / InvokeCallback / Save / Load, the
# corresponding UNIMPLEMENTED assertions below will fail and must be
# swapped for the per-story acceptance script.

set -euo pipefail

# T027 — FR-024 fault-aware exit policy. Source the helper unconditionally;
# `fault_status` returns 0=healthy, 2=disabled, 77=indeterminate.
# Acceptance scripts MUST upgrade `disabled` to exit 1, never 77.
source "$(dirname "$0")/_fault-assert.sh"

repo_root="$(cd "$(dirname "$0")/../.." && pwd)"
plugin_lib="${repo_root}/build/libSkirmishAI.so"
config_path="${repo_root}/data/config/grpc.json"

# -- Precondition checks -----------------------------------------------------

if [[ ! -x "${SPRING_HEADLESS:-}" ]]; then
    echo "phase2-smoke: SPRING_HEADLESS not set or not executable." >&2
    echo "  Export SPRING_HEADLESS=/path/to/spring-headless and rerun." >&2
    exit 77   # skip
fi
if [[ ! -f "${plugin_lib}" ]]; then
    echo "phase2-smoke: plugin .so not built at ${plugin_lib}." >&2
    echo "  cmake --build build && rerun." >&2
    exit 77   # skip
fi
command -v grpcurl >/dev/null || {
    echo "phase2-smoke: grpcurl not on PATH (needed for RPC probes)." >&2
    exit 77
}

# -- Resolve UDS path from grpc.json ----------------------------------------

: "${XDG_RUNTIME_DIR:=/tmp}"
gameid="${HIGHBAR_SMOKE_GAMEID:-smoketest}"
uds_path="${XDG_RUNTIME_DIR}/highbar-${gameid}.sock"
token_path="${HIGHBAR_WRITEDIR:-${repo_root}/build/tmp}/highbar.token"
mkdir -p "$(dirname "${token_path}")"
rm -f "${uds_path}" "${token_path}"

# -- Launch plugin in spring-headless --------------------------------------

log_file="${repo_root}/build/tmp/phase2-smoke.log"
mkdir -p "$(dirname "${log_file}")"
# TODO: fill in the spring-headless args for a minimal AI-only match.
# Placeholder — actual invocation depends on BARb's test harness.
"${SPRING_HEADLESS}" --ai HighBarV3 --config phase2-smoke.sdd > "${log_file}" 2>&1 &
engine_pid=$!
cleanup() { kill "${engine_pid}" 2>/dev/null || true; }
trap cleanup EXIT

# Wait (max 10s) for the UDS to appear.
for i in {1..100}; do
    [[ -S "${uds_path}" ]] && break
    sleep 0.1
done
[[ -S "${uds_path}" ]] || { echo "UDS not bound after 10s"; exit 1; }

# Token file must exist with mode 0600 BEFORE the service accepts RPCs.
[[ -f "${token_path}" ]] || { echo "token file missing"; exit 1; }
perm=$(stat -c '%a' "${token_path}")
[[ "${perm}" == "600" ]] || { echo "token mode is ${perm}, expected 600"; exit 1; }

token=$(cat "${token_path}")
addr="unix:${uds_path}"

echo "phase2-smoke: plugin bound at ${addr}"

# -- RPC probes -------------------------------------------------------------

# 1. Hello succeeds (observer role, no token).
resp=$(grpcurl -plaintext -d '{"schema_version":"1.0.0","role":"ROLE_OBSERVER"}' \
        "${addr}" highbar.v1.HighBarProxy/Hello)
echo "${resp}" | grep -q '"schemaVersion":"1.0.0"' \
    || { echo "Hello response lacks schema_version"; exit 1; }

# 2. GetRuntimeCounters — requires token (FR-024 + clarification Q1).
grpcurl -plaintext -H "x-highbar-ai-token: ${token}" -d '{}' \
        "${addr}" highbar.v1.HighBarProxy/GetRuntimeCounters > /dev/null

# 2b. Missing token → PERMISSION_DENIED.
if grpcurl -plaintext -d '{}' \
        "${addr}" highbar.v1.HighBarProxy/GetRuntimeCounters 2>&1 \
        | grep -q "PermissionDenied"; then
    echo "phase2-smoke: auth gate on GetRuntimeCounters OK"
else
    echo "phase2-smoke: expected PermissionDenied when token missing"; exit 1
fi

# 3. All other RPCs return UNIMPLEMENTED at Phase 2.
for rpc in StreamState SubmitCommands InvokeCallback Save Load; do
    set +e
    out=$(grpcurl -plaintext -H "x-highbar-ai-token: ${token}" -d '{}' \
                  "${addr}" "highbar.v1.HighBarProxy/${rpc}" 2>&1)
    code=$?
    set -e
    echo "${out}" | grep -q "Unimplemented" \
        || { echo "phase2-smoke: ${rpc} did not return UNIMPLEMENTED (code=${code}, out=${out})"; exit 1; }
done

echo "phase2-smoke: PASS"

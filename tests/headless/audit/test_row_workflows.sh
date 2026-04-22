#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "$0")/../../.." && pwd)"
"${repo_root}/tests/headless/audit/run-all.sh" >/dev/null
repro_output="$("${repo_root}/tests/headless/audit/repro.sh" cmd-build-unit --phase=1)"
hyp_output="$("${repo_root}/tests/headless/audit/hypothesis.sh" cmd-move-unit phase1_reissuance)"

grep -q "manifest-backed repro artifact" <<<"${repro_output}"
grep -q "CONFIRMED: phase1_reissuance" <<<"${hyp_output}"

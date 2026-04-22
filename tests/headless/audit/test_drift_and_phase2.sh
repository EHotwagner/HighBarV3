#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "$0")/../../.." && pwd)"
"${repo_root}/tests/headless/audit/run-all.sh" >/dev/null
drift_output="$("${repo_root}/tests/headless/audit/repro-stability.sh")"
phase2_output="$("${repo_root}/tests/headless/audit/phase2-macro-chain.sh")"
partial_output="$(PYTHONPATH="${repo_root}/clients/python" python -m highbar_client.behavioral_coverage audit refresh --summary-only --fail-rows cmd-move-unit --topology-failure "launcher degraded")"

grep -q "PASS: drift report written" <<<"${drift_output}"
grep -q "PASS: phase2 macro-chain report generated" <<<"${phase2_output}"
grep -q "command-audit=partial" <<<"${partial_output}"
grep -q "launcher degraded" <<<"${partial_output}"

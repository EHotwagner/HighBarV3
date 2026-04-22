#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "$0")/../../.." && pwd)"
PYTHONPATH="${repo_root}/clients/python" python -m highbar_client.behavioral_coverage audit refresh --audit-dir "${repo_root}/audit"
"${repo_root}/tests/headless/audit/repro.sh" cmd-build-unit --phase=1 >/dev/null
"${repo_root}/tests/headless/audit/hypothesis.sh" cmd-move-unit phase1_reissuance >/dev/null
"${repo_root}/tests/headless/audit/repro-stability.sh" >/dev/null
"${repo_root}/tests/headless/audit/phase2-macro-chain.sh" >/dev/null
echo "PASS: live audit evidence refreshed from the latest completed manifest"

#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "$0")/../../.." && pwd)"
"${repo_root}/tests/headless/audit/repro.sh" cmd-build-unit --phase=1
"${repo_root}/tests/headless/audit/hypothesis.sh" cmd-move-unit phase1_reissuance >/dev/null
"${repo_root}/tests/headless/audit/repro-stability.sh"
"${repo_root}/tests/headless/audit/phase2-macro-chain.sh" >/dev/null
echo "PASS: 004 audit seed artifacts refreshed"

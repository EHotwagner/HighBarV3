#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "$0")/../../.." && pwd)"
tmp1="${repo_root}/build/reports/004-stability-run-1.md"
tmp2="${repo_root}/build/reports/004-stability-run-2.md"
mkdir -p "${repo_root}/build/reports"

PYTHONPATH="${repo_root}/clients/python" python -m highbar_client.behavioral_coverage audit >/dev/null
cp "${repo_root}/audit/command-audit.md" "${tmp1}"
PYTHONPATH="${repo_root}/clients/python" python -m highbar_client.behavioral_coverage audit >/dev/null
cp "${repo_root}/audit/command-audit.md" "${tmp2}"

if diff -u "${tmp1}" "${tmp2}" >/dev/null; then
    echo "PASS: audit markdown stable across two regeneration passes"
else
    echo "FAIL: audit markdown changed between regeneration passes" >&2
    exit 1
fi

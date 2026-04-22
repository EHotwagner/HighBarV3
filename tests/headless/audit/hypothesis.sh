#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "$0")/../../.." && pwd)"
row_id="${1:-}"
hypothesis_class="${2:-}"
if [[ -z "${row_id}" || -z "${hypothesis_class}" ]]; then
    echo "usage: tests/headless/audit/hypothesis.sh <row-id> <hypothesis-class>" >&2
    exit 1
fi

mkdir -p "${repo_root}/build/reports"
report_path="${repo_root}/build/reports/hypothesis-${row_id}-${hypothesis_class}.md"
verdict="$(PYTHONPATH="${repo_root}/clients/python" python -m highbar_client.behavioral_coverage audit hypothesis "${row_id}" "${hypothesis_class}" --report-path "${report_path}")"
echo "${verdict}"

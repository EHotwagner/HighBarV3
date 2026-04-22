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
report_path="${repo_root}/build/reports/004-hypothesis-${row_id}-${hypothesis_class}.md"
verdict="$(
    REPO_ROOT="${repo_root}" ROW_ID="${row_id}" HYPOTHESIS_CLASS="${hypothesis_class}" REPORT_PATH="${report_path}" \
    PYTHONPATH="${repo_root}/clients/python" python - <<'PY'
from pathlib import Path
import os
from highbar_client.behavioral_coverage.audit_runner import execute_hypothesis

result = execute_hypothesis(
    os.environ["ROW_ID"],
    os.environ["HYPOTHESIS_CLASS"],
)
Path(os.environ["REPORT_PATH"]).write_text(result.body, encoding="utf-8")
print(f"{result.verdict}: {result.hypothesis_class}")
PY
)"
echo "${verdict}"

#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "$0")/../../.." && pwd)"
row_id="${1:-}"
if [[ -z "${row_id}" ]]; then
    echo "usage: tests/headless/audit/repro.sh <row-id>" >&2
    exit 1
fi
shift || true

phase="phase1"
report_path=""
for arg in "$@"; do
    case "$arg" in
        --phase=1|--phase=phase1) phase="phase1" ;;
        --phase=2|--phase=phase2) phase="phase2" ;;
        --phase=tuned|--phase=live-tuned) phase="phase1" ;;
        --report-path=*) report_path="${arg#--report-path=}" ;;
    esac
done

mkdir -p "${repo_root}/build/reports"
if [[ -z "${report_path}" ]]; then
    report_path="${repo_root}/build/reports/repro-${row_id}.md"
fi
mkdir -p "$(dirname "${report_path}")"

if [[ "${row_id}" == rpc-* || "${row_id}" == cmd-* ]]; then
    summary="$(PYTHONPATH="${repo_root}/clients/python" python -m highbar_client.behavioral_coverage audit repro "${row_id}" --phase "${phase}" --report-path "${report_path}")"
    echo "${summary}"
    exit 0
fi

echo "FAIL: unknown row id ${row_id}" >&2
exit 1

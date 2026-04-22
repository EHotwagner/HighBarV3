#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "$0")/../../.." && pwd)"
mkdir -p "${repo_root}/build/reports"

PYTHONPATH="${repo_root}/clients/python" python -m highbar_client.behavioral_coverage audit refresh --summary-only >/dev/null
output="$(PYTHONPATH="${repo_root}/clients/python" python -m highbar_client.behavioral_coverage audit drift)"
echo "${output}"

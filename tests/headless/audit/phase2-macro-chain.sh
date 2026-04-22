#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "$0")/../../.." && pwd)"
mkdir -p "${repo_root}/build/reports"
report_path="${repo_root}/build/reports/004-phase2-smoke.md"
PYTHONPATH="${repo_root}/clients/python" REPORT_PATH="${report_path}" python - <<'PY'
from pathlib import Path
import os
from highbar_client.behavioral_coverage.audit_runner import phase2_macro_chain

report, _ = phase2_macro_chain()
Path(os.environ["REPORT_PATH"]).write_text(report, encoding="utf-8")
PY

echo "PASS: phase2 macro-chain report generated"

#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-2.0-only

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"

if ! command -v uv >/dev/null 2>&1; then
    echo "test_command_contract_hardening: uv missing — skip" >&2
    exit 77
fi

TMP_DIR="${HIGHBAR_CONTRACT_HARDENING_TMPDIR:-/tmp/highbar-contract-hardening}"
mkdir -p "$TMP_DIR"

uv run --project "$REPO_ROOT/clients/python" python - "$TMP_DIR" <<'PY'
from __future__ import annotations

import json
import sys
from pathlib import Path

from highbar_client.behavioral_coverage.itertesting_report import render_run_report
from highbar_client.behavioral_coverage.itertesting_runner import build_run
from highbar_client.behavioral_coverage.itertesting_types import manifest_dict
from highbar_client.behavioral_coverage.registry import REGISTRY

reports_dir = Path(sys.argv[1])
reports_dir.mkdir(parents=True, exist_ok=True)

run = build_run(
    campaign_id="contract-hardening-smoke",
    sequence_index=0,
    reports_dir=reports_dir,
    live_rows=[
        {
            "arm_name": "move_unit",
            "category": REGISTRY["move_unit"].category,
            "dispatched": "false",
            "verified": "false",
            "evidence": "batch target 4 disagreed with command unit 9",
            "error": "target_drift",
        },
        {
            "arm_name": "fight",
            "category": REGISTRY["fight"].category,
            "dispatched": "true",
            "verified": "false",
            "evidence": "inert dispatch left no durable effect",
            "error": "effect_not_observed",
        },
    ],
)

assert run.contract_health_decision is not None
assert run.contract_health_decision.decision_status == "blocked_foundational"
assert run.contract_issues, "expected foundational issues"
assert run.deterministic_repros, "expected deterministic repro records"
assert not run.improvement_actions, "ordinary improvement actions must be withheld"

bundle = reports_dir / run.run_id
bundle.mkdir(parents=True, exist_ok=True)
manifest_path = bundle / "manifest.json"
report_path = bundle / "run-report.md"
manifest_path.write_text(json.dumps(manifest_dict(run), indent=2, sort_keys=True) + "\n", encoding="utf-8")
rendered = render_run_report(run)
report_path.write_text(rendered, encoding="utf-8")

assert "## Contract Health" in rendered
assert "## Foundational Blockers" in rendered
assert "Ordinary improvement guidance is withheld" in rendered

print(f"test_command_contract_hardening: PASS manifest={manifest_path} report={report_path}")
PY

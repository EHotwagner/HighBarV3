# SPDX-License-Identifier: GPL-2.0-only
from __future__ import annotations

from highbar_client.behavioral_coverage.audit_runner import (
    collect_live_audit_run,
    execute_hypothesis,
)


def test_execute_hypothesis_reports_verdict():
    run = collect_live_audit_run()
    result = execute_hypothesis("cmd-move-unit", "phase1_reissuance", run=run)

    assert result.verdict == "CONFIRMED"
    assert run.run_id in result.body

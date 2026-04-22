# SPDX-License-Identifier: GPL-2.0-only
from __future__ import annotations

from highbar_client.behavioral_coverage.audit_runner import (
    collect_live_audit_run,
    render_repro_report,
)


def test_render_repro_report_uses_manifest_row():
    run = collect_live_audit_run()
    result = render_repro_report("cmd-build-unit", run=run)

    assert result.row_id == "cmd-build-unit"
    assert "manifest-backed repro artifact" in result.summary
    assert run.run_id in result.body

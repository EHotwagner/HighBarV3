# SPDX-License-Identifier: GPL-2.0-only
from __future__ import annotations

from highbar_client.behavioral_coverage.audit_runner import collect_live_audit_run


def test_second_run_compares_against_previous_manifest():
    first = collect_live_audit_run()
    second = collect_live_audit_run(previous_run=first)

    assert second.historical_comparison is not None
    assert second.historical_comparison.previous_run_id == first.run_id
    assert second.summary.drifted_count == 0

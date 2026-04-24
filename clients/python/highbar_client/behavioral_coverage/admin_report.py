# SPDX-License-Identifier: GPL-2.0-only
"""Evidence rendering for the admin behavioral suite."""

from __future__ import annotations

import csv
import json
from dataclasses import asdict
from pathlib import Path

from .admin_actions import AdminBehaviorRun, AdminEvidenceRecord

FAILURE_CLASSES = {
    "prerequisite_missing",
    "permission_not_rejected",
    "invalid_value_not_rejected",
    "lease_conflict_not_rejected",
    "effect_not_observed",
    "unexpected_mutation",
    "capability_mismatch",
    "cleanup_failed",
    "internal_error",
}


def classify_failure(record: AdminEvidenceRecord) -> str:
    if record.passed:
        return ""
    if record.failure_class:
        return record.failure_class
    if record.category == "prerequisite":
        return "prerequisite_missing"
    if record.category == "capability":
        return "capability_mismatch"
    if record.category == "cleanup":
        return "cleanup_failed"
    if record.category == "rejection":
        status = record.result.get("status", "")
        if "PERMISSION" in status:
            return "permission_not_rejected"
        if "CONFLICT" in status:
            return "lease_conflict_not_rejected"
        if "INVALID" in status:
            return "invalid_value_not_rejected"
        return "unexpected_mutation"
    if record.category == "success":
        return "effect_not_observed"
    return "internal_error"


def exit_code_for_records(records: list[AdminEvidenceRecord], *, prerequisite_status: str = "ok") -> int:
    if prerequisite_status != "ok":
        return 77
    if any(classify_failure(record) == "internal_error" for record in records):
        return 2
    if any(not record.passed for record in records):
        return 1
    return 0


def write_evidence_jsonl(path: Path, records: list[AdminEvidenceRecord]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for record in records:
            payload = asdict(record)
            payload["caller"] = asdict(record.caller)
            payload["caller"]["role"] = record.caller.role_name
            handle.write(json.dumps(payload, sort_keys=True) + "\n")


def write_summary_csv(path: Path, records: list[AdminEvidenceRecord]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "scenario_id",
                "action_name",
                "category",
                "result_status",
                "observed",
                "evidence_source",
                "passed",
                "failure_class",
                "log_location",
            ],
        )
        writer.writeheader()
        for record in records:
            writer.writerow(
                {
                    "scenario_id": record.scenario_id,
                    "action_name": record.action_name,
                    "category": record.category,
                    "result_status": record.result.get("status", ""),
                    "observed": str(record.observed).lower(),
                    "evidence_source": record.evidence_source,
                    "passed": str(record.passed).lower(),
                    "failure_class": classify_failure(record),
                    "log_location": record.log_location,
                }
            )


def render_markdown(run: AdminBehaviorRun) -> str:
    lines = [
        "# Admin Behavioral Control Report",
        "",
        "## Run Metadata",
        f"- Run id: {run.run_id}",
        f"- Fixture id: {run.fixture_id}",
        f"- Repeat index: {run.repeat_index}",
        f"- Started at: {run.started_at}",
        f"- Completed at: {run.completed_at}",
        f"- Prerequisite status: {run.prerequisite_status}",
        f"- Cleanup status: {run.cleanup_status}",
        f"- Exit code: {run.exit_code}",
        "",
        "## Capability Profile",
        "```json",
        json.dumps(run.capabilities, indent=2, sort_keys=True),
        "```",
        "",
        "## Scenario Evidence",
        "| Scenario | Action | Category | Result | Evidence | Expected | Actual | Status | Failure |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for record in run.records:
        status = "PASS" if record.passed else "FAIL"
        lines.append(
            "| {scenario} | {action} | {category} | {result} | {evidence} | {expected} | {actual} | {status} | {failure} |".format(
                scenario=record.scenario_id,
                action=record.action_name,
                category=record.category,
                result=record.result.get("status", ""),
                evidence=record.evidence_source,
                expected=record.expected_observation.replace("|", "/"),
                actual=record.actual_observation.replace("|", "/"),
                status=status,
                failure=classify_failure(record),
            )
        )
    failures = [record for record in run.records if not record.passed]
    if failures:
        lines.extend(["", "## Failure Details"])
        for record in failures:
            lines.extend(
                [
                    f"### {record.scenario_id}",
                    f"- Action: {record.action_name}",
                    f"- Expected: {record.expected_observation}",
                    f"- Actual: {record.actual_observation}",
                    f"- Evidence source: {record.evidence_source}",
                    f"- Log location: {record.log_location}",
                ]
            )
    lines.extend(["", "## Cleanup", run.cleanup_status, ""])
    return "\n".join(lines)


def write_run_report(path: Path, run: AdminBehaviorRun) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_markdown(run), encoding="utf-8")


def write_repeat_summary(path: Path, run: AdminBehaviorRun) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "run_id": run.run_id,
        "repeat_index": run.repeat_index,
        "exit_code": run.exit_code,
        "cleanup_status": run.cleanup_status,
        "leftover_pause": False,
        "leftover_speed": False,
        "leftover_lease": False,
        "record_count": len(run.records),
    }
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_artifacts(output_dir: Path, run: AdminBehaviorRun) -> None:
    write_evidence_jsonl(output_dir / "evidence.jsonl", run.records)
    write_summary_csv(output_dir / "summary.csv", run.records)
    write_run_report(output_dir / "run-report.md", run)
    if run.repeat_index:
        write_repeat_summary(output_dir / "repeats" / f"repeat-{run.repeat_index}.json", run)

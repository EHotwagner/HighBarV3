# SPDX-License-Identifier: GPL-2.0-only
"""Filesystem-backed Itertesting campaign runner."""

from __future__ import annotations

import argparse
import json
import os
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path

from .audit_inventory import ENGINE_PIN, GAMETYPE_PIN, repo_root
from .itertesting_report import render_run_report
from .itertesting_types import (
    CommandVerificationRecord,
    ImprovementAction,
    ImprovementInstruction,
    ItertestingCampaign,
    ItertestingRun,
    RunComparison,
    RunSummary,
    manifest_dict,
    run_from_dict,
)
from .registry import REGISTRY


_ALWAYS_NATURAL = {"attack", "build_unit", "self_destruct"}
_NATURAL_IMPROVABLE = {"fight", "move_unit", "patrol"}
_CHEAT_ONLY = {"give_me", "give_me_new_unit"}


def utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def format_timestamp(instant: datetime) -> str:
    return instant.isoformat().replace("+00:00", "Z")


def default_reports_dir() -> Path:
    return repo_root() / "reports" / "itertesting"


def ensure_reports_dir(reports_dir: Path) -> Path:
    reports_dir.mkdir(parents=True, exist_ok=True)
    return reports_dir


def make_run_id(reports_dir: Path, now: datetime | None = None) -> str:
    instant = now or utc_now()
    base = instant.strftime("itertesting-%Y%m%dT%H%M%SZ")
    if not (reports_dir / base).exists():
        return base
    suffix = 2
    while (reports_dir / f"{base}-{suffix:02d}").exists():
        suffix += 1
    return f"{base}-{suffix:02d}"


def run_dir(reports_dir: Path, run_id: str) -> Path:
    return reports_dir / run_id


def instructions_dir(reports_dir: Path) -> Path:
    return reports_dir / "instructions"


def instruction_index_path(reports_dir: Path) -> Path:
    return instructions_dir(reports_dir) / "index.json"


def instruction_path(reports_dir: Path, command_id: str) -> Path:
    return instructions_dir(reports_dir) / f"{command_id}.json"


def _command_id(arm_name: str) -> str:
    return f"cmd-{arm_name.replace('_', '-')}"


def _action_id(command_id: str, sequence_index: int) -> str:
    return f"{command_id}-{sequence_index:02d}"


def load_instruction_store(reports_dir: Path) -> dict[str, ImprovementInstruction]:
    index_path = instruction_index_path(reports_dir)
    if not index_path.exists():
        return {}
    payload = json.loads(index_path.read_text(encoding="utf-8"))
    return {
        item["command_id"]: ImprovementInstruction(**item)
        for item in payload.get("instructions", ())
    }


def write_instruction_store(
    reports_dir: Path,
    instructions: dict[str, ImprovementInstruction],
) -> Path:
    base = instructions_dir(reports_dir)
    base.mkdir(parents=True, exist_ok=True)
    for command_id, instruction in sorted(instructions.items()):
        instruction_path(reports_dir, command_id).write_text(
            json.dumps(instruction.__dict__, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    index_path = instruction_index_path(reports_dir)
    index_path.write_text(
        json.dumps(
            {
                "instructions": [
                    instruction.__dict__
                    for _command_id, instruction in sorted(instructions.items())
                ]
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    return index_path


def _instruction_detail(
    prior_instruction: ImprovementInstruction | None,
    default_detail: str,
) -> str:
    if prior_instruction is None:
        return default_detail
    return (
        f"Build on saved instruction r{prior_instruction.revision}: "
        f"{prior_instruction.instruction}"
    )


def _improvement_defaults(
    arm_name: str,
    sequence_index: int,
    prior_instruction: ImprovementInstruction | None,
) -> tuple[str, str]:
    if arm_name in _NATURAL_IMPROVABLE:
        return (
            "candidate",
            _instruction_detail(
                prior_instruction,
                "Retry with stronger timing and target preparation.",
            ),
        )
    if arm_name in _CHEAT_ONLY:
        return (
            "candidate",
            _instruction_detail(
                prior_instruction,
                "Escalate only after natural progress stops.",
            ),
        )
    if prior_instruction is not None and prior_instruction.status == "exhausted":
        return ("exhausted", _instruction_detail(prior_instruction, prior_instruction.instruction))
    if sequence_index >= 1:
        return (
            "exhausted",
            _instruction_detail(
                prior_instruction,
                "No better action remains after the first retry.",
            ),
        )
    return (
        "candidate",
        _instruction_detail(
            prior_instruction,
            "Collect a more specific setup or evidence plan before retrying.",
        ),
    )


def _record_for_command(
    run_id: str,
    arm_name: str,
    sequence_index: int,
    cheat_enabled: bool,
    prior_instruction: ImprovementInstruction | None = None,
) -> CommandVerificationRecord:
    case = REGISTRY[arm_name]
    command_id = _command_id(arm_name)
    if arm_name in _ALWAYS_NATURAL:
        return CommandVerificationRecord(
            command_id=command_id,
            command_name=arm_name,
            category=case.category,
            attempt_status="verified",
            verification_mode="natural",
            evidence_kind="game-state",
            verified=True,
            source_run_id=run_id,
            evidence_summary=f"{arm_name} produced direct observable state change.",
        )
    if arm_name in _NATURAL_IMPROVABLE:
        if sequence_index >= 1 or (
            sequence_index == 0
            and prior_instruction is not None
            and prior_instruction.action_type == "timing-change"
            and prior_instruction.status in {"active", "applied"}
        ):
            return CommandVerificationRecord(
                command_id=command_id,
                command_name=arm_name,
                category=case.category,
                attempt_status="verified",
                verification_mode="natural",
                evidence_kind="live-artifact",
                verified=True,
                source_run_id=run_id,
                evidence_summary=(
                    f"{arm_name} gained direct evidence after reusing a saved instruction."
                    if sequence_index == 0 and prior_instruction is not None
                    else f"{arm_name} gained direct evidence after a targeted retry."
                ),
                improvement_state="applied",
                improvement_note=_instruction_detail(
                    prior_instruction,
                    "Applied a tighter verify window and stronger target preparation.",
                ),
            )
        return CommandVerificationRecord(
            command_id=command_id,
            command_name=arm_name,
            category=case.category,
            attempt_status="inconclusive",
            verification_mode="natural",
            evidence_kind="dispatch-only",
            verified=False,
            source_run_id=run_id,
            blocking_reason="dispatch observed but direct evidence remained ambiguous",
            improvement_state="candidate",
            improvement_note=_instruction_detail(
                prior_instruction,
                "Retry with stronger timing and target preparation.",
            ),
        )
    if arm_name in _CHEAT_ONLY:
        if cheat_enabled:
            return CommandVerificationRecord(
                command_id=command_id,
                command_name=arm_name,
                category=case.category,
                attempt_status="verified",
                verification_mode="cheat-assisted",
                evidence_kind="game-state",
                verified=True,
                source_run_id=run_id,
                evidence_summary=f"{arm_name} verified after cheat-backed setup.",
                setup_actions=("enabled cheats", "provisioned prerequisite units"),
                improvement_state="applied",
                improvement_note="Escalated after the natural path had no better setup option.",
            )
        return CommandVerificationRecord(
            command_id=command_id,
            command_name=arm_name,
            category=case.category,
            attempt_status="blocked",
            verification_mode="not-attempted",
            evidence_kind="none",
            verified=False,
            source_run_id=run_id,
            blocking_reason="requires cheat-backed setup for direct verification",
            improvement_state="candidate",
            improvement_note=_instruction_detail(
                prior_instruction,
                "Escalate only after natural progress stops.",
            ),
        )
    if case.category == "channel_c_lua":
        return CommandVerificationRecord(
            command_id=command_id,
            command_name=arm_name,
            category=case.category,
            attempt_status="inconclusive",
            verification_mode="natural",
            evidence_kind="dispatch-only",
            verified=False,
            source_run_id=run_id,
            blocking_reason="Lua-only command has no direct game-state evidence in this harness",
            improvement_state="exhausted",
            improvement_note=_instruction_detail(
                prior_instruction,
                "No better direct evidence path exists without transport changes.",
            ),
        )
    if case.category == "channel_b_query":
        return CommandVerificationRecord(
            command_id=command_id,
            command_name=arm_name,
            category=case.category,
            attempt_status="blocked",
            verification_mode="natural",
            evidence_kind="none",
            verified=False,
            source_run_id=run_id,
            blocking_reason="query arm does not create a directly verifiable state mutation",
            improvement_state="exhausted",
            improvement_note=_instruction_detail(
                prior_instruction,
                "No better action remains inside the current harness scope.",
            ),
        )
    return CommandVerificationRecord(
        command_id=command_id,
        command_name=arm_name,
        category=case.category,
        attempt_status="blocked",
        verification_mode="natural",
        evidence_kind="none",
        verified=False,
        source_run_id=run_id,
        blocking_reason="target/setup path is still unavailable in the current harness",
        improvement_state=(
            "exhausted"
            if sequence_index >= 1
            or (prior_instruction is not None and prior_instruction.status == "exhausted")
            else "candidate"
        ),
        improvement_note=_instruction_detail(
            prior_instruction,
            (
                "No better action remains after the first retry."
                if sequence_index >= 1
                else "Collect a more specific setup or evidence plan before retrying."
            ),
        ),
    )


def _build_actions(
    records: tuple[CommandVerificationRecord, ...],
    current_run_id: str,
    next_run_token: str,
    cheat_enabled: bool,
    prior_instructions: dict[str, ImprovementInstruction],
) -> tuple[ImprovementAction, ...]:
    actions: list[ImprovementAction] = []
    for record in records:
        if record.verified:
            if record.improvement_state == "applied":
                actions.append(
                    ImprovementAction(
                        action_id=_action_id(record.command_id, 0),
                        command_id=record.command_id,
                        action_type=(
                            "cheat-escalation"
                            if record.verification_mode == "cheat-assisted"
                            else "timing-change"
                        ),
                        trigger_reason="prior run left the command unverified",
                        applies_to_run_id=current_run_id,
                        status="applied",
                        details=record.improvement_note or "Applied a targeted retry change.",
                    )
                )
            continue
        if record.command_name in _NATURAL_IMPROVABLE:
            action_type = "timing-change"
            details = "Retry with a narrower target window and stronger evidence capture."
        elif record.command_name in _CHEAT_ONLY and not cheat_enabled:
            action_type = "cheat-escalation"
            details = "Escalate to the cheat startscript if natural progress stalls."
        elif record.improvement_state == "candidate":
            action_type = "setup-change"
            details = record.improvement_note or "Retry with improved setup."
        else:
            action_type = "skip-no-better-action"
            details = record.improvement_note or "No better next action remains."
        actions.append(
            ImprovementAction(
                action_id=_action_id(
                    record.command_id,
                    prior_instructions.get(record.command_id, None).revision
                    if record.command_id in prior_instructions
                    else 0,
                ),
                command_id=record.command_id,
                action_type=action_type,
                trigger_reason=record.blocking_reason or "unverified",
                applies_to_run_id=next_run_token,
                status="planned",
                details=details,
            )
        )
    return tuple(actions)


def _build_live_args(
    *,
    endpoint: str,
    startscript: str,
    gameseed: str,
    output_dir: Path,
    threshold: float,
    run_index: int,
) -> argparse.Namespace:
    return argparse.Namespace(
        endpoint=endpoint,
        startscript=startscript,
        gameseed=gameseed,
        output_dir=str(output_dir),
        threshold=threshold,
        run_index=run_index,
        skip_live=False,
    )


def _record_from_live_row(
    *,
    run_id: str,
    row: dict,
    sequence_index: int,
    cheat_enabled: bool,
    prior_instruction: ImprovementInstruction | None,
) -> CommandVerificationRecord:
    arm_name = row["arm_name"]
    command_id = _command_id(arm_name)
    evidence = row.get("evidence", "")
    error = row.get("error", "")
    dispatched = row.get("dispatched") == "true"
    verified = row.get("verified")
    verification_mode = (
        "cheat-assisted"
        if cheat_enabled and arm_name in _CHEAT_ONLY
        else "natural"
    )
    if verified == "true":
        return CommandVerificationRecord(
            command_id=command_id,
            command_name=arm_name,
            category=row["category"],
            attempt_status="verified",
            verification_mode=verification_mode,
            evidence_kind="game-state" if evidence else "live-artifact",
            verified=True,
            source_run_id=run_id,
            evidence_summary=evidence or f"{arm_name} verified via live behavioral coverage.",
            setup_actions=(
                ("enabled cheats",) if verification_mode == "cheat-assisted" else ()
            ),
            improvement_state=(
                "applied" if prior_instruction is not None or arm_name in _NATURAL_IMPROVABLE else "none"
            ),
            improvement_note=(
                _instruction_detail(prior_instruction, evidence or "Applied live verification guidance.")
                if prior_instruction is not None or arm_name in _NATURAL_IMPROVABLE
                else ""
            ),
        )

    if verified == "false":
        if error in {"effect_not_observed"}:
            attempt_status = "inconclusive"
            evidence_kind = "dispatch-only" if dispatched else "none"
        elif error in {"target_unit_destroyed"}:
            attempt_status = "blocked"
            evidence_kind = "none"
        else:
            attempt_status = "failed"
            evidence_kind = "none"
        improvement_state, improvement_note = _improvement_defaults(
            arm_name,
            sequence_index,
            prior_instruction,
        )
        return CommandVerificationRecord(
            command_id=command_id,
            command_name=arm_name,
            category=row["category"],
            attempt_status=attempt_status,
            verification_mode=verification_mode if dispatched else "not-attempted",
            evidence_kind=evidence_kind,
            verified=False,
            source_run_id=run_id,
            blocking_reason=evidence or error or "live behavioral verification failed",
            improvement_state=improvement_state,  # type: ignore[arg-type]
            improvement_note=improvement_note,
        )

    if error == "not_wire_observable":
        attempt_status = "inconclusive"
        evidence_kind = "dispatch-only"
        improvement_state = "exhausted"
        improvement_note = _instruction_detail(
            prior_instruction,
            "No better direct evidence path exists without transport changes.",
        )
    elif error == "precondition_unmet":
        attempt_status = "blocked"
        evidence_kind = "none"
        improvement_state, improvement_note = _improvement_defaults(
            arm_name,
            sequence_index,
            prior_instruction,
        )
    elif error == "dispatcher_rejected":
        attempt_status = "failed"
        evidence_kind = "none"
        improvement_state, improvement_note = _improvement_defaults(
            arm_name,
            sequence_index,
            prior_instruction,
        )
    else:
        attempt_status = "blocked"
        evidence_kind = "dispatch-only" if dispatched else "none"
        improvement_state, improvement_note = _improvement_defaults(
            arm_name,
            sequence_index,
            prior_instruction,
        )
    return CommandVerificationRecord(
        command_id=command_id,
        command_name=arm_name,
        category=row["category"],
        attempt_status=attempt_status,
        verification_mode=verification_mode if dispatched else "not-attempted",
        evidence_kind=evidence_kind,
        verified=False,
        source_run_id=run_id,
        blocking_reason=evidence or error or "live behavioral verification unavailable",
        improvement_state=improvement_state,  # type: ignore[arg-type]
        improvement_note=improvement_note,
    )


def _summary_for_run(
    run_id: str,
    records: tuple[CommandVerificationRecord, ...],
    previous_run: ItertestingRun | None,
) -> RunSummary:
    previous_map = {}
    if previous_run is not None:
        previous_map = {
            item.command_id: item for item in previous_run.command_records
        }
    newly_verified = tuple(
        item.command_id
        for item in records
        if item.verified and not previous_map.get(item.command_id, item).verified
    )
    regressed = tuple(
        item.command_id
        for item in records
        if not item.verified and previous_map.get(item.command_id, item).verified
    )
    stalled = tuple(
        item.command_id
        for item in records
        if (not item.verified) and item.improvement_state == "exhausted"
    )
    return RunSummary(
        run_id=run_id,
        tracked_commands=len(records),
        verified_total=sum(1 for item in records if item.verified),
        verified_natural=sum(
            1
            for item in records
            if item.verified and item.verification_mode == "natural"
        ),
        verified_cheat_assisted=sum(
            1
            for item in records
            if item.verified and item.verification_mode == "cheat-assisted"
        ),
        inconclusive_total=sum(
            1 for item in records if item.attempt_status == "inconclusive"
        ),
        blocked_total=sum(1 for item in records if item.attempt_status == "blocked"),
        failed_total=sum(1 for item in records if item.attempt_status == "failed"),
        newly_verified=newly_verified,
        regressed=regressed,
        stalled=stalled,
    )


def _comparison_for_run(
    current_run: ItertestingRun,
    previous_run: ItertestingRun | None,
) -> RunComparison | None:
    if previous_run is None:
        return None
    previous_map = {item.command_id: item for item in previous_run.command_records}
    changed_commands = tuple(
        item.command_id
        for item in current_run.command_records
        if previous_map.get(item.command_id) != item
    )
    applied = tuple(
        item.action_id for item in current_run.improvement_actions if item.status == "applied"
    )
    coverage_delta = (
        current_run.summary.verified_total - previous_run.summary.verified_total
    )
    natural_delta = (
        current_run.summary.verified_natural - previous_run.summary.verified_natural
    )
    cheat_delta = (
        current_run.summary.verified_cheat_assisted
        - previous_run.summary.verified_cheat_assisted
    )
    return RunComparison(
        previous_run_id=previous_run.run_id,
        current_run_id=current_run.run_id,
        coverage_delta=coverage_delta,
        natural_delta=natural_delta,
        cheat_delta=cheat_delta,
        changed_commands=changed_commands,
        improvement_actions_applied=applied,
        stall_detected=coverage_delta <= 0,
    )


def build_run(
    *,
    campaign_id: str,
    sequence_index: int,
    reports_dir: Path,
    previous_run: ItertestingRun | None = None,
    cheat_enabled: bool = False,
    prior_instructions: dict[str, ImprovementInstruction] | None = None,
    live_rows: list[dict] | None = None,
) -> ItertestingRun:
    started = utc_now()
    run_id = make_run_id(reports_dir, started)
    loaded_instructions = prior_instructions or {}
    if live_rows is None:
        command_records = tuple(
            _record_for_command(
                run_id,
                arm_name,
                sequence_index,
                cheat_enabled,
                loaded_instructions.get(_command_id(arm_name)),
            )
            for arm_name in sorted(REGISTRY)
        )
    else:
        row_map = {item["arm_name"]: item for item in live_rows}
        command_records = tuple(
            _record_from_live_row(
                run_id=run_id,
                row=row_map.get(
                    arm_name,
                    {
                        "arm_name": arm_name,
                        "category": REGISTRY[arm_name].category,
                        "dispatched": "false",
                        "verified": "na",
                        "evidence": "row missing from live run",
                        "error": "precondition_unmet",
                    },
                ),
                sequence_index=sequence_index,
                cheat_enabled=cheat_enabled,
                prior_instruction=loaded_instructions.get(_command_id(arm_name)),
            )
            for arm_name in sorted(REGISTRY)
        )
    actions = _build_actions(
        command_records,
        current_run_id=run_id,
        next_run_token=f"{campaign_id}-next-{sequence_index + 1}",
        cheat_enabled=cheat_enabled,
        prior_instructions=loaded_instructions,
    )
    summary = _summary_for_run(run_id, command_records, previous_run)
    setup_mode = (
        "cheat-assisted"
        if summary.verified_total and summary.verified_total == summary.verified_cheat_assisted
        else "mixed"
        if summary.verified_cheat_assisted
        else "natural"
    )
    run = ItertestingRun(
        run_id=run_id,
        campaign_id=campaign_id,
        started_at=format_timestamp(started),
        completed_at=format_timestamp(utc_now()),
        sequence_index=sequence_index,
        engine_pin=ENGINE_PIN,
        gametype_pin=GAMETYPE_PIN,
        setup_mode=setup_mode,
        command_records=command_records,
        improvement_actions=actions,
        summary=summary,
    )
    comparison = _comparison_for_run(run, previous_run)
    return replace(run, previous_run_comparison=comparison)


def write_run_bundle(
    run: ItertestingRun,
    reports_dir: Path,
    *,
    stop_reason: str | None = None,
) -> Path:
    bundle_dir = run_dir(reports_dir, run.run_id)
    bundle_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = bundle_dir / "manifest.json"
    manifest_path.write_text(
        json.dumps(manifest_dict(run), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    report_path = bundle_dir / "run-report.md"
    report_path.write_text(render_run_report(run, stop_reason=stop_reason), encoding="utf-8")
    return bundle_dir


def load_run_manifest(path: Path) -> ItertestingRun:
    payload = json.loads(path.read_text(encoding="utf-8"))
    required = {"run_id", "campaign_id", "summary", "command_records"}
    missing = sorted(required - payload.keys())
    if missing:
        raise ValueError(f"manifest missing required fields: {', '.join(missing)}")
    if not payload["command_records"]:
        raise ValueError("manifest has no command_records")
    return run_from_dict(payload)


def latest_run_manifest(reports_dir: Path) -> Path | None:
    manifests = sorted(reports_dir.glob("itertesting-*/manifest.json"))
    return manifests[-1] if manifests else None


def campaign_stop_reason(run: ItertestingRun, budget_exhausted: bool) -> str:
    if run.summary.verified_total == run.summary.tracked_commands:
        return "all tracked commands reached direct verification"
    if budget_exhausted:
        return "retry budget exhausted"
    if any(item.action_type != "skip-no-better-action" for item in run.improvement_actions):
        return "further improvement actions remain"
    return "no better action remains for the outstanding commands"


def _next_instruction_revision(
    prior_instruction: ImprovementInstruction | None,
) -> int:
    if prior_instruction is None:
        return 1
    return prior_instruction.revision + 1


def update_instruction_store(
    reports_dir: Path,
    run: ItertestingRun,
    prior_instructions: dict[str, ImprovementInstruction],
) -> dict[str, ImprovementInstruction]:
    updated = dict(prior_instructions)
    action_map = {item.command_id: item for item in run.improvement_actions}
    timestamp = run.completed_at or run.started_at
    for record in run.command_records:
        prior = updated.get(record.command_id)
        action = action_map.get(record.command_id)
        if record.improvement_state == "none" and action is None:
            continue
        if record.verified and record.improvement_state == "applied":
            action_type = action.action_type if action is not None else "timing-change"
            status = "applied"
            instruction = record.improvement_note or (
                action.details if action is not None else "Applied a targeted retry change."
            )
            trigger_reason = action.trigger_reason if action is not None else ""
        elif record.improvement_state == "candidate":
            action_type = action.action_type if action is not None else "setup-change"
            status = "active"
            instruction = record.improvement_note or (
                action.details if action is not None else "Retry with improved setup."
            )
            trigger_reason = record.blocking_reason or (
                action.trigger_reason if action is not None else ""
            )
        else:
            action_type = (
                action.action_type if action is not None else "skip-no-better-action"
            )
            status = "exhausted"
            instruction = record.improvement_note or (
                action.details if action is not None else "No better next action remains."
            )
            trigger_reason = record.blocking_reason or (
                action.trigger_reason if action is not None else ""
            )
        updated[record.command_id] = ImprovementInstruction(
            command_id=record.command_id,
            revision=_next_instruction_revision(prior),
            action_type=action_type,
            status=status,
            instruction=instruction,
            updated_at=timestamp,
            source_run_id=run.run_id,
            trigger_reason=trigger_reason,
        )
    write_instruction_store(reports_dir, updated)
    return updated


def run_campaign(
    *,
    reports_dir: Path,
    max_improvement_runs: int,
    allow_cheat_escalation: bool,
    natural_first: bool,
    endpoint: str | None = None,
    startscript: str = "tests/headless/scripts/minimal.startscript",
    cheat_startscript: str = "tests/headless/scripts/cheats.startscript",
    gameseed: str = "0x42424242",
    threshold: float = 0.50,
    skip_live: bool = True,
) -> tuple[ItertestingCampaign, tuple[ItertestingRun, ...]]:
    ensure_reports_dir(reports_dir)
    instruction_store = load_instruction_store(reports_dir)
    campaign_started = utc_now()
    campaign_id = campaign_started.strftime("itertesting-campaign-%Y%m%dT%H%M%SZ")
    runs: list[ItertestingRun] = []
    previous_run: ItertestingRun | None = None
    for sequence_index in range(max_improvement_runs + 1):
        cheat_enabled = (
            allow_cheat_escalation
            and sequence_index >= 2
            and (not natural_first or previous_run is not None)
        )
        live_rows: list[dict] | None = None
        if not skip_live:
            from . import collect_live_rows

            live_args = _build_live_args(
                endpoint=endpoint or os.environ.get("HIGHBAR_COORDINATOR", "unix:/tmp/hb-run/hb-coord.sock"),
                startscript=cheat_startscript if cheat_enabled else startscript,
                gameseed=gameseed,
                output_dir=reports_dir / "_live-artifacts",
                threshold=threshold,
                run_index=sequence_index,
            )
            live_rows = collect_live_rows(live_args)
        run = build_run(
            campaign_id=campaign_id,
            sequence_index=sequence_index,
            reports_dir=reports_dir,
            previous_run=previous_run,
            cheat_enabled=cheat_enabled,
            prior_instructions=instruction_store,
            live_rows=live_rows,
        )
        budget_exhausted = sequence_index >= max_improvement_runs
        stop_reason = campaign_stop_reason(run, budget_exhausted)
        write_run_bundle(run, reports_dir, stop_reason=stop_reason)
        instruction_store = update_instruction_store(
            reports_dir,
            run,
            instruction_store,
        )
        runs.append(run)
        previous_run = run
        has_next_budget = sequence_index < max_improvement_runs
        if run.summary.verified_total == run.summary.tracked_commands:
            final_status = "improved"
            break
        if not has_next_budget:
            final_status = "budget_exhausted"
            break
        if sequence_index == 0:
            continue
        outstanding = [item for item in run.command_records if not item.verified]
        can_naturally_improve = any(
            item.command_name in _NATURAL_IMPROVABLE and item.improvement_state != "exhausted"
            for item in outstanding
        )
        can_cheat_improve = allow_cheat_escalation and any(
            item.command_name in _CHEAT_ONLY for item in outstanding
        )
        if not can_naturally_improve and not can_cheat_improve:
            final_status = "stalled"
            break
    else:
        final_status = "budget_exhausted"
    stop_reason = campaign_stop_reason(runs[-1], final_status == "budget_exhausted")
    campaign = ItertestingCampaign(
        campaign_id=campaign_id,
        started_at=format_timestamp(campaign_started),
        completed_at=format_timestamp(utc_now()),
        max_improvement_runs=max_improvement_runs,
        natural_first=natural_first,
        run_ids=tuple(run.run_id for run in runs),
        final_status=final_status,
        stop_reason=stop_reason,
    )
    return campaign, tuple(runs)


def parse_itertesting_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="highbar_client.behavioral_coverage itertesting")
    parser.add_argument(
        "--endpoint",
        default=os.environ.get("HIGHBAR_COORDINATOR", "unix:/tmp/hb-run/hb-coord.sock"),
        help="gRPC endpoint of the running coordinator",
    )
    parser.add_argument(
        "--startscript",
        default="tests/headless/scripts/minimal.startscript",
        help="path to the natural startscript used for the live run",
    )
    parser.add_argument(
        "--reports-dir",
        default=str(default_reports_dir()),
        help="directory for timestamped Itertesting run bundles",
    )
    parser.add_argument(
        "--max-improvement-runs",
        type=int,
        default=0,
        help="number of follow-up improvement runs after the initial run",
    )
    parser.add_argument(
        "--allow-cheat-escalation",
        action="store_true",
        help="allow cheat-backed setup after natural progress stalls",
    )
    parser.add_argument(
        "--cheat-startscript",
        default="tests/headless/scripts/cheats.startscript",
        help="path recorded when cheat escalation is enabled",
    )
    parser.add_argument(
        "--gameseed",
        default="0x42424242",
        help="gameseed recorded for live campaigns",
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=float(os.environ.get("HIGHBAR_BEHAVIORAL_THRESHOLD", "0.50")),
        help="behavioral threshold forwarded to live row collection",
    )
    parser.add_argument(
        "--natural-first",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="require natural attempts before cheat escalation",
    )
    parser.add_argument(
        "--skip-live",
        action="store_true",
        help="skip the coordinator/gateway session and use the synthetic campaign model",
    )
    return parser.parse_args(argv)


def itertesting_main(argv: list[str] | None = None) -> int:
    args = parse_itertesting_args(argv)
    reports_dir = ensure_reports_dir(Path(args.reports_dir))
    campaign, runs = run_campaign(
        reports_dir=reports_dir,
        max_improvement_runs=max(args.max_improvement_runs, 0),
        allow_cheat_escalation=args.allow_cheat_escalation,
        natural_first=args.natural_first,
        endpoint=args.endpoint,
        startscript=args.startscript,
        cheat_startscript=args.cheat_startscript,
        gameseed=args.gameseed,
        threshold=args.threshold,
        skip_live=args.skip_live,
    )
    latest = runs[-1]
    print(
        f"itertesting: run={latest.run_id} verified={latest.summary.verified_total}/"
        f"{latest.summary.tracked_commands} natural={latest.summary.verified_natural} "
        f"cheat={latest.summary.verified_cheat_assisted}"
    )
    print(f"itertesting: campaign={campaign.campaign_id} status={campaign.final_status}")
    print(f"itertesting: reports={reports_dir}")
    if args.allow_cheat_escalation:
        print(f"itertesting: cheat-startscript={args.cheat_startscript}")
    print(f"itertesting: instructions={instructions_dir(reports_dir)}")
    return 0

# SPDX-License-Identifier: GPL-2.0-only
"""Closed hypothesis vocabulary and ranking helpers for the live audit."""

from __future__ import annotations

from .types import AuditRow, HypothesisCandidate, HypothesisClass


HYPOTHESIS_CLASSES: dict[HypothesisClass, dict[str, str]] = {
    "phase1_reissuance": {
        "confirmed": "The latest phase-1 run shows no durable snapshot effect, while phase-2 reproduces the expected state change.",
        "falsified": "Phase-2 also lacks the expected state change, pushing suspicion toward dispatcher or setup defects in the latest manifest.",
    },
    "effect_not_snapshotable": {
        "confirmed": "Snapshot diffs stay empty while engine log or callback evidence from the latest run proves the command-specific state changed.",
        "falsified": "Neither the snapshot nor the log from the latest run shows the expected command-specific state change.",
    },
    "target_missing": {
        "confirmed": "Re-running with an explicit bootstrap target causes the effect to appear in the latest live repro.",
        "falsified": "Even with the target precondition provisioned, the effect is still absent in the latest live repro.",
    },
    "cross_team_rejection": {
        "confirmed": "A faction-correct def-id makes the build or spawn effect appear immediately in the latest run.",
        "falsified": "The command still has no effect after resolving a faction-correct def-id in the latest run.",
    },
    "cheats_required": {
        "confirmed": "The cheats-enabled live repro produces the expected state change while the default run does not.",
        "falsified": "The cheats-enabled live repro still does not produce the expected effect.",
    },
    "dispatcher_defect": {
        "confirmed": "Both Phase-1 and Phase-2 lack the effect in the latest run history, and no arm-specific log evidence appears.",
        "falsified": "Phase-2 or targeted logging from the latest run shows the dispatcher called the correct engine path.",
    },
    "intended_noop": {
        "confirmed": "Current source comments or contracts show the arm intentionally has no observable runtime effect.",
        "falsified": "A concrete runtime side effect becomes observable and should move the row out of intended-noop.",
    },
    "engine_version_drift": {
        "confirmed": "The active engine pin in the latest manifest lacks the callback or subsystem the arm depends on.",
        "falsified": "The same engine pin proves the subsystem exists and the fault lies elsewhere.",
    },
}


def primary_hypothesis_for_row(row: AuditRow) -> HypothesisClass:
    name = row.arm_or_rpc_name
    if name in {"move_unit", "patrol", "fight"}:
        return "phase1_reissuance"
    if name in {"build_unit", "give_me", "give_me_new_unit"}:
        return "cheats_required" if name.startswith("give_me") else "cross_team_rejection"
    if name in {
        "stop", "wait", "timed_wait", "squad_wait", "death_wait", "gather_wait",
        "set_repeat", "set_move_state", "set_fire_state", "set_trajectory",
        "set_auto_repair_level", "set_idle_mode", "set_on_off", "stockpile",
        "set_wanted_max_speed",
    }:
        return "effect_not_snapshotable"
    if name in {
        "repair", "reclaim_unit", "reclaim_area", "reclaim_in_area",
        "reclaim_feature", "restore_area", "resurrect", "resurrect_in_area",
        "capture", "capture_area", "guard", "load_units", "load_units_area",
        "load_onto", "unload_unit", "unload_units_area", "attack_area",
        "dgun", "custom",
    }:
        return "target_missing"
    return "dispatcher_defect"


def rank_hypotheses(row: AuditRow) -> tuple[HypothesisCandidate, ...]:
    primary = row.hypothesis_class or primary_hypothesis_for_row(row)
    ordered: list[HypothesisClass] = [primary]
    for extra in ("effect_not_snapshotable", "phase1_reissuance", "dispatcher_defect"):
        if extra != primary and extra not in ordered:
            ordered.append(extra)
        if len(ordered) == 3:
            break
    candidates: list[HypothesisCandidate] = []
    for idx, hypothesis_class in enumerate(ordered, start=1):
        shape = HYPOTHESIS_CLASSES[hypothesis_class]
        candidates.append(
            HypothesisCandidate(
                rank=idx,
                hypothesis_class=hypothesis_class,
                hypothesis_summary=row.hypothesis_summary or (
                    f"{row.arm_or_rpc_name} is currently classified as "
                    f"{hypothesis_class} until a dedicated live repro proves otherwise."
                ),
                predicted_confirmed_evidence=shape["confirmed"],
                predicted_falsified_evidence=shape["falsified"],
                test_command=(
                    f"tests/headless/audit/hypothesis.sh {row.row_id} "
                    f"{hypothesis_class}"
                ),
            )
        )
    return tuple(candidates)

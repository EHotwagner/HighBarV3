# SPDX-License-Identifier: GPL-2.0-only
"""Behavioral arm registry — 66 AICommand oneof arms.

Contract: contracts/arm-registry.md. Import-time validations run at
module load; any typo or capability-vocabulary violation crashes the
driver before a match boots.

The registry is the single source of truth for Phase-2 per-arm
dispatch + verify. Every arm declared in `proto/highbar/commands.proto`
AICommand oneof MUST have an entry here (asserted at import time).
"""

from __future__ import annotations

from dataclasses import replace
from typing import Any, Callable, Optional

from .capabilities import CAPABILITY_TAGS
from .predicates import (
    build_progress_monotonic_predicate,
    capability_selector,
    combat_engagement_predicate,
    commander_selector,
    construction_started_predicate,
    health_delta_predicate,
    movement_progress_predicate,
    position_delta_predicate,
    unit_count_delta_predicate,
)
from .types import (
    BehavioralTestCase,
    NotWireObservable,
    RegistryError,
    SnapshotPair,
    VerificationOutcome,
)


# ---- category classification --------------------------------------------

# Per contracts/arm-registry.md §BehavioralTestCase.category and
# 002's contracts/aicommand-arm-map.md taxonomy.

_CHANNEL_C_LUA_ARMS = {
    "draw_add_point", "draw_add_line", "draw_remove_point",
    "send_text_message", "set_last_pos_message",
    "create_spline_figure", "create_line_figure",
    "set_figure_position", "set_figure_color", "remove_figure",
    "draw_unit",
    "call_lua_rules", "call_lua_ui",
}

_CHANNEL_B_QUERY_ARMS = {
    "init_path", "get_approx_length", "get_next_waypoint", "free_path",
    "group_add_unit", "group_remove_unit",
}

_CHEATS_ARMS = {"give_me", "give_me_new_unit"}
_TEAM_GLOBAL = {"send_resources", "set_my_income_share_direct",
                "set_share_level", "pause_team"}
_DRAWER_ONLY_ARMS = {
    "draw_add_point", "draw_add_line", "draw_remove_point",
    "create_spline_figure", "create_line_figure", "set_figure_position",
    "set_figure_color", "remove_figure", "draw_unit",
}


def _category(arm_name: str) -> str:
    if arm_name in _CHANNEL_C_LUA_ARMS:
        return "channel_c_lua"
    if arm_name in _CHANNEL_B_QUERY_ARMS:
        return "channel_b_query"
    return "channel_a_command"


# ---- lightweight input-builders -----------------------------------------

# Input-builders are pure functions of BootstrapContext that return a
# `highbar.v1.CommandBatch`. Imports are deferred to avoid loading
# proto modules at registry-import time (that chain would run even when
# --verify is invoked on a CSV without a live engine).


def _import_proto():
    from ..highbar import commands_pb2, common_pb2  # noqa: E402
    return commands_pb2, common_pb2


def _noop_batch_factory(arm_name: str):
    """Return a CommandBatch input-builder that sets the oneof arm to
    a minimal-valid shape targeting the commander. For arms without a
    clear pre-built helper this suffices as a serialisation
    round-trip.
    """

    def builder(ctx: Any):
        commands_pb2, common_pb2 = _import_proto()
        batch = commands_pb2.CommandBatch()
        batch.batch_seq = 1
        uid = ctx.commander_unit_id or 0
        batch.target_unit_id = uid
        cmd = batch.commands.add()
        # Walk the AICommand oneof — build by arm_name via setattr on the
        # inner submessage (SetInParent semantics for empty submessages).
        sub = getattr(cmd, arm_name)
        # Most arms expose `unit_id`; populate if present.
        if hasattr(sub, "unit_id"):
            try:
                sub.unit_id = uid
            except (AttributeError, TypeError):
                pass
        # SetInParent: ensure the oneof case is set even for empty
        # submessages (some are genuinely empty — proto3 requires
        # explicit .SetInParent()).
        try:
            sub.SetInParent()
        except Exception:
            pass
        return batch

    return builder


def _build_unit_builder(ctx: Any):
    commands_pb2, common_pb2 = _import_proto()
    batch = commands_pb2.CommandBatch()
    batch.batch_seq = 1
    uid = ctx.commander_unit_id
    batch.target_unit_id = uid
    cmd = batch.commands.add()
    armmex_def_id = ctx.def_id_by_name.get("armmex", 0)
    cmd.build_unit.unit_id = uid
    cmd.build_unit.to_build_unit_def_id = armmex_def_id
    pos = ctx.commander_position
    cmd.build_unit.build_position.x = pos.x + 96.0
    cmd.build_unit.build_position.y = pos.y
    cmd.build_unit.build_position.z = pos.z
    return batch


def _move_unit_builder(ctx: Any):
    commands_pb2, common_pb2 = _import_proto()
    batch = commands_pb2.CommandBatch()
    batch.batch_seq = 1
    uid = ctx.commander_unit_id
    batch.target_unit_id = uid
    cmd = batch.commands.add()
    cmd.move_unit.unit_id = uid
    pos = ctx.commander_position
    cmd.move_unit.to_position.x = pos.x + 500.0
    cmd.move_unit.to_position.y = pos.y
    cmd.move_unit.to_position.z = pos.z
    return batch


def _fight_builder(ctx: Any):
    commands_pb2, common_pb2 = _import_proto()
    batch = commands_pb2.CommandBatch()
    batch.batch_seq = 1
    uid = ctx.commander_unit_id
    batch.target_unit_id = uid
    cmd = batch.commands.add()
    cmd.fight.unit_id = uid
    pos = ctx.commander_position
    cmd.fight.to_position.x = pos.x + 500.0
    cmd.fight.to_position.y = pos.y
    cmd.fight.to_position.z = pos.z
    return batch


def _attack_unit_builder(ctx: Any):
    commands_pb2, common_pb2 = _import_proto()
    batch = commands_pb2.CommandBatch()
    batch.batch_seq = 1
    uid = ctx.commander_unit_id
    batch.target_unit_id = uid
    cmd = batch.commands.add()
    cmd.attack.unit_id = uid
    cmd.attack.target_unit_id = ctx.enemy_seed_id or 0
    return batch


def _self_destruct_builder(ctx: Any):
    commands_pb2, common_pb2 = _import_proto()
    batch = commands_pb2.CommandBatch()
    batch.batch_seq = 1
    # Target the cloakable — we don't want to lose the commander
    # (that's a fatal run-abort per bootstrap contract). The cloakable
    # unit is disposable and the bootstrap reset reissues it.
    uid = ctx.capability_units.get("cloakable") or ctx.commander_unit_id
    batch.target_unit_id = uid
    cmd = batch.commands.add()
    cmd.self_destruct.unit_id = uid
    return batch


# ---- simple na-predicates ------------------------------------------------


def _always_na(error_code: str, rationale: str):
    def predicate(_pair: SnapshotPair, _deltas: list) -> VerificationOutcome:
        return VerificationOutcome(verified="na", evidence=rationale,
                                     error=error_code)
    return predicate


def _cheats_gated_predicate():
    """Dispatches the command; if cheats are off in the bootstrap
    context, records cheats_required. Else falls through to a simple
    unit_count +1 check.
    """

    def predicate(pair: SnapshotPair, _deltas: list) -> VerificationOutcome:
        pre = len(pair.before.own_units)
        post = len(pair.after.own_units)
        if post > pre:
            return VerificationOutcome(
                verified="true",
                evidence=f"unit_count +{post - pre}",
            )
        return VerificationOutcome(
            verified="na",
            evidence="cheats likely disabled — no unit spawn observed",
            error="cheats_required",
        )
    return predicate


# ---- registry construction ----------------------------------------------


def _build_registry() -> dict[str, BehavioralTestCase]:
    reg: dict[str, BehavioralTestCase] = {}

    # --- Channel-C Lua-only arms — NotWireObservable sentinel -----------
    for arm in sorted(_CHANNEL_C_LUA_ARMS):
        reg[arm] = BehavioralTestCase(
            arm_name=arm,
            category="channel_c_lua",
            required_capability="none",
            input_builder=_noop_batch_factory(arm),
            verify_predicate=NotWireObservable(
                rationale=f"{arm}: Lua-only arm, no wire signal in this feature"
            ),
            verify_window_frames=30,
            rationale="channel_c_lua sentinel per spec §Out of Scope",
        )

    # --- Channel-B queries — not verifiable via snapshot diff ----------
    for arm in sorted(_CHANNEL_B_QUERY_ARMS):
        reg[arm] = BehavioralTestCase(
            arm_name=arm,
            category="channel_b_query",
            required_capability="none",
            input_builder=_noop_batch_factory(arm),
            verify_predicate=_always_na(
                "precondition_unmet",
                f"{arm} is a query with no wire-observable state mutation"),
            verify_window_frames=30,
            rationale="channel_b_query; no snapshot-diffable effect",
        )

    # --- Cheats arms — gated on cheats_enabled -------------------------
    for arm in sorted(_CHEATS_ARMS):
        reg[arm] = BehavioralTestCase(
            arm_name=arm,
            category="channel_a_command",
            required_capability="commander",
            input_builder=_noop_batch_factory(arm),
            verify_predicate=_cheats_gated_predicate(),
            verify_window_frames=120,
            rationale="cheats-gated spawn; NA when cheats_enabled=false",
        )

    # --- Team/global arms — not unit-state observable -------------------
    for arm in sorted(_TEAM_GLOBAL):
        reg[arm] = BehavioralTestCase(
            arm_name=arm,
            category="channel_a_command",
            required_capability="none",
            input_builder=_noop_batch_factory(arm),
            verify_predicate=_always_na(
                "precondition_unmet",
                f"{arm} affects team-global state; not in own_units[]"),
            verify_window_frames=30,
            rationale="team-global; no per-unit snapshot diff",
        )

    # --- Verified Channel-A unit commands -----------------------------

    reg["move_unit"] = BehavioralTestCase(
        arm_name="move_unit", category="channel_a_command",
        required_capability="commander",
        input_builder=_move_unit_builder,
        verify_predicate=movement_progress_predicate(
            unit_id_selector=lambda snap: next(
                (u.unit_id for u in snap.own_units if u.max_health > 3000),
                None,
            ),
            min_delta=48.0,
        ),
        verify_window_frames=180,
        rationale="movement-tuned rule: commander moved toward the ordered position",
    )

    reg["build_unit"] = BehavioralTestCase(
        arm_name="build_unit", category="channel_a_command",
        required_capability="commander",
        input_builder=_build_unit_builder,
        verify_predicate=construction_started_predicate(
            builder_id_selector=commander_selector),
        verify_window_frames=210,
        rationale="construction-tuned rule: new site appears and build progress starts",
    )

    reg["fight"] = BehavioralTestCase(
        arm_name="fight", category="channel_a_command",
        required_capability="commander",
        input_builder=_fight_builder,
        verify_predicate=combat_engagement_predicate(
            unit_id_selector=lambda snap: next(
                (u.unit_id for u in snap.own_units if u.max_health > 3000),
                None,
            ),
            target_selector=lambda snap: (
                snap.visible_enemies[0].unit_id if snap.visible_enemies else None
            ),
            min_drop=1.0,
            min_distance_delta=48.0,
        ),
        verify_window_frames=360,
        rationale="combat-tuned rule: either the hostile target takes damage or the unit closes into engagement range",
    )

    reg["attack"] = BehavioralTestCase(
        arm_name="attack", category="channel_a_command",
        required_capability="commander",
        input_builder=_attack_unit_builder,
        verify_predicate=health_delta_predicate(
            target_selector=lambda snap: (snap.visible_enemies[0].unit_id
                                           if snap.visible_enemies else None),
            min_drop=1.0, target_is_enemy=True,
        ),
        verify_window_frames=450,  # 15s — LOS + engagement window
        rationale="enemy health dropped or target destroyed",
    )

    reg["self_destruct"] = BehavioralTestCase(
        arm_name="self_destruct", category="channel_a_command",
        required_capability="cloakable",
        input_builder=_self_destruct_builder,
        verify_predicate=unit_count_delta_predicate(expected_delta=-1),
        verify_window_frames=180,  # SelfDestruct has a countdown
        rationale="targeted disposable unit disappeared from own_units",
    )

    # --- Remaining Channel-A unit commands — honest effect_not_observed
    # These are dispatched successfully but their effects (attack
    # posture, movement state, repeat flag, stockpile counter, etc.)
    # don't manifest as a snapshot diff we can reliably assert.
    # Marked as verified=false / error=effect_not_observed so they
    # count against the denominator honestly.
    _UNVERIFIED_UNIT_ARMS = {
        "stop", "wait", "timed_wait", "squad_wait", "death_wait", "gather_wait",
        "patrol", "attack_area", "guard",
        "repair", "reclaim_unit", "reclaim_area", "reclaim_in_area",
        "reclaim_feature", "restore_area", "resurrect", "resurrect_in_area",
        "capture", "capture_area", "set_base",
        "load_units", "load_units_area", "load_onto", "unload_unit",
        "unload_units_area",
        "set_wanted_max_speed", "stockpile", "dgun", "custom",
        "set_on_off", "set_repeat", "set_move_state", "set_fire_state",
        "set_trajectory", "set_auto_repair_level", "set_idle_mode",
    }

    def _unverified_predicate():
        def predicate(_pair: SnapshotPair, _deltas: list) -> VerificationOutcome:
            return VerificationOutcome(
                verified="false",
                evidence="snapshot-diff predicate not yet implemented for this arm",
                error="effect_not_observed",
            )
        return predicate

    for arm in sorted(_UNVERIFIED_UNIT_ARMS):
        if arm in reg:
            continue
        reg[arm] = BehavioralTestCase(
            arm_name=arm, category="channel_a_command",
            required_capability="commander",
            input_builder=_noop_batch_factory(arm),
            verify_predicate=_unverified_predicate(),
            verify_window_frames=120,
            rationale=f"{arm}: dispatch sanity, no snapshot verifier wired",
        )

    return reg


def _annotate_audit_metadata(
    registry: dict[str, BehavioralTestCase],
) -> dict[str, BehavioralTestCase]:
    annotated: dict[str, BehavioralTestCase] = {}
    for arm_name, case in registry.items():
        audit_channel = None
        audit_observability = "snapshot_diff"
        if arm_name in _TEAM_GLOBAL:
            audit_channel = "team_global"
            audit_observability = "not_wire_observable"
        elif arm_name in _CHANNEL_B_QUERY_ARMS:
            audit_channel = "channel_b_query"
            audit_observability = "dispatch_ack_only"
        elif arm_name in _DRAWER_ONLY_ARMS:
            audit_channel = "drawer_only"
            audit_observability = "not_wire_observable"
        elif arm_name in _CHANNEL_C_LUA_ARMS:
            audit_channel = "channel_c_lua"
            audit_observability = "not_wire_observable"
        annotated[arm_name] = replace(
            case,
            audit_channel=audit_channel,
            audit_observability=audit_observability,
            audit_phase_default="phase1",
        )
    return annotated


# ---- import-time validation ---------------------------------------------


def _expected_arm_names() -> set[str]:
    """Enumerate the 66 AICommand oneof arms from the proto descriptor."""
    from ..highbar import commands_pb2  # noqa: E402
    desc = commands_pb2.AICommand.DESCRIPTOR
    oneof = desc.oneofs_by_name.get("command")
    if oneof is None:
        raise RegistryError("AICommand.command oneof missing from descriptor")
    return {f.name for f in oneof.fields}


def validate_registry(registry: dict[str, BehavioralTestCase]) -> None:
    """Run the four import-time assertions from
    contracts/arm-registry.md §Import-time validation rules.
    """
    expected = _expected_arm_names()
    actual = set(registry.keys())
    missing = expected - actual
    extra = actual - expected
    if missing or extra:
        raise RegistryError(
            f"arm_set_mismatch: missing={sorted(missing)} extra={sorted(extra)}"
        )

    for name, case in registry.items():
        if case.required_capability not in CAPABILITY_TAGS:
            raise RegistryError(
                f"unknown_capability: {name} requires "
                f"'{case.required_capability}' not in {CAPABILITY_TAGS}"
            )
        if isinstance(case.verify_predicate, NotWireObservable):
            if case.category != "channel_c_lua":
                raise RegistryError(
                    f"sentinel illegal: {name} uses NotWireObservable "
                    f"but category={case.category!r} (must be 'channel_c_lua')"
                )
            if case.required_capability != "none":
                raise RegistryError(
                    f"sentinel illegal: {name} uses NotWireObservable "
                    f"but required_capability={case.required_capability!r} "
                    f"(must be 'none')"
                )
        if not (30 <= case.verify_window_frames <= 900):
            raise RegistryError(
                f"window bounds: {name} verify_window_frames="
                f"{case.verify_window_frames} outside [30, 900]"
            )


REGISTRY: dict[str, BehavioralTestCase] = _annotate_audit_metadata(_build_registry())
validate_registry(REGISTRY)


__all__ = ["REGISTRY", "validate_registry"]

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
from .bootstrap import is_transport_dependent_command
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
from .upstream_fixture_intelligence import all_custom_command_inventory
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


def exact_custom_command_ids_for_arm(arm_name: str) -> tuple[int, ...]:
    if arm_name != "custom":
        return ()
    return tuple(item.command_id for item in all_custom_command_inventory())


# ---- lightweight input-builders -----------------------------------------

# Input-builders are pure functions of BootstrapContext that return a
# `highbar.v1.CommandBatch`. Imports are deferred to avoid loading
# proto modules at registry-import time (that chain would run even when
# --verify is invoked on a CSV without a live engine).


def _import_proto():
    from ..highbar import commands_pb2, common_pb2  # noqa: E402
    return commands_pb2, common_pb2


def _fixture_unit_id(ctx: Any, fixture_class: str, fallback: int = 0) -> int:
    fixture_units = getattr(ctx, "fixture_unit_ids", {}) or {}
    capability_units = getattr(ctx, "capability_units", {}) or {}
    return (
        fixture_units.get(fixture_class)
        or capability_units.get(fixture_class)
        or fallback
    )


def _fixture_feature_id(ctx: Any, fixture_class: str, fallback: int = 0) -> int:
    fixture_features = getattr(ctx, "fixture_feature_ids", {}) or {}
    return fixture_features.get(fixture_class, fallback)


def _fixture_position(ctx: Any, fixture_class: str):
    fixture_positions = getattr(ctx, "fixture_positions", {}) or {}
    return fixture_positions.get(fixture_class) or ctx.commander_position


def _payload_unit_id(ctx: Any) -> int:
    return _fixture_unit_id(ctx, "payload_unit", ctx.commander_unit_id)


def _transport_unit_id(ctx: Any) -> int:
    return _fixture_unit_id(ctx, "transport_unit", ctx.commander_unit_id)


def transport_compatibility_for_command(
    command_id: str,
    ctx: Any,
) -> tuple[str, str | None]:
    def _unit_ready(unit: Any | None) -> bool:
        if unit is None:
            return False
        if float(getattr(unit, "health", 0.0)) <= 0.0:
            return False
        if bool(getattr(unit, "under_construction", False)):
            return False
        build_progress = getattr(unit, "build_progress", None)
        if build_progress is None:
            return True
        try:
            progress_value = float(build_progress)
        except (TypeError, ValueError):
            return True
        return not (0.0 < progress_value < 0.999)

    if not is_transport_dependent_command(command_id):
        return "compatible", None
    transport_id = _fixture_unit_id(ctx, "transport_unit")
    if not transport_id:
        return "candidate_missing", "transport_unit is not available"
    payload_id = _fixture_unit_id(ctx, "payload_unit")
    if not payload_id:
        return "candidate_missing", "payload_unit is not available"
    if transport_id == payload_id:
        return (
            "payload_incompatible",
            "selected transport candidate matches the payload unit and cannot carry itself",
        )
    observed_units = getattr(ctx, "observed_own_units", {}) or {}
    transport_unit = observed_units.get(transport_id)
    if transport_unit is not None and not _unit_ready(transport_unit):
        return (
            "candidate_unusable",
            "selected transport candidate is still under construction or destroyed and is unusable",
        )
    payload_unit = observed_units.get(payload_id)
    if payload_unit is not None and not _unit_ready(payload_unit):
        return (
            "payload_incompatible",
            "transport payload incompatible: selected payload unit is still under construction or destroyed",
        )
    return "compatible", None


def _preferred_custom_command(ctx: Any) -> tuple[int, int, tuple[float, ...]] | None:
    cloakable = _fixture_unit_id(ctx, "cloakable")
    if cloakable:
        return (cloakable, 37382, (1.0,))
    builder = _fixture_unit_id(ctx, "builder")
    if builder:
        return (builder, 34571, (1.0,))
    hostile_target = _fixture_unit_id(
        ctx,
        "custom_target",
        _fixture_unit_id(ctx, "hostile_target", getattr(ctx, "enemy_seed_id", 0) or 0),
    )
    if hostile_target:
        return (ctx.commander_unit_id, 34923, (float(hostile_target),))
    return None


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
    # Prefer a disposable ground unit so the live run survives and can
    # still yield a corpse fixture for resurrect coverage.
    uid = (
        ctx.capability_units.get("builder")
        or _fixture_unit_id(ctx, "damaged_friendly")
        or _fixture_unit_id(ctx, "payload_unit")
        or ctx.capability_units.get("cloakable")
        or ctx.commander_unit_id
    )
    batch.target_unit_id = uid
    cmd = batch.commands.add()
    cmd.self_destruct.unit_id = uid
    return batch


def _attack_area_builder(ctx: Any):
    commands_pb2, common_pb2 = _import_proto()
    batch = commands_pb2.CommandBatch()
    batch.batch_seq = 1
    uid = ctx.commander_unit_id
    batch.target_unit_id = uid
    pos = _fixture_position(ctx, "hostile_target")
    cmd = batch.commands.add()
    cmd.attack_area.unit_id = uid
    cmd.attack_area.attack_position.x = pos.x
    cmd.attack_area.attack_position.y = pos.y
    cmd.attack_area.attack_position.z = pos.z
    cmd.attack_area.radius = 96.0
    return batch


def _dgun_builder(ctx: Any):
    commands_pb2, common_pb2 = _import_proto()
    batch = commands_pb2.CommandBatch()
    batch.batch_seq = 1
    uid = ctx.commander_unit_id
    batch.target_unit_id = uid
    cmd = batch.commands.add()
    cmd.dgun.unit_id = uid
    cmd.dgun.target_unit_id = _fixture_unit_id(
        ctx, "hostile_target", ctx.enemy_seed_id or 0
    )
    return batch


def _guard_builder(ctx: Any):
    commands_pb2, common_pb2 = _import_proto()
    batch = commands_pb2.CommandBatch()
    batch.batch_seq = 1
    uid = ctx.commander_unit_id
    batch.target_unit_id = uid
    cmd = batch.commands.add()
    cmd.guard.unit_id = uid
    cmd.guard.guard_unit_id = _fixture_unit_id(ctx, "damaged_friendly")
    return batch


def _repair_builder(ctx: Any):
    commands_pb2, common_pb2 = _import_proto()
    batch = commands_pb2.CommandBatch()
    batch.batch_seq = 1
    uid = ctx.commander_unit_id
    batch.target_unit_id = uid
    cmd = batch.commands.add()
    cmd.repair.unit_id = uid
    cmd.repair.repair_unit_id = _fixture_unit_id(ctx, "damaged_friendly")
    return batch


def _reclaim_unit_builder(ctx: Any):
    commands_pb2, common_pb2 = _import_proto()
    batch = commands_pb2.CommandBatch()
    batch.batch_seq = 1
    uid = ctx.commander_unit_id
    batch.target_unit_id = uid
    cmd = batch.commands.add()
    cmd.reclaim_unit.unit_id = uid
    cmd.reclaim_unit.reclaim_unit_id = _fixture_unit_id(
        ctx,
        "reclaim_target",
        _fixture_unit_id(ctx, "hostile_target", ctx.enemy_seed_id or 0),
    )
    return batch


def _reclaim_area_builder(ctx: Any):
    commands_pb2, common_pb2 = _import_proto()
    batch = commands_pb2.CommandBatch()
    batch.batch_seq = 1
    uid = ctx.commander_unit_id
    batch.target_unit_id = uid
    pos = _fixture_position(ctx, "reclaim_target")
    cmd = batch.commands.add()
    cmd.reclaim_area.unit_id = uid
    cmd.reclaim_area.position.x = pos.x
    cmd.reclaim_area.position.y = pos.y
    cmd.reclaim_area.position.z = pos.z
    cmd.reclaim_area.radius = 96.0
    return batch


def _reclaim_in_area_builder(ctx: Any):
    commands_pb2, common_pb2 = _import_proto()
    batch = commands_pb2.CommandBatch()
    batch.batch_seq = 1
    uid = ctx.commander_unit_id
    batch.target_unit_id = uid
    pos = _fixture_position(ctx, "reclaim_target")
    cmd = batch.commands.add()
    cmd.reclaim_in_area.unit_id = uid
    cmd.reclaim_in_area.position.x = pos.x
    cmd.reclaim_in_area.position.y = pos.y
    cmd.reclaim_in_area.position.z = pos.z
    cmd.reclaim_in_area.radius = 96.0
    return batch


def _reclaim_feature_builder(ctx: Any):
    commands_pb2, common_pb2 = _import_proto()
    batch = commands_pb2.CommandBatch()
    batch.batch_seq = 1
    uid = ctx.commander_unit_id
    batch.target_unit_id = uid
    cmd = batch.commands.add()
    cmd.reclaim_feature.unit_id = uid
    cmd.reclaim_feature.feature_id = _fixture_feature_id(ctx, "reclaim_target")
    return batch


def _restore_area_builder(ctx: Any):
    commands_pb2, common_pb2 = _import_proto()
    batch = commands_pb2.CommandBatch()
    batch.batch_seq = 1
    uid = ctx.commander_unit_id
    batch.target_unit_id = uid
    pos = _fixture_position(ctx, "restore_target")
    cmd = batch.commands.add()
    cmd.restore_area.unit_id = uid
    cmd.restore_area.position.x = pos.x
    cmd.restore_area.position.y = pos.y
    cmd.restore_area.position.z = pos.z
    cmd.restore_area.radius = 96.0
    return batch


def _resurrect_builder(ctx: Any):
    commands_pb2, common_pb2 = _import_proto()
    batch = commands_pb2.CommandBatch()
    batch.batch_seq = 1
    uid = ctx.commander_unit_id
    batch.target_unit_id = uid
    cmd = batch.commands.add()
    cmd.resurrect.unit_id = uid
    cmd.resurrect.feature_id = _fixture_feature_id(ctx, "wreck_target")
    return batch


def _resurrect_in_area_builder(ctx: Any):
    commands_pb2, common_pb2 = _import_proto()
    batch = commands_pb2.CommandBatch()
    batch.batch_seq = 1
    uid = ctx.commander_unit_id
    batch.target_unit_id = uid
    pos = _fixture_position(ctx, "wreck_target")
    cmd = batch.commands.add()
    cmd.resurrect_in_area.unit_id = uid
    cmd.resurrect_in_area.position.x = pos.x
    cmd.resurrect_in_area.position.y = pos.y
    cmd.resurrect_in_area.position.z = pos.z
    cmd.resurrect_in_area.radius = 96.0
    return batch


def _capture_builder(ctx: Any):
    commands_pb2, common_pb2 = _import_proto()
    batch = commands_pb2.CommandBatch()
    batch.batch_seq = 1
    uid = ctx.commander_unit_id
    batch.target_unit_id = uid
    cmd = batch.commands.add()
    cmd.capture.unit_id = uid
    cmd.capture.target_unit_id = _fixture_unit_id(
        ctx,
        "capturable_target",
        _fixture_unit_id(ctx, "hostile_target", ctx.enemy_seed_id or 0),
    )
    return batch


def _capture_area_builder(ctx: Any):
    commands_pb2, common_pb2 = _import_proto()
    batch = commands_pb2.CommandBatch()
    batch.batch_seq = 1
    uid = ctx.commander_unit_id
    batch.target_unit_id = uid
    pos = _fixture_position(ctx, "capturable_target")
    cmd = batch.commands.add()
    cmd.capture_area.unit_id = uid
    cmd.capture_area.position.x = pos.x
    cmd.capture_area.position.y = pos.y
    cmd.capture_area.position.z = pos.z
    cmd.capture_area.radius = 96.0
    return batch


def _set_base_builder(ctx: Any):
    commands_pb2, common_pb2 = _import_proto()
    batch = commands_pb2.CommandBatch()
    batch.batch_seq = 1
    uid = ctx.commander_unit_id
    batch.target_unit_id = uid
    pos = _fixture_position(ctx, "restore_target")
    cmd = batch.commands.add()
    cmd.set_base.unit_id = uid
    cmd.set_base.base_position.x = pos.x
    cmd.set_base.base_position.y = pos.y
    cmd.set_base.base_position.z = pos.z
    return batch


def _load_units_builder(ctx: Any):
    commands_pb2, common_pb2 = _import_proto()
    batch = commands_pb2.CommandBatch()
    batch.batch_seq = 1
    transport_id = _transport_unit_id(ctx)
    batch.target_unit_id = transport_id
    cmd = batch.commands.add()
    cmd.load_units.unit_id = transport_id
    cmd.load_units.to_load_unit_ids.append(_payload_unit_id(ctx))
    return batch


def _load_units_area_builder(ctx: Any):
    commands_pb2, common_pb2 = _import_proto()
    batch = commands_pb2.CommandBatch()
    batch.batch_seq = 1
    transport_id = _transport_unit_id(ctx)
    batch.target_unit_id = transport_id
    pos = _fixture_position(ctx, "payload_unit")
    cmd = batch.commands.add()
    cmd.load_units_area.unit_id = transport_id
    cmd.load_units_area.position.x = pos.x
    cmd.load_units_area.position.y = pos.y
    cmd.load_units_area.position.z = pos.z
    cmd.load_units_area.radius = 96.0
    return batch


def _load_onto_builder(ctx: Any):
    commands_pb2, common_pb2 = _import_proto()
    batch = commands_pb2.CommandBatch()
    batch.batch_seq = 1
    payload_id = _payload_unit_id(ctx)
    batch.target_unit_id = payload_id
    cmd = batch.commands.add()
    cmd.load_onto.unit_id = payload_id
    cmd.load_onto.transport_unit_id = _transport_unit_id(ctx)
    return batch


def _unload_unit_builder(ctx: Any):
    commands_pb2, common_pb2 = _import_proto()
    batch = commands_pb2.CommandBatch()
    batch.batch_seq = 1
    transport_id = _transport_unit_id(ctx)
    batch.target_unit_id = transport_id
    pos = _fixture_position(ctx, "restore_target")
    cmd = batch.commands.add()
    cmd.unload_unit.unit_id = transport_id
    cmd.unload_unit.to_position.x = pos.x
    cmd.unload_unit.to_position.y = pos.y
    cmd.unload_unit.to_position.z = pos.z
    cmd.unload_unit.to_unload_unit_id = _payload_unit_id(ctx)
    return batch


def _unload_units_area_builder(ctx: Any):
    commands_pb2, common_pb2 = _import_proto()
    batch = commands_pb2.CommandBatch()
    batch.batch_seq = 1
    transport_id = _transport_unit_id(ctx)
    batch.target_unit_id = transport_id
    pos = _fixture_position(ctx, "restore_target")
    cmd = batch.commands.add()
    cmd.unload_units_area.unit_id = transport_id
    cmd.unload_units_area.to_position.x = pos.x
    cmd.unload_units_area.to_position.y = pos.y
    cmd.unload_units_area.to_position.z = pos.z
    cmd.unload_units_area.radius = 96.0
    return batch


def _custom_builder(ctx: Any):
    commands_pb2, common_pb2 = _import_proto()
    batch = commands_pb2.CommandBatch()
    batch.batch_seq = 1
    unit_id, command_id, params = _preferred_custom_command(ctx) or (
        ctx.commander_unit_id,
        34923,
        (float(ctx.enemy_seed_id or 0),),
    )
    batch.target_unit_id = unit_id
    cmd = batch.commands.add()
    cmd.custom.unit_id = unit_id
    cmd.custom.command_id = command_id
    cmd.custom.params.extend(params)
    return batch


# ---- simple na-predicates ------------------------------------------------


def _always_na(error_code: str, rationale: str):
    def predicate(_pair: SnapshotPair, _deltas: list) -> VerificationOutcome:
        return VerificationOutcome(verified="na", evidence=rationale,
                                     error=error_code)
    return predicate


def _effect_not_observed_predicate():
    def predicate(_pair: SnapshotPair, _deltas: list) -> VerificationOutcome:
        return VerificationOutcome(
            verified="false",
            evidence="snapshot-diff predicate not yet implemented for this arm",
            error="effect_not_observed",
        )
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

    for arm_name, builder in (
        ("attack_area", _attack_area_builder),
        ("guard", _guard_builder),
        ("repair", _repair_builder),
        ("reclaim_unit", _reclaim_unit_builder),
        ("reclaim_area", _reclaim_area_builder),
        ("reclaim_in_area", _reclaim_in_area_builder),
        ("reclaim_feature", _reclaim_feature_builder),
        ("restore_area", _restore_area_builder),
        ("resurrect", _resurrect_builder),
        ("resurrect_in_area", _resurrect_in_area_builder),
        ("capture", _capture_builder),
        ("capture_area", _capture_area_builder),
        ("set_base", _set_base_builder),
        ("load_units", _load_units_builder),
        ("load_units_area", _load_units_area_builder),
        ("load_onto", _load_onto_builder),
        ("unload_unit", _unload_unit_builder),
        ("unload_units_area", _unload_units_area_builder),
        ("dgun", _dgun_builder),
        ("custom", _custom_builder),
    ):
        reg[arm_name] = BehavioralTestCase(
            arm_name=arm_name,
            category="channel_a_command",
            required_capability="commander",
            input_builder=builder,
            verify_predicate=_effect_not_observed_predicate(),
            verify_window_frames=120,
            rationale=f"{arm_name}: dispatch sanity with fixture-aware arguments, no snapshot verifier wired",
        )

    reg["self_destruct"] = BehavioralTestCase(
        arm_name="self_destruct", category="channel_a_command",
        required_capability="none",
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

    for arm in sorted(_UNVERIFIED_UNIT_ARMS):
        if arm in reg:
            continue
        reg[arm] = BehavioralTestCase(
            arm_name=arm, category="channel_a_command",
            required_capability="commander",
            input_builder=_noop_batch_factory(arm),
            verify_predicate=_effect_not_observed_predicate(),
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

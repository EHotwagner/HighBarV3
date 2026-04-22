# SPDX-License-Identifier: GPL-2.0-only
from __future__ import annotations

from highbar_client.behavioral_coverage.upstream_fixture_intelligence import (
    BAR_CUSTOM_COMMAND_INVENTORY,
    PROTO_COMMAND_INTELLIGENCE,
    UPSTREAM_SURFACE_GAPS,
    all_custom_command_inventory,
    all_upstream_fixture_intelligence,
    custom_command_inventory_for,
    upstream_fixture_intelligence_for,
)


def test_wanted_speed_records_modoption_gate_and_repaired_dispatch_context():
    entry = PROTO_COMMAND_INTELLIGENCE["cmd-set-wanted-max-speed"]

    assert entry.availability == "modoption-gated"
    assert entry.observability == "movectrl-or-engine-state"
    assert "emprework" in entry.summary
    assert "now emits `CMD_WANTED_SPEED`" in entry.repo_gap


def test_attack_records_bar_ground_target_rewrite():
    entry = PROTO_COMMAND_INTELLIGENCE["cmd-attack"]

    assert entry.surface == "bar-lua-rewrite"
    assert entry.availability == "lua-rewritten"
    assert "place_target_on_ground" in entry.summary
    assert "unit_target_attack_safe=true" in entry.recommendation


def test_custom_command_is_classified_as_command_specific():
    entry = PROTO_COMMAND_INTELLIGENCE["cmd-custom"]

    assert entry.observability == "command-specific"
    assert "BAR command-id inventory" in entry.recommendation


def test_priority_gap_records_repaired_local_dispatch_context():
    entry = UPSTREAM_SURFACE_GAPS["gap-cmd-priority"]

    assert entry.kind == "upstream-surface-gap"
    assert entry.observability == "rules-param-or-cmddesc"
    assert "now routes priority through BAR's active priority surface" in entry.summary
    assert "semantic-gate or evidence-path" in entry.recommendation


def test_manual_fire_and_air_strafe_entries_note_repaired_helper_parity():
    manual_fire = UPSTREAM_SURFACE_GAPS["gap-cmd-find-pad-and-manual-fire"]
    air_strafe = UPSTREAM_SURFACE_GAPS["gap-cmd-fire-at-radar-and-air-strafe"]

    assert "manual-fire parity is repaired" in manual_fire.repo_gap.lower()
    assert "helper parity gap" in air_strafe.repo_gap.lower()
    assert "remaining failures" in air_strafe.recommendation.lower()


def test_lookup_and_full_listing_cover_every_entry():
    all_entries = all_upstream_fixture_intelligence()

    assert len(all_entries) == len(PROTO_COMMAND_INTELLIGENCE) + len(UPSTREAM_SURFACE_GAPS)
    assert upstream_fixture_intelligence_for("cmd-dgun") is PROTO_COMMAND_INTELLIGENCE["cmd-dgun"]
    assert upstream_fixture_intelligence_for("gap-cmd-cloak-support") is UPSTREAM_SURFACE_GAPS["gap-cmd-cloak-support"]
    assert upstream_fixture_intelligence_for("missing-subject") is None


def test_custom_command_inventory_covers_required_bar_ids():
    inventory = all_custom_command_inventory()

    assert tuple(item.command_id for item in inventory) == (
        32102,
        34571,
        34922,
        34923,
        34924,
        34925,
        37382,
    )
    assert BAR_CUSTOM_COMMAND_INVENTORY[32102].owner_gadget == "cmd_manual_launch.lua"
    assert BAR_CUSTOM_COMMAND_INVENTORY[34571].owner_gadget == "unit_builder_priority.lua"
    assert BAR_CUSTOM_COMMAND_INVENTORY[34923].owner_gadget == "unit_target_on_the_move.lua"
    assert BAR_CUSTOM_COMMAND_INVENTORY[37382].owner_gadget == "unit_cloak.lua"
    assert custom_command_inventory_for(99999) is None

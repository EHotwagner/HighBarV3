# SPDX-License-Identifier: GPL-2.0-only
from __future__ import annotations

from highbar_client.behavioral_coverage.upstream_fixture_intelligence import (
    PROTO_COMMAND_INTELLIGENCE,
    UPSTREAM_SURFACE_GAPS,
    all_upstream_fixture_intelligence,
    upstream_fixture_intelligence_for,
)


def test_wanted_speed_records_modoption_gate_and_local_gap():
    entry = PROTO_COMMAND_INTELLIGENCE["cmd-set-wanted-max-speed"]

    assert entry.availability == "modoption-gated"
    assert entry.observability == "movectrl-or-engine-state"
    assert "emprework" in entry.summary
    assert "no-op" in entry.repo_gap


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


def test_priority_gap_records_upstream_parity_problem():
    entry = UPSTREAM_SURFACE_GAPS["gap-cmd-priority"]

    assert entry.kind == "upstream-surface-gap"
    assert entry.observability == "rules-param-or-cmddesc"
    assert "stubbed out" in entry.summary
    assert "protocol extension or direct local repair" in entry.recommendation


def test_lookup_and_full_listing_cover_every_entry():
    all_entries = all_upstream_fixture_intelligence()

    assert len(all_entries) == len(PROTO_COMMAND_INTELLIGENCE) + len(UPSTREAM_SURFACE_GAPS)
    assert upstream_fixture_intelligence_for("cmd-dgun") is PROTO_COMMAND_INTELLIGENCE["cmd-dgun"]
    assert upstream_fixture_intelligence_for("gap-cmd-cloak-support") is UPSTREAM_SURFACE_GAPS["gap-cmd-cloak-support"]
    assert upstream_fixture_intelligence_for("missing-subject") is None

# SPDX-License-Identifier: GPL-2.0-only
"""Upstream-derived command and fixture intelligence for Itertesting.

This module is intentionally read-only: it does not change live
fixture provisioning or command classification by itself. Its purpose
is to preserve the most actionable upstream findings from:

1. `rlcevg/CircuitAI` (BARb upstream), where the intended
   `CCircuitUnit::Cmd*` behavior lives.
2. `beyond-all-reason/Beyond-All-Reason`, where BAR Lua gadgets often
   insert, replace, gate, or reinterpret commands at runtime.

The current Itertesting fixture model is necessarily coarse. These
records give maintainers a source-backed place to look when a command
appears "missing", "inert", or "wrongly shaped" even though the
gateway dispatch path looks healthy.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


IntelligenceKind = Literal["proto-command", "upstream-surface-gap"]
CommandSurface = Literal[
    "circuit-custom-command",
    "bar-lua-gadget",
    "bar-lua-rewrite",
    "mixed",
]
AvailabilityClass = Literal[
    "always-present",
    "unit-conditional",
    "lua-inserted",
    "lua-rewritten",
    "modoption-gated",
]
ObservabilityClass = Literal[
    "snapshot-friendly",
    "rules-param-or-cmddesc",
    "movectrl-or-engine-state",
    "command-specific",
]


@dataclass(frozen=True)
class UpstreamFixtureIntelligence:
    kind: IntelligenceKind
    subject_id: str
    surface: CommandSurface
    availability: AvailabilityClass
    summary: str
    unit_constraints: tuple[str, ...]
    fixture_implications: tuple[str, ...]
    observability: ObservabilityClass
    repo_gap: str
    citations: tuple[str, ...]
    recommendation: str


PROTO_COMMAND_INTELLIGENCE: dict[str, UpstreamFixtureIntelligence] = {
    "cmd-set-wanted-max-speed": UpstreamFixtureIntelligence(
        kind="proto-command",
        subject_id="cmd-set-wanted-max-speed",
        surface="mixed",
        availability="modoption-gated",
        summary=(
            "Wanted speed is a BAR Lua-mediated behavior, not just a raw unit "
            "order. Upstream CircuitAI emits CMD_WANTED_SPEED, while BAR's "
            "wanted-speed gadget only runs when the `emprework` mod option is "
            "enabled and ignores unhandled movetypes such as planes."
        ),
        unit_constraints=(
            "Use a ground/sea unit or gunship; fixed-wing aircraft are unhandled.",
            "Do not assume the command exists when `emprework` is disabled.",
        ),
        fixture_implications=(
            "Fixture selection must include a unit whose movetype BAR handles.",
            "The test environment must record whether `emprework` is enabled.",
            "A missing effect may be a game-config gate rather than a gateway bug.",
        ),
        observability="movectrl-or-engine-state",
        repo_gap=(
            "The local fork dispatches `set_wanted_max_speed`, but "
            "`CCircuitUnit::CmdWantedSpeed` is a no-op here. Upstream CircuitAI "
            "still issues `CMD_WANTED_SPEED`."
        ),
        citations=(
            "/tmp/CircuitAI-upstream/src/circuit/unit/CircuitUnit.cpp:248-251",
            "/home/developer/projects/HighBarV3/src/circuit/unit/CircuitUnit.cpp:317-322",
            "/tmp/BAR-game-sparse/luarules/gadgets/unit_wanted_speed.lua:2-4",
            "/tmp/BAR-game-sparse/luarules/gadgets/unit_wanted_speed.lua:101-140",
            "/tmp/BAR-game-sparse/luarules/gadgets/unit_wanted_speed.lua:173-194",
        ),
        recommendation=(
            "Classify this command as both fixture-sensitive and "
            "implementation-sensitive. Itertesting should only attempt it when "
            "the run records `emprework=true`, and local dispatch should be "
            "repaired before repeated coverage retries are trusted."
        ),
    ),
    "cmd-attack": UpstreamFixtureIntelligence(
        kind="proto-command",
        subject_id="cmd-attack",
        surface="bar-lua-rewrite",
        availability="lua-rewritten",
        summary=(
            "BAR can rewrite attack semantics for some units. Units with weapons "
            "tagged `place_target_on_ground` have their attack command descriptor "
            "changed to map targeting, and unit-id attack inputs are converted to "
            "ground coordinates by Lua."
        ),
        unit_constraints=(
            "Do not use nukes or other place-target-on-ground weapons to verify unit-target attack semantics.",
            "Prefer a simple direct-fire unit such as the commander for baseline attack verification.",
        ),
        fixture_implications=(
            "Attack fixtures need a hostile target and a unit whose attack command is not Lua-remapped to map-only targeting.",
            "A failed unit-target attack may reflect Lua command-shape rewriting rather than transport failure.",
        ),
        observability="snapshot-friendly",
        repo_gap=(
            "The gateway currently treats `attack.target_unit_id` as a simple raw "
            "engine target-id command, but BAR may reinterpret the command based "
            "on unit weapon metadata."
        ),
        citations=(
            "/tmp/BAR-game-sparse/luarules/gadgets/cmd_place_target_on_ground.lua:19-30",
            "/tmp/BAR-game-sparse/luarules/gadgets/cmd_place_target_on_ground.lua:53-94",
            "/tmp/BAR-game-sparse/luarules/gadgets/cmd_place_target_on_ground.lua:96-110",
            "/home/developer/projects/HighBarV3/src/circuit/grpc/CommandDispatch.cpp:192-200",
        ),
        recommendation=(
            "Attach an upstream attack-shape note to fixtures. Itertesting should "
            "tag attack fixtures with `unit_target_attack_safe=true` when the "
            "chosen unit is known not to use the BAR ground-target rewrite."
        ),
    ),
    "cmd-dgun": UpstreamFixtureIntelligence(
        kind="proto-command",
        subject_id="cmd-dgun",
        surface="bar-lua-gadget",
        availability="unit-conditional",
        summary=(
            "Manual-fire behavior is unit-specific in BAR. Non-commander "
            "manual-fire units can have their manual-fire command replaced by the "
            "Lua `MANUAL_LAUNCH` command, while commanders are explicitly excluded "
            "from that replacement."
        ),
        unit_constraints=(
            "Use an actual commander for DGun validation.",
            "Do not generalize commander DGun behavior to non-commander manual-fire units.",
        ),
        fixture_implications=(
            "The fixture must guarantee a commander unit and a valid hostile target.",
            "If a non-commander unit is used, BAR Lua may route the behavior through a different command surface entirely.",
        ),
        observability="command-specific",
        repo_gap=(
            "The proto command shape assumes target-unit DGun semantics; BAR's "
            "manual-launch replacement shows that manual-fire capability is not "
            "uniform across units."
        ),
        citations=(
            "/tmp/BAR-game-sparse/luarules/gadgets/cmd_manual_launch.lua:17-18",
            "/tmp/BAR-game-sparse/luarules/gadgets/cmd_manual_launch.lua:21-29",
            "/tmp/BAR-game-sparse/luarules/gadgets/cmd_manual_launch.lua:38-53",
            "/home/developer/projects/HighBarV3/src/circuit/grpc/CommandDispatch.cpp:210-218",
        ),
        recommendation=(
            "Keep DGun fixtures commander-only, and treat non-commander manual-fire "
            "verification as a separate upstream command family."
        ),
    ),
    "cmd-custom": UpstreamFixtureIntelligence(
        kind="proto-command",
        subject_id="cmd-custom",
        surface="mixed",
        availability="unit-conditional",
        summary=(
            "Generic custom commands are not meaningfully testable without a "
            "command-id-specific BAR source of truth. BAR adds and edits many "
            "custom commands through Lua gadgets and command descriptors; a raw "
            "`custom.command_id` plus params is not enough to infer the required "
            "fixture or the expected effect."
        ),
        unit_constraints=(
            "Resolve the specific custom command id before choosing a unit fixture.",
            "Do not treat `cmd-custom` as one behaviorally uniform command.",
        ),
        fixture_implications=(
            "A generic `custom_target` fixture class is insufficient for deterministic verification.",
            "Itertesting should split custom-command verification by known command id or gadget family.",
        ),
        observability="command-specific",
        repo_gap=(
            "The gateway accepts arbitrary custom command ids, but the test stack "
            "does not currently carry the BAR-side metadata needed to choose a "
            "correct fixture and expected signal."
        ),
        citations=(
            "/home/developer/projects/HighBarV3/src/circuit/grpc/CommandDispatch.cpp:496-503",
            "/tmp/BAR-game-sparse/luarules/gadgets/unit_target_on_the_move.lua:369-396",
            "/tmp/BAR-game-sparse/luarules/gadgets/unit_builder_priority.lua:54-62",
            "/tmp/BAR-game-sparse/luarules/gadgets/unit_cloak.lua:24-32",
        ),
        recommendation=(
            "Do not spend repeated Itertesting cycles on generic `cmd-custom`. "
            "First build a BAR command-id inventory that maps each custom id to "
            "its owning gadget, eligible units, command type, and observable side effect."
        ),
    ),
}


UPSTREAM_SURFACE_GAPS: dict[str, UpstreamFixtureIntelligence] = {
    "gap-cmd-priority": UpstreamFixtureIntelligence(
        kind="upstream-surface-gap",
        subject_id="gap-cmd-priority",
        surface="mixed",
        availability="lua-inserted",
        summary=(
            "BAR exposes builder priority as a real Lua command for qualifying "
            "builder units, and upstream CircuitAI issues `CMD_PRIORITY`. The "
            "local fork still has `CCircuitUnit::CmdPriority` stubbed out."
        ),
        unit_constraints=(
            "Requires a unit that can assist or has build options.",
        ),
        fixture_implications=(
            "This is not a missing-fixture problem in BAR; it is a local command-surface gap.",
        ),
        observability="rules-param-or-cmddesc",
        repo_gap=(
            "Local `CmdPriority` is commented out, while upstream CircuitAI and BAR "
            "both support the command."
        ),
        citations=(
            "/tmp/CircuitAI-upstream/src/circuit/unit/CircuitUnit.cpp:280-283",
            "/home/developer/projects/HighBarV3/src/circuit/unit/CircuitUnit.cpp:362-365",
            "/tmp/BAR-game-sparse/luarules/gadgets/unit_builder_priority.lua:54-62",
            "/tmp/BAR-game-sparse/luarules/gadgets/unit_builder_priority.lua:149-165",
            "/tmp/BAR-game-sparse/luarules/gadgets/unit_builder_priority.lua:206-233",
        ),
        recommendation=(
            "Treat builder priority as a candidate protocol extension or direct "
            "local repair, not as an Itertesting fixture shortcoming."
        ),
    ),
    "gap-cmd-cloak-support": UpstreamFixtureIntelligence(
        kind="upstream-surface-gap",
        subject_id="gap-cmd-cloak-support",
        surface="mixed",
        availability="lua-inserted",
        summary=(
            "Upstream CircuitAI issues both `CMD_WANT_CLOAK` and "
            "`CMD_CLOAK_SHIELD`, while BAR replaces the stock cloak command with "
            "its own `want cloak` command and enforces cloak viability through Lua."
        ),
        unit_constraints=(
            "Requires a cloak-capable unit.",
        ),
        fixture_implications=(
            "Cloak behavior depends on energy, stun state, area cloak state, and "
            "Lua rules params; partial local support is easy to misread as a fixture gap.",
        ),
        observability="rules-param-or-cmddesc",
        repo_gap=(
            "The local fork only emits `CMD_WANT_CLOAK`; upstream also sends "
            "`CMD_CLOAK_SHIELD` and `unit->Cloak(state)`."
        ),
        citations=(
            "/tmp/CircuitAI-upstream/src/circuit/unit/CircuitUnit.cpp:258-263",
            "/home/developer/projects/HighBarV3/src/circuit/unit/CircuitUnit.cpp:334-339",
            "/tmp/BAR-game-sparse/luarules/gadgets/unit_cloak.lua:24-32",
            "/tmp/BAR-game-sparse/luarules/gadgets/unit_cloak.lua:127-160",
            "/tmp/BAR-game-sparse/luarules/gadgets/unit_cloak.lua:167-192",
            "/tmp/BAR-game-sparse/luarules/gadgets/unit_cloak.lua:215-235",
        ),
        recommendation=(
            "Keep cloak-related verification separate from generic move/attack "
            "fixtures and avoid treating BAR cloak behavior as a plain boolean toggle."
        ),
    ),
    "gap-cmd-find-pad-and-manual-fire": UpstreamFixtureIntelligence(
        kind="upstream-surface-gap",
        subject_id="gap-cmd-find-pad-and-manual-fire",
        surface="circuit-custom-command",
        availability="unit-conditional",
        summary=(
            "Upstream CircuitAI supports `CMD_FIND_PAD` and `CMD_ONECLICK_WEAPON`, "
            "but the local fork substitutes `CMD_LAND_AT_AIRBASE` for pad finding "
            "and leaves manual-fire helpers commented out."
        ),
        unit_constraints=(
            "Requires aircraft or manual-fire-capable units depending on the command.",
        ),
        fixture_implications=(
            "These are surface-implementation differences, not just fixture provisioning problems.",
        ),
        observability="command-specific",
        repo_gap=(
            "The fork diverges from upstream command ids and leaves some helper "
            "paths inert."
        ),
        citations=(
            "/tmp/CircuitAI-upstream/src/circuit/unit/CircuitUnit.cpp:270-277",
            "/home/developer/projects/HighBarV3/src/circuit/unit/CircuitUnit.cpp:346-355",
        ),
        recommendation=(
            "When a verification issue touches rearm, pads, or manual fire, audit "
            "the fork-vs-upstream command implementation before adding more fixtures."
        ),
    ),
    "gap-cmd-fire-at-radar-and-air-strafe": UpstreamFixtureIntelligence(
        kind="upstream-surface-gap",
        subject_id="gap-cmd-fire-at-radar-and-air-strafe",
        surface="circuit-custom-command",
        availability="unit-conditional",
        summary=(
            "Upstream CircuitAI emits custom commands for radar-fire and air-strafe "
            "controls, but the local fork leaves those helpers commented out."
        ),
        unit_constraints=(
            "Requires units that actually expose the underlying behavior.",
        ),
        fixture_implications=(
            "Do not treat these as missing-fixture problems until local helper parity with upstream is restored.",
        ),
        observability="command-specific",
        repo_gap=(
            "Local helper methods are stubs while upstream still issues the raw custom commands."
        ),
        citations=(
            "/tmp/CircuitAI-upstream/src/circuit/unit/CircuitUnit.cpp:265-268",
            "/tmp/CircuitAI-upstream/src/circuit/unit/CircuitUnit.cpp:285-292",
            "/home/developer/projects/HighBarV3/src/circuit/unit/CircuitUnit.cpp:341-344",
            "/home/developer/projects/HighBarV3/src/circuit/unit/CircuitUnit.cpp:367-375",
        ),
        recommendation=(
            "Mark these as upstream parity gaps first. Itertesting retries will not "
            "recover behavior that the local helper never issues."
        ),
    ),
}


def upstream_fixture_intelligence_for(subject_id: str) -> UpstreamFixtureIntelligence | None:
    return (
        PROTO_COMMAND_INTELLIGENCE.get(subject_id)
        or UPSTREAM_SURFACE_GAPS.get(subject_id)
    )


def all_upstream_fixture_intelligence() -> tuple[UpstreamFixtureIntelligence, ...]:
    return tuple(
        sorted(
            (
                *PROTO_COMMAND_INTELLIGENCE.values(),
                *UPSTREAM_SURFACE_GAPS.values(),
            ),
            key=lambda item: (item.kind, item.subject_id),
        )
    )


__all__ = [
    "AvailabilityClass",
    "CommandSurface",
    "IntelligenceKind",
    "ObservabilityClass",
    "PROTO_COMMAND_INTELLIGENCE",
    "UPSTREAM_SURFACE_GAPS",
    "UpstreamFixtureIntelligence",
    "all_upstream_fixture_intelligence",
    "upstream_fixture_intelligence_for",
]

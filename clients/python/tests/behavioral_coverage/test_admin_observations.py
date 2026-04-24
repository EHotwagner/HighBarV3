# SPDX-License-Identifier: GPL-2.0-only
from __future__ import annotations

from highbar_client.behavioral_coverage.admin_observations import (
    ObservedMatchState,
    frame_advanced,
    frame_stopped,
    owner_changed,
    resource_increased,
    speed_matches,
    unchanged_state,
    unit_spawned,
)


def test_success_observation_predicates():
    before = ObservedMatchState(
        frame=100,
        speed=1.0,
        resources={(0, 0): 50.0},
        units={1: {"team_id": 0, "unit_def_id": 1, "position": (100.0, 0.0, 100.0)}},
    )
    after = ObservedMatchState(
        frame=130,
        speed=2.0,
        resources={(0, 0): 150.0},
        units={
            1: {"team_id": 1, "unit_def_id": 1, "position": (100.0, 0.0, 100.0)},
            2: {"team_id": 1, "unit_def_id": 1, "position": (1025.0, 0.0, 1024.0)},
        },
    )

    assert frame_stopped(ObservedMatchState(frame=10), ObservedMatchState(frame=10)).observed is True
    assert frame_advanced(before, after).observed is True
    assert speed_matches(after, 2.0).observed is True
    assert resource_increased(before, after, team_id=0, resource_id=0, amount=100.0).observed is True
    assert unit_spawned(before, after, team_id=1, unit_def_id=1, position=(1024.0, 0.0, 1024.0)).observed is True
    assert owner_changed(before, after, unit_id=1, to_team_id=1).observed is True


def test_unchanged_state_detects_rejection_mutation():
    state = ObservedMatchState(frame=5, resources={(0, 0): 1.0})
    mutated = ObservedMatchState(frame=5, resources={(0, 0): 2.0})

    assert unchanged_state(state, state).observed is True
    assert unchanged_state(state, mutated).observed is False

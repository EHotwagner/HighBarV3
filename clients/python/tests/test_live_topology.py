# SPDX-License-Identifier: GPL-2.0-only
from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from highbar_client.live_topology import (
    TopologyOptions,
    TopologyPrerequisiteError,
    _ResolvedOptions,
    render_host_startscript,
    render_viewer_startscript,
    turtlevsnull,
)


MINIMAL_STARTSCRIPT = """
[GAME]
{
\tHostPort=8452;
\tMinSpeed=1;
\tMaxSpeed=1;
\tGameStartDelay=10;
\t[AI0]
\t{
\t\tName=HighBarV3-team1;
\t\tTeam=1;
\t\tShortName=NullAI;
\t\tVersion=0.1;
\t}
\t[AI1]
\t{
\t\tName=HighBarV3-team0;
\t\tTeam=0;
\t\tShortName=highBar;
\t\tVersion=stable;
\t}
}
"""


def test_turtlevsnull_preset_is_saved_topology_object():
    assert turtlevsnull.name == "turtlevsnull"
    assert turtlevsnull.ai_plugin == "turtle1"
    assert turtlevsnull.opponent_ai_name == "NullAI"
    assert turtlevsnull.attach_bnv is True
    assert Path(turtlevsnull.run_dir).name == "hb-run-turtlevsnull"


def test_render_host_startscript_rewrites_port_speed_and_ai_names():
    options = replace(
        turtlevsnull,
        host_port=18470,
        min_speed="3",
        max_speed="10",
        game_start_delay="3",
        host_team_ai_name="turtle1-proxy",
        opponent_ai_name="NullAI",
    )

    rendered = render_host_startscript(MINIMAL_STARTSCRIPT, options)

    assert "HostPort=18470;" in rendered
    assert "MinSpeed=3;" in rendered
    assert "MaxSpeed=10;" in rendered
    assert "GameStartDelay=3;" in rendered
    assert "Name=turtle1-proxy;" in rendered
    assert "Name=NullAI;" in rendered
    assert "ShortName=highBar;" in rendered


def test_render_host_startscript_requires_expected_speed_keys():
    options = TopologyOptions(name="broken", run_dir="/tmp/broken")

    with pytest.raises(ValueError, match="HostPort"):
        render_host_startscript("[GAME]\n{\n}\n", options)


def test_render_viewer_startscript_joins_host_port():
    rendered = render_viewer_startscript("127.0.0.1", 18470)

    assert "HostIP=127.0.0.1;" in rendered
    assert "HostPort=18470;" in rendered
    assert "MyPlayerName=HighBarV3BNV;" in rendered
    assert "IsHost=0;" in rendered


def test_resolved_options_rejects_missing_launcher(tmp_path: Path):
    options = replace(turtlevsnull, repo_root=tmp_path)

    with pytest.raises(TopologyPrerequisiteError, match="_launch.sh"):
        _ResolvedOptions.from_options(options)

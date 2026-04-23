#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-2.0-only

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")/../.." && pwd)"

if ! command -v uv >/dev/null 2>&1; then
    echo "test_live_run_viewer: uv missing - skip" >&2
    exit 77
fi

TMPDIR="$(mktemp -d)"
trap 'rm -rf "$TMPDIR"' EXIT

REPORTS_DIR="$TMPDIR/reports"
FAKE_SPRING="$TMPDIR/fake-spring.sh"

cat >"$FAKE_SPRING" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
trap 'exit 0' TERM INT
printf '%s\n' "$*" >> "${HIGHBAR_FAKE_SPRING_LOG:?}"
sleep 30 &
wait "$!"
EOF
chmod +x "$FAKE_SPRING"

export HIGHBAR_BAR_CLIENT_BINARY="$FAKE_SPRING"
export HIGHBAR_ITERTESTING_WATCH_LAUNCHED=true
export HIGHBAR_ITERTESTING_WATCH_ENGINE_MODE=graphical-client
export HIGHBAR_ITERTESTING_WATCH_ENGINE_BINARY="$FAKE_SPRING"
export HIGHBAR_ITERTESTING_WATCH_ENGINE_PID=777
export HIGHBAR_ITERTESTING_WATCH_STARTSCRIPT=tests/headless/scripts/minimal.startscript
export HIGHBAR_WRITE_DIR="$TMPDIR/write"
export HIGHBAR_FAKE_SPRING_LOG="$TMPDIR/fake-spring.log"
export HIGHBAR_BNV_BRIDGE_TIMEOUT_SECONDS=0.2

verify_watch_speed_wrapper_helpers() {
    local helper_dir="$TMPDIR/helper-check"
    local widget_dir="$HIGHBAR_WRITE_DIR/LuaUI/Widgets"
    local widget_path="$widget_dir/api_ai_bridge.lua"
    local packages_dir="$HIGHBAR_WRITE_DIR/packages"
    local pool_dir="$HIGHBAR_WRITE_DIR/pool"
    local ai_namer_hash="11111111111111111111111111111111"
    local ai_namer_pool_path="$pool_dir/${ai_namer_hash:0:2}/${ai_namer_hash:2}.gz"
    local advplayerslist_hash="22222222222222222222222222222222"
    local advplayerslist_pool_path="$pool_dir/${advplayerslist_hash:0:2}/${advplayerslist_hash:2}.gz"
    local chat_hash="33333333333333333333333333333333"
    local chat_pool_path="$pool_dir/${chat_hash:0:2}/${chat_hash:2}.gz"
    local share_unit_hash="44444444444444444444444444444444"
    local share_unit_pool_path="$pool_dir/${share_unit_hash:0:2}/${share_unit_hash:2}.gz"
    local gui_info_hash="55555555555555555555555555555555"
    local gui_info_pool_path="$pool_dir/${gui_info_hash:0:2}/${gui_info_hash:2}.gz"
    local com_nametags_hash="66666666666666666666666666666666"
    local com_nametags_pool_path="$pool_dir/${com_nametags_hash:0:2}/${com_nametags_hash:2}.gz"
    local camera_player_tv_hash="77777777777777777777777777777777"
    local camera_player_tv_pool_path="$pool_dir/${camera_player_tv_hash:0:2}/${camera_player_tv_hash:2}.gz"
    local map_startbox_hash="88888888888888888888888888888888"
    local map_startbox_pool_path="$pool_dir/${map_startbox_hash:0:2}/${map_startbox_hash:2}.gz"
    local territorial_domination_hash="99999999999999999999999999999999"
    local territorial_domination_pool_path="$pool_dir/${territorial_domination_hash:0:2}/${territorial_domination_hash:2}.gz"
    local advplayerslist_override_source="$helper_dir/gui_advplayerslist.override.lua"
    local gui_info_override_source="$helper_dir/gui_info.override.lua"
    local gui_com_nametags_override_source="$helper_dir/gui_com_nametags.override.lua"
    local camera_player_tv_override_source="$helper_dir/camera_player_tv.override.lua"
    local host_startscript
    local client_startscript

    mkdir -p "$helper_dir" "$widget_dir" "$packages_dir" \
        "$(dirname "$ai_namer_pool_path")" \
        "$(dirname "$advplayerslist_pool_path")" \
        "$(dirname "$chat_pool_path")" \
        "$(dirname "$share_unit_pool_path")" \
        "$(dirname "$gui_info_pool_path")" \
        "$(dirname "$com_nametags_pool_path")" \
        "$(dirname "$camera_player_tv_pool_path")" \
        "$(dirname "$map_startbox_pool_path")" \
        "$(dirname "$territorial_domination_pool_path")"
    cat >"$widget_path" <<'EOF'
local handleSetSpeed
local handlePause
local handleClientDisconnect

local handlers = {
  set_speed  = function(msg) handleSetSpeed(msg) end,
  pause      = function(msg) handlePause(msg) end,
}

local function sendError() end
local function sendMessage() end

function handleSetSpeed(msg)
  Spring.SendCommands("setminspeed " .. msg.speed)
  Spring.SendCommands("setmaxspeed " .. msg.speed)
end

handlePause = function(msg)
  if type(msg.paused) ~= "boolean" then
    sendError(msg.id, "invalid_message", "Missing or invalid paused (expected boolean)")
    return
  end

  Spring.SendCommands("pause " .. (msg.paused and "1" or "0"))
  sendMessage({ type = "ok", id = msg.id })
end
EOF
    cat >"$advplayerslist_override_source" <<'EOF'
function GetAIName(teamID)
    return Spring.I18N('ui.playersList.aiName', { name = 'UNKNOWN' })
end

function CreatePlayerFromTeam(teamID)
end
EOF
    cat >"$gui_info_override_source" <<'EOF'
local function GetAIName(teamID)
	local _, _, _, name, _, options = Spring.GetAIInfo(teamID)
	local niceName = Spring.GetGameRulesParam('ainame_' .. teamID)
	if niceName then
		name = niceName
	end
	return Spring.I18N('ui.playersList.aiName', { name = name })
end
EOF
    cat >"$gui_com_nametags_override_source" <<'EOF'
local function commanderName(team, unitDefID)
	local name
	if false then
		name = 'noop'
	elseif spGetGameRulesParam('ainame_' .. team) then
		local unitDefCustomParams = UnitDefs[unitDefID].customParams
		if unitDefCustomParams.decoyfor then
			name = Spring.I18N('units.decoyCommanderNameTag')
		else
			name = Spring.I18N('ui.playersList.aiName', { name = spGetGameRulesParam('ainame_' .. team) })
		end

	else
		name = 'fallback'
	end
	return name
end
EOF
    cat >"$camera_player_tv_override_source" <<'EOF'
local myTeamID = 0
local function refreshUiDrawing()
	local name
	if select(4, Spring.GetTeamInfo(myTeamID,false)) then	-- is AI?
		local _, _, _, aiName = Spring.GetAIInfo(myTeamID)
		local niceName = Spring.GetGameRulesParam('ainame_' .. myTeamID)
		name = niceName or aiName
		name = Spring.I18N('ui.playersList.aiName', { name = name })
	end
	return name
end
EOF
    python - <<'PY' \
        "$packages_dir/test.sdp" \
        "$ai_namer_hash" "$ai_namer_pool_path" \
        "$advplayerslist_hash" "$advplayerslist_pool_path" \
        "$chat_hash" "$chat_pool_path" \
        "$share_unit_hash" "$share_unit_pool_path" \
        "$gui_info_hash" "$gui_info_pool_path" \
        "$com_nametags_hash" "$com_nametags_pool_path" \
        "$camera_player_tv_hash" "$camera_player_tv_pool_path" \
        "$map_startbox_hash" "$map_startbox_pool_path" \
        "$territorial_domination_hash" "$territorial_domination_pool_path"
from pathlib import Path
import gzip
import sys

sdp_path = Path(sys.argv[1])
entries = [
    ("luarules/gadgets/ai_namer.lua", sys.argv[2], Path(sys.argv[3]), "ORIGINAL AI NAMER\n"),
    (
        "luaui/widgets/gui_advplayerslist.lua",
        sys.argv[4],
        Path(sys.argv[5]),
        "function GetAIName(teamID)\n    return Spring.I18N('ui.playersList.aiName', { name = 'UNKNOWN' })\nend\n\nfunction CreatePlayerFromTeam(teamID)\nend\n",
    ),
    (
        "luaui/widgets/gui_chat.lua",
        sys.argv[6],
        Path(sys.argv[7]),
        "local function getAIName(teamID)\n\treturn Spring.I18N('ui.playersList.aiName', { name = 'UNKNOWN' })\nend\n",
    ),
    (
        "luaui/widgets/cmd_share_unit.lua",
        sys.argv[8],
        Path(sys.argv[9]),
        "local function findPlayerName(teamId)\n\treturn I18N('ui.playersList.aiName', { name = GetGameRulesParam('ainame_' .. teamId) })\nend\n",
    ),
    (
        "luaui/widgets/gui_info.lua",
        sys.argv[10],
        Path(sys.argv[11]),
        "local function GetAIName(teamID)\n\tlocal _, _, _, name, _, options = Spring.GetAIInfo(teamID)\n\tlocal niceName = Spring.GetGameRulesParam('ainame_' .. teamID)\n\tif niceName then\n\t\tname = niceName\n\tend\n\treturn Spring.I18N('ui.playersList.aiName', { name = name })\nend\n",
    ),
    (
        "luaui/widgets/gui_com_nametags.lua",
        sys.argv[12],
        Path(sys.argv[13]),
        "local function commanderName(team, unitDefID)\n\tlocal name\n\tif false then\n\t\tname = 'noop'\n\telseif spGetGameRulesParam('ainame_' .. team) then\n\t\tlocal unitDefCustomParams = UnitDefs[unitDefID].customParams\n\t\tif unitDefCustomParams.decoyfor then\n\t\t\tname = Spring.I18N('units.decoyCommanderNameTag')\n\t\telse\n\t\t\tname = Spring.I18N('ui.playersList.aiName', { name = spGetGameRulesParam('ainame_' .. team) })\n\t\tend\n\n\telse\n\t\tname = 'fallback'\n\tend\n\treturn name\nend\n",
    ),
    (
        "luaui/widgets/camera_player_tv.lua",
        sys.argv[14],
        Path(sys.argv[15]),
        "local myTeamID = 0\nlocal function refreshUiDrawing()\n\tlocal name\n\tif select(4, Spring.GetTeamInfo(myTeamID,false)) then\t-- is AI?\n\t\tlocal _, _, _, aiName = Spring.GetAIInfo(myTeamID)\n\t\tlocal niceName = Spring.GetGameRulesParam('ainame_' .. myTeamID)\n\t\tname = niceName or aiName\n\t\tname = Spring.I18N('ui.playersList.aiName', { name = name })\n\tend\n\treturn name\nend\n",
    ),
    (
        "luaui/widgets/map_startbox.lua",
        sys.argv[16],
        Path(sys.argv[17]),
        "local function teamName(teamID, isAI)\n\tlocal baseName = 'player'\n\tlocal aiNameI18NTable = {}\n\tif isAI then\n\t\t\tlocal _, _, _, aiName = Spring.GetAIInfo(teamID)\n\t\t\tlocal niceName = Spring.GetGameRulesParam('ainame_' .. teamID)\n\t\t\tif niceName then\n\t\t\t\taiName = niceName\n\t\t\tend\n\t\t\taiNameI18NTable.name = aiName\n\t\t\tbaseName = Spring.I18N('ui.playersList.aiName', aiNameI18NTable)\n\t\telse\n\t\t\tbaseName = 'player'\n\t\tend\n\treturn baseName\nend\n",
    ),
    (
        "luaui/rmlwidgets/gui_territorial_domination/gui_territorial_domination.lua",
        sys.argv[18],
        Path(sys.argv[19]),
        "local function getAIName(teamID)\n\treturn Spring.I18N('ui.playersList.aiName', { name = 'UNKNOWN' })\nend\n",
    ),
]
payload = b""
for entry_name, hash_hex, pool_path, content in entries:
    entry_name_bytes = entry_name.encode("utf-8")
    payload += bytes([len(entry_name_bytes)]) + entry_name_bytes + bytes.fromhex(hash_hex) + (123).to_bytes(4, "big")
    with gzip.open(pool_path, "wt", encoding="utf-8") as handle:
        handle.write(content)
with gzip.open(sdp_path, "wb") as handle:
    handle.write(payload)
PY

    # shellcheck source=tests/headless/itertesting.sh
    source "$REPO_ROOT/tests/headless/itertesting.sh"
    ACTIVE_RUN_DIR="$helper_dir"
    WRITE_DIR="$HIGHBAR_WRITE_DIR"
    export HIGHBAR_WATCH_ADVPLAYERSLIST_SOURCE="file://$advplayerslist_override_source"
    export HIGHBAR_WATCH_GUI_INFO_SOURCE="file://$gui_info_override_source"
    export HIGHBAR_WATCH_GUI_COM_NAMETAGS_SOURCE="file://$gui_com_nametags_override_source"
    export HIGHBAR_WATCH_CAMERA_PLAYER_TV_SOURCE="file://$camera_player_tv_override_source"

    host_startscript="$(prepare_watch_host_startscript "$REPO_ROOT/tests/headless/scripts/minimal.startscript" "18452" "HighBarV3Watch")"
    client_startscript="$(prepare_watch_client_startscript "18452" "HighBarV3Watch")"
    grep -q 'MinSpeed=0.0;' "$host_startscript" || {
        echo "test_live_run_viewer: watched startscript did not rewrite MinSpeed to 0.0" >&2
        exit 1
    }
    grep -q 'MaxSpeed=10.0;' "$host_startscript" || {
        echo "test_live_run_viewer: watched startscript did not rewrite MaxSpeed to 10.0" >&2
        exit 1
    }
    grep -q 'HostPort=18452;' "$host_startscript" || {
        echo "test_live_run_viewer: watched host startscript did not set HostPort" >&2
        exit 1
    }
    grep -q '\[PLAYER1\]' "$host_startscript" || {
        echo "test_live_run_viewer: watched host startscript did not add viewer player" >&2
        exit 1
    }
    grep -q 'Name=HighBarV3Watch;' "$host_startscript" || {
        echo "test_live_run_viewer: watched host startscript did not add expected viewer player name" >&2
        exit 1
    }
    grep -q 'Name=NullAI;' "$host_startscript" || {
        echo "test_live_run_viewer: watched host startscript did not rewrite AI0 name to NullAI" >&2
        exit 1
    }
    grep -q 'Name=BARb;' "$host_startscript" || {
        echo "test_live_run_viewer: watched host startscript did not rewrite AI1 name to BARb" >&2
        exit 1
    }
    grep -q 'NumPlayers=2;' "$host_startscript" || {
        echo "test_live_run_viewer: watched host startscript did not bump NumPlayers" >&2
        exit 1
    }
    grep -q 'IsHost=0;' "$client_startscript" || {
        echo "test_live_run_viewer: watched client startscript did not set IsHost=0" >&2
        exit 1
    }
    grep -q 'HostPort=18452;' "$client_startscript" || {
        echo "test_live_run_viewer: watched client startscript did not preserve HostPort" >&2
        exit 1
    }
    grep -q 'MyPlayerName=HighBarV3Watch;' "$client_startscript" || {
        echo "test_live_run_viewer: watched client startscript did not set viewer player name" >&2
        exit 1
    }
    patch_watch_ai_namer
    python - <<'PY' "$ai_namer_pool_path"
from pathlib import Path
import gzip
import sys

text = gzip.open(Path(sys.argv[1]), "rt", encoding="utf-8").read()
assert 'local PUBLIC = { public = true }' in text
assert 'string.format("HighBarV3-team%d", teamID)' in text
assert 'Spring.SetGameRulesParam("ainame_" .. teamID, aiName, PUBLIC)' in text
assert 'HighBar AI name override: team ' in text
PY
    restore_watch_ai_namer
    python - <<'PY' "$ai_namer_pool_path"
from pathlib import Path
import gzip
import sys

text = gzip.open(Path(sys.argv[1]), "rt", encoding="utf-8").read()
assert text == "ORIGINAL AI NAMER\n"
PY
    [[ -f "$helper_dir/ai_namer.lua.pre-highbar.gz" ]] || {
        echo "test_live_run_viewer: AI namer backup was not created" >&2
        exit 1
    }
    grep -q 'ORIGINAL AI NAMER' <(gzip -dc "$helper_dir/ai_namer.lua.pre-highbar.gz") || {
        echo "test_live_run_viewer: AI namer backup did not preserve original payload" >&2
        exit 1
    }

    install_watch_ai_name_gadget
    [[ -f "$HIGHBAR_WRITE_DIR/LuaRules/Gadgets/highbar_ai_name_override.lua" ]] || {
        echo "test_live_run_viewer: AI name override gadget was not created" >&2
        exit 1
    }
    grep -q 'HighBar AI Name Override' "$HIGHBAR_WRITE_DIR/LuaRules/Gadgets/highbar_ai_name_override.lua" || {
        echo "test_live_run_viewer: AI name override gadget did not contain expected marker" >&2
        exit 1
    }
    grep -q 'Spring.SetGameRulesParam("ainame_" .. teamID, aiName, PUBLIC)' "$HIGHBAR_WRITE_DIR/LuaRules/Gadgets/highbar_ai_name_override.lua" || {
        echo "test_live_run_viewer: AI name override gadget did not set public ai names" >&2
        exit 1
    }
    restore_watch_ai_name_gadget
    [[ ! -f "$HIGHBAR_WRITE_DIR/LuaRules/Gadgets/highbar_ai_name_override.lua" ]] || {
        echo "test_live_run_viewer: AI name override gadget was not removed on restore" >&2
        exit 1
    }

    install_watch_ai_name_widget
    [[ -f "$HIGHBAR_WRITE_DIR/LuaUI/Widgets/aaa_highbar_ai_names.lua" ]] || {
        echo "test_live_run_viewer: AI name override widget was not created" >&2
        exit 1
    }
    grep -q 'Spring.GetAIInfo = patchState.patchedGetAIInfo' "$HIGHBAR_WRITE_DIR/LuaUI/Widgets/aaa_highbar_ai_names.lua" || {
        echo "test_live_run_viewer: AI name override widget did not patch GetAIInfo" >&2
        exit 1
    }
    grep -q 'local _, aiName, _, shortName, _, options = patchState.originalGetAIInfo(teamID)' "$HIGHBAR_WRITE_DIR/LuaUI/Widgets/aaa_highbar_ai_names.lua" || {
        echo "test_live_run_viewer: AI name override widget did not derive labels from AI identity fields" >&2
        exit 1
    }
    grep -q 'options.profile' "$HIGHBAR_WRITE_DIR/LuaUI/Widgets/aaa_highbar_ai_names.lua" || {
        echo "test_live_run_viewer: AI name override widget did not consider AI profile metadata" >&2
        exit 1
    }
    restore_watch_ai_name_widget
    [[ ! -f "$HIGHBAR_WRITE_DIR/LuaUI/Widgets/aaa_highbar_ai_names.lua" ]] || {
        echo "test_live_run_viewer: AI name override widget was not removed on restore" >&2
        exit 1
    }

    install_watch_name_widget_overrides
    [[ -f "$HIGHBAR_WRITE_DIR/LuaUI/Widgets/gui_advplayerslist.lua" ]] || {
        echo "test_live_run_viewer: AdvPlayersList override was not created" >&2
        exit 1
    }
    [[ -f "$HIGHBAR_WRITE_DIR/LuaUI/Widgets/gui_info.lua" ]] || {
        echo "test_live_run_viewer: gui_info override was not created" >&2
        exit 1
    }
    [[ -f "$HIGHBAR_WRITE_DIR/LuaUI/Widgets/gui_com_nametags.lua" ]] || {
        echo "test_live_run_viewer: gui_com_nametags override was not created" >&2
        exit 1
    }
    [[ -f "$HIGHBAR_WRITE_DIR/LuaUI/Widgets/camera_player_tv.lua" ]] || {
        echo "test_live_run_viewer: camera_player_tv override was not created" >&2
        exit 1
    }
    grep -q 'options.profile or options.difficulty' "$HIGHBAR_WRITE_DIR/LuaUI/Widgets/gui_advplayerslist.lua" || {
        echo "test_live_run_viewer: AdvPlayersList override did not derive AI labels from profile metadata" >&2
        exit 1
    }
    grep -q 'shortName' "$HIGHBAR_WRITE_DIR/LuaUI/Widgets/gui_info.lua" || {
        echo "test_live_run_viewer: gui_info override did not derive AI labels from ShortName" >&2
        exit 1
    }
    grep -q 'aiLabel = shortName' "$HIGHBAR_WRITE_DIR/LuaUI/Widgets/gui_com_nametags.lua" || {
        echo "test_live_run_viewer: gui_com_nametags override did not derive AI labels from ShortName" >&2
        exit 1
    }
    grep -q "name = shortName" "$HIGHBAR_WRITE_DIR/LuaUI/Widgets/camera_player_tv.lua" || {
        echo "test_live_run_viewer: camera_player_tv override did not derive AI labels from ShortName" >&2
        exit 1
    }
    restore_watch_name_widget_overrides
    [[ ! -f "$HIGHBAR_WRITE_DIR/LuaUI/Widgets/gui_advplayerslist.lua" ]] || {
        echo "test_live_run_viewer: AdvPlayersList override was not removed on restore" >&2
        exit 1
    }
    [[ ! -f "$HIGHBAR_WRITE_DIR/LuaUI/Widgets/gui_info.lua" ]] || {
        echo "test_live_run_viewer: gui_info override was not removed on restore" >&2
        exit 1
    }
    [[ ! -f "$HIGHBAR_WRITE_DIR/LuaUI/Widgets/gui_com_nametags.lua" ]] || {
        echo "test_live_run_viewer: gui_com_nametags override was not removed on restore" >&2
        exit 1
    }
    [[ ! -f "$HIGHBAR_WRITE_DIR/LuaUI/Widgets/camera_player_tv.lua" ]] || {
        echo "test_live_run_viewer: camera_player_tv override was not removed on restore" >&2
        exit 1
    }

    patch_watch_name_widgets
    python - <<'PY' \
        "$advplayerslist_pool_path" \
        "$chat_pool_path" \
        "$share_unit_pool_path" \
        "$gui_info_pool_path" \
        "$com_nametags_pool_path" \
        "$camera_player_tv_pool_path" \
        "$map_startbox_pool_path" \
        "$territorial_domination_pool_path"
from pathlib import Path
import gzip
import sys

adv = gzip.open(Path(sys.argv[1]), "rt", encoding="utf-8").read()
chat = gzip.open(Path(sys.argv[2]), "rt", encoding="utf-8").read()
share = gzip.open(Path(sys.argv[3]), "rt", encoding="utf-8").read()
gui_info = gzip.open(Path(sys.argv[4]), "rt", encoding="utf-8").read()
com_nametags = gzip.open(Path(sys.argv[5]), "rt", encoding="utf-8").read()
camera_player_tv = gzip.open(Path(sys.argv[6]), "rt", encoding="utf-8").read()
startbox = gzip.open(Path(sys.argv[7]), "rt", encoding="utf-8").read()
territorial = gzip.open(Path(sys.argv[8]), "rt", encoding="utf-8").read()

assert 'return name' in adv
assert 'string.format("HighBarV3-team%d", teamID)' in adv
assert "return name" in chat
assert "HighBarV3-team%d" in chat
assert "return name" in share
assert "string.format('HighBarV3-team%d', teamId)" in share
assert "return name" in gui_info
assert 'string.format("HighBarV3-team%d", teamID)' in gui_info
assert "name = aiName" in com_nametags
assert 'string.format("HighBarV3-team%d", team)' in com_nametags
assert "string.format(\"HighBarV3-team%d\", myTeamID)" in camera_player_tv
assert "!=" not in camera_player_tv
assert "baseName = aiName" in startbox
assert 'string.format("HighBarV3-team%d", teamID)' in startbox
assert "return name" in territorial
assert "HighBarV3-team%d" in territorial
PY
    restore_watch_name_widgets
    python - <<'PY' \
        "$advplayerslist_pool_path" \
        "$chat_pool_path" \
        "$share_unit_pool_path" \
        "$gui_info_pool_path" \
        "$com_nametags_pool_path" \
        "$camera_player_tv_pool_path" \
        "$map_startbox_pool_path" \
        "$territorial_domination_pool_path"
from pathlib import Path
import gzip
import sys

assert "ui.playersList.aiName" in gzip.open(Path(sys.argv[1]), "rt", encoding="utf-8").read()
assert "ui.playersList.aiName" in gzip.open(Path(sys.argv[2]), "rt", encoding="utf-8").read()
assert "ui.playersList.aiName" in gzip.open(Path(sys.argv[3]), "rt", encoding="utf-8").read()
assert "ui.playersList.aiName" in gzip.open(Path(sys.argv[4]), "rt", encoding="utf-8").read()
assert "ui.playersList.aiName" in gzip.open(Path(sys.argv[5]), "rt", encoding="utf-8").read()
assert "ui.playersList.aiName" in gzip.open(Path(sys.argv[6]), "rt", encoding="utf-8").read()
assert "ui.playersList.aiName" in gzip.open(Path(sys.argv[7]), "rt", encoding="utf-8").read()
assert "ui.playersList.aiName" in gzip.open(Path(sys.argv[8]), "rt", encoding="utf-8").read()
PY

    patch_watch_ai_bridge_widget
    grep -q 'Spring.SendCommands("setspeed " .. msg.speed)' "$widget_path" || {
        echo "test_live_run_viewer: AI Bridge widget was not patched to setspeed" >&2
        exit 1
    }
    grep -q 'grab_input = function(msg) handleGrabInput(msg) end' "$widget_path" || {
        echo "test_live_run_viewer: AI Bridge widget was not patched with grab_input handler" >&2
        exit 1
    }
    grep -q 'Spring.SendCommands("GrabInput " .. (msg.enabled and "1" or "0"))' "$widget_path" || {
        echo "test_live_run_viewer: AI Bridge widget was not patched to forward GrabInput" >&2
        exit 1
    }
    restore_watch_ai_bridge_widget
    grep -q 'Spring.SendCommands("setminspeed " .. msg.speed)' "$widget_path" || {
        echo "test_live_run_viewer: AI Bridge widget restore did not restore setminspeed" >&2
        exit 1
    }
    grep -q 'Spring.SendCommands("setmaxspeed " .. msg.speed)' "$widget_path" || {
        echo "test_live_run_viewer: AI Bridge widget restore did not restore setmaxspeed" >&2
        exit 1
    }
}

run_launch_time_watch() {
    local output_file="$TMPDIR/watch-launch.out"
    local started_at finished_at elapsed manifest_path

    started_at="$(date +%s)"
    uv run --project "$REPO_ROOT/clients/python" python - "$REPORTS_DIR" >"$output_file" 2>&1 <<'PY'
from pathlib import Path
import sys

import highbar_client.behavioral_coverage as behavioral_coverage
from highbar_client.behavioral_coverage.itertesting_runner import itertesting_main
from highbar_client.behavioral_coverage.registry import REGISTRY

reports_dir = Path(sys.argv[1])


def fake_collect_live_rows(_args):
    return [
        {
            "arm_name": "attack",
            "category": REGISTRY["attack"].category,
            "dispatched": "true",
            "verified": "true",
            "evidence": "attack verified while watch mode was enabled",
            "error": "",
        }
    ]


behavioral_coverage.collect_live_rows = fake_collect_live_rows
raise SystemExit(
    itertesting_main(
        [
            "--reports-dir",
            str(reports_dir),
            "--watch",
            "--watch-profile",
            "default",
        ]
    )
)
PY
    finished_at="$(date +%s)"
    elapsed=$((finished_at - started_at))
    [[ $elapsed -le 30 ]] || {
        echo "test_live_run_viewer: watch launch exceeded 30 seconds ($elapsed)" >&2
        cat "$output_file" >&2
        exit 1
    }

    manifest_path="$(find "$REPORTS_DIR" -maxdepth 2 -name manifest.json | head -n 1)"
    [[ -n "$manifest_path" && -f "$manifest_path" ]] || {
        echo "test_live_run_viewer: manifest missing after watch launch" >&2
        cat "$output_file" >&2
        exit 1
    }
    [[ -f "$REPORTS_DIR/active-watch-sessions.json" ]] || {
        echo "test_live_run_viewer: active watch index missing" >&2
        exit 1
    }
    python - "$manifest_path" <<'PY'
import json
import sys

payload = json.load(open(sys.argv[1], "r", encoding="utf-8"))
watch = payload.get("watch_session") or {}
assert watch.get("watch_requested") is True
assert (watch.get("preflight_result") or {}).get("status") == "ready"
assert (watch.get("viewer_access") or {}).get("availability_state") == "available"
PY
}

run_watch_preflight_failure() {
    local output_file="$TMPDIR/watch-failure.out"
    local started_at finished_at elapsed rc

    started_at="$(date +%s)"
    set +e
    HIGHBAR_BAR_CLIENT_READY=false \
    HIGHBAR_BAR_CLIENT_REASON="graphical BAR client prerequisites are not installed" \
    uv run --project "$REPO_ROOT/clients/python" python - "$REPORTS_DIR" >"$output_file" 2>&1 <<'PY'
from pathlib import Path
import sys

import highbar_client.behavioral_coverage as behavioral_coverage
from highbar_client.behavioral_coverage.itertesting_runner import itertesting_main

reports_dir = Path(sys.argv[1])


def fake_collect_live_rows(_args):
    raise AssertionError("collect_live_rows should not run when watch preflight fails")


behavioral_coverage.collect_live_rows = fake_collect_live_rows
raise SystemExit(
    itertesting_main(
        [
            "--reports-dir",
            str(reports_dir),
            "--watch",
            "--watch-profile",
            "default",
        ]
    )
)
PY
    rc=$?
    set -e
    finished_at="$(date +%s)"
    elapsed=$((finished_at - started_at))
    [[ $rc -eq 1 ]] || {
        echo "test_live_run_viewer: expected watch preflight failure rc=1, got $rc" >&2
        cat "$output_file" >&2
        exit 1
    }
    [[ $elapsed -le 10 ]] || {
        echo "test_live_run_viewer: watch preflight failure exceeded 10 seconds ($elapsed)" >&2
        cat "$output_file" >&2
        exit 1
    }
    grep -q "watch_preflight status=environment_unready" "$output_file" || {
        echo "test_live_run_viewer: missing watch preflight failure output" >&2
        cat "$output_file" >&2
        exit 1
    }
}

seed_attach_later_runs() {
    uv run --project "$REPO_ROOT/clients/python" python - "$REPORTS_DIR" <<'PY'
import json
from pathlib import Path
import sys

from highbar_client.behavioral_coverage.itertesting_types import (
    ViewerAccessRecord,
    WatchPreflightResult,
    WatchRequest,
    WatchedRunSession,
    manifest_dict,
)
from highbar_client.behavioral_coverage.itertesting_runner import build_run
from highbar_client.behavioral_coverage.watch_registry import upsert_watch_session

reports_dir = Path(sys.argv[1])


def session(run_id: str) -> WatchedRunSession:
    return WatchedRunSession(
        run_id=run_id,
        campaign_id="campaign-attach",
        run_lifecycle_state="active",
        watch_requested=True,
        watch_request=WatchRequest(
            request_id=f"watch-{run_id}",
            request_mode="launch-time",
            requested_at="2026-04-23T10:00:00Z",
            target_run_id=run_id,
            selection_mode="explicit",
            profile_ref="default",
            watch_required=True,
        ),
        preflight_result=WatchPreflightResult(
            status="ready",
            reason="BAR graphical client watch preflight succeeded",
            checked_at="2026-04-23T10:00:00Z",
            blocking=False,
        ),
        viewer_access=ViewerAccessRecord(
            availability_state="available",
            reason="graphical BAR client launched for watched run",
            launch_command=("spring", "--window", "tests/headless/scripts/minimal.startscript"),
            launched_at="2026-04-23T10:00:01Z",
            viewer_pid=123,
            last_transition_at="2026-04-23T10:00:01Z",
        ),
        report_path=str(reports_dir / run_id / "run-report.md"),
    )

def persist(run_id: str, updated_at: str) -> None:
    watched = session(run_id)
    run = build_run(
        campaign_id=watched.campaign_id or "campaign-attach",
        sequence_index=0,
        reports_dir=reports_dir,
        run_id=watched.run_id,
        watch_session=watched,
    )
    bundle = reports_dir / run_id
    bundle.mkdir(parents=True, exist_ok=True)
    manifest_path = bundle / "manifest.json"
    manifest_path.write_text(json.dumps(manifest_dict(run)), encoding="utf-8")
    upsert_watch_session(
        reports_dir,
        watched,
        updated_at=updated_at,
        manifest_path=str(manifest_path),
    )


persist("run-attach-1", "2026-04-23T10:00:01Z")
persist("run-attach-2", "2026-04-23T10:01:01Z")
expired = session("run-expired")
expired = expired.__class__(
    run_id=expired.run_id,
    campaign_id=expired.campaign_id,
    run_lifecycle_state="completed",
    watch_requested=expired.watch_requested,
    watch_request=expired.watch_request,
    preflight_result=expired.preflight_result,
    viewer_access=expired.viewer_access,
    report_path=expired.report_path,
)
run = build_run(
    campaign_id=expired.campaign_id or "campaign-attach",
    sequence_index=0,
    reports_dir=reports_dir,
    run_id=expired.run_id,
    watch_session=expired,
)
bundle = reports_dir / "run-expired"
bundle.mkdir(parents=True, exist_ok=True)
expired_manifest_path = bundle / "manifest.json"
expired_manifest_path.write_text(json.dumps(manifest_dict(run)), encoding="utf-8")
upsert_watch_session(
    reports_dir,
    expired,
    updated_at="2026-04-23T10:02:01Z",
    manifest_path=str(expired_manifest_path),
)
PY
}

run_attach_later_checks() {
    local explicit_output="$TMPDIR/watch-attach-explicit.out"
    local ambiguous_output="$TMPDIR/watch-attach-ambiguous.out"
    local expired_output="$TMPDIR/watch-attach-expired.out"
    local rc

    seed_attach_later_runs

    uv run --project "$REPO_ROOT/clients/python" python -m highbar_client.behavioral_coverage \
        itertesting \
        --reports-dir "$REPORTS_DIR" \
        --watch-run run-attach-1 \
        --watch-profile default >"$explicit_output" 2>&1
    grep -q "watch_access state=attached" "$explicit_output" || {
        echo "test_live_run_viewer: explicit attach-later did not attach" >&2
        cat "$explicit_output" >&2
        exit 1
    }

    set +e
    uv run --project "$REPO_ROOT/clients/python" python -m highbar_client.behavioral_coverage \
        itertesting \
        --reports-dir "$REPORTS_DIR" \
        --watch-run \
        --watch-profile default >"$ambiguous_output" 2>&1
    rc=$?
    set -e
    [[ $rc -eq 1 ]] || {
        echo "test_live_run_viewer: ambiguous attach-later should fail rc=1, got $rc" >&2
        cat "$ambiguous_output" >&2
        exit 1
    }
    grep -q "attach-later is ambiguous" "$ambiguous_output" || {
        echo "test_live_run_viewer: ambiguous attach-later reason missing" >&2
        cat "$ambiguous_output" >&2
        exit 1
    }

    set +e
    uv run --project "$REPO_ROOT/clients/python" python -m highbar_client.behavioral_coverage \
        itertesting \
        --reports-dir "$REPORTS_DIR" \
        --watch-run run-expired \
        --watch-profile default >"$expired_output" 2>&1
    rc=$?
    set -e
    [[ $rc -eq 1 ]] || {
        echo "test_live_run_viewer: expired attach-later should fail rc=1, got $rc" >&2
        cat "$expired_output" >&2
        exit 1
    }
    grep -q "not attachable" "$expired_output" || {
        echo "test_live_run_viewer: expired attach-later reason missing" >&2
        cat "$expired_output" >&2
        exit 1
    }
}

run_launch_time_watch
verify_watch_speed_wrapper_helpers
run_watch_preflight_failure
run_attach_later_checks

echo "test_live_run_viewer: PASS"

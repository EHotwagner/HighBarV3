#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-2.0-only

set -uo pipefail

REPO_ROOT="$(cd "$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")/../.." && pwd)"
HEADLESS_DIR="$REPO_ROOT/tests/headless"
EXAMPLES_DIR="$REPO_ROOT/specs/002-live-headless-e2e/examples"

# shellcheck source=tests/headless/_coordinator.sh
source "$HEADLESS_DIR/_coordinator.sh"
# shellcheck source=tests/headless/_fault-assert.sh
source "$HEADLESS_DIR/_fault-assert.sh"

if [[ ! -x "$HEADLESS_DIR/_launch.sh" ]]; then
    echo "itertesting: _launch.sh missing — skip" >&2
    exit 77
fi
if [[ ! -f "$EXAMPLES_DIR/coordinator.py" ]]; then
    echo "itertesting: coordinator.py missing — skip" >&2
    exit 77
fi
if ! command -v uv >/dev/null 2>&1; then
    echo "itertesting: uv missing — skip" >&2
    exit 77
fi

RUN_DIR="${HIGHBAR_RUN_DIR:-/tmp/hb-run-itertesting}"
START_SCRIPT="${HIGHBAR_STARTSCRIPT:-$HEADLESS_DIR/scripts/minimal.startscript}"
CHEAT_STARTSCRIPT="${HIGHBAR_ITERTESTING_CHEAT_STARTSCRIPT:-$HEADLESS_DIR/scripts/cheats.startscript}"
WRITE_DIR="${HIGHBAR_WRITE_DIR:-$HOME/.local/state/Beyond All Reason}"
REPORTS_DIR="${HIGHBAR_ITERTESTING_REPORTS_DIR:-$REPO_ROOT/reports/itertesting}"
NATURAL_SMOKE_REPORTS_DIR="${HIGHBAR_ITERTESTING_NATURAL_SMOKE_REPORTS_DIR:-$REPORTS_DIR/natural-smoke}"
RETRY_INTENSITY="${HIGHBAR_ITERTESTING_RETRY_INTENSITY:-standard}"
RUNTIME_TARGET_MINUTES="${HIGHBAR_ITERTESTING_RUNTIME_TARGET_MINUTES:-15}"
SKIP_LIVE="${HIGHBAR_ITERTESTING_SKIP_LIVE:-false}"
LIVE_RETRIES="${HIGHBAR_ITERTESTING_LIVE_RETRIES:-1}"
THRESHOLD="${HIGHBAR_BEHAVIORAL_THRESHOLD:-0.50}"
GAMESEED="${HIGHBAR_GAMESEED:-0x42424242}"
MAX_RUNS="${HIGHBAR_ITERTESTING_MAX_IMPROVEMENT_RUNS:-}"
BOOTSTRAP_WAIT_SECONDS="${HIGHBAR_ITERTESTING_BOOTSTRAP_WAIT_SECONDS:-12}"
ENABLE_BUILTIN="${HIGHBAR_ITERTESTING_ENABLE_BUILTIN:-false}"
SPLIT_LIVE_SETUP="${HIGHBAR_ITERTESTING_SPLIT_LIVE_SETUP:-true}"
EXPLICIT_CALLBACK_PROXY_ENDPOINT="${HIGHBAR_CALLBACK_PROXY_ENDPOINT:-}"
WATCH_ENABLED="${HIGHBAR_ITERTESTING_WATCH:-false}"
WATCH_PROFILE="${HIGHBAR_ITERTESTING_WATCH_PROFILE:-default}"
WATCH_SPEED="${HIGHBAR_ITERTESTING_WATCH_SPEED:-}"
WATCH_HOST_BIND_WAIT_SECONDS="${HIGHBAR_ITERTESTING_WATCH_HOST_BIND_WAIT_SECONDS:-8}"
WATCH_ENGINE_BINARY=""
WATCH_WINDOW_MODE_RESOLVED=""
WATCH_WINDOW_WIDTH_RESOLVED=""
WATCH_WINDOW_HEIGHT_RESOLVED=""
WATCH_MOUSE_CAPTURE_RESOLVED=""
WATCH_SPEED_RESOLVED=""
WATCH_SPEED_MIN_RESOLVED="3.0"
WATCH_SPEED_MAX_RESOLVED="10.0"
WATCH_PLAYER_NAME_RESOLVED="${HIGHBAR_ITERTESTING_WATCH_PLAYER_NAME:-HighBarV3Watch}"
WATCH_HOST_PORT_RESOLVED=""
WATCH_HOST_STARTSCRIPT=""
WATCH_VIEWER_STARTSCRIPT=""
WATCH_VIEWER_RUNTIME_DIR=""
WATCH_VIEWER_LOG=""
WATCH_VIEWER_PID_FILE=""
WATCH_VIEWER_HELPER_PID=""
# The maintainer-facing live path is documented as a default single run.
# Keep profile-driven defaults for synthetic campaign validation, but
# clamp the live wrapper to one run unless the maintainer explicitly
# requests follow-up retries.
if [[ "$SKIP_LIVE" != "true" && -z "$MAX_RUNS" ]]; then
    MAX_RUNS="0"
fi
ACTIVE_RUN_DIR=""
COORD_SOCK=""
COORD_ENDPOINT=""
COORD_LOG=""
ENGINE_LOG=""
ENGINE_PID_FILE=""
COORD_PID=""
BYAR_USER_CONFIG_PATH=""
BYAR_USER_CONFIG_BACKUP=""
BYAR_ENGINE_CONFIG_PATH=""
BYAR_ENGINE_CONFIG_BACKUP=""
AI_BRIDGE_WIDGET_PATH=""
AI_BRIDGE_WIDGET_BACKUP=""
AI_NAMER_POOL_PATH=""
AI_NAMER_POOL_BACKUP=""
WATCH_NAME_WIDGET_MANIFEST=""
WATCH_AI_NAME_GADGET_PATH=""
WATCH_AI_NAME_GADGET_BACKUP=""
WATCH_AI_NAME_WIDGET_PATH=""
WATCH_AI_NAME_WIDGET_BACKUP=""
WATCH_ADVPLAYERSLIST_OVERRIDE_PATH=""
WATCH_ADVPLAYERSLIST_OVERRIDE_BACKUP=""

mkdir -p "$RUN_DIR"

patch_autoquit_config() {
    local config_path="$1"
    local backup_path="$2"
    if [[ ! -f "$config_path" ]]; then
        return 1
    fi
    cp "$config_path" "$backup_path"
    python3 - "$config_path" <<'PY'
from pathlib import Path
import re
import sys

path = Path(sys.argv[1])
lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
updated_lines: list[str] = []
inside_order = False
order_depth = 0
updated = False

for line in lines:
    if not inside_order and re.match(r'^\s*order\s*=\s*{', line):
        inside_order = True
        order_depth = line.count("{") - line.count("}")
        updated_lines.append(line)
        continue

    if inside_order and not updated:
        replaced, count = re.subn(r'^(\s*Autoquit\s*=\s*)\d+(,\s*)$', r'\g<1>0\2', line)
        if count:
            line = replaced
            updated = True

    updated_lines.append(line)

    if inside_order:
        order_depth += line.count("{") - line.count("}")
        if order_depth <= 0:
            inside_order = False

if not updated:
    raise SystemExit(1)

path.write_text("".join(updated_lines), encoding="utf-8")
PY
    return $?
}

disable_autoquit_for_attempt() {
    local engine_release="${HIGHBAR_ENGINE_RELEASE:-recoil_2025.06.19}"
    BYAR_USER_CONFIG_PATH="$WRITE_DIR/LuaUI/Config/BYAR.lua"
    BYAR_USER_CONFIG_BACKUP="$ACTIVE_RUN_DIR/BYAR.user.pre-highbar"
    BYAR_ENGINE_CONFIG_PATH="$WRITE_DIR/engine/$engine_release/LuaUI/Config/BYAR.lua"
    BYAR_ENGINE_CONFIG_BACKUP="$ACTIVE_RUN_DIR/BYAR.engine.pre-highbar"

    if ! patch_autoquit_config "$BYAR_USER_CONFIG_PATH" "$BYAR_USER_CONFIG_BACKUP"; then
        BYAR_USER_CONFIG_PATH=""
        BYAR_USER_CONFIG_BACKUP=""
    fi
    if ! patch_autoquit_config "$BYAR_ENGINE_CONFIG_PATH" "$BYAR_ENGINE_CONFIG_BACKUP"; then
        BYAR_ENGINE_CONFIG_PATH=""
        BYAR_ENGINE_CONFIG_BACKUP=""
    fi
}

restore_autoquit_config() {
    if [[ -n "$BYAR_USER_CONFIG_PATH" && -n "$BYAR_USER_CONFIG_BACKUP" && -f "$BYAR_USER_CONFIG_BACKUP" ]]; then
        cp "$BYAR_USER_CONFIG_BACKUP" "$BYAR_USER_CONFIG_PATH"
    fi
    if [[ -n "$BYAR_ENGINE_CONFIG_PATH" && -n "$BYAR_ENGINE_CONFIG_BACKUP" && -f "$BYAR_ENGINE_CONFIG_BACKUP" ]]; then
        cp "$BYAR_ENGINE_CONFIG_BACKUP" "$BYAR_ENGINE_CONFIG_PATH"
    fi
    BYAR_USER_CONFIG_PATH=""
    BYAR_USER_CONFIG_BACKUP=""
    BYAR_ENGINE_CONFIG_PATH=""
    BYAR_ENGINE_CONFIG_BACKUP=""
}

enable_watch_ai_name_widget_config() {
    local config_path="$1"
    [[ -f "$config_path" ]] || return 0
    python3 - "$config_path" <<'PY'
from pathlib import Path
import re
import sys

path = Path(sys.argv[1])
text = path.read_text(encoding="utf-8")
pattern = r'(\["HighBar AI Names"\]\s*=\s*)0(,)'
updated, count = re.subn(pattern, r'\g<1>1\2', text, count=1)
if count:
    path.write_text(updated, encoding="utf-8")
PY
}

patch_watch_ai_bridge_widget() {
    AI_BRIDGE_WIDGET_PATH="$WRITE_DIR/LuaUI/Widgets/api_ai_bridge.lua"
    AI_BRIDGE_WIDGET_BACKUP="$ACTIVE_RUN_DIR/api_ai_bridge.lua.pre-highbar"
    if [[ ! -f "$AI_BRIDGE_WIDGET_PATH" ]]; then
        AI_BRIDGE_WIDGET_PATH=""
        AI_BRIDGE_WIDGET_BACKUP=""
        return 1
    fi
    cp "$AI_BRIDGE_WIDGET_PATH" "$AI_BRIDGE_WIDGET_BACKUP"
    python3 - "$AI_BRIDGE_WIDGET_PATH" <<'PY'
from pathlib import Path
import sys

path = Path(sys.argv[1])
text = path.read_text(encoding="utf-8")
original = '  Spring.SendCommands("setminspeed " .. msg.speed)\n  Spring.SendCommands("setmaxspeed " .. msg.speed)\n'
patched = '  Spring.SendCommands("setspeed " .. msg.speed)\n'
if original in text:
    text = text.replace(original, patched, 1)
elif patched in text:
    pass
else:
    raise SystemExit(1)

original_handlers = '  set_speed  = function(msg) handleSetSpeed(msg) end,\n  pause      = function(msg) handlePause(msg) end,\n'
grab_handlers = (
    '  set_speed  = function(msg) handleSetSpeed(msg) end,\n'
    '  grab_input = function(msg) handleGrabInput(msg) end,\n'
    '  pause      = function(msg) handlePause(msg) end,\n'
)
patched_handlers = (
    '  set_speed  = function(msg) handleSetSpeed(msg) end,\n'
    '  grab_input = function(msg) handleGrabInput(msg) end,\n'
    '  force_start = function(msg) handleForceStart(msg) end,\n'
    '  pause      = function(msg) handlePause(msg) end,\n'
)
if original_handlers in text:
    text = text.replace(original_handlers, patched_handlers, 1)
elif grab_handlers in text:
    text = text.replace(grab_handlers, patched_handlers, 1)
elif patched_handlers in text:
    pass
else:
    raise SystemExit(1)

original_forward = (
    'local handleSetSpeed\n'
    'local handlePause\n'
    'local handleClientDisconnect\n'
)
grab_forward = (
    'local handleSetSpeed\n'
    'local handleGrabInput\n'
    'local handlePause\n'
    'local handleClientDisconnect\n'
)
patched_forward = (
    'local handleSetSpeed\n'
    'local handleGrabInput\n'
    'local handleForceStart\n'
    'local handlePause\n'
    'local handleClientDisconnect\n'
)
if original_forward in text:
    text = text.replace(original_forward, patched_forward, 1)
elif grab_forward in text:
    text = text.replace(grab_forward, patched_forward, 1)
elif patched_forward in text:
    pass
else:
    raise SystemExit(1)

original_pause = (
    'handlePause = function(msg)\n'
    '  if type(msg.paused) ~= "boolean" then\n'
    '    sendError(msg.id, "invalid_message", "Missing or invalid paused (expected boolean)")\n'
    '    return\n'
    '  end\n\n'
    '  Spring.SendCommands("pause " .. (msg.paused and "1" or "0"))\n'
    '  sendMessage({ type = "ok", id = msg.id })\n'
    'end\n'
)
patched_pause = (
    'handleGrabInput = function(msg)\n'
    '  if type(msg.enabled) ~= "boolean" then\n'
    '    sendError(msg.id, "invalid_message", "Missing or invalid enabled (expected boolean)")\n'
    '    return\n'
    '  end\n\n'
    '  Spring.SendCommands("GrabInput " .. (msg.enabled and "1" or "0"))\n'
    '  sendMessage({ type = "ok", id = msg.id })\n'
    'end\n\n'
    'handleForceStart = function(msg)\n'
    '  Spring.SendCommands("forcestart")\n'
    '  sendMessage({ type = "ok", id = msg.id })\n'
    'end\n\n'
    'handlePause = function(msg)\n'
    '  if type(msg.paused) ~= "boolean" then\n'
    '    sendError(msg.id, "invalid_message", "Missing or invalid paused (expected boolean)")\n'
    '    return\n'
    '  end\n\n'
    '  Spring.SendCommands("pause " .. (msg.paused and "1" or "0"))\n'
    '  sendMessage({ type = "ok", id = msg.id })\n'
    'end\n'
)
if original_pause in text:
    text = text.replace(original_pause, patched_pause, 1)
elif 'handleGrabInput = function(msg)' in text and 'handleForceStart = function(msg)' not in text:
    text = text.replace(
        'handlePause = function(msg)\n',
        'handleForceStart = function(msg)\n'
        '  Spring.SendCommands("forcestart")\n'
        '  sendMessage({ type = "ok", id = msg.id })\n'
        'end\n\n'
        'handlePause = function(msg)\n',
        1,
    )
elif 'handleGrabInput = function(msg)' in text:
    pass
else:
    raise SystemExit(1)
path.write_text(text, encoding="utf-8")
PY
    return $?
}

restore_watch_ai_bridge_widget() {
    if [[ -n "$AI_BRIDGE_WIDGET_PATH" && -n "$AI_BRIDGE_WIDGET_BACKUP" && -f "$AI_BRIDGE_WIDGET_BACKUP" ]]; then
        cp "$AI_BRIDGE_WIDGET_BACKUP" "$AI_BRIDGE_WIDGET_PATH"
    fi
    AI_BRIDGE_WIDGET_PATH=""
    AI_BRIDGE_WIDGET_BACKUP=""
}

resolve_watch_package_pool_entry() {
    local entry_name="$1"
    python3 - "$WRITE_DIR" "$entry_name" <<'PY'
from pathlib import Path
import gzip
import sys

write_dir = Path(sys.argv[1])
needle = sys.argv[2].encode("utf-8")
packages_dir = write_dir / "packages"
pool_dir = write_dir / "pool"

if not packages_dir.is_dir() or not pool_dir.is_dir():
    raise SystemExit(1)

for sdp_path in sorted(packages_dir.glob("*.sdp")):
    try:
        data = gzip.open(sdp_path, "rb").read()
    except OSError:
        continue
    entry_index = data.find(needle)
    if entry_index < 0:
        continue
    digest_start = entry_index + len(needle)
    digest = data[digest_start : digest_start + 16].hex()
    if len(digest) != 32:
        continue
    pool_path = pool_dir / digest[:2] / f"{digest[2:]}.gz"
    if pool_path.is_file():
        print(pool_path)
        raise SystemExit(0)

raise SystemExit(1)
PY
}

resolve_watch_package_pool_entries() {
    local entry_name="$1"
    python3 - "$WRITE_DIR" "$entry_name" <<'PY'
from pathlib import Path
import gzip
import sys

write_dir = Path(sys.argv[1])
needle = sys.argv[2].encode("utf-8")
packages_dir = write_dir / "packages"
pool_dir = write_dir / "pool"

if not packages_dir.is_dir() or not pool_dir.is_dir():
    raise SystemExit(1)

paths: list[str] = []
seen: set[str] = set()
for sdp_path in sorted(packages_dir.glob("*.sdp")):
    try:
        data = gzip.open(sdp_path, "rb").read()
    except OSError:
        continue
    start = 0
    while True:
        entry_index = data.find(needle, start)
        if entry_index < 0:
            break
        digest_start = entry_index + len(needle)
        digest = data[digest_start : digest_start + 16].hex()
        pool_path = pool_dir / digest[:2] / f"{digest[2:]}.gz"
        if len(digest) == 32 and pool_path.is_file():
            key = str(pool_path)
            if key not in seen:
                seen.add(key)
                paths.append(key)
        start = entry_index + 1

if not paths:
    raise SystemExit(1)

print("\n".join(paths))
PY
}

patch_watch_ai_namer() {
    AI_NAMER_POOL_PATH="$(
        resolve_watch_package_pool_entry "luarules/gadgets/ai_namer.lua"
    )" || {
        AI_NAMER_POOL_PATH=""
        AI_NAMER_POOL_BACKUP=""
        return 1
    }

    AI_NAMER_POOL_BACKUP="$ACTIVE_RUN_DIR/ai_namer.lua.pre-highbar.gz"
    cp "$AI_NAMER_POOL_PATH" "$AI_NAMER_POOL_BACKUP"
    python3 - "$AI_NAMER_POOL_PATH" <<'PY'
from pathlib import Path
import gzip
import sys

path = Path(sys.argv[1])
patched = """local gadget = gadget ---@type Gadget

function gadget:GetInfo()
  return {
    name    = "AI namer",
    desc    = "Assignes deterministic names to AI teams",
    author  = "HighBar",
    date    = "April 2026",
    license = "GNU GPL, v2 or later",
    layer   = 999,
    enabled = true,
  }
end

if not gadgetHandler:IsSyncedCode() then
  return false
end

local PUBLIC = { public = true }

local function applyStableAINames()
  local updated = false
  for _, teamID in ipairs(Spring.GetTeamList()) do
    if select(4, Spring.GetTeamInfo(teamID, false)) then
      local aiName = string.format("HighBarV3-team%d", teamID)
      Spring.SetGameRulesParam("ainame_" .. teamID, aiName, PUBLIC)
      Spring.Echo("HighBar AI name override: team " .. teamID .. " => " .. aiName)
      updated = true
    end
  end
  return updated
end

function gadget:Initialize()
  applyStableAINames()
end

function gadget:GameID()
  applyStableAINames()
end

function gadget:GameFrame(frame)
  if frame < 1 then
    return
  end
  applyStableAINames()
  gadgetHandler:RemoveGadget(self)
end
"""
with gzip.open(path, "wt", encoding="utf-8") as handle:
    handle.write(patched)
PY
    return $?
}

restore_watch_ai_namer() {
    if [[ -n "$AI_NAMER_POOL_PATH" && -n "$AI_NAMER_POOL_BACKUP" && -f "$AI_NAMER_POOL_BACKUP" ]]; then
        cp "$AI_NAMER_POOL_BACKUP" "$AI_NAMER_POOL_PATH"
    fi
    AI_NAMER_POOL_PATH=""
    AI_NAMER_POOL_BACKUP=""
}

install_watch_ai_name_gadget() {
    local gadget_dir="$WRITE_DIR/LuaRules/Gadgets"
    WATCH_AI_NAME_GADGET_PATH="$gadget_dir/highbar_ai_name_override.lua"
    WATCH_AI_NAME_GADGET_BACKUP="$ACTIVE_RUN_DIR/highbar_ai_name_override.lua.pre-highbar"
    mkdir -p "$gadget_dir"
    if [[ -f "$WATCH_AI_NAME_GADGET_PATH" ]]; then
        cp "$WATCH_AI_NAME_GADGET_PATH" "$WATCH_AI_NAME_GADGET_BACKUP"
    else
        WATCH_AI_NAME_GADGET_BACKUP=""
    fi
    python3 - "$WATCH_AI_NAME_GADGET_PATH" <<'PY'
from pathlib import Path
import sys

path = Path(sys.argv[1])
path.write_text(
    """local gadget = gadget ---@type Gadget

function gadget:GetInfo()
  return {
    name    = "HighBar AI Name Override",
    desc    = "Publishes stable AI names for watched BAR runs",
    author  = "HighBar",
    date    = "April 2026",
    license = "MIT",
    layer   = 999999,
    enabled = true,
  }
end

if not gadgetHandler:IsSyncedCode() then
  return false
end

local PUBLIC = { public = true }

local function normalizedText(value)
  if type(value) ~= "string" then
    return nil
  end
  if value == "" or value == "UNKNOWN" or value == "n/a" then
    return nil
  end
  return value
end

local function buildDesiredAIName(teamID)
  local _, aiName, _, shortName, _, options = Spring.GetAIInfo(teamID)
  local label = normalizedText(shortName) or normalizedText(aiName)
  local detail = nil
  if type(options) == "table" then
    detail = normalizedText(options.profile) or normalizedText(options.difficulty)
  end
  if not label then
    return string.format("AI team %d", teamID)
  end
  if detail and detail ~= label then
    return string.format("%s (%s)", label, detail)
  end
  return label
end

local function applyStableAINames()
  local updated = false
  for _, teamID in ipairs(Spring.GetTeamList()) do
    if select(4, Spring.GetTeamInfo(teamID, false)) then
      local aiName = buildDesiredAIName(teamID)
      Spring.SetGameRulesParam("ainame_" .. teamID, aiName, PUBLIC)
      updated = true
    end
  end
  return updated
end

function gadget:Initialize()
  applyStableAINames()
end

function gadget:GameID()
  applyStableAINames()
end

function gadget:GameFrame(frame)
  if frame < 1 then
    return
  end
  applyStableAINames()
  gadgetHandler:RemoveGadget(self)
end
""",
    encoding="utf-8",
)
PY
}

restore_watch_ai_name_gadget() {
    if [[ -z "$WATCH_AI_NAME_GADGET_PATH" ]]; then
        return
    fi
    if [[ -n "$WATCH_AI_NAME_GADGET_BACKUP" && -f "$WATCH_AI_NAME_GADGET_BACKUP" ]]; then
        cp "$WATCH_AI_NAME_GADGET_BACKUP" "$WATCH_AI_NAME_GADGET_PATH"
    else
        rm -f "$WATCH_AI_NAME_GADGET_PATH"
    fi
    WATCH_AI_NAME_GADGET_PATH=""
    WATCH_AI_NAME_GADGET_BACKUP=""
}

install_watch_ai_name_widget() {
    local widget_dir="$WRITE_DIR/LuaUI/Widgets"
    WATCH_AI_NAME_WIDGET_PATH="$widget_dir/aaa_highbar_ai_names.lua"
    WATCH_AI_NAME_WIDGET_BACKUP="$ACTIVE_RUN_DIR/aaa_highbar_ai_names.lua.pre-highbar"
    mkdir -p "$widget_dir"
    if [[ -f "$WATCH_AI_NAME_WIDGET_PATH" ]]; then
        cp "$WATCH_AI_NAME_WIDGET_PATH" "$WATCH_AI_NAME_WIDGET_BACKUP"
    else
        WATCH_AI_NAME_WIDGET_BACKUP=""
    fi
    python3 - "$WATCH_AI_NAME_WIDGET_PATH" <<'PY'
from pathlib import Path
import sys

path = Path(sys.argv[1])
path.write_text(
    """local widget = widget ---@type Widget

local PATCH_KEY = "__highbar_ai_name_patch"
local globalTable = widget._G or {}
local patchState = rawget(globalTable, PATCH_KEY)
if not patchState then
  patchState = {
    originalGetAIInfo = Spring.GetAIInfo,
    originalGetGameRulesParam = Spring.GetGameRulesParam,
  }
  rawset(globalTable, PATCH_KEY, patchState)
end

local function normalizedText(value)
  if type(value) ~= "string" then
    return nil
  end
  if value == "" or value == "UNKNOWN" or value == "n/a" then
    return nil
  end
  return value
end

local function buildDesiredAIName(teamID, aiName, shortName, options)
  local label = normalizedText(shortName) or normalizedText(aiName)
  local detail = nil
  if type(options) == "table" then
    detail = normalizedText(options.profile) or normalizedText(options.difficulty)
  end
  if not label then
    return string.format("AI team %d", teamID)
  end
  if detail and detail ~= label then
    return string.format("%s (%s)", label, detail)
  end
  return label
end

local function resolveAIName(teamID, currentName)
  local _, _, _, isAI = Spring.GetTeamInfo(teamID, false)
  if isAI then
    local _, aiName, _, shortName, _, options = patchState.originalGetAIInfo(teamID)
    return buildDesiredAIName(teamID, aiName, shortName, options)
  end
  return currentName
end

local function resolveGameRulesParam(key)
  if type(key) ~= "string" then
    return nil
  end
  local teamID = key:match("^ainame_(%d+)$")
  if not teamID then
    return nil
  end
  teamID = tonumber(teamID)
  if teamID == nil then
    return nil
  end
  local _, aiName, _, shortName, _, options = patchState.originalGetAIInfo(teamID)
  return buildDesiredAIName(teamID, aiName, shortName, options)
end

if not patchState.patchedGetAIInfo then
  patchState.patchedGetAIInfo = function(teamID, ...)
    local skirmishAIID, aiName, hostingPlayerID, shortName, version, options =
      patchState.originalGetAIInfo(teamID, ...)
    return skirmishAIID, resolveAIName(teamID, aiName), hostingPlayerID, shortName, version, options
  end
end

if not patchState.patchedGetGameRulesParam then
  patchState.patchedGetGameRulesParam = function(key, ...)
    local resolved = resolveGameRulesParam(key)
    if resolved ~= nil then
      return resolved
    end
    return patchState.originalGetGameRulesParam(key, ...)
  end
end

Spring.GetAIInfo = patchState.patchedGetAIInfo
Spring.GetGameRulesParam = patchState.patchedGetGameRulesParam

function widget:GetInfo()
  return {
    name = "HighBar AI Names",
    desc = "Provides stable AI names to BAR UI widgets",
    author = "HighBar",
    date = "2026-04-23",
    license = "MIT",
    layer = -1000000,
    enabled = true,
  }
end

function widget:Shutdown()
  local state = rawget(globalTable, PATCH_KEY)
  if state and state.originalGetAIInfo then
    Spring.GetAIInfo = state.originalGetAIInfo
    if state.originalGetGameRulesParam then
      Spring.GetGameRulesParam = state.originalGetGameRulesParam
    end
    rawset(globalTable, PATCH_KEY, nil)
  end
end
""",
    encoding="utf-8",
)
PY
    enable_watch_ai_name_widget_config "$BYAR_USER_CONFIG_PATH"
    enable_watch_ai_name_widget_config "$BYAR_ENGINE_CONFIG_PATH"
}

restore_watch_ai_name_widget() {
    if [[ -z "$WATCH_AI_NAME_WIDGET_PATH" ]]; then
        return
    fi
    if [[ -n "$WATCH_AI_NAME_WIDGET_BACKUP" && -f "$WATCH_AI_NAME_WIDGET_BACKUP" ]]; then
        cp "$WATCH_AI_NAME_WIDGET_BACKUP" "$WATCH_AI_NAME_WIDGET_PATH"
    else
        rm -f "$WATCH_AI_NAME_WIDGET_PATH"
    fi
    WATCH_AI_NAME_WIDGET_PATH=""
    WATCH_AI_NAME_WIDGET_BACKUP=""
}

install_watch_widget_override() {
    local widget_filename="$1"
    local source_ref="$2"
    local package_entry_name="$3"
    local widget_dir="$WRITE_DIR/LuaUI/Widgets"
    local target_path="$widget_dir/$widget_filename"
    local backup_path="$ACTIVE_RUN_DIR/$widget_filename.pre-highbar"
    local effective_source_ref="$source_ref"
    mkdir -p "$widget_dir"
    if [[ -f "$target_path" ]]; then
        cp "$target_path" "$backup_path"
    else
        backup_path=""
    fi
    if [[ -z "$effective_source_ref" ]]; then
        effective_source_ref="$(
            resolve_watch_package_pool_entry "$package_entry_name"
        )" || return 1
    fi
    python3 - "$effective_source_ref" "$target_path" "$widget_filename" <<'PY'
from pathlib import Path
import gzip
import re
import sys
import urllib.request

source_ref = sys.argv[1]
target_path = Path(sys.argv[2])
widget_filename = sys.argv[3]

if "://" in source_ref:
    with urllib.request.urlopen(source_ref, timeout=20) as response:
        target_path.write_bytes(response.read())
else:
    source_path = Path(source_ref)
    if source_path.suffix == ".gz":
        with gzip.open(source_path, "rt", encoding="utf-8") as handle:
            target_path.write_text(handle.read(), encoding="utf-8")
    else:
        target_path.write_text(source_path.read_text(encoding="utf-8"), encoding="utf-8")

text = target_path.read_text(encoding="utf-8")

if widget_filename == "gui_advplayerslist.lua":
    pattern = re.compile(
        r"function GetAIName\(teamID\)\n.*?\nend\n\nfunction CreatePlayerFromTeam",
        re.DOTALL,
    )
    replacement = """function GetAIName(teamID)
    local name = Spring.GetGameRulesParam('ainame_' .. teamID)
    if not name or name == "" or name == "n/a" then
        local _, aiName, _, shortName, _, options = sp.GetAIInfo(teamID)
        name = shortName
        if not name or name == "" or name == "UNKNOWN" or name == "n/a" then
            name = aiName
        end
        local detail = options and (options.profile or options.difficulty) or nil
        if detail and detail ~= "" and detail ~= name then
            name = name .. " (" .. detail .. ")"
        end
    end
    return name or string.format("AI team %d", teamID)
end

function CreatePlayerFromTeam"""
elif widget_filename == "gui_info.lua":
    pattern = re.compile(
        r"local function GetAIName\(teamID\)\n.*?\nend",
        re.DOTALL,
    )
    replacement = """local function GetAIName(teamID)
\tlocal name = Spring.GetGameRulesParam('ainame_' .. teamID)
\tif not name or name == "" or name == "n/a" then
\t\tlocal _, aiName, _, shortName, _, options = Spring.GetAIInfo(teamID)
\t\tname = shortName
\t\tif not name or name == "" or name == "UNKNOWN" or name == "n/a" then
\t\t\tname = aiName
\t\tend
\t\tlocal detail = options and (options.profile or options.difficulty) or nil
\t\tif detail and detail ~= "" and detail ~= name then
\t\t\tname = name .. " (" .. detail .. ")"
\t\tend
\tend
\treturn name or string.format("AI team %d", teamID)
end"""
elif widget_filename == "gui_com_nametags.lua":
    pattern = re.compile(
        r"name = Spring\.I18N\('ui\.playersList\.aiName', \{ name = spGetGameRulesParam\('ainame_' \.\. team\) \}\)",
    )
    replacement = """local aiLabel = spGetGameRulesParam('ainame_' .. team)
\t\t\tif not aiLabel or aiLabel == "" or aiLabel == "n/a" then
\t\t\t\tlocal _, aiName, _, shortName, _, options = Spring.GetAIInfo(team)
\t\t\t\taiLabel = shortName
\t\t\t\tif not aiLabel or aiLabel == "" or aiLabel == "UNKNOWN" or aiLabel == "n/a" then
\t\t\t\t\taiLabel = aiName
\t\t\t\tend
\t\t\t\tlocal detail = options and (options.profile or options.difficulty) or nil
\t\t\t\tif detail and detail ~= "" and detail ~= aiLabel then
\t\t\t\t\taiLabel = aiLabel .. " (" .. detail .. ")"
\t\t\t\tend
\t\t\tend
\t\t\tname = aiLabel or string.format("AI team %d", team)"""
elif widget_filename == "camera_player_tv.lua":
    pattern = re.compile(
        r"(?P<indent>\s*)name = niceName or aiName(?:\n(?P=indent)name = Spring\.I18N\('ui\.playersList\.aiName', \{ name = name \}\))?",
        re.MULTILINE,
    )

    def replace_camera_name(match: re.Match[str]) -> str:
        indent = match.group("indent")
        return (
            f"{indent}name = niceName\n"
            f"{indent}if not name or name == '' or name == 'n/a' then\n"
            f"{indent}\tname = aiName\n"
            f"{indent}end\n"
            f"{indent}local _, _, _, shortName, _, options = Spring.GetAIInfo(myTeamID)\n"
            f"{indent}if shortName and shortName ~= '' and shortName ~= 'UNKNOWN' and shortName ~= 'n/a' then\n"
            f"{indent}\tname = shortName\n"
            f"{indent}end\n"
            f"{indent}local detail = options and (options.profile or options.difficulty) or nil\n"
            f"{indent}if detail and detail ~= '' and detail ~= name then\n"
            f"{indent}\tname = name .. ' (' .. detail .. ')'\n"
            f"{indent}end\n"
            f"{indent}if not name or name == '' or name == 'n/a' then\n"
            f"{indent}\tname = string.format('AI team %d', myTeamID)\n"
            f"{indent}end"
        )

    text, count = pattern.subn(replace_camera_name, text)
    if count < 1:
        raise SystemExit(1)
    target_path.write_text(text, encoding="utf-8")
    raise SystemExit(0)
else:
    raise SystemExit(1)

text, count = pattern.subn(replacement, text, count=1)
if count != 1:
    raise SystemExit(1)
target_path.write_text(text, encoding="utf-8")
PY
    if [[ $? -ne 0 ]]; then
        if [[ -n "$backup_path" && -f "$backup_path" ]]; then
            cp "$backup_path" "$target_path"
        else
            rm -f "$target_path"
        fi
        return 1
    fi
    printf '%s|%s\n' "$target_path" "$backup_path" >> "$WATCH_WIDGET_OVERRIDE_MANIFEST"
}

install_watch_name_widget_overrides() {
    WATCH_WIDGET_OVERRIDE_MANIFEST="$ACTIVE_RUN_DIR/watch-widget-overrides.manifest"
    : > "$WATCH_WIDGET_OVERRIDE_MANIFEST"
    install_watch_widget_override "gui_advplayerslist.lua" "${HIGHBAR_WATCH_ADVPLAYERSLIST_SOURCE:-}" "luaui/widgets/gui_advplayerslist.lua" || return 1
    install_watch_widget_override "gui_info.lua" "${HIGHBAR_WATCH_GUI_INFO_SOURCE:-}" "luaui/widgets/gui_info.lua" || return 1
    install_watch_widget_override "gui_com_nametags.lua" "${HIGHBAR_WATCH_GUI_COM_NAMETAGS_SOURCE:-}" "luaui/widgets/gui_com_nametags.lua" || return 1
    install_watch_widget_override "camera_player_tv.lua" "${HIGHBAR_WATCH_CAMERA_PLAYER_TV_SOURCE:-}" "luaui/widgets/camera_player_tv.lua" || return 1
}

restore_watch_name_widget_overrides() {
    if [[ -n "$WATCH_WIDGET_OVERRIDE_MANIFEST" && -f "$WATCH_WIDGET_OVERRIDE_MANIFEST" ]]; then
        while IFS='|' read -r target_path backup_path; do
            [[ -n "$target_path" ]] || continue
            if [[ -n "$backup_path" && -f "$backup_path" ]]; then
                cp "$backup_path" "$target_path"
            else
                rm -f "$target_path"
            fi
        done < "$WATCH_WIDGET_OVERRIDE_MANIFEST"
    fi
    WATCH_WIDGET_OVERRIDE_MANIFEST=""
}

patch_watch_name_widgets() {
    WATCH_NAME_WIDGET_MANIFEST="$ACTIVE_RUN_DIR/watch-name-widgets.manifest"
    : > "$WATCH_NAME_WIDGET_MANIFEST"
    while IFS= read -r entry_name; do
        [[ -n "$entry_name" ]] || continue
        local pool_paths
        local backup_path
        pool_paths="$(
            resolve_watch_package_pool_entries "$entry_name"
        )" || {
            restore_watch_name_widgets
            WATCH_NAME_WIDGET_MANIFEST=""
            return 1
        }
        while IFS= read -r pool_path; do
            [[ -n "$pool_path" ]] || continue
            backup_path="$ACTIVE_RUN_DIR/$(basename "$pool_path").pre-highbar.gz"
            cp "$pool_path" "$backup_path"
            printf '%s|%s\n' "$pool_path" "$backup_path" >> "$WATCH_NAME_WIDGET_MANIFEST"
            python3 - "$pool_path" "$entry_name" <<'PY'
from pathlib import Path
import gzip
import re
import sys

path = Path(sys.argv[1])
entry_name = sys.argv[2]
text = gzip.open(path, "rt", encoding="utf-8").read()

if entry_name.endswith("gui_advplayerslist.lua"):
    pattern = re.compile(
        r"function GetAIName\(teamID\)\n.*?\nend\n\nfunction CreatePlayerFromTeam",
        re.DOTALL,
    )
    replacement = """function GetAIName(teamID)
    local _, _, _, name, _, options = sp.GetAIInfo(teamID)
    local niceName = Spring.GetGameRulesParam('ainame_' .. teamID)

    if niceName and niceName ~= "" and niceName ~= "n/a" then
        name = niceName
    elseif not name or name == "" or name == "n/a" then
        name = string.format("HighBarV3-team%d", teamID)
    end

    if Spring.Utilities.ShowDevUI() and options and options.profile then
        name = name .. " [" .. options.profile .. "]"
    end

    return name
end

function CreatePlayerFromTeam"""
elif entry_name.endswith("chat.lua") or entry_name.endswith("gui_territorial_domination.lua"):
    pattern = re.compile(
        r"local function getAIName\(teamID\)\n.*?\nend",
        re.DOTALL,
    )
    replacement = """local function getAIName(teamID)
\tlocal _, _, _, name, _, options = Spring.GetAIInfo(teamID)
\tlocal niceName = Spring.GetGameRulesParam('ainame_' .. teamID)
\tif niceName and niceName ~= "" and niceName ~= "n/a" then
\t\tname = niceName
\telseif not name or name == "" or name == "n/a" then
\t\tname = string.format("HighBarV3-team%d", teamID)
\tend
\tif Spring.Utilities.ShowDevUI() and options and options.profile then
\t\tname = name .. " [" .. options.profile .. "]"
\tend
\treturn name
end"""
elif entry_name.endswith("gui_info.lua"):
    pattern = re.compile(
        r"local function GetAIName\(teamID\)\n.*?\nend",
        re.DOTALL,
    )
    replacement = """local function GetAIName(teamID)
\tlocal _, _, _, name, _, options = Spring.GetAIInfo(teamID)
\tlocal niceName = Spring.GetGameRulesParam('ainame_' .. teamID)
\tif niceName and niceName ~= "" and niceName ~= "n/a" then
\t\tname = niceName
\telseif not name or name == "" or name == "n/a" then
\t\tname = string.format("HighBarV3-team%d", teamID)
\tend
\tif Spring.Utilities.ShowDevUI() and options and options.profile then
\t\tname = name .. " [" .. options.profile .. "]"
\tend
\treturn name
end"""
elif entry_name.endswith("cmd_share_unit.lua"):
    pattern = re.compile(
        r"local function findPlayerName\(teamId\)\n.*?\nend",
        re.DOTALL,
    )
    replacement = """local function findPlayerName(teamId)
\tlocal name = ''
\tlocal niceName = GetGameRulesParam('ainame_' .. teamId)
\tif niceName and niceName ~= "" and niceName ~= "n/a" then
\t\tname = niceName
\telse
\t\tlocal players = GetPlayerList(teamId)
\t\tname = (#players > 0) and GetPlayerInfo(players[1], false) or string.format('HighBarV3-team%d', teamId)

\t\tfor _, pID in ipairs(players) do
\t\t\tlocal pname, active, isspec = GetPlayerInfo(pID, false)
\t\t\tif active and not isspec then
\t\t\t\tname = pname
\t\t\t\tbreak
\t\t\tend
\t\tend
\tend
\treturn name
end"""
elif entry_name.endswith("map_startbox.lua"):
    pattern = re.compile(
        r"if isAI then\n.*?\n\t\telse",
        re.DOTALL,
    )
    replacement = """if isAI then
\t\t\tlocal _, _, _, aiName = Spring.GetAIInfo(teamID)
\t\t\tlocal niceName = Spring.GetGameRulesParam('ainame_' .. teamID)
\t\t\tif niceName and niceName ~= "" and niceName ~= "n/a" then
\t\t\t\taiName = niceName
\t\t\telseif not aiName or aiName == "" or aiName == "n/a" then
\t\t\t\taiName = string.format("HighBarV3-team%d", teamID)
\t\t\tend
\t\t\tbaseName = aiName
\t\telse"""
elif entry_name.endswith("gui_com_nametags.lua"):
    pattern = re.compile(
        r"name = Spring\.I18N\('ui\.playersList\.aiName', \{ name = spGetGameRulesParam\('ainame_' \.\. team\) \}\)",
    )
    replacement = """local aiName = spGetGameRulesParam('ainame_' .. team)
\t\t\tif aiName and aiName ~= "" and aiName ~= "n/a" then
\t\t\t\tname = aiName
\t\t\telse
\t\t\t\tname = string.format("HighBarV3-team%d", team)
\t\t\tend"""
elif entry_name.endswith("camera_player_tv.lua"):
    pattern = re.compile(
        r"(?P<indent>\s*)name = niceName or aiName(?:\n(?P=indent)name = Spring\.I18N\('ui\.playersList\.aiName', \{ name = name \}\))?",
        re.MULTILINE,
    )

    def replace_camera_name(match: re.Match[str]) -> str:
        indent = match.group("indent")
        return (
            f"{indent}if niceName and niceName ~= \"\" and niceName ~= \"n/a\" then\n"
            f"{indent}\tname = niceName\n"
            f"{indent}elseif aiName and aiName ~= \"\" and aiName ~= \"n/a\" then\n"
            f"{indent}\tname = aiName\n"
            f"{indent}else\n"
            f"{indent}\tname = string.format(\"HighBarV3-team%d\", myTeamID)\n"
            f"{indent}end"
        )

    updated, count = pattern.subn(replace_camera_name, text)
    if count < 1:
        raise SystemExit(1)
    with gzip.open(path, "wt", encoding="utf-8") as handle:
        handle.write(updated)
    raise SystemExit(0)
else:
    raise SystemExit(1)

updated, count = pattern.subn(replacement, text, count=1)
if count != 1:
    raise SystemExit(1)
with gzip.open(path, "wt", encoding="utf-8") as handle:
    handle.write(updated)
PY
            if [[ $? -ne 0 ]]; then
                restore_watch_name_widgets
                WATCH_NAME_WIDGET_MANIFEST=""
                return 1
            fi
        done <<< "$pool_paths"
    done <<'EOF'
luaui/widgets/gui_advplayerslist.lua
luaui/widgets/gui_chat.lua
luaui/widgets/cmd_share_unit.lua
luaui/widgets/gui_info.lua
luaui/widgets/gui_com_nametags.lua
luaui/widgets/camera_player_tv.lua
luaui/widgets/map_startbox.lua
luaui/rmlwidgets/gui_territorial_domination/gui_territorial_domination.lua
EOF
    return 0
}

restore_watch_name_widgets() {
    if [[ -n "$WATCH_NAME_WIDGET_MANIFEST" && -f "$WATCH_NAME_WIDGET_MANIFEST" ]]; then
        while IFS='|' read -r pool_path backup_path; do
            [[ -n "$pool_path" && -n "$backup_path" && -f "$backup_path" ]] || continue
            cp "$backup_path" "$pool_path"
        done < "$WATCH_NAME_WIDGET_MANIFEST"
    fi
    WATCH_NAME_WIDGET_MANIFEST=""
}

clear_watch_launch_context() {
    unset HIGHBAR_ITERTESTING_WATCH_LAUNCHED
    unset HIGHBAR_ITERTESTING_WATCH_ENGINE_MODE
    unset HIGHBAR_ITERTESTING_WATCH_ENGINE_BINARY
    unset HIGHBAR_ITERTESTING_WATCH_ENGINE_PID
    unset HIGHBAR_ITERTESTING_WATCH_STARTSCRIPT
    unset HIGHBAR_BAR_CLIENT_BINARY
    WATCH_HOST_PORT_RESOLVED=""
    WATCH_HOST_STARTSCRIPT=""
    WATCH_VIEWER_STARTSCRIPT=""
    WATCH_VIEWER_RUNTIME_DIR=""
    WATCH_VIEWER_LOG=""
    WATCH_VIEWER_PID_FILE=""
    WATCH_VIEWER_HELPER_PID=""
}

stop_live_topology() {
    if [[ -n "$WATCH_VIEWER_HELPER_PID" ]]; then
        kill -TERM "$WATCH_VIEWER_HELPER_PID" 2>/dev/null || true
    fi
    if [[ -n "$WATCH_VIEWER_PID_FILE" && -f "$WATCH_VIEWER_PID_FILE" ]]; then
        kill -TERM "$(cat "$WATCH_VIEWER_PID_FILE")" 2>/dev/null || true
    fi
    if [[ -f "$ENGINE_PID_FILE" ]]; then
        kill -TERM "$(cat "$ENGINE_PID_FILE")" 2>/dev/null || true
    fi
    if [[ -n "$COORD_PID" ]]; then
        kill -TERM "$COORD_PID" 2>/dev/null || true
    fi
    sleep 1
    restore_watch_ai_name_widget
    restore_watch_ai_name_gadget
    restore_watch_ai_bridge_widget
    restore_autoquit_config
    clear_watch_launch_context
}

prepare_attempt_dir() {
    local attempt="$1"
    ACTIVE_RUN_DIR="$RUN_DIR/attempt-$attempt"
    rm -rf "$ACTIVE_RUN_DIR"
    mkdir -p "$ACTIVE_RUN_DIR"
    COORD_SOCK="$ACTIVE_RUN_DIR/hb-coord.sock"
    COORD_ENDPOINT=""
    COORD_LOG="$ACTIVE_RUN_DIR/coord.log"
    ENGINE_LOG="$ACTIVE_RUN_DIR/highbar-launch.log"
    ENGINE_PID_FILE="$ACTIVE_RUN_DIR/highbar-launch.pid"
    COORD_PID=""
}

resolve_watch_launch_profile() {
    local resolved
    if [[ "$WATCH_ENABLED" != "true" ]]; then
        return 0
    fi
    resolved="$(
        HIGHBAR_WRITE_DIR="$WRITE_DIR" \
        HIGHBAR_ENGINE_RELEASE="${HIGHBAR_ENGINE_RELEASE:-recoil_2025.06.19}" \
        uv run --project "$REPO_ROOT/clients/python" python - "$WATCH_PROFILE" <<'PY'
import os
import shlex
import sys

from highbar_client.behavioral_coverage.bnv_watch import parse_watch_profile

profile = parse_watch_profile(sys.argv[1], environ=os.environ)
watch_speed = profile.watch_speed if profile.watch_speed is not None else 3.0
watch_speed_max = max(10.0, float(watch_speed))
for key, value in (
    ("WATCH_ENGINE_BINARY", profile.viewer_binary),
    ("WATCH_WINDOW_MODE_RESOLVED", profile.window_mode),
    ("WATCH_WINDOW_WIDTH_RESOLVED", str(profile.window_width)),
    ("WATCH_WINDOW_HEIGHT_RESOLVED", str(profile.window_height)),
    ("WATCH_MOUSE_CAPTURE_RESOLVED", "true" if profile.mouse_capture else "false"),
    ("WATCH_SPEED_RESOLVED", str(watch_speed)),
    ("WATCH_SPEED_MIN_RESOLVED", str(watch_speed)),
    ("WATCH_SPEED_MAX_RESOLVED", str(watch_speed_max)),
):
    print(f"{key}={shlex.quote(value)}")
PY
    )" || {
        echo "itertesting: failed to resolve watch profile '$WATCH_PROFILE'" >&2
        return 1
    }
    eval "$resolved"
}

reserve_watch_host_port() {
    python3 - <<'PY'
import socket

with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
    sock.bind(("127.0.0.1", 0))
    print(sock.getsockname()[1])
PY
}

prepare_watch_host_startscript() {
    local source_start_script="$1"
    local host_port="$2"
    local viewer_player_name="$3"
    local target_start_script="$ACTIVE_RUN_DIR/$(basename "${source_start_script%.startscript}")-watch-host.startscript"

    python3 - "$source_start_script" "$target_start_script" "$WATCH_SPEED_MIN_RESOLVED" "$WATCH_SPEED_MAX_RESOLVED" "$host_port" "$viewer_player_name" <<'PY'
from pathlib import Path
import re
import sys

source = Path(sys.argv[1])
target = Path(sys.argv[2])
min_speed = sys.argv[3]
max_speed = sys.argv[4]
host_port = sys.argv[5]
viewer_player_name = sys.argv[6]
text = source.read_text(encoding="utf-8")

for key, value in (("MinSpeed", min_speed), ("MaxSpeed", max_speed), ("HostPort", host_port)):
    pattern = rf"(^\s*{key}\s*=)\s*[^;]+;"
    replacement = rf"\g<1>{value};"
    updated, count = re.subn(pattern, replacement, text, flags=re.MULTILINE)
    if count == 0:
        raise SystemExit(f"missing {key} in {source}")
    text = updated

ai_block_pattern = re.compile(r"(?P<header>\n\t\[AI\d+\]\n\t\{\n)(?P<body>.*?)(?P<footer>\n\t\})", re.DOTALL)

def rewrite_ai_block(match: re.Match[str]) -> str:
    body = match.group("body")
    short_name_match = re.search(r"(^\s*ShortName\s*=)\s*([^;]+);", body, flags=re.MULTILINE)
    if not short_name_match:
        return match.group(0)
    short_name = short_name_match.group(2).strip()
    detail_match = re.search(r"^\s*(?:difficulty|profile)\s*=\s*([^;]+);", body, flags=re.MULTILINE)
    label = short_name
    if detail_match:
        detail = detail_match.group(1).strip()
        if detail and detail != short_name:
            label = f"{short_name} ({detail})"
    updated_body, count = re.subn(
        r"(^\s*Name\s*=)\s*[^;]+;",
        rf"\g<1>{label};",
        body,
        count=1,
        flags=re.MULTILINE,
    )
    if count == 0:
        updated_body = f"\t\tName={label};\n" + body
    return f"{match.group('header')}{updated_body}{match.group('footer')}"

text = ai_block_pattern.sub(rewrite_ai_block, text)

target.write_text(text, encoding="utf-8")
PY
    printf '%s\n' "$target_start_script"
}

prepare_watch_client_startscript() {
    local host_port="$1"
    local viewer_player_name="$2"
    local target_start_script="$ACTIVE_RUN_DIR/watch-client.startscript"

    python3 - "$target_start_script" "$host_port" "$viewer_player_name" <<'PY'
from pathlib import Path
import sys

target = Path(sys.argv[1])
host_port = sys.argv[2]
viewer_player_name = sys.argv[3]

target.write_text(
    f"""[GAME]
{{
\tHostIP=127.0.0.1;
\tHostPort={host_port};
\tSourcePort=0;
\tMyPlayerName={viewer_player_name};
\tIsHost=0;
}}
""",
    encoding="utf-8",
)
PY
    printf '%s\n' "$target_start_script"
}

launch_watch_viewer() {
    local viewer_engine="$1"
    local client_start_script="$2"

    WATCH_VIEWER_RUNTIME_DIR="$ACTIVE_RUN_DIR/viewer-runtime"
    WATCH_VIEWER_LOG="$ACTIVE_RUN_DIR/viewer-launch.log"
    WATCH_VIEWER_PID_FILE="$ACTIVE_RUN_DIR/viewer-launch.pid"
    mkdir -p "$WATCH_VIEWER_RUNTIME_DIR"

    if ! patch_watch_ai_bridge_widget; then
        echo "itertesting: failed to patch BAR AI Bridge widget for watch speed control" >&2
        return 1
    fi

    "$HEADLESS_DIR/_launch.sh" \
        --start-script "$client_start_script" \
        --engine "$viewer_engine" \
        --runtime-dir "$WATCH_VIEWER_RUNTIME_DIR" \
        --log "$WATCH_VIEWER_LOG" \
        --pid-file "$WATCH_VIEWER_PID_FILE" \
        --window-mode "$WATCH_WINDOW_MODE_RESOLVED" \
        --window-width "$WATCH_WINDOW_WIDTH_RESOLVED" \
        --window-height "$WATCH_WINDOW_HEIGHT_RESOLVED" \
        --mouse-capture "$WATCH_MOUSE_CAPTURE_RESOLVED" \
        --viewer-only true >/dev/null 2>&1 || {
            echo "itertesting: failed to launch graphical BAR watch client" >&2
            return 1
        }

    return 0
}

configure_live_attempt_env() {
    export HIGHBAR_WRITE_DIR="$WRITE_DIR"
    export HIGHBAR_ENGINE_RELEASE="recoil_2025.06.19"
    export HIGHBAR_COORDINATOR_OWNER_SKIRMISH_AI_ID="${HIGHBAR_COORDINATOR_OWNER_SKIRMISH_AI_ID:-1}"
    export HIGHBAR_TOKEN_PATH="${HIGHBAR_TOKEN_PATH:-/tmp/highbar.token}"
    if [[ -n "$EXPLICIT_CALLBACK_PROXY_ENDPOINT" ]]; then
        export HIGHBAR_CALLBACK_PROXY_ENDPOINT="$EXPLICIT_CALLBACK_PROXY_ENDPOINT"
    else
        export HIGHBAR_CALLBACK_PROXY_ENDPOINT="unix:$ACTIVE_RUN_DIR/highbar-1.sock"
    fi
}

wait_for_gateway_startup() {
    for _ in $(seq 1 30); do
        if grep -q '\[hb-gateway\] startup' "$ENGINE_LOG" 2>/dev/null; then
            return 0
        fi
        sleep 1
    done
    return 1
}

wait_for_watch_host_listener_bound() {
    local host_port="$1"
    local deadline
    deadline=$((SECONDS + WATCH_HOST_BIND_WAIT_SECONDS))
    while [[ $SECONDS -le $deadline ]]; do
        if [[ -f "$ENGINE_PID_FILE" ]] && ! kill -0 "$(cat "$ENGINE_PID_FILE")" 2>/dev/null; then
            echo "itertesting: host engine exited before watch listener became ready" >&2
            return 1
        fi
        if grep -q "\\[UDPListener\\] successfully bound socket on port $host_port" "$ENGINE_LOG" 2>/dev/null; then
            return 0
        fi
        sleep 0.2
    done
    echo "itertesting: watch host UDP listener did not bind on port $host_port within ${WATCH_HOST_BIND_WAIT_SECONDS}s" >&2
    return 1
}

export_watch_launch_context() {
    local watch_viewer_engine="$1"
    export HIGHBAR_ITERTESTING_WATCH_LAUNCHED="true"
    export HIGHBAR_ITERTESTING_WATCH_ENGINE_MODE="graphical-client"
    export HIGHBAR_ITERTESTING_WATCH_ENGINE_BINARY="$watch_viewer_engine"
    export HIGHBAR_BAR_CLIENT_BINARY="$watch_viewer_engine"
    export HIGHBAR_ITERTESTING_WATCH_STARTSCRIPT="$WATCH_VIEWER_STARTSCRIPT"
    if [[ -f "$WATCH_VIEWER_PID_FILE" ]]; then
        export HIGHBAR_ITERTESTING_WATCH_ENGINE_PID
        HIGHBAR_ITERTESTING_WATCH_ENGINE_PID="$(cat "$WATCH_VIEWER_PID_FILE")"
    fi
}

emit_watch_viewer_connection_notice() {
    if [[ -z "$WATCH_VIEWER_LOG" || ! -f "$WATCH_VIEWER_LOG" ]]; then
        return 0
    fi
    if grep -q '\[PreGame::UpdateClientNet\] server connection timeout' "$WATCH_VIEWER_LOG"; then
        echo "itertesting: watch_viewer connection=timeout log=$WATCH_VIEWER_LOG" >&2
        return 0
    fi
    if grep -q '\[Game::ClientReadNet\] added new player' "$WATCH_VIEWER_LOG"; then
        if grep -qE '\[f=[0-9-]+\]' "$WATCH_VIEWER_LOG"; then
            echo "itertesting: watch_viewer connection=live log=$WATCH_VIEWER_LOG" >&2
        else
            echo "itertesting: watch_viewer connection=joined log=$WATCH_VIEWER_LOG" >&2
        fi
        return 0
    fi
    if grep -q '\[PreGame::UpdateClientNet\] added new player' "$WATCH_VIEWER_LOG"; then
        echo "itertesting: watch_viewer connection=pregame log=$WATCH_VIEWER_LOG" >&2
        return 0
    fi
    echo "itertesting: watch_viewer connection=pending log=$WATCH_VIEWER_LOG" >&2
}

latest_stop_decision_path() {
    find "$REPORTS_DIR" -maxdepth 2 \
        \( -path "$NATURAL_SMOKE_REPORTS_DIR" -o -path "$NATURAL_SMOKE_REPORTS_DIR/*" \) -prune -o \
        -name 'campaign-stop-decision.json' -printf '%T@ %p\n' 2>/dev/null \
        | sort -nr \
        | head -n 1 \
        | cut -d' ' -f2-
}

latest_run_manifest_path() {
    find "$REPORTS_DIR" -maxdepth 2 \
        \( -path "$NATURAL_SMOKE_REPORTS_DIR" -o -path "$NATURAL_SMOKE_REPORTS_DIR/*" \) -prune -o \
        -name 'manifest.json' -printf '%T@ %p\n' 2>/dev/null \
        | sort -nr \
        | head -n 1 \
        | cut -d' ' -f2-
}

latest_manifest_in_dir() {
    local reports_dir="$1"
    find "$reports_dir" -maxdepth 2 -name 'manifest.json' -printf '%T@ %p\n' 2>/dev/null \
        | sort -nr \
        | head -n 1 \
        | cut -d' ' -f2-
}

emit_contract_health_notice() {
    local manifest_path="$1"
    if [[ -z "$manifest_path" || ! -f "$manifest_path" ]]; then
        return 1
    fi
    python3 - "$manifest_path" <<'PY'
import json
import os
import sys

manifest_path = sys.argv[1]
with open(manifest_path, "r", encoding="utf-8") as handle:
    manifest = json.load(handle)

decision = manifest.get("contract_health_decision") or {}
status = decision.get("decision_status", "ready_for_itertesting")
if status == "ready_for_itertesting":
    raise SystemExit(1)

report_path = os.path.join(os.path.dirname(manifest_path), "run-report.md")
print(f"itertesting: contract_health={status} report={report_path}")
for issue in manifest.get("contract_issues", ()):
    print(
        "itertesting: blocker="
        f"{issue.get('issue_id')} class={issue.get('issue_class')} "
        f"status={issue.get('status')}"
    )
for repro in manifest.get("deterministic_repros", ()):
    args = " ".join(repro.get("arguments", ()))
    command = " ".join(part for part in (repro.get("entrypoint", ""), args) if part)
    print(f"itertesting: repro[{repro.get('issue_id')}]={command}")
PY
}

emit_fixture_provisioning_notice() {
    local manifest_path="$1"
    if [[ -z "$manifest_path" || ! -f "$manifest_path" ]]; then
        return 1
    fi
    python3 - "$manifest_path" <<'PY'
import json
import re
import sys
from pathlib import Path

manifest_path = sys.argv[1]
with open(manifest_path, "r", encoding="utf-8") as handle:
    manifest = json.load(handle)

fixture = manifest.get("fixture_provisioning") or {}
transport = manifest.get("transport_provisioning") or {}
bootstrap = manifest.get("bootstrap_readiness") or {}
runtime_capability_profile = manifest.get("runtime_capability_profile") or {}
callback_diagnostics = manifest.get("callback_diagnostics") or []
prerequisite_resolution = manifest.get("prerequisite_resolution") or []
map_source_decisions = manifest.get("map_source_decisions") or []
interpretation_warnings = manifest.get("interpretation_warnings") or []
decision_trace = manifest.get("decision_trace") or []
class_statuses = fixture.get("class_statuses") or []
if not class_statuses:
    raise SystemExit(1)

affected = fixture.get("affected_command_ids") or []
print(
    "itertesting: fixture_statuses="
    + ",".join(
        f"{item.get('fixture_class')}:{item.get('status')}"
        for item in class_statuses
    )
)
print(
    "itertesting: fixture_affected_commands="
    + (",".join(affected) if affected else "none")
)
print(
    "itertesting: transport_status="
    + transport.get("status", "none")
)
print(
    "itertesting: transport_affected_commands="
    + (
        ",".join(transport.get("affected_command_ids", ()))
        if transport.get("affected_command_ids")
        else "none"
    )
)
print(
    "itertesting: bootstrap_readiness="
    + bootstrap.get("readiness_status", "none")
)
print(
    "itertesting: callback_diagnostics="
    + ",".join(
        f"{item.get('capture_stage')}:{item.get('availability_status')}"
        for item in callback_diagnostics
    )
    if callback_diagnostics
    else "itertesting: callback_diagnostics=none"
)
print(
    "itertesting: runtime_capability_profile="
    + (
        f"callbacks={','.join(str(item) for item in runtime_capability_profile.get('supported_callbacks', ())) or 'none'} "
        f"map={runtime_capability_profile.get('map_data_source_status', 'none')}"
    )
)
print(
    "itertesting: prerequisite_resolution="
    + ",".join(
        f"{item.get('prerequisite_name')}:{item.get('resolution_status')}"
        for item in prerequisite_resolution
    )
    if prerequisite_resolution
    else "itertesting: prerequisite_resolution=none"
)
print(
    "itertesting: map_source_decisions="
    + ",".join(
        f"{item.get('consumer')}:{item.get('selected_source')}"
        for item in map_source_decisions
    )
    if map_source_decisions
    else "itertesting: map_source_decisions=none"
)
print(
    "itertesting: fully_interpreted="
    + ("yes" if manifest.get("fully_interpreted", True) else "no")
)
print(
    "itertesting: interpretation_warnings="
    + (
        ",".join(
            f"{item.get('record_type')}:{item.get('severity')}"
            for item in interpretation_warnings
        )
        if interpretation_warnings
        else "none"
    )
)
print(
    "itertesting: decision_trace="
    + (
        ",".join(
            f"{item.get('concern')}:{item.get('source_layer')}"
            for item in decision_trace[:8]
        )
        if decision_trace
        else "none"
    )
)
report_path = Path(manifest_path).with_name("run-report.md")
semantic_inventory = []
if report_path.exists():
    in_section = False
    for line in report_path.read_text(encoding="utf-8").splitlines():
        if line == "## Command Semantic Inventory":
            in_section = True
            continue
        if in_section and line.startswith("## "):
            break
        if not in_section:
            continue
        match = re.match(r"- `(\d+)` `([^`]+)` .*`([^`]+)`", line)
        if match:
            semantic_inventory.append(
                f"{match.group(1)}:{match.group(2)}@{match.group(3)}"
            )
print(
    "itertesting: semantic_inventory="
    + (",".join(semantic_inventory) if semantic_inventory else "none")
)
semantic_gates = [
    item.get("command_id")
    + ":"
    + item.get("gate_kind", "")
    for item in manifest.get("semantic_gates", ())
]
print(
    "itertesting: semantic_gates="
    + (",".join(semantic_gates) if semantic_gates else "none")
)
PY
}

should_retry_live_session() {
    local manifest_path="$1"
    local decision_path="$2"
    local command_output="$3"
    local channel_dropped=1
    if [[ -f "$COORD_LOG" ]] && grep -q '\[cmd-ch\].*disconnected' "$COORD_LOG"; then
        channel_dropped=0
    fi

    if [[ -n "$manifest_path" && -f "$manifest_path" ]]; then
        python3 - "$manifest_path" "$decision_path" "$channel_dropped" <<'PY'
import json
import sys
manifest_path = sys.argv[1]
decision_path = sys.argv[2]
channel_dropped = sys.argv[3] == "0"
with open(manifest_path, "r", encoding="utf-8") as handle:
    manifest = json.load(handle)
decision = {}
if decision_path and decision_path != "None":
    try:
        with open(decision_path, "r", encoding="utf-8") as handle:
            decision = json.load(handle)
    except FileNotFoundError:
        decision = {}
channel = manifest.get("channel_health") or {}
summary = manifest.get("summary") or {}
should_retry = (
    channel_dropped
    and channel.get("status") in {"degraded", "recovered", "interrupted"}
    and (
        decision.get("stop_reason") in {"stalled", "interrupted"}
        or summary.get("transport_interrupted")
    )
    and summary.get("direct_verified_total", 0) == 0
)
raise SystemExit(0 if should_retry else 1)
PY
        return $?
    fi

    if [[ $channel_dropped -eq 0 ]] && printf '%s\n' "$command_output" | grep -q 'plugin command channel is not connected'; then
        return 0
    fi

    return 1
}

launch_live_topology() {
    local launch_start_script="${1:-$START_SCRIPT}"
    local watch_viewer_engine="${2:-}"
    local effective_start_script="$launch_start_script"
    configure_live_attempt_env
    disable_autoquit_for_attempt
    clear_watch_launch_context
    if ! highbar_start_coordinator "$EXAMPLES_DIR" "$ACTIVE_RUN_DIR" "bcov" "$COORD_LOG"; then
        echo "itertesting: coordinator failed to bind on unix or tcp — skip" >&2
        cat "$COORD_LOG" >&2
        return 77
    fi
    COORD_PID="$HIGHBAR_COORDINATOR_PID"
    COORD_ENDPOINT="$HIGHBAR_COORDINATOR_ENDPOINT"

    if [[ -n "$watch_viewer_engine" ]]; then
        if ! install_watch_ai_name_gadget; then
            echo "itertesting: failed to install BAR AI name override gadget" >&2
            return 1
        fi
        if ! install_watch_ai_name_widget; then
            echo "itertesting: failed to install BAR AI name override widget" >&2
            return 1
        fi
        WATCH_HOST_PORT_RESOLVED="$(reserve_watch_host_port)"
        WATCH_HOST_STARTSCRIPT="$(prepare_watch_host_startscript "$launch_start_script" "$WATCH_HOST_PORT_RESOLVED" "$WATCH_PLAYER_NAME_RESOLVED")"
        WATCH_VIEWER_STARTSCRIPT="$(prepare_watch_client_startscript "$WATCH_HOST_PORT_RESOLVED" "$WATCH_PLAYER_NAME_RESOLVED")"
        effective_start_script="$WATCH_HOST_STARTSCRIPT"
    fi

    LAUNCH_ARGS=(
        "$HEADLESS_DIR/_launch.sh"
        --start-script "$effective_start_script"
        --coordinator "$COORD_ENDPOINT"
        --enable-builtin "$ENABLE_BUILTIN"
        --runtime-dir "$ACTIVE_RUN_DIR"
    )
    LAUNCH_OUT=$("${LAUNCH_ARGS[@]}" 2>&1)
    LAUNCH_RC=$?
    if [[ $LAUNCH_RC -eq 77 ]]; then
        echo "itertesting: _launch.sh prereq missing — skip" >&2
        return 77
    fi
    if [[ $LAUNCH_RC -ne 0 ]]; then
        echo "itertesting: _launch.sh failed — fail" >&2
        return 1
    fi

    if [[ -n "$watch_viewer_engine" ]]; then
        if ! wait_for_watch_host_listener_bound "$WATCH_HOST_PORT_RESOLVED"; then
            return 1
        fi
        if ! launch_watch_viewer "$watch_viewer_engine" "$WATCH_VIEWER_STARTSCRIPT"; then
            return 1
        fi
        export_watch_launch_context "$watch_viewer_engine"
        echo "itertesting: watch_viewer launched pid=${HIGHBAR_ITERTESTING_WATCH_ENGINE_PID:-unknown} port=$WATCH_HOST_PORT_RESOLVED log=$WATCH_VIEWER_LOG" >&2
    fi

    if ! wait_for_gateway_startup; then
        echo "itertesting: gateway startup not seen — fail" >&2
        return 1
    fi

    EFFECTIVE_WRITEDIR="$WRITE_DIR/engine/recoil_2025.06.19"
    fault_status "$EFFECTIVE_WRITEDIR"
    fs=$?
    if [[ $fs -eq 2 ]]; then
        echo "itertesting: gateway Disabled at start — skip" >&2
        return 77
    fi

    sleep "$BOOTSTRAP_WAIT_SECONDS"
    if [[ -n "$watch_viewer_engine" ]]; then
        emit_watch_viewer_connection_notice
    fi
    return 0
}

run_live_campaign() {
    local attempt="$1"
    local out_file="$ACTIVE_RUN_DIR/itertesting.out"
    local before_stop=""
    local after_stop=""
    local before_manifest=""
    local after_manifest=""
    local command_output=""
    local rc=0

    before_stop="$(latest_stop_decision_path)"
    before_manifest="$(latest_run_manifest_path)"
    ARGS=(
        itertesting
        --endpoint "$COORD_ENDPOINT"
        --startscript "$START_SCRIPT"
        --reports-dir "$REPORTS_DIR"
        --retry-intensity "$RETRY_INTENSITY"
        --runtime-target-minutes "$RUNTIME_TARGET_MINUTES"
        --threshold "$THRESHOLD"
        --gameseed "$GAMESEED"
        --cheat-startscript "$CHEAT_STARTSCRIPT"
    )
    if [[ -n "$MAX_RUNS" ]]; then
        ARGS+=(--max-improvement-runs "$MAX_RUNS")
    fi
    if [[ "$SPLIT_LIVE_SETUP" == "true" ]]; then
        ARGS+=(--allow-cheat-escalation --no-natural-first)
    elif [[ "${HIGHBAR_ITERTESTING_ALLOW_CHEAT_ESCALATION:-false}" == "true" ]]; then
        ARGS+=(--allow-cheat-escalation)
    fi
    if [[ "$WATCH_ENABLED" == "true" ]]; then
        ARGS+=(--watch --watch-profile "$WATCH_PROFILE")
        if [[ -n "$WATCH_SPEED" ]]; then
            ARGS+=(--watch-speed "$WATCH_SPEED")
        fi
    fi

    echo "itertesting: invoking live campaign (attempt $attempt): ${ARGS[*]}"
    uv run --project "$REPO_ROOT/clients/python" python -m highbar_client.behavioral_coverage "${ARGS[@]}" >"$out_file" 2>&1
    rc=$?
    command_output="$(cat "$out_file")"
    printf '%s\n' "$command_output"

    after_stop="$(latest_stop_decision_path)"
    after_manifest="$(latest_run_manifest_path)"
    emit_contract_health_notice "$after_manifest" || true
    emit_fixture_provisioning_notice "$after_manifest" || true
    if should_retry_live_session "$after_manifest" "$after_stop" "$command_output"; then
        if [[ "$after_stop" != "$before_stop" && -n "$after_stop" ]]; then
            echo "itertesting: live session degraded; latest stop decision=$(basename "$(dirname "$after_stop")")/$(basename "$after_stop")" >&2
        elif [[ "$after_manifest" != "$before_manifest" && -n "$after_manifest" ]]; then
            echo "itertesting: live session degraded; latest manifest=$(basename "$(dirname "$after_manifest")")/$(basename "$after_manifest")" >&2
        else
            echo "itertesting: live session degraded before a new stop decision artifact was written" >&2
        fi
        return 86
    fi

    return $rc
}

emit_natural_smoke_notice() {
    local manifest_path="$1"
    if [[ -z "$manifest_path" || ! -f "$manifest_path" ]]; then
        return 1
    fi
    python3 - "$manifest_path" <<'PY'
import json
import os
import sys

manifest_path = sys.argv[1]
with open(manifest_path, "r", encoding="utf-8") as handle:
    manifest = json.load(handle)

decision = manifest.get("contract_health_decision") or {}
bootstrap = manifest.get("bootstrap_readiness") or {}
print(
    "itertesting: natural_smoke="
    f"{decision.get('decision_status', 'unknown')} "
    f"bootstrap={bootstrap.get('readiness_status', 'none')} "
    f"report={os.path.join(os.path.dirname(manifest_path), 'run-report.md')}"
)
PY
}

run_natural_smoke_campaign() {
    local smoke_reports_dir="$NATURAL_SMOKE_REPORTS_DIR"
    local smoke_out_file="$ACTIVE_RUN_DIR/natural-smoke.out"
    local smoke_output=""
    local smoke_manifest=""

    mkdir -p "$smoke_reports_dir"
    ARGS=(
        itertesting
        --endpoint "$COORD_ENDPOINT"
        --startscript "$START_SCRIPT"
        --reports-dir "$smoke_reports_dir"
        --retry-intensity quick
        --runtime-target-minutes 1
        --threshold "$THRESHOLD"
        --gameseed "$GAMESEED"
        --cheat-startscript "$CHEAT_STARTSCRIPT"
        --max-improvement-runs 0
        --no-watch
    )

    echo "itertesting: invoking natural smoke: ${ARGS[*]}"
    uv run --project "$REPO_ROOT/clients/python" python -m highbar_client.behavioral_coverage "${ARGS[@]}" >"$smoke_out_file" 2>&1
    smoke_output="$(cat "$smoke_out_file")"
    printf '%s\n' "$smoke_output"

    smoke_manifest="$(latest_manifest_in_dir "$smoke_reports_dir")"
    emit_natural_smoke_notice "$smoke_manifest" || true
    return 0
}

cleanup() {
    stop_live_topology
}

main() {
    trap cleanup EXIT

    if [[ "$SKIP_LIVE" == "true" ]]; then
        ARGS=(
            itertesting
            --reports-dir "$REPORTS_DIR"
            --retry-intensity "$RETRY_INTENSITY"
            --runtime-target-minutes "$RUNTIME_TARGET_MINUTES"
            --threshold "$THRESHOLD"
            --gameseed "$GAMESEED"
            --cheat-startscript "$CHEAT_STARTSCRIPT"
            --skip-live
        )
        if [[ -n "$MAX_RUNS" ]]; then
            ARGS+=(--max-improvement-runs "$MAX_RUNS")
        fi

        if [[ "${HIGHBAR_ITERTESTING_ALLOW_CHEAT_ESCALATION:-false}" == "true" ]]; then
            ARGS+=(--allow-cheat-escalation)
        fi
        if [[ "$WATCH_ENABLED" == "true" ]]; then
            ARGS+=(--watch --watch-profile "$WATCH_PROFILE")
            if [[ -n "$WATCH_SPEED" ]]; then
                ARGS+=(--watch-speed "$WATCH_SPEED")
            fi
        fi

        echo "itertesting: invoking synthetic campaign: ${ARGS[*]}"
        uv run --project "$REPO_ROOT/clients/python" python -m highbar_client.behavioral_coverage "${ARGS[@]}" "$@"
        rc=$?
        emit_contract_health_notice "$(latest_run_manifest_path)" || true
        emit_fixture_provisioning_notice "$(latest_run_manifest_path)" || true
        return $rc
    fi

    if [[ "$WATCH_ENABLED" == "true" ]]; then
        resolve_watch_launch_profile || return 1
    fi

    if [[ "$SPLIT_LIVE_SETUP" == "true" ]]; then
        prepare_attempt_dir "smoke"
        launch_live_topology "$START_SCRIPT"
        launch_rc=$?
        if [[ $launch_rc -ne 0 ]]; then
            return $launch_rc
        fi
        run_natural_smoke_campaign
        stop_live_topology
    fi

    attempt=1
    total_attempts=$((LIVE_RETRIES + 1))
    while [[ $attempt -le $total_attempts ]]; do
        prepare_attempt_dir "$attempt"
        if [[ "$SPLIT_LIVE_SETUP" == "true" ]]; then
            if [[ "$WATCH_ENABLED" == "true" ]]; then
                launch_live_topology "$CHEAT_STARTSCRIPT" "$WATCH_ENGINE_BINARY"
            else
                launch_live_topology "$CHEAT_STARTSCRIPT"
            fi
        else
            if [[ "$WATCH_ENABLED" == "true" ]]; then
                launch_live_topology "$START_SCRIPT" "$WATCH_ENGINE_BINARY"
            else
                launch_live_topology "$START_SCRIPT"
            fi
        fi
        launch_rc=$?
        if [[ $launch_rc -ne 0 ]]; then
            return $launch_rc
        fi

        run_live_campaign "$attempt"
        campaign_rc=$?
        if [[ $campaign_rc -eq 86 && $attempt -lt $total_attempts ]]; then
            echo "itertesting: retrying live run with a clean coordinator/engine session" >&2
            stop_live_topology
            attempt=$((attempt + 1))
            continue
        fi
        return $campaign_rc
    done
}

if [[ "${BASH_SOURCE[0]}" == "$0" ]]; then
    main "$@"
fi

function gadget:GetInfo()
  return {
    name = "HighBar Enemy Spawner",
    desc = "Spawns passive enemy fixtures for HighBar live coverage",
    author = "HighBar",
    version = "0.1",
    date = "2026-04-23",
    license = "MIT",
    layer = 1001,
    enabled = true,
  }
end

if not gadgetHandler:IsSyncedCode() then
  return false
end

local MESSAGE_PREFIX = "highbar_spawn_enemy:"
local DAMAGE_PREFIX = "highbar_damage_unit:"
local spawnedByAiTeam = {}

local function splitFields(payload)
  local fields = {}
  for field in payload:gmatch("([^:]+)") do
    fields[#fields + 1] = field
  end
  return fields
end

local function firstEnemyTeam(aiTeam)
  local senderAllyTeam = select(6, Spring.GetTeamInfo(aiTeam, false))
  if senderAllyTeam == nil then
    return nil
  end
  local gaiaTeam = Spring.GetGaiaTeamID()
  for _, teamID in ipairs(Spring.GetTeamList()) do
    if teamID ~= gaiaTeam then
      local _, _, _, isDead, _, allyTeam = Spring.GetTeamInfo(teamID, false)
      if not isDead and allyTeam ~= senderAllyTeam then
        return teamID
      end
    end
  end
  return nil
end

local function destroyTrackedUnit(aiTeam)
  local unitID = spawnedByAiTeam[aiTeam]
  if unitID and Spring.ValidUnitID(unitID) then
    Spring.DestroyUnit(unitID, false, true)
  end
  spawnedByAiTeam[aiTeam] = nil
end

function gadget:RecvSkirmishAIMessage(aiTeam, dataStr)
  if dataStr:sub(1, #DAMAGE_PREFIX) == DAMAGE_PREFIX then
    local fields = splitFields(dataStr:sub(#DAMAGE_PREFIX + 1))
    local unitID = tonumber(fields[1] or "")
    local damage = tonumber(fields[2] or "") or 25
    if not unitID or not Spring.ValidUnitID(unitID) then
      return "error:invalid_unit"
    end
    if Spring.GetUnitTeam(unitID) ~= aiTeam then
      return "error:not_owned"
    end
    local health, maxHealth = Spring.GetUnitHealth(unitID)
    if not health or not maxHealth then
      return "error:health_unavailable"
    end
    if health <= 1 then
      return "error:unit_already_critical"
    end
    local appliedDamage = math.max(1, math.min(damage, health - 1))
    local newHealth = math.max(1, health - appliedDamage)
    Spring.SetUnitHealth(unitID, newHealth)
    return string.format("%.1f", newHealth)
  end

  if dataStr:sub(1, #MESSAGE_PREFIX) ~= MESSAGE_PREFIX then
    return nil
  end

  local fields = splitFields(dataStr:sub(#MESSAGE_PREFIX + 1))
  local unitName = fields[1]
  local x = tonumber(fields[2] or "")
  local z = tonumber(fields[3] or "")
  local facing = fields[4] or "west"
  if not unitName or not x or not z then
    return "error:invalid_args"
  end

  local enemyTeam = firstEnemyTeam(aiTeam)
  if enemyTeam == nil then
    return "error:no_enemy_team"
  end

  destroyTrackedUnit(aiTeam)

  local y = Spring.GetGroundHeight(x, z)
  local unitID = Spring.CreateUnit(unitName, x, y, z, facing, enemyTeam)
  if not unitID then
    return "error:create_failed"
  end

  Spring.GiveOrderToUnit(unitID, CMD.STOP, {}, {})
  spawnedByAiTeam[aiTeam] = unitID
  return tostring(unitID)
end

function gadget:UnitDestroyed(unitID)
  for aiTeam, trackedUnitID in pairs(spawnedByAiTeam) do
    if trackedUnitID == unitID then
      spawnedByAiTeam[aiTeam] = nil
    end
  end
end

function widget:GetInfo()
  return {
    name = "HighBar Admin Speed",
    desc = "Applies HighBar admin speed requests in headless live tests",
    author = "HighBar",
    version = "0.1",
    date = "2026-04-24",
    license = "MIT",
    layer = 1001,
    enabled = true,
  }
end

local SPEED_PREFIX = "highbar_admin_speed:"

function widget:RecvSkirmishAIMessage(_, dataStr)
  if dataStr:sub(1, #SPEED_PREFIX) ~= SPEED_PREFIX then
    return nil
  end

  local speed = tonumber(dataStr:sub(#SPEED_PREFIX + 1))
  if not speed or speed <= 0 then
    return "error:invalid_speed"
  end

  local text = string.format("%g", speed)
  Spring.SendCommands({
    "setmaxspeed " .. text,
    "setminspeed " .. text,
    "setmaxspeed " .. text,
  })
  return "ok"
end

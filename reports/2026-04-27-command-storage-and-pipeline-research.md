# Command Storage and Assembly in Recoil/BAR/CircuitAI/HighBarV3

**Date:** 2026-04-27
**Scope:** Comprehensive trace of "where command information is stored
and how it is put together" across the four layers HighBarV3 sits on:

1. The **Recoil/Spring engine** (`/home/developer/recoil-engine`).
2. The **Spring AI C ABI** that engine plugins talk to.
3. The **CircuitAI/BARb** fork that HighBarV3 inherits
   (`/home/developer/projects/HighBarV3/src/circuit`).
4. The **HighBarV3 gRPC gateway** layered on top.

Repos surveyed:
- `/home/developer/recoil-engine` — Recoil engine source (rts/, AI/).
- `/home/developer/projects/HighBarV3` — the CircuitAI/BARb fork with the
  new `CGrpcGatewayModule`.
- BAR / `Beyond-All-Reason` game files were **not present** as a separate
  checkout; everything BAR-specific that V3 cares about (custom CMD ids,
  unit defs, build options) is consumed at runtime through the engine's
  AI callback. Where this report says "BAR-side", it means the data and
  CMD ids the BAR game registers with the engine — visible in V3 only as
  numeric constants in `circuit/unit/CircuitUnit.h` and as proto arms.

---

## 0. The Mental Model

A "command" is one record in a per-unit FIFO of orders. It is the same
shape no matter who issued it (Lua gadget, human player, Skirmish AI,
HighBarV3 gateway), and the same shape no matter what it does (move,
build, fire-state). The engine carries that record in a single struct
(`Command`), holds them in a `std::deque<Command>` per unit
(`CCommandQueue`), and **also** holds a parallel set of `SCommandDescription`
records describing the *kinds* of commands that unit can accept (its
"command card" / build menu).

Everything else is a translator that converts some external representation
(Lua table, network packet, AI C struct, protobuf message) into either:
- a fully-populated `Command` to feed `CCommandAI::GiveCommand`, or
- a high-level engine call (`unit->MoveTo`, `unit->Build`, …) that
  *itself* synthesizes a `Command` and gives it to the same entry point.

Once given, the command flows through:

```
GiveCommand → eventHandler.AllowCommand → eventHandler.UnitCommand
  → GiveCommandReal → AllowedCommand check
  → GiveAllowedCommand → ExecuteStateCommand (toggles)
                       │
                       └── flush queue if !SHIFT, then commandQue.push_back
                             ↓
                           SlowUpdate / Execute*
                             ↓
                           FinishCommand → commandQue.pop_front
                             ↓
                           eventHandler.UnitCmdDone + AI CommandFinished
```

From here the report walks each layer top-to-bottom.

---

## 1. Engine Storage Primitives

All paths under `rts/Sim/Units/CommandAI/`.

### 1.1 `struct Command` — the universal record

`rts/Sim/Units/CommandAI/Command.h:150–454`

```cpp
struct Command {
private:
    /// [0] := CMD_xxx code (custom codes can also be used)
    /// [1] := AI Command callback id
    int id[2] = {0, -1};

    int timeOut = INT_MAX;          // absolute frame; INT_MAX = never

    unsigned int pageIndex = -1u;   // CommandParamsPool page (if >8 params)
    unsigned int numParams = 0;
    unsigned int tag = 0;           // unique within the owning queue
    unsigned char options = 0;      // bitfield: SHIFT, CTRL, ALT, META, RMB,
                                    //          INTERNAL_ORDER

    float params[MAX_COMMAND_PARAMS]; // inline params, used if numParams ≤ 8
};
```

Key invariants:

- `id[0]` carries the engine command code: positive for built-in CMDs (see
  table below), **negative for build orders** (`-unitDefId`), values
  ≥1000 for custom Lua-registered or BAR/CircuitAI commands.
- `id[1]` is the **AI Command callback id** — the value an AI plugin
  registers when issuing the order; it is echoed back on
  `CommandFinished` so the AI can correlate.
- The 32 bytes of `float params[8]` sit inline; once the command needs a
  ninth parameter, `pageIndex` is allocated from `CommandParamsPool` and
  the inline buffer is zeroed (`Command.cpp:61–83`). `IsPooledCommand()
  == (pageIndex != -1u)`. The pool handles the unbounded-arity case
  (e.g. terraform polygons, multi-target priority lists) without
  bloating every `Command` to many KB.
- `tag` is assigned by `CCommandQueue::push_*` using a 24-bit rolling
  counter (`CommandQueue.h:29, 116`), giving the queue a stable
  per-command identifier independent of slot index.
- `options` flag bits — `Command.h:89–94`:

  | Bit          | Meaning                                                                  |
  |--------------|--------------------------------------------------------------------------|
  | `META_KEY`   | `0x04` – attack lock-on (don't drop target after attack-cmd) |
  | `INTERNAL_ORDER` | `0x08` – not user-initiated (engine/AI generated)                |
  | `RIGHT_MOUSE_KEY` | `0x10` – right-click semantics (e.g. queue front for retreat)   |
  | `SHIFT_KEY`  | `0x20` – append to queue (the most important one)                       |
  | `CONTROL_KEY` | `0x40` – modifier (e.g. stockpile +20)                                 |
  | `ALT_KEY`    | `0x80` – override-queued / per-command modifier                          |

  The header itself notes "these names are misleading" — `SHIFT_KEY` is
  really "queue this order"; treat them as opaque flags whose meaning
  depends on the command kind.

`Command` has a parallel C-linkage view, `RawCommand`
(`Command.h:125–141`), used at the AI ABI boundary. `ToRawCommand()` /
`FromRawCommand()` swap between the two; `FromRawCommand` preserves the
pooled-params reference rather than copying the float array.

### 1.2 Built-in command codes

`Command.h:14–53`. The complete set of CMD_* values that the engine
itself defines:

| Code | Constant            | Meaning                                            |
|-----:|---------------------|----------------------------------------------------|
| 0    | `CMD_STOP`          | clear / cancel current order                       |
| 1    | `CMD_INSERT`        | meta: insert another command into the queue        |
| 2    | `CMD_REMOVE`        | meta: remove commands matching (id, tag) selectors |
| 5    | `CMD_WAIT`          | block on signal                                    |
| 6    | `CMD_TIMEWAIT`      | wait N seconds                                     |
| 7    | `CMD_DEATHWAIT`     | wait until a specific unit dies                    |
| 8    | `CMD_SQUADWAIT`     | wait until N units have arrived                    |
| 9    | `CMD_GATHERWAIT`    | wait for the whole group                           |
| 10   | `CMD_MOVE`          | move to position                                    |
| 15   | `CMD_PATROL`        | patrol to position                                  |
| 16   | `CMD_FIGHT`         | fight-move (attack-on-the-way)                      |
| 20   | `CMD_ATTACK`        | attack unit / ground                                |
| 21   | `CMD_AREA_ATTACK`   | attack area                                         |
| 25   | `CMD_GUARD`         | guard ally                                          |
| 35–37| `CMD_GROUPSELECT/ADD/CLEAR` | UI groups                                  |
| 40   | `CMD_REPAIR`        | repair friendly unit / area                        |
| 45   | `CMD_FIRE_STATE`    | hold fire / return / fire at will / at neutral     |
| 50   | `CMD_MOVE_STATE`    | hold pos / maneuver / roam                         |
| 55   | `CMD_SETBASE`       | factory rally point                                 |
| 60   | `CMD_INTERNAL`      | engine-internal markers (NEXT/PREV/CUSTOM)         |
| 65   | `CMD_SELFD`         | self destruct                                       |
| 75   | `CMD_LOAD_UNITS`    | transport load                                      |
| 76   | `CMD_LOAD_ONTO`     | mark transportee                                    |
| 80–81| `CMD_UNLOAD_UNITS/UNIT` | transport unload                              |
| 85   | `CMD_ONOFF`         | activate state                                      |
| 90   | `CMD_RECLAIM`       | reclaim feature/unit                                |
| 95   | `CMD_CLOAK`         | cloak toggle                                        |
| 100  | `CMD_STOCKPILE`     | stockpile weapon                                    |
| 105  | `CMD_MANUALFIRE`    | manual-fire (aliased `CMD_DGUN` for AIs)            |
| 110  | `CMD_RESTORE`       | restore terrain                                     |
| 115  | `CMD_REPEAT`        | toggle queue repeat                                 |
| 120  | `CMD_TRAJECTORY`    | low/high trajectory                                 |
| 125  | `CMD_RESURRECT`     | resurrect feature                                   |
| 130  | `CMD_CAPTURE`       | capture enemy                                       |
| 135  | `CMD_AUTOREPAIRLEVEL`| auto-repair gauge (UI)                             |
| 145  | `CMD_IDLEMODE`      | idle behavior                                       |
| 150  | `CMD_FAILED`        | sentinel: command failed                            |

Any negative `cmdID` is a build order: `-cmdID` is the `UnitDef::id` of
the thing to build (`Command.h:13`, `BuilderCAI.cpp` populates these
from `unitDef->buildOptions`).

### 1.3 `CCommandQueue` — per-unit FIFO

`rts/Sim/Units/CommandAI/CommandQueue.h`

A thin friend-wrapper around `std::deque<Command>` plus:
- `QueueType` enum: `CommandQueueType` (normal), `BuildQueueType`
  (factory production), `NewUnitQueueType` (template applied to
  newly-built units).
- `tagCounter` — a per-queue 24-bit cyclic counter that names every
  pushed command (`maxTagValue = (1<<24) = 16777216`,
  `CommandQueue.h:29`). Pushing increments the counter and stamps the
  back/front entry's `tag`.
- All mutators (`push_back`, `push_front`, `insert`, `emplace_*`)
  re-stamp the tag on each operation, so the tag is always assigned by
  the queue, never carried in from the caller's `Command`.
- The class is non-copyable (private copy ctor) — queues live inside
  their owner `CCommandAI`.

### 1.4 `CommandParamsPool` — overflow storage

`rts/Sim/Units/CommandAI/CommandParamsPool.hpp`

A two-vector arena: a `vector<vector<float>>` of "pages" plus a free-
index stack. `AcquirePage()` returns a page index; the `Command`
serializes its params into that page, sets `pageIndex`, and reads back
through `cmdParamsPool.GetPtr(pageIndex, idx)`. On destruction
(`Command.cpp:22–26`) the page is released. The pool is global
(`extern CommandParamsPool cmdParamsPool` in `CommandParamsPool.hpp:72`,
defined in `Command.cpp:6`). Parameters >8 are appended via
`Command::PushParam` which transparently migrates the inline buffer to a
pooled page on overflow (`Command.cpp:61–83`).

### 1.5 `SCommandDescription` — what a unit *can* do

`rts/Sim/Units/CommandAI/CommandDescription.h:11–74`

```cpp
struct SCommandDescription {
    int id = 0;                  // CMD_* code (or -unitDefId for build options)
    int type = CMDTYPE_ICON;     // UI shape (see types in Command.h:55–71)
    mutable int refCount = 1;
    bool queueing, hidden, disabled, showUnique, onlyTexture;
    std::string name, action, iconname, mouseicon, tooltip;
    std::vector<std::string> params; // mode-strings (e.g. "Hold fire", "Roam")
};
```

This is the **command card / button metadata**, not an issued order. It
backs everything the UI shows: the build menu, fire-state cycle, the
greyed-out states, the mouse icons.

The 13 `CMDTYPE_*` codes (`Command.h:55–71`) tell callers how many
return parameters to expect — e.g. `CMDTYPE_ICON_MAP` expects 3 (a map
position), `CMDTYPE_ICON_AREA` expects 4 (pos + radius),
`CMDTYPE_ICON_UNIT_OR_RECTANGLE` accepts 1, 3, or 6.

`CCommandDescriptionCache` (`CommandDescription.h:77–106`) is a
hash-indexed pool of 2048 slots. Many units share identical descriptions
(every `CMD_STOP`, every `CMD_FIRE_STATE` with the same defaults), so
the cache keeps one canonical copy and hands out `const
SCommandDescription*` to each `CCommandAI::possibleCommands` vector with
ref-counting. Inserting a new descriptor with the same hash returns the
existing pointer; `DecRef` reclaims the slot when no `CCommandAI` holds
it.

### 1.6 `CCommandAI` — the per-unit owner

`rts/Sim/Units/CommandAI/CommandAI.h:20–165`

Held by `CUnit::commandAI`. State:
- `std::vector<const SCommandDescription*> possibleCommands` — the
  command card.
- `spring::unordered_set<int> nonQueingCommands` — fast lookup for ids
  whose `SCommandDescription::queueing == false` (they execute
  immediately and never enter the queue).
- `CCommandQueue commandQue` — the actual orders.
- `CUnit* orderTarget` — the currently-targeted unit for attack/repair,
  registered as a death-dependency so the queue is cleaned if it dies
  (`CommandAI.h:167–178`).
- `int inCommand` — the command currently executing (`CMD_STOP` when
  idle).
- `int targetLostTimer` — counts down while the target is out of LOS;
  reaching 0 cancels the order.
- `CWeapon* stockpileWeapon`.

Subclasses (`MobileCAI`, `BuilderCAI`, `FactoryCAI`, `AirCAI`) override
`GiveCommandReal` and add the type-specific `Execute*` methods. The
ctor of each subclass registers extra `SCommandDescription`s into
`possibleCommands` (e.g. `BuilderCAI` adds `CMD_REPAIR`, `CMD_RECLAIM`,
`CMD_RESURRECT`, `CMD_RESTORE`, `CMD_CAPTURE`, plus one **negative-id**
descriptor per `unitDef->buildOptions`).

### 1.7 The Give → Execute lifecycle

`rts/Sim/Units/CommandAI/CommandAI.cpp:816–1069` is the single chokepoint
every command source converges on:

```cpp
void CCommandAI::GiveCommand(const Command& c, bool fromSynced) {
    GiveCommand(c, teamHandler.Team(owner->team)->leader, fromSynced, false);
}
void CCommandAI::GiveCommand(const Command& c, int playerNum,
                             bool fromSynced, bool fromLua) {
    if (!eventHandler.AllowCommand(owner, c, playerNum, fromSynced, fromLua))
        return;
    eventHandler.UnitCommand(owner, c, playerNum, fromSynced, fromLua);
    GiveCommandReal(c, fromSynced);
}
void CCommandAI::GiveCommandReal(const Command& c, bool fromSynced) {
    if (!AllowedCommand(c, fromSynced))
        return;
    GiveAllowedCommand(c, fromSynced);
}
```

`GiveAllowedCommand` (lines 958–1069) is where the queue actually
mutates. Decision tree:

1. **State commands** (`CMD_FIRE_STATE`, `CMD_MOVE_STATE`,
   `CMD_REPEAT`, `CMD_TRAJECTORY`, `CMD_ONOFF`, `CMD_CLOAK`,
   `CMD_STOCKPILE`) are handled by `ExecuteStateCommand` and **never
   queued** — they mutate `owner->fireState` etc. directly and bump the
   `SCommandDescription`'s `params[0]` so the UI re-renders.
2. **Custom Lua non-queuing commands** (registered with
   `queueing=false`) trigger `eventHandler.CommandFallback(owner, c)`
   and exit.
3. `CMD_SELFD`, `CMD_WAIT`, `CMD_INSERT`, `CMD_REMOVE` have dedicated
   paths — `CMD_INSERT` parses `params[0]=position, params[1]=cmdID,
   params[2]=options, params[3..]=cmd params` and inserts the inner
   command at the given queue position; `CMD_REMOVE` filters the queue
   by id or tag depending on `options & ALT_KEY`.
4. Otherwise: **if `SHIFT_KEY` not set**, the queue is wiped:
   `waitCommandsAI.ClearUnitQueue`, `ClearTargetLock`,
   `ClearCommandDependencies`, `SetOrderTarget(nullptr)`,
   `commandQue.clear()`, `inCommand = CMD_STOP`.
5. `AddCommandDependency(c)` walks `c.IsObjectCommand` and registers
   death-dependence on the referenced unit/feature. `IsObjectCommand`
   knows where the target id sits in `params[]` per command type
   (`Command.h:267–306`) — `params[0]` for ATTACK / FIGHT / GUARD /
   REPAIR / RECLAIM / RESURRECT / LOAD_ONTO / CAPTURE,
   `params[3]` for `CMD_UNLOAD_UNIT`, recursive for `CMD_INSERT`.
6. Special-case `CMD_PATROL`: if no patrol exists yet, push the unit's
   own position so the unit returns to the start of the patrol.
7. `CancelCommands` and `GetOverlapQueued` filter duplicates.
8. Finally `commandQue.push_back(c)` — the queue stamps the tag.
9. If the queue had been empty, `SlowUpdate()` is invoked synchronously
   so the new command starts on the same frame.

`SlowUpdate` (and the subclass overrides) calls into `Execute*` per
`commandQue.front().GetID()`. Each `Execute*` either advances the
movement controller, shoots, builds, etc., and on completion calls
`FinishCommand` → `commandQue.pop_front()` and fires
`eventHandler.UnitCmdDone`/`CommandFinished` (which propagates to AIs;
see §3).

### 1.8 Factories: the dual queue

`CFactoryCAI` is the special case that has **two** queues:
- `commandQue` is `BuildQueueType` and stores the production list.
- `newUnitCommands` is `NewUnitQueueType` and stores the orders to
  apply to every newly-built unit (factory rally + waypoint commands).

Both are filled the same way (Lua / GUI / AI / gateway), but the second
is consumed when the new unit comes off the assembly line — its
`CCommandAI` constructor copies these into the new unit's queue. This
is how a factory rally point becomes a `CMD_MOVE` on every produced
tank.

---

## 2. Where Commands Come From — Five Sources

All five end at `unit->commandAI->GiveCommand(...)`.

### 2.1 Lua → engine

`rts/Lua/LuaSyncedCtrl.cpp` exposes a family of bindings:
`Spring.GiveOrderToUnit`, `GiveOrderToUnitMap`,
`GiveOrderToUnitArray`, `GiveOrderArrayToUnitArray`. All of them
synthesize a `Command` via `LuaUtils::ParseCommand`
(`rts/Lua/LuaUtils.cpp:1115–1151`):

```cpp
Command LuaUtils::ParseCommand(lua_State* L, const char* caller, int idIndex) {
    Command cmd(lua_toint(L, idIndex));   // cmdID
    if (lua_istable(L, idIndex + 1)) {
        for (lua_pushnil(L); lua_next(L, idIndex + 1) != 0; lua_pop(L, 1)) {
            if (!lua_israwnumber(L, -2)) continue;   // skip 'n' key
            cmd.PushParam(lua_tofloat(L, -1));
        }
    }
    ParseCommandOptions(L, cmd, caller, idIndex + 2);
    ParseCommandTimeOut(L, cmd, caller, idIndex + 3);
    return cmd;
}
```

`Spring.GiveOrderToUnit` then calls
`unit->commandAI->GiveCommand(cmd, -1, /*fromSynced*/true,
/*fromLua*/true)` — the `fromLua` bit is what makes
`AllowCommand`/`UnitCommand` event handlers know the order originated
in Lua.

Custom Lua commands (the >999 ids you see in BAR mods) are registered
with `Spring.InsertUnitCmdDesc(unitID, [pos], cmdDescTable)`
(`LuaSyncedCtrl.cpp:7913–8011`). These produce `SCommandDescription`s
that go through `CCommandAI::InsertCommandDescription` →
`commandDescriptionCache.GetPtr` and are appended to
`possibleCommands`. Removing/editing uses `RemoveUnitCmdDesc` /
`EditUnitCmdDesc`. The matching orders flow as ordinary `Command`s with
the registered id.

### 2.2 GUI / human player → engine (host side)

`rts/Game/SelectedUnitsHandler.cpp:158–250`:

```cpp
void CSelectedUnitsHandler::GiveCommand(const Command& c, bool fromUser) {
    if (gu->spectating && gs->godMode == 0) return;
    if (selectedUnits.empty()) return;
    // … intercepts CMD_GROUPSELECT/ADD/CLEAR and the wait family …
    selectedUnitsAI.GiveCommandNet(c, playerId);
    SendCommand(c);                                        // network
}

void CSelectedUnitsHandler::SendCommand(const Command& c) {
    SendSelect();                                          // selection delta
    clientNet->Send(CBaseNetProtocol::Get().SendCommand(
        gu->myPlayerNum, c.GetID(), c.GetTimeOut(), c.GetOpts(),
        c.GetNumParams(), c.GetParams()));
}
```

The `Command` is built locally by `CGuiHandler` from the active mouse
state (selected command icon + click position), but the actual
push-to-queue does not happen on the host; the packet round-trips
through the netcode so all clients see the command in lockstep.

### 2.3 Network → engine (every client)

`rts/Net/NetCommands.cpp` (`CGame::ClientReadNet`) handles
`NETMSG_COMMAND`, `NETMSG_AICOMMAND`, `NETMSG_AICOMMAND_TRACKED`. The
ai-command branch (~line 750) reads:

```
playerID, aiInstID, aiTeamID, unitID,
cmdID, timeOut, options, numParams, [aiCmdId], params[numParams]
```

constructs a `Command` (with `c.SetAICmdID(...)` for tracked variant),
and dispatches via `CSelectedUnitsHandler::AINetOrder`:

```cpp
void CSelectedUnitsHandler::AINetOrder(int unitID, int aiTeamID, int playerID,
                                       const Command& c) {
    CUnit* unit = unitHandler.GetUnit(unitID);
    if (unit == nullptr) return;
    // permission checks against player and team
    unit->commandAI->GiveCommand(c, playerID, /*fromSynced*/true,
                                 /*fromLua*/false);
}
```

Outbound, `CBaseNetProtocol::SendAICommand`
(`rts/Net/Protocol/BaseNetProtocol.cpp:140–177`) packs the same fields.

### 2.4 Skirmish AI plugin → engine (the path HighBarV3 inherits)

This is the most layered route. Six layers of translation:

1. **AI code** uses the Cpp wrapper:
   `unit->MoveTo(pos, options, timeout)`, `unit->Build(def, pos, …)`,
   `unit->ExecuteCustomCommand(cmdId, params, options, timeout)`, etc.
   (`build/AI/Wrappers/Cpp/src-generated/Unit.h`,
   `WrappUnit.cpp`).

2. The wrapper calls a `bridged_Unit_*` function with arrays / scalars.

3. `CombinedCallbackBridge.c` packs the call into a flat C struct
   (`SMoveUnitCommand`, `SBuildUnitCommand`, `SCustomUnitCommand`, …
   defined in `rts/ExternalAI/Interface/AISCommands.h`) and invokes
   `id_clb[skirmishAIId]->Engine_handleCommand(skirmishAIId,
   COMMAND_TO_ID_ENGINE, -1, COMMAND_UNIT_*, &commandData)`.
   Example for a build (`CombinedCallbackBridge.c:2814–2826`):

   ```c
   struct SBuildUnitCommand commandData;
   commandData.unitId           = unitId;
   commandData.groupId          = groupId;
   commandData.options          = options;
   commandData.timeOut          = timeOut;
   commandData.toBuildUnitDefId = toBuildUnitDefId;
   commandData.buildPos_posF3   = buildPos_posF3;
   commandData.facing           = facing;
   id_clb[skirmishAIId]->Engine_handleCommand(skirmishAIId,
       COMMAND_TO_ID_ENGINE, -1, COMMAND_UNIT_BUILD, &commandData);
   ```

4. The engine entry point is `skirmishAiCallback_Engine_handleCommand`
   in `rts/ExternalAI/SSkirmishAICallbackImpl.cpp:641`. Its switch
   statement handles all the non-unit-order commands directly (cheats,
   draw, send-text, pause, path queries, debug-drawer). Unit-order
   commands fall through the `default` arm at line 1143:

   ```cpp
   default: {
       Command c;
       if (newCommand(commandData, commandTopic, unitHandler.MaxUnits(), &c)) {
           c.SetAICmdID(commandId);
           const SStopUnitCommand* cmd =
               static_cast<SStopUnitCommand*>(commandData);
           if (cmd->unitId >= 0) ret = clb->GiveOrder(cmd->unitId, &c);
           else                  ret = clb->GiveGroupOrder(cmd->groupId, &c);
       } else { ret = -1; }
   }
   ```

   `newCommand` (`rts/ExternalAI/AISCommands.cpp:463`) is a giant switch
   that translates each `S*UnitCommand` topic back into a `Command` with
   the right `CMD_*` id and `params[]` layout. Excerpts:

   ```cpp
   case COMMAND_UNIT_BUILD: {                               // -unitDefId
       SBuildUnitCommand* cmd = static_cast<SBuildUnitCommand*>(data);
       *c = Command(-cmd->toBuildUnitDefId, cmd->options);
       c->SetTimeOut(cmd->timeOut);
       if (cmd->buildPos_posF3) c->PushPos(cmd->buildPos_posF3);
       if (cmd->facing != UNIT_COMMAND_BUILD_NO_FACING)
           c->PushParam(cmd->facing);
   } break;
   case COMMAND_UNIT_MOVE: {                                // CMD_MOVE
       SMoveUnitCommand* cmd = static_cast<SMoveUnitCommand*>(data);
       *c = Command(CMD_MOVE, cmd->options);
       c->SetTimeOut(cmd->timeOut);
       c->PushPos(cmd->toPos_posF3);
   } break;
   case COMMAND_UNIT_RECLAIM_FEATURE: {                     // CMD_RECLAIM
       SReclaimFeatureUnitCommand* cmd = static_cast<…>(data);
       *c = Command(CMD_RECLAIM, cmd->options,
                    maxUnits + cmd->toReclaimFeatureId); // ← feature ids
   } break;                                                 //   are offset
   ```

   Note the **feature-id offset** (`maxUnits + featureId`) — when an AI
   issues a reclaim or resurrect for a feature, the engine encodes the
   target as `unitHandler.MaxUnits() + featureId`. This lets the same
   `params[0]` slot describe either a unit or a feature; the
   downstream code (`CommandAI.cpp:489–493`) uses
   `if (refId < unitHandler.MaxUnits())` to decide which side to look
   up.

5. `CAICallback::GiveOrder` (`rts/ExternalAI/AICallback.cpp:351`)
   does **not** call `unit->commandAI->GiveCommand` directly. Instead
   it ships the command back over the network:

   ```cpp
   clientNet->Send(CBaseNetProtocol::Get().SendAICommand(
       gu->myPlayerNum, skirmishAIHandler.GetCurrentAIID(), team, unitId,
       c->GetID(false), c->GetID(true),  // engineId, aiCmdId
       c->GetTimeOut(), c->GetOpts(),
       c->GetNumParams(), c->GetParams()));
   ```

   This is the round-trip that keeps every client's sim in lockstep:
   even orders an AI issues for *its own* team go through netcode and
   land back in `ClientReadNet → AINetOrder → GiveCommand`. (Singleplayer
   matches loopback the same packets.)

6. Reverse direction — `EngineOutHandler::PlayerCommandGiven` and
   `CommandFinished` (`rts/ExternalAI/EngineOutHandler.cpp:459–477`)
   notify the AI when a command was issued by anyone or when one of
   *its* commands finished (matched by `command.GetID(true) ==
   aiCmdId`).

The AI-command catalog (`COMMAND_*` topics) is in
`rts/ExternalAI/Interface/AISCommands.h` — a dense enum 0..96 with
matching POD structs. `extractAICommandTopic` (same file’s `.cpp:244`)
does the inverse mapping, used when the engine reports a finished
command back to the AI.

The legacy C++ AI API (`AIAICallback::Internal_GiveOrder`,
`AIAICallback.cpp:1461`) bypasses the catalog and goes straight through
`Engine_executeCommand` — a separate callback that takes a `RawCommand`
and chooses the topic itself
(`SSkirmishAICallbackImpl.cpp:291–639`). It is what BARb's
`Unit::ExecuteCustomCommand` actually exercises on the AI side, and is
the key reason CircuitAI can issue *any* CMD_* code (including the BAR
4-digit custom ones in §3.2 below) just by passing a free-form id and
float params:

```cpp
// rts/ExternalAI/SSkirmishAICallbackImpl.cpp:291–303
EXPORT(int) skirmishAiCallback_Engine_executeCommand(int skirmishAIId,
    int unitId, int groupId, void* commandData) {
    RawCommand* rc = static_cast<RawCommand*>(commandData);
    Command c;
    c.FromRawCommand(*rc);
    const int maxUnits = skirmishAiCallback_Unit_getMax(skirmishAIId);
    const int aiCmdId = extractAICommandTopic(&c, maxUnits);
    // dispatch to handleCommand using aiCmdId — see §2.4 step 4
}
```

### 2.5 Reading commands back

The same C ABI that writes commands also reads them. From an AI:

- `Unit::GetCurrentCommands()` →
  `bridged_Unit_getCurrentCommands` → `CCommandQueue*` returned by
  `CAICallback::GetCurrentUnitCommands` (`AICallback.cpp:383`) which
  is just `&unit->commandAI->commandQue`.
- `Unit::CurrentCommand_*` accessors
  (`SSkirmishAICallbackImpl.cpp:3489–3539`) iterate the deque by index
  and surface `getId / getOpts / getTag / getTimeOut / getParams`.
- `Unit::GetSupportedCommands()` (the command card) returns
  `unit->commandAI->possibleCommands`, the
  `vector<const SCommandDescription*>`.

Cheat-enabled AIs use `GetCheatCallBack(skirmishAIId)->GetCurrentUnitCommands(unitId)`
which can read enemy queues; non-cheating AIs only see their own.

---

## 3. CircuitAI / BARb Layer

`/home/developer/projects/HighBarV3/src/circuit`

This is a direct fork of `rlcevg/CircuitAI` at commit
`0ef36267633d6c1b2f6408a8d8a59fff38745dc3`, BAR-targeted (shortName
`BARb`). It does *not* invent its own command-storage primitives — it
only adds two things on top of §2.4:

### 3.1 `CCircuitUnit::Cmd*` convenience methods

`src/circuit/unit/CircuitUnit.h:133–166`,
`src/circuit/unit/CircuitUnit.cpp:280–449`. These are thin wrappers
that pick the right Spring AI callback for a high-level intent:

```cpp
void CCircuitUnit::CmdMoveTo(const AIFloat3& pos, short options, int timeout) {
    assert(utils::is_in_map(pos));
    unit->MoveTo(pos, options, timeout);                  // → COMMAND_UNIT_MOVE
}
void CCircuitUnit::CmdAttackGround(const AIFloat3& pos, short opts, int timeout){
    unit->ExecuteCustomCommand(CMD_ATTACK_GROUND, {pos.x, pos.y, pos.z},
                               opts, timeout);            // raw CMD_ATTACK
}
void CCircuitUnit::CmdBuild(CCircuitDef* buildDef, const AIFloat3& buildPos,
                            int facing, short options, int timeout) {
    unit->Build(buildDef->GetDef(), buildPos, facing, options, timeout);
    taskState = ETaskState::EXECUTE;
}
```

The full set covers move/jump/fight/patrol/attack-ground, stop/wait,
build/repair/reclaim/resurrect, fire-state/move-state, manualfire, set-target,
cloak, fire-at-radar, find-pad/land-at-airbase, stockpile-internal
toggles like `priority`, `misc-priority`, `air-strafe`, `BAR-priority`,
`terraform`, `selfd`. They all funnel into either a typed engine
callback (which produces `COMMAND_UNIT_*`) or the catch-all
`unit->ExecuteCustomCommand(cmdId, params, opts, timeout)` →
`COMMAND_UNIT_CUSTOM`.

### 3.2 BAR-game custom command codes

Defined as macros in `src/circuit/unit/CircuitUnit.h:31–60`:

| Code   | Constant                    | What it is                                  |
|-------:|-----------------------------|---------------------------------------------|
| 20     | `CMD_ATTACK_GROUND`         | shadow alias used by CircuitAI              |
| 10001  | `CMD_RETREAT_ZONE`          | retreat-zone overlay                        |
| 13923  | `CMD_ORBIT`                 | orbit command (gunship)                     |
| 13924  | `CMD_ORBIT_DRAW`            | orbit visual                                |
| 32102  | `CMD_MANUAL_LAUNCH`         | nuke / manual-fire button                   |
| 31101  | `CMD_CLOAK_SHIELD`          | area cloaker toggle                         |
| 31109  | `CMD_RAW_MOVE`              | bypass formation move                       |
| 31207–10 | `CMD_MORPH_*`             | morph upgrade                               |
| 31208  | `CMD_UPGRADE_STOP`          | stop upgrade                                |
| 33411  | `CMD_FIND_PAD`              | aircraft pad-finding                        |
| 34220–34221 | `CMD_PRIORITY` / `MISC_PRIORITY` | construction priority toggle      |
| 34223  | `CMD_RETREAT`               | retreat toggle                              |
| 34571  | `CMD_BAR_PRIORITY`          | BAR construction priority slider            |
| 34923–34924 | `CMD_UNIT_SET_TARGET` / `CANCEL_TARGET` | target lock              |
| 35000  | `CMD_ONECLICK_WEAPON`       | commander dgun                              |
| 35430  | `CMD_LAND_AT_AIRBASE`       | aircraft auto-land                          |
| 37382  | `CMD_WANT_CLOAK`            | personal cloak toggle                       |
| 38372  | `CMD_DONT_FIRE_AT_RADAR`    | radar-fire toggle                           |
| 38521  | `CMD_JUMP`                  | jumpjets                                    |
| 38571  | `CMD_AIR_MANUALFIRE`        | aircraft manual fire at point               |
| 38825  | `CMD_WANTED_SPEED`          | speed-throttle slider                       |
| 39381  | `CMD_AIR_STRAFE`            | strafing toggle                             |
| 39801  | `CMD_TERRAFORM_INTERNAL`    | terraform polygon                           |
| 31143  | `CMD_AUTOMEX`               | automatic mex placement                     |

These are all **registered by Lua gadgets in the BAR game files** —
the engine itself knows nothing about them. CircuitAI hard-codes the
numeric ids and uses `ExecuteCustomCommand` to push them as raw
`Command{cmdId, params}`. The same path is open to HighBarV3 for any
arm not modelled in proto.

### 3.3 `CommandFinished` / `Done` correlation

`CCircuitUnit::CmdSetTarget` and `CmdAttackGround` rely on the round-trip
of `aiCmdId` (`Command::id[1]`) — when the engine raises
`COMMAND_FINISHED`, CircuitAI matches the ai-cmd-id against its own
in-flight bookkeeping. The CircuitAI scheduler holds task→cmdId
mappings; the gateway adds its own bookkeeping (§4.4).

---

## 4. HighBarV3 Gateway Layer

The gRPC gateway treats the engine's `Command` as the destination
format and adds its own MPSC pipeline. Files all live under
`src/circuit/grpc/` and `proto/highbar/`.

### 4.1 The wire format — `highbar.v1.AICommand`

`proto/highbar/commands.proto`. One protobuf message holds a `oneof
command` with **66 active arms** (53 unit-bound, 13 game-wide) numbered
to match the `COMMAND_TOPIC` enum in the engine's `AISCommands.h`
(field numbers are the topic numbers — `BuildUnitCommand build_unit =
35`, `MoveUnitCommand move_unit = 42`, `AttackCommand attack = 45`,
…). Each arm is its own message with the same fields that
`S*UnitCommand` carries, plus optional `options` and `timeout`:

```proto
message AICommand {
  oneof command {
    DrawAddPointCommand   draw_add_point     = 1;
    SendTextMessageCommand send_text_message = 4;
    BuildUnitCommand      build_unit         = 35;
    StopCommand           stop               = 36;
    MoveUnitCommand       move_unit          = 42;
    AttackCommand         attack             = 45;
    RepairCommand         repair             = 48;
    ReclaimUnitCommand    reclaim_unit       = 49;
    SelfDestructCommand   self_destruct      = 59;
    DGunCommand           dgun               = 67;
    SetFireStateCommand   set_fire_state     = 72;
    // … 66 arms total …
  }
}
```

Batches arrive as `CommandBatch { repeated AICommand commands;
target_unit_id; batch_seq; client_command_id; … }` and are submitted
through the `SubmitCommands` RPC.

### 4.2 `CommandValidator` — synchronous accept/reject

`src/circuit/grpc/CommandValidator.h:33–93`,
`CommandValidator.cpp`. Runs on the gRPC worker thread before the
queue push (constitution requires no engine-thread work in workers).
Per data-model §4 it is **all-or-nothing**: any single failed arm
discards the whole batch with `INVALID_ARGUMENT`.

Checks performed:
- `OwnsLiveUnit(target_unit_id)` for unit-bound arms — must be a live,
  team-owned unit at validate time. (The engine-thread re-resolves at
  drain time too, since the unit can die in between.)
- `KnownBuildDef(def_id)` against `CCircuitAI::GetCircuitDefSafe`.
- `InMapExtents(x, z)` for any position.
- `ValidateCommandTarget` for the authoritative-batch-target contract:
  every unit-bound arm in a batch must agree with `batch.target_unit_id`.
- Settings (`CommandValidationSettings`): `max_batch_commands = 64`,
  optional `require_correlation`, `require_state_basis`,
  `reject_unsupported_arms`.

A `ValidationResult { ok, error, batch_result }` carries per-issue
`CommandIssue` records back to the client.

### 4.3 `CommandQueue` — bounded MPSC

`src/circuit/grpc/CommandQueue.h:38–76`,
`CommandQueue.cpp`. A mutex-guarded `std::queue<QueuedCommand>`,
default capacity 1024 (T055). Each entry remembers the originating
session, batch_seq, client_command_id, command_index, and the
authoritative target unit id, so the engine-thread side can
correlate dispatch outcomes back to the client without round-tripping
the original batch object:

```cpp
struct QueuedCommand {
    std::string session_id;
    std::uint64_t batch_seq = 0;
    std::uint64_t client_command_id = 0;
    std::uint32_t command_index = 0;
    std::int32_t authoritative_target_unit_id = 0;
    ::highbar::v1::AICommand command;
};
```

`TryPush` returns false (without mutating the queue) when full, so the
worker can reply `RESOURCE_EXHAUSTED`. `TryPushBatch` is atomic — a
batch is enqueued whole or not at all (FR-012a). `Drain` is called
once per engine frame from `OnFrameTick` and moves up to N entries
(default: all) into the engine-thread caller's vector.

### 4.4 `OrderStateTracker` and `CommandDispatch` — engine-thread drain

`CGrpcGatewayModule::OnFrameTick` (`module/GrpcGatewayModule.cpp:761`) is
called from `CScheduler::GameJob` every engine frame and calls
`DrainCommandQueue` (line 800). The drain
(`GrpcGatewayModule.cpp:1309–1437`):

1. Pulls everything off the MPSC queue into a local vector.
2. Builds a `CommandDispatchEvent` for each entry into the current
   frame's outgoing `StateDelta` (so clients learn whether their
   command applied, was skipped, etc.).
3. Resolves the live `CCircuitUnit*` via `circuit->GetTeamUnit(targetId)`
   — guarded against missing/dead units (`COMMAND_DISPATCH_SKIPPED_TARGET_*`).
4. Calls `circuit::grpc::DispatchCommand(circuit, unit_ctx, cmd)`.
5. On success, marks the order via `OrderStateTracker::MarkAccepted`
   (records batch_seq, client_command_id, frame, command kind) so
   future `command_finished` events can be reported back.
6. On exception, the gateway's hot-path guard
   (`TransitionToDisabled`) marks itself unhealthy with a reason code.

`grpc::DispatchCommand` (`grpc/CommandDispatch.cpp:151–600+`) is the
huge `switch` over `cmd.command_case()` that drives one of:
- a `CCircuitUnit::Cmd*` method (move, patrol, fight, attack-ground,
  stop, wait, build, repair, reclaim-unit/area, resurrect-area,
  self-destruct, set-fire-state, set-move-state, set-wanted-speed),
- `unit->ExecuteCustomCommand(CMD_*, params, opts, timeout)` for arms
  without a `Cmd*` shortcut (CMD_ATTACK with target id, CMD_GUARD,
  CMD_DGUN, CMD_CAPTURE, CMD_ONOFF, CMD_REPEAT, CMD_STOCKPILE,
  CMD_TIMEWAIT, CMD_SQUADWAIT, CMD_DEATHWAIT, CMD_GATHERWAIT,
  CMD_RECLAIM area+feature, CMD_RESTORE, CMD_RESURRECT, CMD_SETBASE,
  CMD_LOAD_*, CMD_UNLOAD_*, plus the BAR custom 4-digit ids), or
- a game-wide springai callback (Drawer, Game, Pathing, Lua, Cheats,
  Economy, Resource — these don't bind to any unit).

`IsGameWideCommand` (`CommandDispatch.h:33–62`) is the gate — game-wide
arms set `target_unit_id = -1` so the dispatcher uses any own unit as
context (the springai callbacks need a non-null wrapper).

### 4.5 Snapshot / delta side: command information *out*

The same gateway publishes command information back to clients in two
shapes:

1. **`CommandDispatchEvent`** (`proto/highbar/state.proto:249`) per
   queued command: `batch_seq`, `client_command_id`, `command_index`,
   `target_unit_id`, `frame`, `status`, optional `CommandIssue`.
2. **`PlayerCommandEvent`** and **`CommandFinishedEvent`** in
   `events.proto`/`state.proto`, fed from the engine's
   `EngineOutHandler::PlayerCommandGiven` /
   `CommandFinished` hooks (see §2.4 step 6).

What is **not currently in the snapshot** (verified by reading
`proto/highbar/state.proto` `OwnUnit`): the live `commandQue` of each
unit and the `possibleCommands` (command card). V2 had a `command_queue`
field on units; V3's `OwnUnit` (`state.proto:90–99`) currently carries
only `unit_id, def_id, position, health, max_health, under_construction,
build_progress, team_id`. If a client needs the per-unit queue, the
gateway would have to call `unit->GetCurrentCommands()` (which returns
the engine's `CCommandQueue`) and serialize it.

---

## 5. End-to-End Walk: a Single Move Order from a HighBarV3 Client

Putting it all together for the most common case — a F#/.NET client
issues "move unit 1234 to (X, Y, Z)":

1. Client constructs `CommandBatch { target_unit_id=1234,
   batch_seq=N, client_command_id=M, commands=[ AICommand{ move_unit:
   { to_position: {X,Y,Z}, options: 0, timeout: 0 } } ] }` and calls
   `SubmitCommands` over the UDS / loopback gRPC channel.
2. **gRPC worker thread** in the gateway runs `CommandValidator`:
   confirms unit 1234 is alive and on our team, position is in map
   bounds, batch ≤ 64 commands.
3. Worker calls `command_queue_->TryPushBatch(...)`. On success returns
   `OK` to the client with a `CommandBatchResult`; on capacity failure
   returns `RESOURCE_EXHAUSTED`.
4. **Engine thread** at next tick: `OnFrameTick → DrainCommandQueue`
   pulls the entry, re-resolves unit 1234 via
   `circuit->GetTeamUnit(1234)`.
5. `grpc::DispatchCommand` enters `case C::kMoveUnit:` →
   `unit->CmdMoveTo(ToFloat3(cmd.move_unit().to_position()), opts,
   timeout)`.
6. `CCircuitUnit::CmdMoveTo` calls `unit->MoveTo(pos, opts, timeout)`
   on the springai wrapper.
7. Wrapper → `bridged_Unit_moveTo` → packs `SMoveUnitCommand` →
   `Engine_handleCommand(skirmishAIId, COMMAND_TO_ID_ENGINE, -1,
   COMMAND_UNIT_MOVE, &cmd)`.
8. Engine `skirmishAiCallback_Engine_handleCommand` falls through to
   the default arm → `newCommand(...)` builds
   `Command(CMD_MOVE, options)` with `params=[X, Y, Z]`,
   `id[1]=aiCommandId`.
9. `clb->GiveOrder(unitId, &c)` → `CAICallback::GiveOrder` →
   `clientNet->Send(CBaseNetProtocol::Get().SendAICommand(...))`.
10. The packet goes through the netcode loop (even in singleplayer)
    and arrives in `CGame::ClientReadNet → AINetOrder →
    unit->commandAI->GiveCommand(c, playerID, true, false)`.
11. Engine: `AllowCommand` event fires (Lua gadgets can veto), then
    `UnitCommand`, then `GiveCommandReal → AllowedCommand →
    GiveAllowedCommand`. SHIFT not set, so the existing queue is
    flushed; `commandQue.push_back(c)` stamps a tag and the move begins
    on the next `SlowUpdate`.
12. The unit moves; on arrival `MobileCAI::FinishCommand` pops the
    front, fires `eventHandler.UnitCmdDone` and (via
    `EngineOutHandler::CommandFinished`) the AI gets its
    `CommandFinished(unitId, aiCmdId, COMMAND_UNIT_MOVE)` callback.
13. The gateway's `OrderStateTracker` matches the `aiCmdId` to its
    in-flight bookkeeping and emits a `CommandFinishedEvent` plus
    final `CommandDispatchEvent` status into the next `StateDelta`,
    which goes back to the client.

Note the **two queue hops** the same byte-content makes: HighBarV3's
own `CommandQueue` (worker → engine thread), and the engine's
internal netcode loop (host → all clients). Both exist for the same
reason: keep the hot path single-threaded and deterministic.

---

## 6. Cross-Layer Storage Map

| Layer                  | Storage type                                    | Lives in                                           | Lifetime                            |
|------------------------|--------------------------------------------------|----------------------------------------------------|-------------------------------------|
| HighBarV3 wire         | `highbar.v1.AICommand` (proto oneof, 66 arms)    | client request bytes                                | per-RPC                              |
| HighBarV3 staging      | `circuit::grpc::QueuedCommand` (mutex+`std::queue`)| `CommandQueue::queue_` in `GrpcGatewayModule`      | one engine frame                     |
| HighBarV3 audit        | `CommandDispatchEvent`                           | current `StateDelta` events                          | one frame, then sent out             |
| HighBarV3 correlation  | `OrderStateTracker` (per-unit map)               | `GrpcGatewayModule::order_state_tracker_`           | until `CommandFinished` resolves     |
| CircuitAI/BARb intent  | `CCircuitUnit::Cmd*` thunks                      | per-call stack only                                  | per call                             |
| AI ABI (out)           | `S*UnitCommand` POD struct                       | bridge stack                                         | per call                             |
| AI ABI (in)            | `RawCommand` (C-linkage view of `Command`)       | bridge stack                                         | per call                             |
| Engine network         | `NETMSG_AICOMMAND[_TRACKED]` packet              | `clientNet` send/receive buffers                     | one network round-trip               |
| Engine queue (the truth)| `Command` inside `std::deque<Command>`           | `CUnit::commandAI->commandQue`                       | until executed / cancelled / unit dies |
| Engine queue overflow  | `vector<vector<float>>` pages                    | global `cmdParamsPool`                               | until command destroyed              |
| Engine command card    | `vector<const SCommandDescription*>` interned    | `CUnit::commandAI->possibleCommands` + `commandDescriptionCache` | unit lifetime               |
| Engine target lock     | `CUnit* orderTarget` + death-dependence          | `CUnit::commandAI`                                   | until cleared by next non-SHIFT cmd  |
| Engine factory rally   | second `CCommandQueue (NewUnitQueueType)`        | `CFactoryCAI::newUnitCommands`                       | per produced unit                    |

The single source of truth in this whole stack is
`unit->commandAI->commandQue`. Everything left of that column in §6 is a
translator; everything right of it is observability. HighBarV3 sits
entirely on the input-translation side (proto → AICommand →
`CCircuitUnit::Cmd*` → engine callback → netcode → engine `Command`)
plus a thin observability layer (`CommandDispatchEvent`,
`CommandFinishedEvent`, `OrderStateTracker`).

---

## 7. Notable Pitfalls and Asymmetries

1. **Build options are negative ids.** `Command{id=-137, params=[x,y,z,
   facing]}` means "build the unit whose `UnitDef::id` is 137." This is
   why `BuilderCAI`'s `buildOptions` set tracks negative ids
   (`CommandAI.cpp:502–544`) and `Command::IsBuildCommand()` is just
   `GetID() < 0`.

2. **Feature ids are offset by `unitHandler.MaxUnits()`.** When a
   reclaim/resurrect/restore targets a feature, the engine encodes
   `params[0] = MaxUnits + featureId`. `Command::IsObjectCommand` and
   `AddCommandDependency` decode by comparing against
   `unitHandler.MaxUnits()`. HighBarV3's
   `CommandDispatch::kReclaimFeature` arm currently passes the raw
   feature id and relies on the AI wrapper to translate
   (`CommandDispatch.cpp:362–372`).

3. **AI orders round-trip through the network even in singleplayer.**
   `CAICallback::GiveOrder` sends a `NETMSG_AICOMMAND` rather than
   calling `commandAI->GiveCommand` directly. This is why an AI's order
   doesn't take effect on the same tick it was issued.

4. **`SHIFT_KEY` is the queue bit**, despite the misleading name in
   `Command.h:82`. `META_KEY` is the lock-on bit for attack;
   `INTERNAL_ORDER` distinguishes engine-issued from user-issued
   commands. HighBarV3's `OptionsOf` (`CommandDispatch.cpp:38–67`)
   passes the proto `options` field through as-is, so clients are
   responsible for using the correct bits (the proto comment chain
   should call this out explicitly).

5. **State commands never queue.** `CMD_FIRE_STATE`, `CMD_MOVE_STATE`,
   `CMD_REPEAT`, `CMD_TRAJECTORY`, `CMD_ONOFF`, `CMD_CLOAK`,
   `CMD_STOCKPILE` are handled by `ExecuteStateCommand` and modify the
   unit immediately — they never appear in `commandQue` and clients
   should not expect to see them via `GetCurrentCommands()`. The
   current state is reflected in `SCommandDescription::params[0]` of
   the matching command-card entry.

6. **Tags are per-queue, not global.** The 24-bit `tagCounter` resets
   per `CCommandQueue`, so two units' tag spaces are independent. To
   correlate across the gateway, HighBarV3 uses
   `(batch_seq, client_command_id, target_unit_id)`, not engine tags.

7. **Custom Lua / BAR command ids are unstable across mod versions.**
   The 4-digit `CMD_BAR_PRIORITY = 34571` etc. are agreements between
   CircuitAI and BAR Lua gadgets; if BAR changes its gadget ids, the
   AI's commands silently no-op. There is no engine-level registry —
   the only safety is BAR / CircuitAI changing in lockstep.

8. **`CommandParamsPool` is global, not per-thread.** Once a `Command`
   becomes pooled, it owns a page, and the pool is shared across
   units. Concurrent `Command` construction across threads is
   unsafe. HighBarV3 sidesteps this by keeping all `Command`
   construction on the engine thread (the gRPC worker only handles
   protobuf, never `Command`).

---

## 8. Files Referenced (one-line index)

Engine — primitives:
- `rts/Sim/Units/CommandAI/Command.h` — `Command`, `RawCommand`, CMD_/CMDTYPE_ enums.
- `rts/Sim/Units/CommandAI/Command.cpp` — pool migration, serialization.
- `rts/Sim/Units/CommandAI/CommandQueue.h` — deque wrapper, tag counter.
- `rts/Sim/Units/CommandAI/CommandParamsPool.hpp` — paged float arena.
- `rts/Sim/Units/CommandAI/CommandDescription.h` — `SCommandDescription`, hash cache.
- `rts/Sim/Units/CommandAI/CommandAI.{h,cpp}` — `GiveCommand` chain, lifecycle.
- `rts/Sim/Units/CommandAI/BuilderCAI.cpp` — build-cmd execution; build options.
- `rts/Sim/Units/CommandAI/FactoryCAI.cpp` — production queue + new-unit queue.

Engine — sources:
- `rts/Lua/LuaSyncedCtrl.cpp` — `Spring.GiveOrderToUnit*`,
  `InsertUnitCmdDesc`, `EditUnitCmdDesc`, `RemoveUnitCmdDesc`.
- `rts/Lua/LuaUtils.cpp` — `ParseCommand`, `ParseCommandOptions`, `ParseCommandTimeOut`.
- `rts/Game/SelectedUnitsHandler.cpp` — GUI dispatch + `AINetOrder`.
- `rts/Net/NetCommands.cpp` — `NETMSG_AICOMMAND[_TRACKED]` unpacking.
- `rts/Net/Protocol/BaseNetProtocol.cpp` — `SendAICommand` packing.

AI ABI:
- `rts/ExternalAI/Interface/AISCommands.h` — `enum CommandTopic` and
  `S*UnitCommand` PODs.
- `rts/ExternalAI/AISCommands.cpp` — `extractAICommandTopic`,
  `newCommand` (S*UnitCommand → `Command`).
- `rts/ExternalAI/SSkirmishAICallbackImpl.cpp` —
  `Engine_handleCommand`, `Engine_executeCommand`,
  `Unit_getCurrentCommands` and accessors.
- `rts/ExternalAI/AICallback.cpp` — `GiveOrder` (sends
  `NETMSG_AICOMMAND`).
- `rts/ExternalAI/EngineOutHandler.cpp` — `PlayerCommandGiven`,
  `CommandFinished`, AI fan-out.
- `AI/Wrappers/Cpp/src-generated/{Unit.h,WrappUnit.cpp,
  CombinedCallbackBridge.{c,h}}` — generated C++ AI wrapper.
- `AI/Wrappers/LegacyCpp/AIAICallback.cpp` — legacy `GiveOrder` that
  uses `Engine_executeCommand` + `RawCommand`.

CircuitAI / BARb:
- `src/circuit/unit/CircuitUnit.{h,cpp}` — `CCircuitUnit::Cmd*` plus
  the BAR-game custom command ids.

HighBarV3 gateway:
- `proto/highbar/commands.proto` — `AICommand` oneof + 66 arm messages.
- `proto/highbar/state.proto` — `CommandDispatchEvent`, `OwnUnit`,
  `DeltaEvent`.
- `proto/highbar/events.proto` — `PlayerCommandEvent`,
  `CommandFinishedEvent`.
- `src/circuit/grpc/CommandValidator.{h,cpp}` — synchronous accept/reject.
- `src/circuit/grpc/CommandQueue.{h,cpp}` — bounded MPSC with batch
  atomicity.
- `src/circuit/grpc/CommandDispatch.{h,cpp}` — proto arm →
  `CCircuitUnit::Cmd*` / `ExecuteCustomCommand` switch.
- `src/circuit/grpc/OrderStateTracker.{h,cpp}` — accepted/finished
  bookkeeping per unit.
- `src/circuit/module/GrpcGatewayModule.cpp` (`OnFrameTick`,
  `DrainCommandQueue` ~1083, ~1309) — engine-thread drain and
  `CommandDispatchEvent` emission.

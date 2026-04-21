// SPDX-License-Identifier: GPL-2.0-only
//
// HighBarV3 — proto AICommand → CCircuitUnit::Cmd* dispatch (T057).
//
// Called on the engine thread from CGrpcGatewayModule::OnFrameTick
// after the CommandQueue drain. Never called from a gRPC worker
// (Constitution II — engine-thread supremacy).
//
// Coverage: the 30-ish CCircuitUnit::Cmd* methods exposed in
// unit/CircuitUnit.h (move/patrol/fight/attack-ground/stop/wait/
// build/repair/reclaim/selfd/wantedspeed/priority/fire-state/
// move-state). Proto arms without a matching Cmd* (drawing, chat,
// Lua, pathfinding, group ops, figures, cheats, stockpile, custom,
// transport load/unload) are logged and skipped — follow-up work
// wires them through the springai OOA callback layer, not through
// CCircuitUnit. The US2 Independent Test exercises MoveTo which is
// covered.

#pragma once

#include "highbar/commands.pb.h"

namespace circuit {
class CCircuitAI;
class CCircuitUnit;
}  // namespace circuit

namespace circuit::grpc {

// Dispatch `cmd` for `unit` on the engine thread. `unit` is the live
// CCircuitUnit resolved from the batch's target_unit_id — callers
// must re-resolve before dispatch because a unit can die between
// worker-thread validation and engine-thread drain.
//
// Returns true if the command was dispatched to CCircuitUnit::Cmd*;
// false when the proto arm has no CCircuitUnit counterpart (skipped
// with a log line) or when `unit == nullptr`.
bool DispatchCommand(::circuit::CCircuitAI* ai,
                     ::circuit::CCircuitUnit* unit,
                     const ::highbar::v1::AICommand& cmd);

}  // namespace circuit::grpc

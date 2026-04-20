// SPDX-License-Identifier: GPL-2.0-only
//
// HighBarV3 — structured log wrapper (T028).
//
// Thin façade routing gateway lifecycle events to the engine's
// existing log sink (Spring `springai::Log`) via BARb's LOG() macro.
// Keeping these in one place lets us evolve the record shape
// (structured JSON, OTel span attributes, etc.) without touching
// every call site. FR-023 requires the lifecycle events listed below.

#pragma once

#include <cstdint>
#include <string>

namespace circuit {
class CCircuitAI;
}  // namespace circuit

namespace circuit::grpc {

// Caller-facing API. Every function is a thin formatter that calls
// through to BARb's LOG() in the impl.

void LogStartup(::circuit::CCircuitAI* ai,
                const std::string& transport,
                const std::string& bind_address,
                const std::string& schema_version);

void LogShutdown(::circuit::CCircuitAI* ai,
                 std::uint32_t frames_since_bind);

void LogConnect(::circuit::CCircuitAI* ai,
                const std::string& session_id,
                const std::string& peer,
                const std::string& role);

void LogDisconnect(::circuit::CCircuitAI* ai,
                   const std::string& session_id,
                   const std::string& reason);

void LogAuthReject(::circuit::CCircuitAI* ai,
                   const std::string& peer,
                   const std::string& rpc_name);

void LogSlowConsumerEviction(::circuit::CCircuitAI* ai,
                             const std::string& session_id,
                             std::uint64_t dropped_count);

// Recoverable error — written through and not treated as fatal. For
// invariant violations and unrecoverable faults use
// LogFatalAndFailClosed (below) which also propagates via the
// AI-slot failure path (FR-003a).
void LogError(::circuit::CCircuitAI* ai,
              const std::string& where,
              const std::string& what);

// Fatal path: records the fault, then the gateway top-level exception
// guard (T030) propagates through BARb's Release(RELEASE_CORRUPTED).
// This function ONLY logs; the failure propagation is in the caller.
void LogFatalAndFailClosed(::circuit::CCircuitAI* ai,
                           const std::string& where,
                           const std::string& what);

}  // namespace circuit::grpc

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
#include <exception>
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

// T010 — Structured fault-log line per contracts/gateway-fault.md §1.
//
//   [hb-gateway] fault subsystem=<s> reason=<r> detail="<d>"
//                      schema=highbar.v1 pid=<pid> frame=<f>
//
// Written exactly once per match, immediately before the gateway
// transitions to the Disabled state. `subsystem` is one of
// {transport, serialization, dispatch, callback, handler}; `reason` is
// a snake_case code ≤32 chars (see contract §Reason-code namespace);
// `detail` is typically `e.what()` and is backslash-escaped here.
void LogFault(::circuit::CCircuitAI* ai,
              const std::string& subsystem,
              const std::string& reason,
              const std::string& detail,
              std::uint32_t frame);

// Map a currently-in-flight exception to a stable `reason` code for
// the fault log. Catch site passes `std::current_exception()`. Unknown
// types collapse to `rpc_internal` so operators still get a code they
// can grep on.
std::string ReasonCodeFor(std::exception_ptr ep);

// Write (or rewrite) `$writeDir/highbar.health`. Single-line JSON per
// contracts/gateway-fault.md §2. Healthy form has only status/schema/pid;
// disabled form adds subsystem/reason/detail/frame. Implemented via
// write-temp-and-rename so concurrent readers never observe a partial
// file. Returns true on success; logs and returns false on error.
bool WriteHealthFile(const std::string& path,
                     bool healthy,
                     const std::string& subsystem = "",
                     const std::string& reason = "",
                     const std::string& detail = "",
                     std::uint32_t frame = 0);

}  // namespace circuit::grpc

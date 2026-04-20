// SPDX-License-Identifier: GPL-2.0-only
//
// HighBarV3 — structured log wrapper impl (T028).

#include "grpc/Log.h"

#include "CircuitAI.h"  // brings in LOG() macro

namespace circuit::grpc {

namespace {

// All records prefix with "[hb-gateway] " plus an event tag so
// operators grep a single stream for gateway lifecycle.
constexpr const char* kPrefix = "[hb-gateway]";

}  // namespace

void LogStartup(CCircuitAI* ai,
                const std::string& transport,
                const std::string& bind_address,
                const std::string& schema_version) {
	if (ai == nullptr) return;
	LOG("%s startup transport=%s bind=%s schema=%s",
	    kPrefix, transport.c_str(), bind_address.c_str(), schema_version.c_str());
}

void LogShutdown(CCircuitAI* ai, std::uint32_t frames_since_bind) {
	if (ai == nullptr) return;
	LOG("%s shutdown frames_since_bind=%u", kPrefix, frames_since_bind);
}

void LogConnect(CCircuitAI* ai,
                const std::string& session_id,
                const std::string& peer,
                const std::string& role) {
	if (ai == nullptr) return;
	LOG("%s connect session=%s peer=%s role=%s",
	    kPrefix, session_id.c_str(), peer.c_str(), role.c_str());
}

void LogDisconnect(CCircuitAI* ai,
                   const std::string& session_id,
                   const std::string& reason) {
	if (ai == nullptr) return;
	LOG("%s disconnect session=%s reason=%s",
	    kPrefix, session_id.c_str(), reason.c_str());
}

void LogAuthReject(CCircuitAI* ai,
                   const std::string& peer,
                   const std::string& rpc_name) {
	if (ai == nullptr) return;
	LOG("%s auth-reject peer=%s rpc=%s", kPrefix, peer.c_str(), rpc_name.c_str());
}

void LogSlowConsumerEviction(CCircuitAI* ai,
                             const std::string& session_id,
                             std::uint64_t dropped_count) {
	if (ai == nullptr) return;
	LOG("%s eviction session=%s reason=slow-consumer dropped=%llu",
	    kPrefix, session_id.c_str(),
	    static_cast<unsigned long long>(dropped_count));
}

void LogError(CCircuitAI* ai,
              const std::string& where,
              const std::string& what) {
	if (ai == nullptr) return;
	LOG("%s error where=%s what=%s", kPrefix, where.c_str(), what.c_str());
}

void LogFatalAndFailClosed(CCircuitAI* ai,
                           const std::string& where,
                           const std::string& what) {
	if (ai == nullptr) return;
	LOG("%s fatal where=%s what=%s — failing closed (FR-003a)",
	    kPrefix, where.c_str(), what.c_str());
}

}  // namespace circuit::grpc

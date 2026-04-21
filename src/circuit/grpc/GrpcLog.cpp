// SPDX-License-Identifier: GPL-2.0-only
//
// HighBarV3 — structured log wrapper impl (T028).

#include "grpc/GrpcLog.h"

// The LOG() macro in CircuitAI.h assumes a `GetLog()` member is in scope
// (i.e., callers are CCircuitAI methods). These are free functions, so
// we route through ai->GetLog() explicitly via LOG_AI (below).
#include "CircuitAI.h"
#include "util/Utils.h"
// springai::Log needs to be a complete type for DoLog(). Angle-bracket
// include bypasses the current-dir-first quote search that would find
// the wrong header (CircuitAI.h does `#include "Log.h"` which, during
// grpc/*.cpp compilation, would have shadowed onto our own header —
// fixed by renaming ours to GrpcLog.*). The Cpp wrapper's src-generated
// directory is in -I, so <Log.h> resolves cleanly.
#include <Log.h>
#undef LOG
#define LOG_AI(ai, fmt, ...) \
    ai->GetLog()->DoLog(::utils::string_format(std::string(fmt), ##__VA_ARGS__).c_str())

#include <cstdio>
#include <cstring>
#include <exception>
#include <new>           // std::bad_alloc
#include <stdexcept>
#include <sys/stat.h>
#include <sys/types.h>
#include <unistd.h>

namespace circuit::grpc {

namespace {

// All records prefix with "[hb-gateway] " plus an event tag so
// operators grep a single stream for gateway lifecycle.
constexpr const char* kPrefix = "[hb-gateway]";

// JSON-escape a string's unsafe characters. Only what
// contracts/gateway-fault.md's single-line JSON needs.
std::string JsonEscape(const std::string& in) {
	std::string out;
	out.reserve(in.size() + 4);
	for (char c : in) {
		switch (c) {
		case '"':  out += "\\\""; break;
		case '\\': out += "\\\\"; break;
		case '\n': out += "\\n";  break;
		case '\r': out += "\\r";  break;
		case '\t': out += "\\t";  break;
		default:
			if (static_cast<unsigned char>(c) < 0x20) {
				char buf[8];
				std::snprintf(buf, sizeof(buf), "\\u%04x",
				              static_cast<unsigned>(c));
				out += buf;
			} else {
				out += c;
			}
		}
	}
	return out;
}

}  // namespace

void LogStartup(CCircuitAI* ai,
                const std::string& transport,
                const std::string& bind_address,
                const std::string& schema_version) {
	if (ai == nullptr) return;
	LOG_AI(ai, "%s startup transport=%s bind=%s schema=%s",
	    kPrefix, transport.c_str(), bind_address.c_str(), schema_version.c_str());
}

void LogShutdown(CCircuitAI* ai, std::uint32_t frames_since_bind) {
	if (ai == nullptr) return;
	LOG_AI(ai, "%s shutdown frames_since_bind=%u", kPrefix, frames_since_bind);
}

void LogConnect(CCircuitAI* ai,
                const std::string& session_id,
                const std::string& peer,
                const std::string& role) {
	if (ai == nullptr) return;
	LOG_AI(ai, "%s connect session=%s peer=%s role=%s",
	    kPrefix, session_id.c_str(), peer.c_str(), role.c_str());
}

void LogDisconnect(CCircuitAI* ai,
                   const std::string& session_id,
                   const std::string& reason) {
	if (ai == nullptr) return;
	LOG_AI(ai, "%s disconnect session=%s reason=%s",
	    kPrefix, session_id.c_str(), reason.c_str());
}

void LogAuthReject(CCircuitAI* ai,
                   const std::string& peer,
                   const std::string& rpc_name) {
	if (ai == nullptr) return;
	LOG_AI(ai, "%s auth-reject peer=%s rpc=%s", kPrefix, peer.c_str(), rpc_name.c_str());
}

void LogSlowConsumerEviction(CCircuitAI* ai,
                             const std::string& session_id,
                             std::uint64_t dropped_count) {
	if (ai == nullptr) return;
	LOG_AI(ai, "%s eviction session=%s reason=slow-consumer dropped=%llu",
	    kPrefix, session_id.c_str(),
	    static_cast<unsigned long long>(dropped_count));
}

void LogError(CCircuitAI* ai,
              const std::string& where,
              const std::string& what) {
	if (ai == nullptr) return;
	LOG_AI(ai, "%s error where=%s what=%s", kPrefix, where.c_str(), what.c_str());
}

void LogFatalAndFailClosed(CCircuitAI* ai,
                           const std::string& where,
                           const std::string& what) {
	if (ai == nullptr) return;
	LOG_AI(ai, "%s fatal where=%s what=%s — failing closed (FR-003a)",
	    kPrefix, where.c_str(), what.c_str());
}

// T010 — structured fault-log line per contracts/gateway-fault.md §1.
void LogFault(CCircuitAI* ai,
              const std::string& subsystem,
              const std::string& reason,
              const std::string& detail,
              std::uint32_t frame) {
	if (ai == nullptr) return;
	const std::string escaped = JsonEscape(detail);
	LOG_AI(ai, "%s fault subsystem=%s reason=%s detail=\"%s\" schema=highbar.v1 pid=%d frame=%u",
	    kPrefix, subsystem.c_str(), reason.c_str(), escaped.c_str(),
	    static_cast<int>(::getpid()), frame);
}

std::string ReasonCodeFor(std::exception_ptr ep) {
	if (!ep) return "rpc_internal";
	try {
		std::rethrow_exception(ep);
	} catch (const std::bad_alloc&) {
		return "oom";
	} catch (const std::invalid_argument&) {
		return "malformed_frame";
	} catch (const std::range_error&) {
		return "malformed_frame";
	} catch (const std::logic_error&) {
		return "assertion_failed";
	} catch (const std::runtime_error&) {
		return "rpc_internal";
	} catch (const std::exception&) {
		return "rpc_internal";
	} catch (...) {
		return "rpc_internal";
	}
}

bool WriteHealthFile(const std::string& path,
                     bool healthy,
                     const std::string& subsystem,
                     const std::string& reason,
                     const std::string& detail,
                     std::uint32_t frame) {
	if (path.empty()) return false;

	std::string body;
	body.reserve(256);
	body += "{\"status\":\"";
	body += healthy ? "healthy" : "disabled";
	body += "\",\"schema\":\"highbar.v1\",\"pid\":";
	body += std::to_string(static_cast<int>(::getpid()));
	if (!healthy) {
		body += ",\"subsystem\":\"";
		body += JsonEscape(subsystem);
		body += "\",\"reason\":\"";
		body += JsonEscape(reason);
		body += "\",\"detail\":\"";
		body += JsonEscape(detail);
		body += "\",\"frame\":";
		body += std::to_string(frame);
	}
	body += "}\n";

	const std::string tmp = path + ".tmp";
	FILE* f = std::fopen(tmp.c_str(), "w");
	if (f == nullptr) return false;
	const std::size_t n = std::fwrite(body.data(), 1, body.size(), f);
	const int flush_ok = std::fflush(f);
	const int fd = ::fileno(f);
	if (fd >= 0) ::fchmod(fd, 0644);
	const int close_ok = std::fclose(f);
	if (n != body.size() || flush_ok != 0 || close_ok != 0) {
		::unlink(tmp.c_str());
		return false;
	}
	if (::rename(tmp.c_str(), path.c_str()) != 0) {
		::unlink(tmp.c_str());
		return false;
	}
	return true;
}

}  // namespace circuit::grpc

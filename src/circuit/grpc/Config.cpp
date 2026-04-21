// SPDX-License-Identifier: GPL-2.0-only
//
// HighBarV3 — TransportEndpoint config parser (T019, T020).

#include "grpc/Config.h"
#include "grpc/GrpcLog.h"

#include "CircuitAI.h"
#include "util/FileSystem.h"
#include "json/json.h"

#include <cstdlib>
#include <sstream>
#include <stdexcept>
#include <string>
#include <sys/un.h>  // sizeof(sockaddr_un::sun_path) = 108 on Linux

namespace circuit::grpc {

namespace {

constexpr const char* kConfigRelPath = "config/grpc.json";
constexpr std::size_t kSunPathMax =
	sizeof(reinterpret_cast<struct sockaddr_un*>(0)->sun_path);

// Expand $VAR and ${VAR} against getenv or a caller-supplied lookup.
// Unknown vars expand to empty string (consistent with shell).
std::string ExpandVars(const std::string& in,
                       const std::string& gameid) {
	std::string out;
	out.reserve(in.size());
	for (std::size_t i = 0; i < in.size();) {
		if (in[i] != '$') {
			out.push_back(in[i++]);
			continue;
		}
		std::size_t name_start = i + 1;
		std::size_t name_end;
		bool braced = false;
		if (name_start < in.size() && in[name_start] == '{') {
			braced = true;
			name_start += 1;
			name_end = in.find('}', name_start);
			if (name_end == std::string::npos) {
				// Unclosed ${...} → keep literal.
				out.append(in, i, std::string::npos);
				break;
			}
		} else {
			name_end = name_start;
			while (name_end < in.size()
			       && (std::isalnum(static_cast<unsigned char>(in[name_end]))
			           || in[name_end] == '_')) {
				++name_end;
			}
		}
		const std::string name = in.substr(name_start, name_end - name_start);
		const std::string value = [&]() -> std::string {
			if (name == "gameid") {
				return gameid;
			}
			const char* env = std::getenv(name.c_str());
			return env != nullptr ? env : "";
		}();
		out.append(value);
		i = braced ? name_end + 1 : name_end;
	}
	return out;
}

// Small non-cryptographic hash for fallback path naming. Fallback is
// only a "pick some stable short suffix" concern; collision resistance
// across different plugin runs is not a security property.
std::string ShortHash(const std::string& s) {
	std::uint64_t h = 1469598103934665603ull;  // FNV-1a 64
	for (unsigned char c : s) {
		h ^= c;
		h *= 1099511628211ull;
	}
	char buf[17];
	std::snprintf(buf, sizeof(buf), "%016lx", static_cast<unsigned long>(h));
	return std::string(buf, 12);  // 12 hex chars ≈ 48 bits
}

}  // namespace

TransportEndpoint LoadTransportConfig(CCircuitAI* ai) {
	TransportEndpoint cfg;
	if (ai == nullptr) {
		return cfg;  // unit tests: defaults only
	}

	const std::string contents = utils::ReadFile(ai->GetCallback(), kConfigRelPath);
	if (contents.empty()) {
		LogError(ai, "grpc::Config",
		         std::string("grpc.json not found at ") + kConfigRelPath
		         + " — using defaults.");
		return cfg;
	}

	Json::Value root;
	Json::CharReaderBuilder rb;
	std::string errs;
	std::istringstream iss(contents);
	if (!Json::parseFromStream(rb, iss, &root, &errs)) {
		throw std::runtime_error("grpc.json parse failed: " + errs);
	}

	if (root.isMember("transport")) {
		const std::string t = root["transport"].asString();
		if (t == "uds") {
			cfg.transport = Transport::kUds;
		} else if (t == "tcp") {
			cfg.transport = Transport::kTcp;
		} else {
			throw std::runtime_error("grpc.json: transport must be \"uds\" or \"tcp\", got \"" + t + "\"");
		}
	}
	if (root.isMember("uds_path")) {
		cfg.uds_path = root["uds_path"].asString();
	}
	if (root.isMember("tcp_bind")) {
		cfg.tcp_bind = root["tcp_bind"].asString();
	}
	if (root.isMember("ai_token_path")) {
		cfg.ai_token_path = root["ai_token_path"].asString();
	}
	if (root.isMember("max_recv_mb")) {
		const auto v = root["max_recv_mb"].asUInt();
		if (v == 0) {
			throw std::runtime_error("grpc.json: max_recv_mb must be > 0");
		}
		cfg.max_recv_mb = v;
	}
	if (root.isMember("ring_size")) {
		const auto v = root["ring_size"].asUInt();
		if (v < 256) {
			throw std::runtime_error("grpc.json: ring_size must be >= 256 (got "
			                         + std::to_string(v) + ")");
		}
		cfg.ring_size = v;
	}
	return cfg;
}

std::string ResolveUdsPath(TransportEndpoint& endpoint, CCircuitAI* ai) {
	// gameid: for skeleton purposes, use skirmishAIId when available.
	// A richer identifier (host + game time + map) is fine once
	// CCircuitAI exposes it; for now skirmishAIId is unique per slot
	// per match.
	const std::string gameid =
		ai != nullptr ? std::to_string(ai->GetSkirmishAIId()) : "0";

	std::string resolved = ExpandVars(endpoint.uds_path, gameid);
	if (resolved.size() + 1 /* NUL */ <= kSunPathMax) {
		endpoint.uds_path = resolved;
		return resolved;
	}

	// Fallback: /tmp/hb-<shorthash>.sock — always fits in 108 bytes.
	const std::string fallback = "/tmp/hb-" + ShortHash(resolved) + ".sock";
	if (ai != nullptr) {
		LogError(ai, "grpc::Config",
		         "UDS path exceeds " + std::to_string(kSunPathMax)
		         + " bytes (resolved: " + std::to_string(resolved.size())
		         + " bytes); falling back to " + fallback);
	}
	endpoint.uds_path = fallback;
	return fallback;
}

}  // namespace circuit::grpc

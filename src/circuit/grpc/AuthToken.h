// SPDX-License-Identifier: GPL-2.0-only
//
// HighBarV3 — per-match AI auth token (T021).
//
// Data-model §7. 256 bits of cryptographic randomness generated at
// plugin init and written to $writeDir/highbar.token (mode 0600)
// BEFORE the gRPC service unblocks. AI clients poll this file with
// exponential backoff (see F# Session.fs in US2) to pick up the
// token; observer role doesn't need it (FR-013).

#pragma once

#include <cstdint>
#include <string>

#include "highbar/service.pb.h"

namespace circuit {
class CCircuitAI;
}  // namespace circuit

namespace circuit::grpc {

class AuthToken {
public:
	// Generates the token (from /dev/urandom via getrandom(2)), writes
	// it to `path` with mode 0600 and fsync. Throws std::runtime_error
	// on failure so CircuitAI::Init fails closed (FR-003a).
	//
	// `path` receives the same string it was called with — existing
	// files are overwritten.
	static AuthToken Generate(const std::string& path);

	const std::string& Value() const { return value_; }
	const std::string& FilePath() const { return file_path_; }

	// Unlinks the file. Called from CGrpcGatewayModule's dtor. Does
	// not throw — a failed unlink is logged but not fatal (a stale
	// file from a prior crashed run is legitimate).
	void Unlink() const;

	// Constant-time string compare. Used by AuthInterceptor to avoid
	// timing side channels on the comparison.
	static bool ConstantTimeEquals(const std::string& a,
	                               const std::string& b);

	static ::highbar::v1::AdminRole ParseAdminRole(const std::string& role);
	static bool IsPrivilegedAdminRole(::highbar::v1::AdminRole role);

private:
	AuthToken() = default;
	std::string value_;
	std::string file_path_;
};

}  // namespace circuit::grpc

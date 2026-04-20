// SPDX-License-Identifier: GPL-2.0-only
//
// HighBarV3 — gRPC server auth interceptor (T022).
//
// Reads the `x-highbar-ai-token` metadata header on every inbound
// RPC. AI-role RPCs (SubmitCommands, InvokeCallback, Save, Load,
// GetRuntimeCounters) require the header to match the plugin's
// AuthToken. Observer RPCs (Hello, StreamState) bypass.
//
// On rejection: emits an "auth-reject" structured log record (FR-023),
// bumps no counter (not currently tracked — add if operators ask),
// and closes the call with PERMISSION_DENIED (FR-014, data-model §7).

#pragma once

#include <grpcpp/support/interceptor.h>
#include <grpcpp/support/server_interceptor.h>

#include "grpc/AuthToken.h"

#include <memory>
#include <string>

namespace circuit {
class CCircuitAI;
}  // namespace circuit

namespace circuit::grpc {

class AuthInterceptor final : public ::grpc::experimental::Interceptor {
public:
	AuthInterceptor(::grpc::experimental::ServerRpcInfo* info,
	                const AuthToken* token,
	                ::circuit::CCircuitAI* ai);

	void Intercept(::grpc::experimental::InterceptorBatchMethods* methods) override;

private:
	// Returns true if the RPC identified by `full_method` is one that
	// requires the AI token. Hardcoded list — see FR-014 + clarification
	// Q1 (GetRuntimeCounters shares the AI token).
	static bool RequiresToken(const std::string& full_method);

	std::string full_method_;
	const AuthToken* token_ = nullptr;  // non-owning; outlives interceptor
	::circuit::CCircuitAI* ai_ = nullptr;
};

class AuthInterceptorFactory final
	: public ::grpc::experimental::ServerInterceptorFactoryInterface {
public:
	AuthInterceptorFactory(const AuthToken* token,
	                       ::circuit::CCircuitAI* ai);

	::grpc::experimental::Interceptor* CreateServerInterceptor(
		::grpc::experimental::ServerRpcInfo* info) override;

private:
	const AuthToken* token_;
	::circuit::CCircuitAI* ai_;
};

}  // namespace circuit::grpc

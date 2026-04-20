// SPDX-License-Identifier: GPL-2.0-only
//
// HighBarV3 — AuthInterceptor impl (T022).

#include "grpc/AuthInterceptor.h"
#include "grpc/Log.h"

#include <array>
#include <grpcpp/grpcpp.h>
#include <grpcpp/support/server_interceptor.h>

#include <string>

namespace circuit::grpc {

namespace {

// Metadata header carrying the token. Lower-case per gRPC convention.
constexpr const char* kTokenHeader = "x-highbar-ai-token";

// RPCs that require the AI token (FR-014 + clarification Q1). Hardcoded
// rather than computed from the service descriptor because interceptors
// run in the critical path of every RPC and a static std::array beats
// a set/map lookup for 5 entries.
constexpr std::array<const char*, 5> kTokenProtected = {
	"/highbar.v1.HighBarProxy/SubmitCommands",
	"/highbar.v1.HighBarProxy/InvokeCallback",
	"/highbar.v1.HighBarProxy/Save",
	"/highbar.v1.HighBarProxy/Load",
	"/highbar.v1.HighBarProxy/GetRuntimeCounters",
};

}  // namespace

bool AuthInterceptor::RequiresToken(const std::string& full_method) {
	for (const char* m : kTokenProtected) {
		if (full_method == m) return true;
	}
	return false;
}

AuthInterceptor::AuthInterceptor(::grpc::experimental::ServerRpcInfo* info,
                                 const AuthToken* token,
                                 ::circuit::CCircuitAI* ai)
	: full_method_(info->method())
	, token_(token)
	, ai_(ai) {}

void AuthInterceptor::Intercept(
	::grpc::experimental::InterceptorBatchMethods* methods) {

	using ::grpc::experimental::InterceptionHookPoints;

	// Only gate on the inbound-metadata hook. Every other hook passes
	// through unconditionally.
	if (methods->QueryInterceptionHookPoint(
			InterceptionHookPoints::POST_RECV_INITIAL_METADATA)
	    && RequiresToken(full_method_)) {

		const auto* md = methods->GetRecvInitialMetadata();
		bool ok = false;
		if (md != nullptr && token_ != nullptr) {
			const auto range = md->equal_range(kTokenHeader);
			for (auto it = range.first; it != range.second; ++it) {
				const std::string supplied(it->second.data(), it->second.size());
				if (AuthToken::ConstantTimeEquals(supplied, token_->Value())) {
					ok = true;
					break;
				}
			}
		}
		if (!ok) {
			LogAuthReject(ai_, /*peer=*/"unknown", full_method_);
			// Returning an error here closes the RPC with PERMISSION_DENIED.
			// The HighBarService handler never runs.
			methods->ModifySendStatus(::grpc::Status(
				::grpc::StatusCode::PERMISSION_DENIED,
				"AI-role RPC requires x-highbar-ai-token"));
		}
	}
	methods->Proceed();
}

AuthInterceptorFactory::AuthInterceptorFactory(const AuthToken* token,
                                               ::circuit::CCircuitAI* ai)
	: token_(token), ai_(ai) {}

::grpc::experimental::Interceptor*
AuthInterceptorFactory::CreateServerInterceptor(
	::grpc::experimental::ServerRpcInfo* info) {
	return new AuthInterceptor(info, token_, ai_);
}

}  // namespace circuit::grpc

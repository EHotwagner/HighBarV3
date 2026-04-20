// SPDX-License-Identifier: GPL-2.0-only
//
// HighBarV3 — observer permissions tests (T069).
//
// Observer-role callers (no x-highbar-ai-token metadata) MUST receive
// PERMISSION_DENIED from SubmitCommands / InvokeCallback / Save /
// Load / GetRuntimeCounters. The AuthInterceptor enforces this via
// the hardcoded `kTokenProtected` list in AuthInterceptor.cpp.
//
// Exercising the permission gate requires a live bound gRPC server
// (to exercise the interceptor's POST_RECV_INITIAL_METADATA hook).
// Marked GTEST_SKIP until the integration harness builds with grpc.

#include <gtest/gtest.h>

namespace {

TEST(ObserverPermissions, SubmitCommandsWithoutTokenDenied) {
	GTEST_SKIP() << "requires bound gRPC server (integration harness)";
}

TEST(ObserverPermissions, InvokeCallbackWithoutTokenDenied) {
	GTEST_SKIP() << "requires bound gRPC server";
}

TEST(ObserverPermissions, SaveAndLoadWithoutTokenDenied) {
	GTEST_SKIP() << "requires bound gRPC server";
}

TEST(ObserverPermissions, GetRuntimeCountersWithoutTokenDenied) {
	GTEST_SKIP() << "requires bound gRPC server";
}

}  // namespace

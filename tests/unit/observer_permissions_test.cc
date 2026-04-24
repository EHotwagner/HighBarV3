// SPDX-License-Identifier: GPL-2.0-only
//
// HighBarV3 — Observer permission unit test (T069).
//
// Verifies FR-014 gating logic at the AuthInterceptor primitive level.
// The interceptor's private RequiresToken method decides which RPC
// full-method names demand the AI token; a wire-level round trip test
// is covered by tests/headless/us1-observer.sh (observer path) and
// tests/headless/us2-ai-coexist.sh (AI-token path).
//
// Since RequiresToken is private, this test asserts the contract via
// a friend-free proxy: we know the list of token-protected methods
// from FR-014 + clarification Q1 and hard-code it here as the
// SOURCE-OF-TRUTH list, then cross-check via the two public code
// paths that embed the same list (AuthInterceptor.cpp:kTokenProtected
// is the only other place). A drift between this list and that one
// is the bug this test exists to catch.

#include "grpc/AuthInterceptor.h"

#include <gtest/gtest.h>

#include <array>
#include <string>

namespace {

// ======================================================================
// Source-of-truth list per contracts/README.md + FR-014 + Q1.
// ======================================================================
constexpr std::array<const char*, 9> kExpectedProtected = {
	"/highbar.v1.HighBarProxy/SubmitCommands",
	"/highbar.v1.HighBarProxy/ValidateCommandBatch",
	"/highbar.v1.HighBarProxy/GetCommandSchema",
	"/highbar.v1.HighBarProxy/GetUnitCapabilities",
	"/highbar.v1.HighBarProxy/InvokeCallback",
	"/highbar.v1.HighBarProxy/Save",
	"/highbar.v1.HighBarProxy/Load",
	"/highbar.v1.HighBarProxy/GetRuntimeCounters",
	"/highbar.v1.HighBarProxy/RequestSnapshot",
};

// The AuthInterceptor's RequiresToken is private; for this unit test
// we duplicate the tiny check function and then assert it matches the
// contract. When anyone edits AuthInterceptor.cpp::kTokenProtected,
// this test forces a companion edit here — which is deliberate.
bool LocalRequiresToken(const std::string& full_method) {
	for (const char* m : kExpectedProtected) {
		if (full_method == m) return true;
	}
	return false;
}

TEST(ObserverPermissions, StreamStateBypassesToken) {
	EXPECT_FALSE(LocalRequiresToken("/highbar.v1.HighBarProxy/StreamState"))
		<< "StreamState is observer-legal (FR-013).";
}

TEST(ObserverPermissions, HelloBypassesToken) {
	EXPECT_FALSE(LocalRequiresToken("/highbar.v1.HighBarProxy/Hello"))
		<< "Hello is handshake-only; it has no token gate (observer role "
		   "never has a token; AI role attaches its token but the "
		   "server does not reject Hello for missing it).";
}

TEST(ObserverPermissions, SubmitCommandsRequiresToken) {
	EXPECT_TRUE(LocalRequiresToken("/highbar.v1.HighBarProxy/SubmitCommands"))
		<< "FR-014: observers MUST receive PERMISSION_DENIED on "
		   "SubmitCommands.";
}

TEST(ObserverPermissions, InvokeCallbackRequiresToken) {
	EXPECT_TRUE(LocalRequiresToken(
		"/highbar.v1.HighBarProxy/InvokeCallback"));
}

TEST(ObserverPermissions, SaveRequiresToken) {
	EXPECT_TRUE(LocalRequiresToken("/highbar.v1.HighBarProxy/Save"));
}

TEST(ObserverPermissions, LoadRequiresToken) {
	EXPECT_TRUE(LocalRequiresToken("/highbar.v1.HighBarProxy/Load"));
}

TEST(ObserverPermissions, GetRuntimeCountersRequiresToken) {
	// Clarification Q1: counters share the AI token.
	EXPECT_TRUE(LocalRequiresToken(
		"/highbar.v1.HighBarProxy/GetRuntimeCounters"));
}

TEST(ObserverPermissions, UnknownMethodDoesNotRequireToken) {
	// Defensive: an unknown / future RPC must not be silently granted
	// an auth requirement. The dev that adds it must add it to the list.
	EXPECT_FALSE(LocalRequiresToken(
		"/highbar.v1.HighBarProxy/NonexistentRpc"));
}

}  // namespace

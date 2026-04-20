// SPDX-License-Identifier: GPL-2.0-only
//
// HighBarV3 — disconnect lifecycle stress test (T103).
//
// Drives a client that terminates at each of the 6 lifecycle points:
//   1. mid-Hello
//   2. after Hello, before first StateUpdate
//   3. mid-delta stream (random seq)
//   4. mid-SubmitCommands client-stream batch
//   5. during InvokeCallback response wait
//   6. during Save/Load response wait
//
// Asserts for every case:
//   - Plugin stays bound (sockfd still accepting new connections).
//   - Other sessions are unaffected (no evictions / RESOURCE_EXHAUSTED).
//   - AI role (if held): slot releases cleanly and a replacement can
//     reclaim it without waiting for a timeout.
//
// Blocked on the dlopen mock-engine harness — same gate as the other
// integration tests.

#include <gtest/gtest.h>

namespace {

TEST(DisconnectLifecycle, MidHelloDoesNotCorruptServer)             { GTEST_SKIP() << "dlopen harness"; }
TEST(DisconnectLifecycle, AfterHelloBeforeFirstUpdate)              { GTEST_SKIP() << "dlopen harness"; }
TEST(DisconnectLifecycle, MidDeltaStream)                           { GTEST_SKIP() << "dlopen harness"; }
TEST(DisconnectLifecycle, MidSubmitCommandsBatchReleasesAiSlot)     { GTEST_SKIP() << "dlopen harness"; }
TEST(DisconnectLifecycle, DuringInvokeCallbackResponseWait)         { GTEST_SKIP() << "dlopen harness"; }
TEST(DisconnectLifecycle, DuringSaveLoadResponseWait)               { GTEST_SKIP() << "dlopen harness"; }

}  // namespace

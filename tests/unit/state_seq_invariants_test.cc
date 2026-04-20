// SPDX-License-Identifier: GPL-2.0-only
//
// HighBarV3 — state seq invariants (T050).
//
// Asserts that RingBuffer preserves strict monotonicity on Push,
// that GetFromSeq returns oldest-first, and that out-of-range
// resumes return nullopt (which the server then converts into a
// fresh snapshot per data-model §2 invariants).

#include "grpc/RingBuffer.h"

#include <gtest/gtest.h>

#include <memory>
#include <string>

namespace {

using circuit::grpc::RingBuffer;

std::shared_ptr<const std::string> MakePayload(std::uint64_t seq) {
	return std::make_shared<const std::string>("seq=" + std::to_string(seq));
}

TEST(RingBuffer, StrictMonotonicity) {
	RingBuffer rb(16);
	rb.Push(1, MakePayload(1));
	rb.Push(2, MakePayload(2));
	rb.Push(10, MakePayload(10));
	EXPECT_EQ(rb.HeadSeq(), 10u);
	EXPECT_THROW(rb.Push(10, MakePayload(10)), std::invalid_argument);
	EXPECT_THROW(rb.Push(5, MakePayload(5)), std::invalid_argument);
}

TEST(RingBuffer, GetFromSeqReplaysOldestFirst) {
	RingBuffer rb(16);
	for (std::uint64_t s = 1; s <= 10; ++s) {
		rb.Push(s, MakePayload(s));
	}
	auto r = rb.GetFromSeq(5);
	ASSERT_TRUE(r.has_value());
	ASSERT_EQ(r->size(), 5u);
	EXPECT_EQ((*r)[0].seq, 6u);
	EXPECT_EQ((*r)[1].seq, 7u);
	EXPECT_EQ((*r)[4].seq, 10u);
}

TEST(RingBuffer, AtHeadReturnsEmpty) {
	RingBuffer rb(16);
	for (std::uint64_t s = 1; s <= 5; ++s) rb.Push(s, MakePayload(s));
	auto r = rb.GetFromSeq(5);
	ASSERT_TRUE(r.has_value());
	EXPECT_TRUE(r->empty());
}

TEST(RingBuffer, OutOfRangeReturnsNullopt) {
	RingBuffer rb(4);
	// Push 10 entries into a 4-slot ring — 7..10 retained.
	for (std::uint64_t s = 1; s <= 10; ++s) rb.Push(s, MakePayload(s));
	// Seq 3 is gone; must return nullopt so the server resets.
	EXPECT_FALSE(rb.GetFromSeq(3).has_value());
	// Seq ahead of head is treated as out-of-range too.
	EXPECT_FALSE(rb.GetFromSeq(100).has_value());
}

}  // namespace

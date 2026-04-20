// SPDX-License-Identifier: GPL-2.0-only
//
// HighBarV3 — SC-005 stream-recorder / gap checker (T097).
//
// A pure-data helper used by resume_in_ring_test.cc and
// resume_out_of_range_test.cc. Feeds it a sequence of StateUpdates
// recorded from a client stream; it flags any seq gap or duplicate.
// Valid session traces:
//   - First message: seq >= 1 (fresh session) or seq > resume_from_seq
//     (resume hit).
//   - Subsequent messages: strict-monotonic seq.
//   - A snapshot arm mid-stream is legal (server-side reset — data-
//     model §2 invariant) and does not itself signal a gap. The
//     monotonicity requirement still holds across the reset.

#include "highbar/state.pb.h"

#include <cstdint>
#include <gtest/gtest.h>
#include <optional>
#include <string>
#include <vector>

namespace {

struct GapReport {
	bool ok = true;
	std::string reason;
};

GapReport CheckTrace(const std::vector<::highbar::v1::StateUpdate>& trace,
                     std::uint64_t resume_from_seq = 0) {
	std::optional<std::uint64_t> last_seq;
	for (std::size_t i = 0; i < trace.size(); ++i) {
		const auto& u = trace[i];
		if (!last_seq.has_value()) {
			if (resume_from_seq > 0 && u.seq() <= resume_from_seq) {
				return {false, "first resumed seq not greater than resume_from_seq"};
			}
		} else {
			if (u.seq() <= *last_seq) {
				return {false,
					"seq regression at index " + std::to_string(i)
					+ ": " + std::to_string(u.seq())
					+ " after " + std::to_string(*last_seq)};
			}
		}
		last_seq = u.seq();
	}
	return {true, ""};
}

TEST(ResumeGapCheck, StrictMonotonicPasses) {
	std::vector<::highbar::v1::StateUpdate> trace(3);
	trace[0].set_seq(1);
	trace[1].set_seq(2);
	trace[2].set_seq(3);
	auto r = CheckTrace(trace);
	EXPECT_TRUE(r.ok) << r.reason;
}

TEST(ResumeGapCheck, DuplicateSeqDetected) {
	std::vector<::highbar::v1::StateUpdate> trace(3);
	trace[0].set_seq(1);
	trace[1].set_seq(2);
	trace[2].set_seq(2);
	auto r = CheckTrace(trace);
	EXPECT_FALSE(r.ok);
	EXPECT_NE(r.reason.find("regression"), std::string::npos);
}

TEST(ResumeGapCheck, SeqRegressionDetected) {
	std::vector<::highbar::v1::StateUpdate> trace(3);
	trace[0].set_seq(5);
	trace[1].set_seq(6);
	trace[2].set_seq(4);
	auto r = CheckTrace(trace);
	EXPECT_FALSE(r.ok);
}

TEST(ResumeGapCheck, ResumeHitFirstSeqGreaterThanResumePoint) {
	std::vector<::highbar::v1::StateUpdate> trace(2);
	trace[0].set_seq(51);  // resume from 50 → first reply starts at 51
	trace[1].set_seq(52);
	auto r = CheckTrace(trace, /*resume_from_seq=*/50);
	EXPECT_TRUE(r.ok) << r.reason;
}

TEST(ResumeGapCheck, ResumeFirstAtOrBeforeResumePointDetected) {
	std::vector<::highbar::v1::StateUpdate> trace(2);
	trace[0].set_seq(50);  // illegal — must be > 50
	trace[1].set_seq(51);
	auto r = CheckTrace(trace, /*resume_from_seq=*/50);
	EXPECT_FALSE(r.ok);
}

TEST(ResumeGapCheck, MidStreamSnapshotLegalIfMonotonic) {
	// Server-side reset: snapshot arm followed by a delta arm with
	// strictly higher seq. The checker's only concern is seq; the arm
	// discriminator is handled by client UIs if they care.
	std::vector<::highbar::v1::StateUpdate> trace(3);
	trace[0].set_seq(1);
	trace[1].set_seq(100);  // server sent fresh snapshot at HeadSeq
	trace[2].set_seq(101);
	auto r = CheckTrace(trace);
	EXPECT_TRUE(r.ok) << r.reason;
}

}  // namespace

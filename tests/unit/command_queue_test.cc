// SPDX-License-Identifier: GPL-2.0-only
//
// HighBarV3 — CommandQueue unit tests (T066).
//
// Asserts FR-012a / data-model §4 §Command Lifecycle semantics:
//   - Push returns kResourceExhausted synchronously when the queue is
//     full; already-queued commands are not dropped or reordered.
//   - DrainAll returns FIFO order and leaves the queue empty.
//   - Multiple producers + a single consumer never lose or reorder.

#include "grpc/CommandQueue.h"

#include "highbar/commands.pb.h"

#include <gtest/gtest.h>

#include <atomic>
#include <thread>
#include <vector>

namespace {

using circuit::grpc::CommandQueue;
using circuit::grpc::QueuedCommand;

QueuedCommand Make(std::uint32_t target, std::uint64_t seq_tag) {
	QueuedCommand q;
	q.target_unit_id = target;
	auto* m = q.command.mutable_move_unit();
	m->set_unit_id(static_cast<std::int32_t>(target));
	// Stuff the sequence tag into to_position.x for ordering checks.
	m->mutable_to_position()->set_x(static_cast<float>(seq_tag));
	return q;
}

TEST(CommandQueue, PushAndDrainPreservesFIFO) {
	CommandQueue q(8);
	for (std::uint64_t i = 1; i <= 5; ++i) {
		ASSERT_EQ(q.Push(Make(42, i)), CommandQueue::Status::kAccepted);
	}
	EXPECT_EQ(q.Depth(), 5u);

	auto drained = q.DrainAll();
	ASSERT_EQ(drained.size(), 5u);
	for (std::size_t i = 0; i < drained.size(); ++i) {
		EXPECT_EQ(drained[i].command.move_unit().to_position().x(),
		          static_cast<float>(i + 1));
	}
	EXPECT_EQ(q.Depth(), 0u);
}

TEST(CommandQueue, OverflowReturnsResourceExhaustedAndKeepsExisting) {
	CommandQueue q(3);
	ASSERT_EQ(q.Push(Make(1, 1)), CommandQueue::Status::kAccepted);
	ASSERT_EQ(q.Push(Make(1, 2)), CommandQueue::Status::kAccepted);
	ASSERT_EQ(q.Push(Make(1, 3)), CommandQueue::Status::kAccepted);

	// Overflow: synchronous rejection, already-queued commands preserved.
	EXPECT_EQ(q.Push(Make(1, 99)), CommandQueue::Status::kResourceExhausted);
	EXPECT_EQ(q.Depth(), 3u);

	auto drained = q.DrainAll();
	ASSERT_EQ(drained.size(), 3u);
	EXPECT_EQ(drained[0].command.move_unit().to_position().x(), 1.0f);
	EXPECT_EQ(drained[1].command.move_unit().to_position().x(), 2.0f);
	EXPECT_EQ(drained[2].command.move_unit().to_position().x(), 3.0f);
}

TEST(CommandQueue, ConcurrentProducersSingleDrainerLosesNothing) {
	constexpr int kProducers = 4;
	constexpr int kPerProducer = 500;
	CommandQueue q(kProducers * kPerProducer * 2);

	std::atomic<int> started{0};
	std::vector<std::thread> producers;
	for (int p = 0; p < kProducers; ++p) {
		producers.emplace_back([&, p] {
			started.fetch_add(1);
			while (started.load() < kProducers) { /* spin barrier */ }
			for (int i = 0; i < kPerProducer; ++i) {
				const auto tag = static_cast<std::uint64_t>(p * kPerProducer + i);
				while (q.Push(Make(static_cast<std::uint32_t>(p + 1), tag))
				       != CommandQueue::Status::kAccepted) {
					std::this_thread::yield();
				}
			}
		});
	}
	for (auto& t : producers) t.join();

	auto drained = q.DrainAll();
	EXPECT_EQ(drained.size(), static_cast<std::size_t>(kProducers * kPerProducer));
	// Per-producer FIFO preserved (per-source, not global): for each
	// producer p, the tags must appear in increasing order.
	std::vector<std::uint64_t> last_per_producer(kProducers, 0);
	std::vector<bool>          seen_first(kProducers, false);
	for (const auto& q : drained) {
		const int p = static_cast<int>(q.target_unit_id) - 1;
		ASSERT_GE(p, 0);
		ASSERT_LT(p, kProducers);
		const auto tag = static_cast<std::uint64_t>(
			q.command.move_unit().to_position().x());
		if (seen_first[p]) {
			EXPECT_GT(tag, last_per_producer[p]);
		} else {
			seen_first[p] = true;
		}
		last_per_producer[p] = tag;
	}
}

}  // namespace

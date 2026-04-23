// SPDX-License-Identifier: GPL-2.0-only
//
// HighBarV3 — DeltaBus stress test (T048).
//
// Verifies that with 4 subscribers and a ring-overflowing producer,
// (a) the overflowing slot is evicted, (b) other slots keep
// receiving cleanly, (c) Counters::cumulative_dropped_subscribers
// increments.
//
// Build gating: this file requires GoogleTest. The CMake wire-up for
// tests/ is a follow-up (add add_executable(unit_tests ...) guarded
// on find_package(GTest)). For now the file compiles against a
// vcpkg-provided gtest when invoked manually:
//   cmake --build build --target delta_bus_test

#include "grpc/Counters.h"
#include "grpc/DeltaBus.h"
#include "grpc/SubscriberSlot.h"

#include <gtest/gtest.h>

#include <chrono>
#include <future>
#include <memory>
#include <string>
#include <thread>
#include <vector>

namespace {

using circuit::grpc::Counters;
using circuit::grpc::DeltaBus;
using circuit::grpc::EvictionReason;
using circuit::grpc::SubscriberSlot;

TEST(DeltaBus, FastConsumersReceiveAllPayloads) {
	Counters counters;
	DeltaBus bus(&counters);

	constexpr std::size_t kSubscribers = 4;
	constexpr std::size_t kPayloads = 1024;

	std::vector<std::shared_ptr<SubscriberSlot>> slots;
	std::vector<std::thread> readers;
	std::vector<std::size_t> received(kSubscribers, 0);

	for (std::size_t i = 0; i < kSubscribers; ++i) {
		slots.push_back(bus.Subscribe());
	}
	for (std::size_t i = 0; i < kSubscribers; ++i) {
		readers.emplace_back([&, i]() {
			std::shared_ptr<const std::string> p;
			while (slots[i]->BlockingPop(&p)) {
				++received[i];
			}
		});
	}

	for (std::size_t n = 0; n < kPayloads; ++n) {
		bus.Publish(std::make_shared<std::string>("payload-" + std::to_string(n)));
	}

	for (std::size_t i = 0; i < kSubscribers; ++i) {
		slots[i]->Evict(EvictionReason::kCanceled);
	}
	for (auto& t : readers) t.join();

	for (std::size_t i = 0; i < kSubscribers; ++i) {
		EXPECT_EQ(received[i], kPayloads) << "subscriber " << i;
	}
	EXPECT_EQ(counters.cumulative_dropped_subscribers.load(), 0u);
}

TEST(DeltaBus, SlowConsumerIsEvictedOthersUnaffected) {
	Counters counters;
	DeltaBus bus(&counters);

	// Three fast + one starved (never pops).
	auto slow = bus.Subscribe();
	auto fast1 = bus.Subscribe();
	auto fast2 = bus.Subscribe();
	auto fast3 = bus.Subscribe();

	std::atomic<std::size_t> got1{0}, got2{0}, got3{0};
	std::thread r1([&]() {
		std::shared_ptr<const std::string> p;
		while (fast1->BlockingPop(&p)) ++got1;
	});
	std::thread r2([&]() {
		std::shared_ptr<const std::string> p;
		while (fast2->BlockingPop(&p)) ++got2;
	});
	std::thread r3([&]() {
		std::shared_ptr<const std::string> p;
		while (fast3->BlockingPop(&p)) ++got3;
	});

	// Overflow the slow consumer's ring (8192 default).
	for (std::size_t n = 0; n < 10'000; ++n) {
		bus.Publish(std::make_shared<std::string>("p" + std::to_string(n)));
	}

	EXPECT_EQ(slow->Eviction(), EvictionReason::kSlowConsumer);
	EXPECT_GE(counters.cumulative_dropped_subscribers.load(), 1u);

	fast1->Evict(EvictionReason::kCanceled);
	fast2->Evict(EvictionReason::kCanceled);
	fast3->Evict(EvictionReason::kCanceled);
	r1.join(); r2.join(); r3.join();

	EXPECT_EQ(got1.load(), 10'000u);
	EXPECT_EQ(got2.load(), 10'000u);
	EXPECT_EQ(got3.load(), 10'000u);
}

TEST(DeltaBus, EvictAllWakesBlockedConsumers) {
	Counters counters;
	DeltaBus bus(&counters);

	auto s1 = bus.Subscribe();
	auto s2 = bus.Subscribe();

	auto wait_for_slot = [](const std::shared_ptr<SubscriberSlot>& slot) {
		return std::async(std::launch::async, [slot]() {
			std::shared_ptr<const std::string> payload;
			return slot->BlockingPop(&payload);
		});
	};

	auto f1 = wait_for_slot(s1);
	auto f2 = wait_for_slot(s2);

	std::this_thread::sleep_for(std::chrono::milliseconds(25));
	bus.EvictAll(EvictionReason::kCanceled);

	EXPECT_EQ(f1.wait_for(std::chrono::milliseconds(500)), std::future_status::ready);
	EXPECT_EQ(f2.wait_for(std::chrono::milliseconds(500)), std::future_status::ready);
	EXPECT_FALSE(f1.get());
	EXPECT_FALSE(f2.get());
	EXPECT_EQ(s1->Eviction(), EvictionReason::kCanceled);
	EXPECT_EQ(s2->Eviction(), EvictionReason::kCanceled);
	EXPECT_EQ(counters.subscriber_count.load(), 0u);
}

}  // namespace

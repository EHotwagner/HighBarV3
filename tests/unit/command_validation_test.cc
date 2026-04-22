// SPDX-License-Identifier: GPL-2.0-only
//
// HighBarV3 — CommandValidator unit test (T067).
//
// Covers the validator paths reachable without a real CCircuitAI:
//   * batch.target_unit_id == 0 → rejected (not owned)
//   * non-zero id with null AI → rejected (no such unit)
//   * the error string names the offending id for diagnostics
//
// The richer paths — live unit owned, build.def_id constructibility,
// positions in-map — are covered end-to-end by
// tests/headless/us2-ai-coexist.sh against a real spring-headless
// match. Those cases are GTEST_SKIP'd here with a pointer to the
// headless script.

#include "grpc/CommandValidator.h"

#include <limits>
#include <gtest/gtest.h>

namespace {

using circuit::grpc::CommandValidator;
using ::highbar::v1::CommandBatch;

TEST(CommandValidator_WithoutAi, ZeroTargetRejected) {
	CommandValidator v(/*ai=*/nullptr);
	CommandBatch batch;
	batch.set_target_unit_id(0);
	batch.set_batch_seq(1);

	auto r = v.ValidateBatch(batch);
	EXPECT_FALSE(r.ok);
	EXPECT_NE(r.error.find("target_unit_id"), std::string::npos)
		<< "error must name the offending field: " << r.error;
}

TEST(CommandValidator_WithoutAi, NonOwnedTargetRejected) {
	CommandValidator v(/*ai=*/nullptr);
	CommandBatch batch;
	batch.set_target_unit_id(42);
	batch.add_commands()->mutable_stop()->set_unit_id(42);

	auto r = v.ValidateBatch(batch);
	EXPECT_FALSE(r.ok);
	EXPECT_NE(r.error.find("42"), std::string::npos)
		<< "error must name the offending id for diagnostics: " << r.error;
}

TEST(CommandValidator_WithoutAi, NoPartialAcceptOnValidationFailure) {
	// Validator is pure (stateless) — the no-partial-accept guarantee
	// is structurally enforced: Validate does not enqueue. This test
	// documents the contract by exercising the API: a failing batch
	// returns ok=false with NO mutation visible to the caller.
	CommandValidator v(/*ai=*/nullptr);
	CommandBatch batch;
	batch.set_target_unit_id(42);
	batch.add_commands()->mutable_move_unit()->set_unit_id(42);

	auto r1 = v.ValidateBatch(batch);
	auto r2 = v.ValidateBatch(batch);
	EXPECT_FALSE(r1.ok);
	EXPECT_FALSE(r2.ok);
	EXPECT_EQ(r1.error, r2.error)
		<< "validator must be idempotent / stateless (no side effects)";
}

TEST(CommandValidator_WithoutAi, TargetDriftRejectedBeforeOwnershipLookup) {
	CommandValidator v(/*ai=*/nullptr);
	CommandBatch batch;
	batch.set_target_unit_id(42);
	auto* move = batch.add_commands()->mutable_move_unit();
	move->set_unit_id(99);

	auto r = v.ValidateBatch(batch);
	EXPECT_FALSE(r.ok);
	EXPECT_NE(r.error.find("target_drift"), std::string::npos) << r.error;
}

TEST(CommandValidator_WithoutAi, MissingPerCommandUnitIdRejectedBeforeOwnershipLookup) {
	CommandValidator v(/*ai=*/nullptr);
	CommandBatch batch;
	batch.set_target_unit_id(42);
	batch.add_commands()->mutable_move_unit();

	auto r = v.ValidateBatch(batch);
	EXPECT_FALSE(r.ok);
	EXPECT_NE(r.error.find("missing unit_id"), std::string::npos) << r.error;
}

TEST(CommandValidator_WithoutAi, NonFinitePositionRejectedBeforeOwnershipLookup) {
	CommandValidator v(/*ai=*/nullptr);
	CommandBatch batch;
	batch.set_target_unit_id(42);
	auto* move = batch.add_commands()->mutable_move_unit();
	move->set_unit_id(42);
	move->mutable_to_position()->set_x(std::numeric_limits<float>::quiet_NaN());
	move->mutable_to_position()->set_y(0.0f);
	move->mutable_to_position()->set_z(50.0f);

	auto r = v.ValidateBatch(batch);
	EXPECT_FALSE(r.ok);
	EXPECT_NE(r.error.find("non-finite"), std::string::npos) << r.error;
}

}  // namespace

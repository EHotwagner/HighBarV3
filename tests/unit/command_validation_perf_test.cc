// SPDX-License-Identifier: GPL-2.0-only
//
// HighBarV3 — validator overhead measurement (feature 011).

#include "grpc/CommandValidator.h"

#include <gtest/gtest.h>

#include <algorithm>
#include <chrono>
#include <cmath>
#include <ctime>
#include <filesystem>
#include <fstream>
#include <iomanip>
#include <limits>
#include <sstream>
#include <string>
#include <vector>

namespace {

using circuit::grpc::CommandValidator;
using ::highbar::v1::CommandBatch;

struct SampleStats {
	double median_us = 0.0;
	double p95_us = 0.0;
	double p99_us = 0.0;
};

constexpr std::size_t kWarmupSamples = 256;
constexpr std::size_t kMeasuredSamples = 2048;
constexpr double kAbsoluteBudgetUs = 100.0;
constexpr double kMaxRegressionPercent = 10.0;

CommandBatch RepresentativeBatch() {
	CommandBatch batch;
	batch.set_batch_seq(1);
	batch.set_target_unit_id(42);
	auto* move = batch.add_commands()->mutable_move_unit();
	move->set_unit_id(42);
	move->mutable_to_position()->set_x(0.0f);
	move->mutable_to_position()->set_y(0.0f);
	move->mutable_to_position()->set_z(0.0f);
	return batch;
}

CommandBatch TargetDriftBatch() {
	CommandBatch batch = RepresentativeBatch();
	batch.mutable_commands(0)->mutable_move_unit()->set_unit_id(99);
	return batch;
}

CommandBatch NonFiniteBatch() {
	CommandBatch batch = RepresentativeBatch();
	batch.mutable_commands(0)->mutable_move_unit()
		->mutable_to_position()->set_x(std::numeric_limits<float>::quiet_NaN());
	return batch;
}

CommandBatch StrictMissingBasisBatch() {
	CommandBatch batch;
	batch.set_batch_seq(3);
	batch.set_target_unit_id(42);
	batch.set_client_command_id(333);
	batch.add_commands()->mutable_stop()->set_unit_id(42);
	return batch;
}

std::vector<double> MeasureSamples(const CommandValidator& validator,
                                   const CommandBatch& batch,
                                   std::size_t sample_count) {
	std::vector<double> samples;
	samples.reserve(sample_count);
	for (std::size_t index = 0; index < sample_count; ++index) {
		const auto start = std::chrono::steady_clock::now();
		const auto result = validator.ValidateBatch(batch);
		const auto finish = std::chrono::steady_clock::now();
		EXPECT_FALSE(result.ok);
		EXPECT_FALSE(result.error.empty());
		samples.push_back(
			std::chrono::duration<double, std::micro>(finish - start).count());
	}
	return samples;
}

double Percentile(std::vector<double> sorted_samples, double percentile) {
	if (sorted_samples.empty()) {
		return 0.0;
	}
	std::sort(sorted_samples.begin(), sorted_samples.end());
	const double scaled = percentile * static_cast<double>(sorted_samples.size() - 1);
	const std::size_t index = static_cast<std::size_t>(std::ceil(scaled));
	return sorted_samples[std::min(index, sorted_samples.size() - 1)];
}

SampleStats Summarize(const std::vector<double>& samples) {
	return SampleStats{
		.median_us = Percentile(samples, 0.50),
		.p95_us = Percentile(samples, 0.95),
		.p99_us = Percentile(samples, 0.99),
	};
}

std::filesystem::path LocateBuildRoot() {
	auto current = std::filesystem::current_path();
	while (!current.empty()) {
		if (std::filesystem::exists(current / "Testing")) {
			return current;
		}
		if (std::filesystem::exists(current / "CTestTestfile.cmake")
		    && std::filesystem::exists(current / "AI")) {
			return current;
		}
		const auto parent = current.parent_path();
		if (parent == current) {
			break;
		}
		current = parent;
	}
	return std::filesystem::current_path();
}

std::string JsonEscape(const std::string& value) {
	std::ostringstream escaped;
	for (const char ch : value) {
		switch (ch) {
		case '\\': escaped << "\\\\"; break;
		case '"': escaped << "\\\""; break;
		case '\n': escaped << "\\n"; break;
		default: escaped << ch; break;
		}
	}
	return escaped.str();
}

std::string IsoTimestampNow() {
	const auto now = std::chrono::system_clock::now();
	const std::time_t seconds = std::chrono::system_clock::to_time_t(now);
	std::tm utc{};
#if defined(_WIN32)
	gmtime_s(&utc, &seconds);
#else
	gmtime_r(&seconds, &utc);
#endif
	std::ostringstream out;
	out << std::put_time(&utc, "%Y-%m-%dT%H:%M:%SZ");
	return out.str();
}

}  // namespace

TEST(CommandValidationPerf, EmitsValidatorOverheadRecordWithinBudget) {
	CommandValidator validator(/*ai=*/nullptr);
	circuit::grpc::CommandValidationSettings strict_settings;
	strict_settings.mode = ::highbar::v1::VALIDATION_MODE_STRICT;
	strict_settings.require_correlation = true;
	strict_settings.require_state_basis = true;
	CommandValidator strict_validator(/*ai=*/nullptr, strict_settings);
	const std::vector<std::pair<std::string, std::pair<const CommandValidator*, CommandBatch>>> scenarios = {
		{"ownership", {&validator, RepresentativeBatch()}},
		{"target_drift", {&validator, TargetDriftBatch()}},
		{"non_finite", {&validator, NonFiniteBatch()}},
		{"strict_missing_basis", {&strict_validator, StrictMissingBasisBatch()}},
	};

	std::vector<double> warmup_all;
	std::vector<double> measured_all;
	for (const auto& scenario : scenarios) {
		const auto warmup = MeasureSamples(*scenario.second.first,
		                                   scenario.second.second,
		                                   kWarmupSamples / scenarios.size());
		const auto measured = MeasureSamples(*scenario.second.first,
		                                     scenario.second.second,
		                                     kMeasuredSamples / scenarios.size());
		warmup_all.insert(warmup_all.end(), warmup.begin(), warmup.end());
		measured_all.insert(measured_all.end(), measured.begin(), measured.end());
	}
	const SampleStats baseline = Summarize(warmup_all);
	const SampleStats measured = Summarize(measured_all);

	const double regression_percent =
		(baseline.p99_us > 0.0)
			? ((measured.p99_us - baseline.p99_us) / baseline.p99_us) * 100.0
			: 0.0;
	const bool within_budget =
		measured.p99_us <= kAbsoluteBudgetUs
		&& regression_percent <= kMaxRegressionPercent;
	const std::string budget_assessment =
		within_budget
			? "within_budget"
			: measured.p99_us > kAbsoluteBudgetUs
				? "breach"
				: "review_required";

	const std::filesystem::path artifact_dir =
		LocateBuildRoot() / "reports" / "command-validation";
	std::filesystem::create_directories(artifact_dir);
	const std::filesystem::path artifact_path =
		artifact_dir / "validator-overhead.json";

	std::ostringstream payload;
	payload << "{\n"
	        << "  \"record_id\": \"command-validation-overhead\",\n"
	        << "  \"measurement_entrypoint\": \"ctest --test-dir build --output-on-failure -R command_validation_perf_test\",\n"
	        << "  \"batch_shape\": \"structured diagnostics matrix: ownership, target drift, non-finite coordinate, strict missing basis\",\n"
	        << "  \"sample_count\": " << kMeasuredSamples << ",\n"
	        << "  \"median_us\": " << std::fixed << std::setprecision(3) << measured.median_us << ",\n"
	        << "  \"p95_us\": " << measured.p95_us << ",\n"
	        << "  \"p99_us\": " << measured.p99_us << ",\n"
	        << "  \"absolute_budget_us\": " << kAbsoluteBudgetUs << ",\n"
	        << "  \"max_regression_percent\": " << kMaxRegressionPercent << ",\n"
	        << "  \"budget_assessment\": \"" << budget_assessment << "\",\n"
	        << "  \"baseline_reference\": \"same-run warmup p99 over the same representative validator batch\",\n"
	        << "  \"baseline_p99_us\": " << baseline.p99_us << ",\n"
	        << "  \"regression_percent\": " << regression_percent << ",\n"
	        << "  \"artifact_path\": \"" << JsonEscape(artifact_path.string()) << "\",\n"
	        << "  \"recorded_at\": \"" << IsoTimestampNow() << "\"\n"
	        << "}\n";

	std::ofstream out(artifact_path);
	ASSERT_TRUE(out.is_open()) << artifact_path;
	out << payload.str();
	out.close();

	EXPECT_TRUE(std::filesystem::exists(artifact_path)) << artifact_path;
	EXPECT_LE(measured.p99_us, kAbsoluteBudgetUs) << payload.str();
	EXPECT_LE(regression_percent, kMaxRegressionPercent) << payload.str();
	EXPECT_EQ(budget_assessment, "within_budget") << payload.str();
}

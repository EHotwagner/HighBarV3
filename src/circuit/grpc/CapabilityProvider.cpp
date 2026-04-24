// SPDX-License-Identifier: GPL-2.0-only
//
// HighBarV3 — command capability discovery helpers.

#include "grpc/CapabilityProvider.h"

#include "grpc/CommandQueue.h"
#include "grpc/SchemaVersion.h"

#include "AIFloat3.h"

#include <algorithm>
#include <array>
#include <string>

namespace circuit::grpc {

namespace {

constexpr std::uint32_t kQueuedCommandOptionMask = 0x7u;  // shift/ctrl/alt.

constexpr std::array<const char*, 15> kSupportedUnitArms = {
	"move_unit",
	"patrol",
	"fight",
	"attack_area",
	"stop",
	"wait",
	"build_unit",
	"repair",
	"reclaim_unit",
	"reclaim_area",
	"resurrect_in_area",
	"self_destruct",
	"set_wanted_max_speed",
	"set_fire_state",
	"set_move_state",
};

void AddFeatureFlags(google::protobuf::RepeatedPtrField<std::string>* flags) {
	flags->Add("protobuf_proxy_safety");
	flags->Add("structured_command_diagnostics");
	flags->Add("dry_run_validation");
	flags->Add("command_capabilities");
}

}  // namespace

CapabilityProvider::CapabilityProvider(::circuit::CCircuitAI* ai,
                                       const CommandQueue* queue)
	: CapabilityProvider(ai, queue, Settings{}) {}

CapabilityProvider::CapabilityProvider(::circuit::CCircuitAI* ai,
                                       const CommandQueue* queue,
                                       Settings settings)
	: ai_(ai), queue_(queue), settings_(settings) {}

bool CapabilityProvider::IsSupportedCommandArm(const std::string& arm) {
	return std::find(kSupportedUnitArms.begin(), kSupportedUnitArms.end(), arm)
	       != kSupportedUnitArms.end();
}

std::uint32_t CapabilityProvider::ValidOptionMaskFor(const std::string& arm) {
	return IsSupportedCommandArm(arm) ? kQueuedCommandOptionMask : 0u;
}

::highbar::v1::CommandSchemaResponse CapabilityProvider::CommandSchema() const {
	::highbar::v1::CommandSchemaResponse response;
	response.set_schema_version(::highbar::v1::kSchemaVersion);
	AddFeatureFlags(response.mutable_feature_flags());
	for (const char* arm : kSupportedUnitArms) {
		response.add_supported_command_arms(arm);
		auto* mask = response.add_option_masks();
		mask->set_command_arm(arm);
		mask->set_valid_option_mask(kQueuedCommandOptionMask);
	}
	response.set_validation_mode(settings_.validation_mode);
	response.set_max_batch_commands(settings_.max_batch_commands);
	if (queue_ != nullptr) {
		response.set_queue_depth(static_cast<std::uint32_t>(queue_->Depth()));
		response.set_queue_capacity(static_cast<std::uint32_t>(queue_->Capacity()));
	}
	auto* limits = response.mutable_map_limits();
	limits->set_min_x(0.0f);
	limits->set_min_z(0.0f);
	limits->set_max_x(springai::AIFloat3::maxxpos > 0.0f
	                  ? springai::AIFloat3::maxxpos : 1.0f);
	limits->set_max_z(springai::AIFloat3::maxzpos > 0.0f
	                  ? springai::AIFloat3::maxzpos : 1.0f);
	response.add_resource_ids("metal");
	response.add_resource_ids("energy");
	return response;
}

::highbar::v1::UnitCapabilitiesResponse CapabilityProvider::UnitCapabilities(
		const ::highbar::v1::UnitCapabilitiesRequest& request) const {
	(void)ai_;
	::highbar::v1::UnitCapabilitiesResponse response;
	response.set_unit_id(request.unit_id());
	*response.mutable_generation() = request.generation();
	AddFeatureFlags(response.mutable_feature_flags());
	for (const char* arm : kSupportedUnitArms) {
		response.add_legal_command_arms(arm);
	}
	if (queue_ != nullptr) {
		response.set_queue_depth(static_cast<std::uint32_t>(queue_->Depth()));
	}
	return response;
}

}  // namespace circuit::grpc

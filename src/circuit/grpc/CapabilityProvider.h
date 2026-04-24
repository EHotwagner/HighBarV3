// SPDX-License-Identifier: GPL-2.0-only
//
// HighBarV3 — command capability discovery helpers.

#pragma once

#include "highbar/service.pb.h"

#include <cstdint>

namespace circuit {
class CCircuitAI;
}  // namespace circuit

namespace circuit::grpc {

class CommandQueue;

class CapabilityProvider {
public:
	struct Settings {
		::highbar::v1::ValidationMode validation_mode =
			::highbar::v1::VALIDATION_MODE_COMPATIBILITY;
		std::uint32_t max_batch_commands = 64;
	};

	CapabilityProvider(::circuit::CCircuitAI* ai,
	                   const CommandQueue* queue);
	CapabilityProvider(::circuit::CCircuitAI* ai,
	                   const CommandQueue* queue,
	                   Settings settings);

	::highbar::v1::CommandSchemaResponse CommandSchema() const;
	::highbar::v1::UnitCapabilitiesResponse UnitCapabilities(
		const ::highbar::v1::UnitCapabilitiesRequest& request) const;

	static bool IsSupportedCommandArm(const std::string& arm);
	static std::uint32_t ValidOptionMaskFor(const std::string& arm);

private:
	::circuit::CCircuitAI* ai_;
	const CommandQueue* queue_;
	Settings settings_;
};

}  // namespace circuit::grpc

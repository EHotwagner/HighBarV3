// SPDX-License-Identifier: GPL-2.0-only
//
// HighBarV3 — sibling async HighBarAdmin service.

#pragma once

#include "grpc/AdminController.h"
#include "highbar/service.grpc.pb.h"

#include <cstdint>
#include <chrono>
#include <functional>

namespace circuit::grpc {

class AdminService final : public ::highbar::v1::HighBarAdmin::AsyncService {
public:
	using FrameFn = std::function<std::uint32_t()>;
	using StateSeqFn = std::function<std::uint64_t()>;
	using ExecuteFn = std::function<::highbar::v1::AdminActionResult(
		const AdminCaller&,
		const ::highbar::v1::AdminAction&,
		std::chrono::milliseconds)>;

	explicit AdminService(AdminController* controller);

	void SetClock(FrameFn frame_fn, StateSeqFn state_seq_fn);
	void SetExecutionFn(ExecuteFn execute_fn);
	void Start(::grpc::ServerCompletionQueue* cq);
	void ExpireLeases();

private:
	class CallDataBase;
	class GetCapabilitiesCallData;
	class ValidateActionCallData;
	class ExecuteActionCallData;

	AdminCaller CallerFrom(const ::grpc::ServerContext& ctx) const;
	std::uint32_t CurrentFrame() const;
	std::uint64_t CurrentStateSeq() const;

	AdminController* controller_;
	FrameFn frame_fn_;
	StateSeqFn state_seq_fn_;
	ExecuteFn execute_fn_;
};

}  // namespace circuit::grpc

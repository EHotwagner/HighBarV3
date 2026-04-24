// SPDX-License-Identifier: GPL-2.0-only
//
// HighBarV3 — sibling async HighBarAdmin service.

#include "grpc/AdminService.h"

#include "grpc/AuthToken.h"

#include <grpcpp/grpcpp.h>

#include <utility>

namespace circuit::grpc {

namespace {

constexpr const char* kRoleHeader = "x-highbar-admin-role";
constexpr const char* kClientHeader = "x-highbar-client-id";

std::string MetadataValue(const ::grpc::ServerContext& ctx,
                          const char* key) {
	const auto& md = ctx.client_metadata();
	const auto range = md.equal_range(key);
	if (range.first == range.second) return "";
	return std::string(range.first->second.data(), range.first->second.size());
}

}  // namespace

class AdminService::CallDataBase {
public:
	virtual ~CallDataBase() = default;
	virtual void Proceed(bool ok) = 0;
};

class AdminService::GetCapabilitiesCallData final : public CallDataBase {
public:
	GetCapabilitiesCallData(AdminService* svc, ::grpc::ServerCompletionQueue* cq)
		: svc_(svc), cq_(cq), responder_(&ctx_) {
		svc_->RequestGetAdminCapabilities(&ctx_, &request_, &responder_,
		                                  cq_, cq_, this);
	}

	void Proceed(bool ok) override {
		if (stage_ == Stage::kFinishing) { delete this; return; }
		if (!ok) { delete this; return; }
		new GetCapabilitiesCallData(svc_, cq_);
		if (svc_->controller_ != nullptr) {
			response_ = svc_->controller_->Capabilities();
		}
		stage_ = Stage::kFinishing;
		responder_.Finish(response_, ::grpc::Status::OK, this);
	}

private:
	enum class Stage { kCreated, kFinishing };
	AdminService* svc_;
	::grpc::ServerCompletionQueue* cq_;
	::grpc::ServerContext ctx_;
	::highbar::v1::AdminCapabilitiesRequest request_;
	::highbar::v1::AdminCapabilitiesResponse response_;
	::grpc::ServerAsyncResponseWriter<::highbar::v1::AdminCapabilitiesResponse> responder_;
	Stage stage_ = Stage::kCreated;
};

class AdminService::ValidateActionCallData final : public CallDataBase {
public:
	ValidateActionCallData(AdminService* svc, ::grpc::ServerCompletionQueue* cq)
		: svc_(svc), cq_(cq), responder_(&ctx_) {
		svc_->RequestValidateAdminAction(&ctx_, &request_, &responder_,
		                                 cq_, cq_, this);
	}

	void Proceed(bool ok) override {
		if (stage_ == Stage::kFinishing) { delete this; return; }
		if (!ok) { delete this; return; }
		new ValidateActionCallData(svc_, cq_);
		if (svc_->controller_ == nullptr) {
			stage_ = Stage::kFinishing;
			responder_.Finish(response_,
				::grpc::Status(::grpc::StatusCode::UNAVAILABLE,
				               "admin controller not wired"),
				this);
			return;
		}
		response_ = svc_->controller_->Validate(
			svc_->CallerFrom(ctx_), request_,
			svc_->CurrentFrame(), svc_->CurrentStateSeq());
		stage_ = Stage::kFinishing;
		responder_.Finish(response_, ::grpc::Status::OK, this);
	}

private:
	enum class Stage { kCreated, kFinishing };
	AdminService* svc_;
	::grpc::ServerCompletionQueue* cq_;
	::grpc::ServerContext ctx_;
	::highbar::v1::AdminAction request_;
	::highbar::v1::AdminActionResult response_;
	::grpc::ServerAsyncResponseWriter<::highbar::v1::AdminActionResult> responder_;
	Stage stage_ = Stage::kCreated;
};

class AdminService::ExecuteActionCallData final : public CallDataBase {
public:
	ExecuteActionCallData(AdminService* svc, ::grpc::ServerCompletionQueue* cq)
		: svc_(svc), cq_(cq), responder_(&ctx_) {
		svc_->RequestExecuteAdminAction(&ctx_, &request_, &responder_,
		                                cq_, cq_, this);
	}

	void Proceed(bool ok) override {
		if (stage_ == Stage::kFinishing) { delete this; return; }
		if (!ok) { delete this; return; }
		new ExecuteActionCallData(svc_, cq_);
		if (svc_->controller_ == nullptr) {
			stage_ = Stage::kFinishing;
			responder_.Finish(response_,
				::grpc::Status(::grpc::StatusCode::UNAVAILABLE,
				               "admin controller not wired"),
				this);
			return;
		}
		const auto caller = svc_->CallerFrom(ctx_);
		response_ = svc_->controller_->Validate(
			caller, request_, svc_->CurrentFrame(), svc_->CurrentStateSeq());
		response_.set_dry_run(false);
		if (response_.status() == ::highbar::v1::ADMIN_ACTION_ACCEPTED) {
			if (svc_->execute_fn_) {
				response_ = svc_->execute_fn_(
					caller, request_, std::chrono::milliseconds(1500));
			} else {
				response_ = svc_->controller_->Execute(
					caller, request_,
					svc_->CurrentFrame(), svc_->CurrentStateSeq());
			}
		} else {
			response_ = svc_->controller_->Execute(
				caller, request_,
				svc_->CurrentFrame(), svc_->CurrentStateSeq());
		}
		stage_ = Stage::kFinishing;
		responder_.Finish(response_, ::grpc::Status::OK, this);
	}

private:
	enum class Stage { kCreated, kFinishing };
	AdminService* svc_;
	::grpc::ServerCompletionQueue* cq_;
	::grpc::ServerContext ctx_;
	::highbar::v1::AdminAction request_;
	::highbar::v1::AdminActionResult response_;
	::grpc::ServerAsyncResponseWriter<::highbar::v1::AdminActionResult> responder_;
	Stage stage_ = Stage::kCreated;
};

AdminService::AdminService(AdminController* controller)
	: controller_(controller) {}

void AdminService::SetClock(FrameFn frame_fn, StateSeqFn state_seq_fn) {
	frame_fn_ = std::move(frame_fn);
	state_seq_fn_ = std::move(state_seq_fn);
}

void AdminService::SetExecutionFn(ExecuteFn execute_fn) {
	execute_fn_ = std::move(execute_fn);
}

void AdminService::Start(::grpc::ServerCompletionQueue* cq) {
	new GetCapabilitiesCallData(this, cq);
	new ValidateActionCallData(this, cq);
	new ExecuteActionCallData(this, cq);
}

void AdminService::ExpireLeases() {
	if (controller_ != nullptr) {
		controller_->ExpireLeases(CurrentFrame());
	}
}

AdminCaller AdminService::CallerFrom(const ::grpc::ServerContext& ctx) const {
	AdminCaller caller;
	caller.identity = MetadataValue(ctx, kClientHeader);
	if (caller.identity.empty()) caller.identity = ctx.peer();
	caller.role = AuthToken::ParseAdminRole(MetadataValue(ctx, kRoleHeader));
	return caller;
}

std::uint32_t AdminService::CurrentFrame() const {
	return frame_fn_ ? frame_fn_() : 0u;
}

std::uint64_t AdminService::CurrentStateSeq() const {
	return state_seq_fn_ ? state_seq_fn_() : 0u;
}

}  // namespace circuit::grpc

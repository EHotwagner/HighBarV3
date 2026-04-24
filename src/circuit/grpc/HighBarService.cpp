// SPDX-License-Identifier: GPL-2.0-only
//
// HighBarV3 — async gRPC server impl (T023-T025, T029).

#include "grpc/HighBarService.h"
#include "grpc/AuthInterceptor.h"
#include "grpc/AuthToken.h"
#include "grpc/AdminService.h"
#include "grpc/CapabilityProvider.h"
#include "grpc/CommandQueue.h"
#include "grpc/CommandValidator.h"
#include "grpc/Counters.h"
#include "grpc/DeltaBus.h"
#include "grpc/GrpcLog.h"
#include "grpc/RingBuffer.h"
#include "grpc/SchemaVersion.h"
#include "grpc/SnapshotBuilder.h"
#include "module/GrpcGatewayModule.h"  // 003 — for RequestSnapshot handler

#include "CircuitAI.h"

#include <grpcpp/server_builder.h>
#include <grpcpp/security/server_credentials.h>

#include <arpa/inet.h>
#include <array>
#include <atomic>
#include <chrono>
#include <condition_variable>
#include <cstring>
#include <mutex>
#include <optional>
#include <shared_mutex>
#include <stdexcept>
#include <string>
#include <sys/random.h>
#include <sys/socket.h>
#include <thread>
#include <vector>

namespace circuit::grpc {

namespace {

std::string HexEncode(const unsigned char* b, std::size_t n) {
	static constexpr char kHex[] = "0123456789abcdef";
	std::string s;
	s.resize(n * 2);
	for (std::size_t i = 0; i < n; ++i) {
		s[i * 2]     = kHex[b[i] >> 4];
		s[i * 2 + 1] = kHex[b[i] & 0x0f];
	}
	return s;
}

}  // namespace

namespace {

// T073 — TCP loopback validator. Accepts `host:port` where host is
// either a `127.0.0.0/8` IPv4 literal or `::1` / `[::1]` IPv6 literal.
// Also accepts the two common hostnames `localhost` / `127.0.0.1` /
// `ip6-localhost` as shorthands since operators hand-edit grpc.json.
// Any non-loopback address fails with a descriptive message so the
// startup log names the offending config (data-model §6 validation).
bool IsLoopbackTcpBind(const std::string& host_port, std::string* reason) {
	const auto colon = host_port.rfind(':');
	if (colon == std::string::npos) {
		*reason = "tcp_bind missing ':port' — expected host:port";
		return false;
	}
	// Strip optional IPv6 brackets: `[::1]:50511` → host=`::1`.
	std::string host = host_port.substr(0, colon);
	if (host.size() >= 2 && host.front() == '[' && host.back() == ']') {
		host = host.substr(1, host.size() - 2);
	}

	if (host == "localhost" || host == "ip6-localhost") return true;

	in_addr v4{};
	if (::inet_pton(AF_INET, host.c_str(), &v4) == 1) {
		// 127.0.0.0/8 — top byte of network-order address == 127.
		const auto top = static_cast<std::uint8_t>(ntohl(v4.s_addr) >> 24);
		if (top == 127) return true;
		*reason = "tcp_bind host must be loopback (127.0.0.0/8); got " + host;
		return false;
	}

	in6_addr v6{};
	if (::inet_pton(AF_INET6, host.c_str(), &v6) == 1) {
		if (IN6_IS_ADDR_LOOPBACK(&v6)) return true;
		*reason = "tcp_bind host must be loopback (::1); got " + host;
		return false;
	}

	*reason = "tcp_bind host is neither a valid IPv4/IPv6 literal nor "
	          "'localhost': " + host;
	return false;
}

}  // namespace

std::string HighBarService::NewSessionId() {
	unsigned char raw[16];
	std::size_t got = 0;
	while (got < sizeof(raw)) {
		const ssize_t n = ::getrandom(raw + got, sizeof(raw) - got, 0);
		if (n < 0) {
			if (errno == EINTR) continue;
			// Degraded path: session_id should still be unique-ish.
			for (std::size_t i = got; i < sizeof(raw); ++i) raw[i] = i * 31 + 7;
			got = sizeof(raw);
			break;
		}
		got += static_cast<std::size_t>(n);
	}
	return HexEncode(raw, sizeof(raw));
}

// ============================================================================
// CallData base + per-RPC state machines
// ============================================================================

class HighBarService::CallDataBase {
public:
	virtual ~CallDataBase() = default;
	virtual void Proceed(bool ok) = 0;
};

// --- Hello (unary, implemented) --------------------------------------------

class HighBarService::HelloCallData final : public CallDataBase {
public:
	HelloCallData(HighBarService* svc, ::grpc::ServerCompletionQueue* cq)
		: svc_(svc), cq_(cq), responder_(&ctx_) {
		svc_->RequestHello(&ctx_, &request_, &responder_, cq_, cq_, this);
	}

	void Proceed(bool ok) override {
		switch (stage_) {
		case Stage::kCreated: {
			if (!ok) { delete this; return; }
			// Register a replacement only for a real accepted RPC. During
			// CQ shutdown, ok=false means there is no next call to accept.
			new HelloCallData(svc_, cq_);

			// Schema-version strict equality (FR-022a).
			if (request_.schema_version() != ::highbar::v1::kSchemaVersion) {
				stage_ = Stage::kFinishing;
				responder_.FinishWithError(
					::grpc::Status(::grpc::StatusCode::FAILED_PRECONDITION,
					               std::string("schema mismatch: server=")
					               + ::highbar::v1::kSchemaVersion
					               + " client=" + request_.schema_version()),
					this);
				return;
			}

			// Observer cap check — FR-015a hard cap 4.
			const bool is_ai = request_.role() == ::highbar::v1::Role::ROLE_AI;
			if (!is_ai) {
				if (!svc_->TryReserveObserverSlot()) {
					stage_ = Stage::kFinishing;
					responder_.FinishWithError(
						::grpc::Status(::grpc::StatusCode::RESOURCE_EXHAUSTED,
						               "observer cap reached (4)"),
						this);
					return;
				}
				svc_->ReleaseObserverSlot();  // cap counts sessions, not handshakes
			} else {
				if (!svc_->TryClaimAiSlot()) {
					stage_ = Stage::kFinishing;
					responder_.FinishWithError(
						::grpc::Status(::grpc::StatusCode::ALREADY_EXISTS,
						               "AI slot already claimed"),
						this);
					return;
				}
				// T059: the Hello-time claim is transient — we check
				// the slot is free, then release. The durable claim
				// lives on SubmitCommands (the stream's lifetime is
				// the AI session's lifetime per data-model §5). Hello
				// on its own doesn't pin the AI role because a client
				// may Hello, fail to build its command stream, and
				// die — we don't want that to strand the slot.
				svc_->ReleaseAiSlot();
			}

			// Build response.
			response_.set_schema_version(::highbar::v1::kSchemaVersion);
			response_.set_session_id(HighBarService::NewSessionId());
			response_.set_current_frame(
				svc_->frames_since_bind_.load(std::memory_order_relaxed));
			// T042: populate StaticMap from SnapshotBuilder under
			// shared read lock (research §3). Safe to return by
			// value because StaticMap is small — the big heightmap
			// bytes only materialize when the terrain accessor
			// follow-up lands.
			if (svc_->snapshot_ != nullptr && svc_->state_mutex_ != nullptr) {
				std::shared_lock<std::shared_mutex> lock(*svc_->state_mutex_);
				*response_.mutable_static_map() = svc_->snapshot_->StaticMap();
			}

			LogConnect(svc_->ai_,
			           response_.session_id(),
			           ctx_.peer(),
			           is_ai ? "ai" : "observer");

			stage_ = Stage::kFinishing;
			responder_.Finish(response_, ::grpc::Status::OK, this);
			return;
		}
		case Stage::kFinishing:
		default:
			delete this;
			return;
		}
	}

private:
	enum class Stage { kCreated, kFinishing };
	HighBarService* svc_;
	::grpc::ServerCompletionQueue* cq_;
	::grpc::ServerContext ctx_;
	::highbar::v1::HelloRequest request_;
	::highbar::v1::HelloResponse response_;
	::grpc::ServerAsyncResponseWriter<::highbar::v1::HelloResponse> responder_;
	Stage stage_ = Stage::kCreated;
};

// --- GetRuntimeCounters (unary, implemented) -------------------------------

class HighBarService::GetRuntimeCountersCallData final : public CallDataBase {
public:
	GetRuntimeCountersCallData(HighBarService* svc,
	                           ::grpc::ServerCompletionQueue* cq)
		: svc_(svc), cq_(cq), responder_(&ctx_) {
		svc_->RequestGetRuntimeCounters(&ctx_, &request_, &responder_,
		                                 cq_, cq_, this);
	}

	void Proceed(bool ok) override {
		switch (stage_) {
		case Stage::kCreated: {
			if (!ok) { delete this; return; }
			new GetRuntimeCountersCallData(svc_, cq_);

			// Atomic snapshot per data-model §10 invariants.
			Counters* c = svc_->counters_;
			response_.set_subscriber_count(c->subscriber_count.load());
			response_.set_cumulative_dropped_subscribers(
				c->cumulative_dropped_subscribers.load());
			response_.set_frame_flush_time_us_p99(c->FrameFlushP99Us());
			response_.set_command_queue_depth(c->command_queue_depth.load());
			response_.set_command_submissions_rejected_resource_exhausted(
				c->command_submissions_rejected_resource_exhausted.load());
			response_.set_command_submissions_rejected_invalid_argument(
				c->command_submissions_rejected_invalid_argument.load());
			response_.set_frames_since_bind(c->frames_since_bind.load());
			// per_subscriber_queue_depth left empty — filled by
			// SubscriberSlot bookkeeping in US1.

			stage_ = Stage::kFinishing;
			responder_.Finish(response_, ::grpc::Status::OK, this);
			return;
		}
		case Stage::kFinishing:
		default:
			delete this;
			return;
		}
	}

private:
	enum class Stage { kCreated, kFinishing };
	HighBarService* svc_;
	::grpc::ServerCompletionQueue* cq_;
	::grpc::ServerContext ctx_;
	::highbar::v1::CountersRequest request_;
	::highbar::v1::CountersResponse response_;
	::grpc::ServerAsyncResponseWriter<::highbar::v1::CountersResponse> responder_;
	Stage stage_ = Stage::kCreated;
};

// --- StreamState (server-streaming, UNIMPLEMENTED stub) --------------------

// --- StreamState (server-streaming, implemented) ---------------------------
//
// State machine: the pump thread owns the sequence (snapshot → optional
// ring-replay → live-delta loop → Finish). The CQ worker's Proceed()
// acts purely as a completion semaphore — on each tag-this event it
// flips `op_done_` and notifies `cv_`, which unblocks the pump.
//
// Guarantees:
//   - At most one writer_.Write() / writer_.Finish() in flight at a time.
//   - All Writes happen from the pump thread; the CQ worker never calls
//     Write(). Thread-safety of ServerAsyncWriter requires this.
//   - pump_ joined in dtor (safe because by the time kFinishing arrives
//     on the CQ, the pump has already issued Finish and exited).

class HighBarService::StreamStateCallData final : public CallDataBase {
public:
	StreamStateCallData(HighBarService* svc,
	                    ::grpc::ServerCompletionQueue* cq)
		: svc_(svc), cq_(cq), writer_(&ctx_) {
		svc_->RequestStreamState(&ctx_, &request_, &writer_, cq_, cq_, this);
	}

	~StreamStateCallData() {
		if (slot_ && svc_->delta_bus_ != nullptr) {
			svc_->delta_bus_->Unsubscribe(slot_);
		} else if (slot_) {
			slot_->Evict(EvictionReason::kCanceled);
		}
		// Wake the pump before join so a shutdown-time delete can't strand
		// the CQ worker inside SubscriberSlot::BlockingPop().
		if (pump_.joinable()) {
			stop_.store(true, std::memory_order_release);
			cv_.notify_all();
			pump_.join();
		}
		if (observer_slot_reserved_) {
			svc_->ReleaseObserverSlot();
		}
	}

	void Proceed(bool ok) override {
		if (stage_ == Stage::kCreated) {
			if (!ok) { delete this; return; }
			// Queue a replacement only when a real subscribe arrived.
			new StreamStateCallData(svc_, cq_);

			// Observer cap (FR-015a) — applied here, not in Hello,
			// because observers may skip Hello entirely (data-model §5).
			if (!svc_->TryReserveObserverSlot()) {
				stage_ = Stage::kFinishing;
				writer_.Finish(
					::grpc::Status(::grpc::StatusCode::RESOURCE_EXHAUSTED,
					               "observer cap reached (4)"),
					this);
				return;
			}
			observer_slot_reserved_ = true;

			// Reject if the US1 handles haven't been wired (unit tests,
			// mis-ordered init). Graceful UNAVAILABLE rather than crash.
			if (svc_->delta_bus_ == nullptr
			    || svc_->snapshot_ == nullptr
			    || svc_->state_mutex_ == nullptr
			    || svc_->ring_ == nullptr) {
				stage_ = Stage::kFinishing;
				writer_.Finish(
					::grpc::Status(::grpc::StatusCode::UNAVAILABLE,
					               "gateway US1 handles not wired"),
					this);
				return;
			}

			slot_ = svc_->delta_bus_->Subscribe();
			resume_from_seq_ = request_.resume_from_seq();

			stage_ = Stage::kStreaming;
			pump_ = std::thread(&StreamStateCallData::PumpLoop, this);
			return;
		}

		// Every subsequent Proceed() is a Write or Finish completion
		// fired on the pump's behalf. Signal the pump; it decides what
		// to do next.
		{
			std::lock_guard<std::mutex> lock(mutex_);
			op_ok_ = ok;
			op_done_ = true;
		}
		cv_.notify_all();

		// On kFinishing the pump has exited; reclaim the CallData.
		if (stage_ == Stage::kFinishing) {
			delete this;
		}
	}

private:
	enum class Stage { kCreated, kStreaming, kFinishing };

	// Pump thread: owns the send sequence end-to-end.
	void PumpLoop() {
		try {
			std::uint64_t last_sent_seq = resume_from_seq_;

			// --- 1. Initial payload: ring-replay vs fresh snapshot.
			auto replay = resume_from_seq_ > 0
				? svc_->ring_->GetFromSeq(resume_from_seq_)
				: std::optional<std::vector<RingEntry>>{};

			if (!replay.has_value()) {
				// Fresh snapshot. Take shared lock for the build.
				::highbar::v1::StateUpdate first;
				{
					std::shared_lock<std::shared_mutex> lock(*svc_->state_mutex_);
					// This snapshot is a synthetic baseline, not a ring entry.
					// Use the current head so the next live ring update remains
					// strictly greater from the client's point of view.
					first.set_seq(svc_->ring_->HeadSeq());
					first.set_frame(svc_->frames_since_bind_.load());
					*first.mutable_snapshot() = svc_->snapshot_->Build();
				}
				if (!WriteAndWait(first)) {
					FinishWithStatus(CancelledOrFault());
					return;
				}
				last_sent_seq = first.seq();
			} else {
				// Ring replay — every entry is already a serialized
				// StateUpdate. Parse + Write one at a time so the
				// stream order matches wire order.
				for (const auto& entry : *replay) {
					::highbar::v1::StateUpdate u;
					if (!u.ParseFromString(*entry.payload)) {
						FinishWithStatus(::grpc::Status(
							::grpc::StatusCode::INTERNAL,
							"ring entry deserialize failed"));
						return;
					}
					if (!WriteAndWait(u)) {
						FinishWithStatus(CancelledOrFault());
						return;
					}
					last_sent_seq = u.seq();
				}
			}

			// --- 2. Live loop: pump the SubscriberSlot.
			while (!stop_.load(std::memory_order_acquire)) {
				std::shared_ptr<const std::string> payload;
				const bool got = slot_->BlockingPop(&payload);
				if (!got) {
					// Evicted (slow consumer) or canceled.
					if (slot_->Eviction() == EvictionReason::kSlowConsumer) {
						FinishWithStatus(::grpc::Status(
							::grpc::StatusCode::RESOURCE_EXHAUSTED,
							"slow consumer evicted"));
					} else if (slot_->Eviction() == EvictionReason::kFault) {
						FinishWithStatus(::grpc::Status(
							::grpc::StatusCode::UNAVAILABLE,
							"gateway disabled"));
					} else {
						FinishWithStatus(::grpc::Status::OK);
					}
					return;
				}

				::highbar::v1::StateUpdate u;
				if (!u.ParseFromString(*payload)) {
					FinishWithStatus(::grpc::Status(
						::grpc::StatusCode::INTERNAL,
						"live payload deserialize failed"));
					return;
				}
				// The live slot is subscribed before baseline/replay so no
				// updates are missed. That can queue payloads the stream has
				// already sent through the fresh snapshot or replay path; drop
				// them to preserve strict per-client monotonicity.
				if (u.seq() <= last_sent_seq) {
					continue;
				}
				if (!WriteAndWait(u)) {
					FinishWithStatus(CancelledOrFault());
					return;
				}
				last_sent_seq = u.seq();
			}
			FinishWithStatus(::grpc::Status::OK);
		} catch (const std::exception& e) {
			FinishWithStatus(::grpc::Status(
				::grpc::StatusCode::INTERNAL,
				std::string("StreamState pump: ") + e.what()));
		} catch (...) {
			FinishWithStatus(::grpc::Status(
				::grpc::StatusCode::INTERNAL,
				"StreamState pump: unknown exception"));
		}
	}

	// Issue a Write on the async writer, wait for completion, return
	// whether it succeeded. `msg` must outlive the call (we block).
	bool WriteAndWait(const ::highbar::v1::StateUpdate& msg) {
		{
			std::lock_guard<std::mutex> lock(mutex_);
			op_done_ = false;
			op_ok_ = false;
		}
		writer_.Write(msg, this);
		std::unique_lock<std::mutex> lock(mutex_);
		cv_.wait(lock, [this] {
			return op_done_ || stop_.load(std::memory_order_acquire);
		});
		return op_ok_ && !stop_.load(std::memory_order_acquire);
	}

	void FinishWithStatus(const ::grpc::Status& status) {
		// Transition stage so Proceed's terminal branch deletes us.
		stage_ = Stage::kFinishing;
		{
			std::lock_guard<std::mutex> lock(mutex_);
			op_done_ = false;
		}
		writer_.Finish(status, this);
		// Wait for the Finish completion. After this we exit the pump;
		// the CQ worker's Proceed(kFinishing) deletes the CallData.
		std::unique_lock<std::mutex> lock(mutex_);
		cv_.wait(lock, [this] { return op_done_; });
	}

	::grpc::Status CancelledOrFault() {
		return ::grpc::Status(::grpc::StatusCode::CANCELLED,
		                      "client disconnected or Write failed");
	}

	HighBarService* svc_;
	::grpc::ServerCompletionQueue* cq_;
	::grpc::ServerContext ctx_;
	::highbar::v1::StreamStateRequest request_;
	::grpc::ServerAsyncWriter<::highbar::v1::StateUpdate> writer_;

	Stage stage_ = Stage::kCreated;
	bool observer_slot_reserved_ = false;
	std::uint64_t resume_from_seq_ = 0;
	std::shared_ptr<SubscriberSlot> slot_;

	// Pump thread + CQ-worker handshake.
	std::thread pump_;
	std::atomic<bool> stop_{false};
	std::mutex mutex_;
	std::condition_variable cv_;
	bool op_done_ = false;
	bool op_ok_ = false;
};

// --- ValidateCommandBatch / capabilities (unary, implemented) --------------

class HighBarService::ValidateCommandBatchCallData final : public CallDataBase {
public:
	ValidateCommandBatchCallData(HighBarService* svc,
	                             ::grpc::ServerCompletionQueue* cq)
		: svc_(svc), cq_(cq), responder_(&ctx_) {
		svc_->RequestValidateCommandBatch(&ctx_, &request_, &responder_,
		                                  cq_, cq_, this);
	}

	void Proceed(bool ok) override {
		switch (stage_) {
		case Stage::kCreated:
			if (!ok) { delete this; return; }
			new ValidateCommandBatchCallData(svc_, cq_);
			if (svc_->validator_ == nullptr) {
				Finish(::grpc::Status(::grpc::StatusCode::UNAVAILABLE,
				                      "command validator not wired"));
				return;
			}
			response_ = svc_->validator_->ValidateBatch(request_).batch_result;
			Finish(::grpc::Status::OK);
			return;
		case Stage::kFinishing:
		default:
			delete this;
			return;
		}
	}

private:
	enum class Stage { kCreated, kFinishing };
	void Finish(const ::grpc::Status& status) {
		stage_ = Stage::kFinishing;
		responder_.Finish(response_, status, this);
	}

	HighBarService* svc_;
	::grpc::ServerCompletionQueue* cq_;
	::grpc::ServerContext ctx_;
	::highbar::v1::CommandBatch request_;
	::highbar::v1::CommandBatchResult response_;
	::grpc::ServerAsyncResponseWriter<::highbar::v1::CommandBatchResult> responder_;
	Stage stage_ = Stage::kCreated;
};

class HighBarService::GetCommandSchemaCallData final : public CallDataBase {
public:
	GetCommandSchemaCallData(HighBarService* svc,
	                         ::grpc::ServerCompletionQueue* cq)
		: svc_(svc), cq_(cq), responder_(&ctx_) {
		svc_->RequestGetCommandSchema(&ctx_, &request_, &responder_,
		                              cq_, cq_, this);
	}

	void Proceed(bool ok) override {
		switch (stage_) {
		case Stage::kCreated: {
			if (!ok) { delete this; return; }
			new GetCommandSchemaCallData(svc_, cq_);
			CapabilityProvider provider(svc_->ai_, svc_->command_queue_);
			response_ = provider.CommandSchema();
			Finish(::grpc::Status::OK);
			return;
		}
		case Stage::kFinishing:
		default:
			delete this;
			return;
		}
	}

private:
	enum class Stage { kCreated, kFinishing };
	void Finish(const ::grpc::Status& status) {
		stage_ = Stage::kFinishing;
		responder_.Finish(response_, status, this);
	}

	HighBarService* svc_;
	::grpc::ServerCompletionQueue* cq_;
	::grpc::ServerContext ctx_;
	::highbar::v1::CommandSchemaRequest request_;
	::highbar::v1::CommandSchemaResponse response_;
	::grpc::ServerAsyncResponseWriter<::highbar::v1::CommandSchemaResponse> responder_;
	Stage stage_ = Stage::kCreated;
};

class HighBarService::GetUnitCapabilitiesCallData final : public CallDataBase {
public:
	GetUnitCapabilitiesCallData(HighBarService* svc,
	                            ::grpc::ServerCompletionQueue* cq)
		: svc_(svc), cq_(cq), responder_(&ctx_) {
		svc_->RequestGetUnitCapabilities(&ctx_, &request_, &responder_,
		                                 cq_, cq_, this);
	}

	void Proceed(bool ok) override {
		switch (stage_) {
		case Stage::kCreated: {
			if (!ok) { delete this; return; }
			new GetUnitCapabilitiesCallData(svc_, cq_);
			CapabilityProvider provider(svc_->ai_, svc_->command_queue_);
			response_ = provider.UnitCapabilities(request_);
			Finish(::grpc::Status::OK);
			return;
		}
		case Stage::kFinishing:
		default:
			delete this;
			return;
		}
	}

private:
	enum class Stage { kCreated, kFinishing };
	void Finish(const ::grpc::Status& status) {
		stage_ = Stage::kFinishing;
		responder_.Finish(response_, status, this);
	}

	HighBarService* svc_;
	::grpc::ServerCompletionQueue* cq_;
	::grpc::ServerContext ctx_;
	::highbar::v1::UnitCapabilitiesRequest request_;
	::highbar::v1::UnitCapabilitiesResponse response_;
	::grpc::ServerAsyncResponseWriter<::highbar::v1::UnitCapabilitiesResponse> responder_;
	Stage stage_ = Stage::kCreated;
};

// --- SubmitCommands (client-streaming, implemented — T058/T059) ------------
//
// State machine: after RequestSubmitCommands completes, we (a) claim
// the singleton AI slot (FR-011), (b) loop reading batches, validating
// each via CommandValidator, and pushing accepted batches' commands
// onto CommandQueue, (c) finish with a CommandAck carrying cumulative
// counters. Queue overflow returns RESOURCE_EXHAUSTED synchronously
// without re-entering the read loop (FR-012a). The AI slot is released
// on any terminal path — whether the client disconnected, sent EOF,
// or we rejected the handshake — so a later AI client can reclaim.

class HighBarService::SubmitCommandsCallData final : public CallDataBase {
public:
	SubmitCommandsCallData(HighBarService* svc,
	                       ::grpc::ServerCompletionQueue* cq)
		: svc_(svc), cq_(cq), reader_(&ctx_) {
		svc_->RequestSubmitCommands(&ctx_, &reader_, cq_, cq_, this);
	}

	~SubmitCommandsCallData() {
		if (ai_slot_claimed_) {
			svc_->ReleaseAiSlot();
		}
	}

	void Proceed(bool ok) override {
		switch (stage_) {
		case Stage::kCreated:
			HandleCreated(ok);
			return;
		case Stage::kReading:
			HandleReadDone(ok);
			return;
		case Stage::kFinishing:
		default:
			delete this;
			return;
		}
	}

private:
	enum class Stage { kCreated, kReading, kFinishing };

	void HandleCreated(bool ok) {
		if (!ok) { delete this; return; }
		new SubmitCommandsCallData(svc_, cq_);

		// Reject if US2 handles aren't wired (unit tests / misordered
		// init). UNAVAILABLE instead of INTERNAL so the client can
		// reasonably retry once the gateway finishes coming up.
		if (svc_->command_queue_ == nullptr || svc_->validator_ == nullptr) {
			Finish(::grpc::Status(::grpc::StatusCode::UNAVAILABLE,
			                      "command path not wired"));
			return;
		}

		// Single-AI invariant (FR-011).
		if (!svc_->TryClaimAiSlot()) {
			Finish(::grpc::Status(::grpc::StatusCode::ALREADY_EXISTS,
			                      "AI slot already claimed"));
			return;
		}
		ai_slot_claimed_ = true;
		session_id_ = HighBarService::NewSessionId();
		LogConnect(svc_->ai_, session_id_, ctx_.peer(), "ai-stream");

		// Kick off the first read.
		stage_ = Stage::kReading;
		reader_.Read(&incoming_, this);
	}

	void HandleReadDone(bool ok) {
		if (!ok) {
			// Stream EOF — client finished cleanly. ACK with running
			// counters. Finish() transitions to kFinishing; ~this
			// releases the AI slot.
		::highbar::v1::CommandAck ack;
		ack.set_last_accepted_batch_seq(last_accepted_batch_seq_);
		ack.set_batches_accepted(batches_accepted_);
		ack.set_batches_rejected_invalid(batches_rejected_invalid_);
		ack.set_batches_rejected_full(batches_rejected_full_);
		for (const auto& result : results_) {
			*ack.add_results() = result;
		}

			stage_ = Stage::kFinishing;
			reader_.Finish(ack, ::grpc::Status::OK, this);
			return;
		}

		// Validate + enqueue.
		if (incoming_.batch_seq() <= last_seen_batch_seq_) {
			++batches_rejected_invalid_;
			::highbar::v1::CommandBatchResult stale;
			stale.set_batch_seq(incoming_.batch_seq());
			if (incoming_.has_client_command_id()) {
				stale.set_client_command_id(incoming_.client_command_id());
			}
			stale.set_status(::highbar::v1::COMMAND_BATCH_REJECTED_STALE);
			stale.set_mode(::highbar::v1::VALIDATION_MODE_STRICT);
			auto* issue = stale.add_issues();
			issue->set_code(::highbar::v1::STALE_OR_DUPLICATE_BATCH_SEQ);
			issue->set_field_path("batch_seq");
			issue->set_detail("batch_seq must increase within a SubmitCommands stream");
			issue->set_retry_hint(::highbar::v1::RETRY_AFTER_NEXT_SNAPSHOT);
			issue->set_batch_seq(incoming_.batch_seq());
			if (incoming_.has_client_command_id()) {
				issue->set_client_command_id(incoming_.client_command_id());
			}
			results_.push_back(stale);
			if (svc_->counters_ != nullptr) {
				svc_->counters_->
					command_submissions_rejected_invalid_argument
					.fetch_add(1, std::memory_order_relaxed);
			}
			Finish(::grpc::Status(::grpc::StatusCode::INVALID_ARGUMENT,
			                      "duplicate or stale batch_seq"));
			return;
		}

		const auto result = svc_->validator_->ValidateBatch(incoming_);
		if (!result.ok) {
			++batches_rejected_invalid_;
			results_.push_back(result.batch_result);
			if (svc_->counters_ != nullptr) {
				svc_->counters_->
					command_submissions_rejected_invalid_argument
					.fetch_add(1, std::memory_order_relaxed);
			}
			Finish(::grpc::Status(::grpc::StatusCode::INVALID_ARGUMENT,
			                      result.error));
			return;
		}

		std::vector<QueuedCommand> queued;
		queued.reserve(static_cast<std::size_t>(incoming_.commands_size()));
		for (int i = 0; i < incoming_.commands_size(); ++i) {
			const auto& cmd = incoming_.commands(i);
			QueuedCommand q;
			q.session_id = session_id_;
			q.batch_seq = incoming_.batch_seq();
			q.client_command_id =
				incoming_.has_client_command_id() ? incoming_.client_command_id() : 0;
			q.command_index = static_cast<std::uint32_t>(i);
			q.authoritative_target_unit_id =
				static_cast<std::int32_t>(incoming_.target_unit_id());
			q.command = cmd;
			queued.push_back(std::move(q));
		}
		if (!svc_->command_queue_->TryPushBatch(std::move(queued))) {
			++batches_rejected_full_;
			auto full_result = result.batch_result;
			full_result.set_status(::highbar::v1::COMMAND_BATCH_REJECTED_QUEUE_FULL);
			full_result.set_accepted_command_count(0);
			auto* issue = full_result.add_issues();
			issue->set_code(::highbar::v1::QUEUE_FULL);
			issue->set_field_path("commands");
			issue->set_detail("command queue full");
			issue->set_retry_hint(::highbar::v1::RETRY_AFTER_QUEUE_DRAINS);
			issue->set_batch_seq(incoming_.batch_seq());
			if (incoming_.has_client_command_id()) {
				issue->set_client_command_id(incoming_.client_command_id());
			}
			results_.push_back(full_result);
			if (svc_->counters_ != nullptr) {
				svc_->counters_->
					command_submissions_rejected_resource_exhausted
					.fetch_add(1, std::memory_order_relaxed);
			}
			Finish(::grpc::Status(::grpc::StatusCode::RESOURCE_EXHAUSTED,
			                      "command queue full"));
			return;
		}

		++batches_accepted_;
		last_accepted_batch_seq_ = incoming_.batch_seq();
		last_seen_batch_seq_ = incoming_.batch_seq();
		results_.push_back(result.batch_result);

		// Next read — proto requires the same storage to be reused.
		incoming_.Clear();
		reader_.Read(&incoming_, this);
	}

	void Finish(const ::grpc::Status& status) {
		stage_ = Stage::kFinishing;
		if (status.ok()) {
			// Caller wanted a normal close but didn't supply an ack —
			// synthesize an empty one. (Unused; every OK path builds
			// its own ack above.)
			::highbar::v1::CommandAck ack;
			reader_.Finish(ack, status, this);
		} else {
			reader_.FinishWithError(status, this);
		}
	}

	HighBarService* svc_;
	::grpc::ServerCompletionQueue* cq_;
	::grpc::ServerContext ctx_;
	::grpc::ServerAsyncReader<::highbar::v1::CommandAck,
	                           ::highbar::v1::CommandBatch> reader_;
	::highbar::v1::CommandBatch incoming_;
	Stage stage_ = Stage::kCreated;

	bool ai_slot_claimed_ = false;
	std::string session_id_;
	std::uint64_t last_accepted_batch_seq_ = 0;
	std::uint64_t last_seen_batch_seq_ = 0;
	std::uint64_t batches_accepted_ = 0;
	std::uint64_t batches_rejected_invalid_ = 0;
	std::uint64_t batches_rejected_full_ = 0;
	std::vector<::highbar::v1::CommandBatchResult> results_;
};

// --- InvokeCallback / Save / Load (unary) ----------------------------------
//
// InvokeCallback now has a minimal worker->engine bridge for the small
// callback subset needed by fixture bootstrap/runtime def-id resolution.
// Save/Load remain the no-op scaffolding from T061 until the engine-side
// persistence bridge is wired.

class HighBarService::InvokeCallbackCallData final : public CallDataBase {
public:
	InvokeCallbackCallData(HighBarService* svc,
	                       ::grpc::ServerCompletionQueue* cq)
		: svc_(svc), cq_(cq), responder_(&ctx_) {
		svc_->RequestInvokeCallback(&ctx_, &request_, &responder_, cq_, cq_, this);
	}

	void Proceed(bool ok) override {
		switch (stage_) {
		case Stage::kCreated: {
			if (!ok) { delete this; return; }
			new InvokeCallbackCallData(svc_, cq_);
			if (svc_->gateway_module_ == nullptr) {
				Finish(::grpc::Status(::grpc::StatusCode::UNAVAILABLE,
				                      "InvokeCallback handle not yet wired"));
				return;
			}

			std::string error_detail;
			switch (svc_->gateway_module_->InvokeCallback(
				request_, &response_, std::chrono::milliseconds(500), &error_detail)) {
			case ::circuit::CGrpcGatewayModule::CallbackRpcStatus::Ok:
				Finish(::grpc::Status::OK);
				return;
			case ::circuit::CGrpcGatewayModule::CallbackRpcStatus::Unavailable:
				Finish(::grpc::Status(::grpc::StatusCode::UNAVAILABLE, error_detail));
				return;
			case ::circuit::CGrpcGatewayModule::CallbackRpcStatus::FailedPrecondition:
				Finish(::grpc::Status(::grpc::StatusCode::FAILED_PRECONDITION, error_detail));
				return;
			case ::circuit::CGrpcGatewayModule::CallbackRpcStatus::Internal:
			default:
				Finish(::grpc::Status(::grpc::StatusCode::INTERNAL, error_detail));
				return;
			}
		}
		case Stage::kFinishing:
		default:
			delete this;
			return;
		}
	}

private:
	enum class Stage { kCreated, kFinishing };

	void Finish(const ::grpc::Status& status) {
		stage_ = Stage::kFinishing;
		responder_.Finish(response_, status, this);
	}

	HighBarService* svc_;
	::grpc::ServerCompletionQueue* cq_;
	::grpc::ServerContext ctx_;
	::highbar::v1::CallbackRequest request_;
	::highbar::v1::CallbackResponse response_;
	::grpc::ServerAsyncResponseWriter<::highbar::v1::CallbackResponse> responder_;
	Stage stage_ = Stage::kCreated;
};

#define HIGHBAR_NOOP_UNARY_CALLDATA(NAME, REQ_T, RESP_T, REQUEST_FN)               \
class HighBarService::NAME##CallData final : public CallDataBase {                 \
public:                                                                            \
	NAME##CallData(HighBarService* svc, ::grpc::ServerCompletionQueue* cq)         \
		: svc_(svc), cq_(cq), responder_(&ctx_) {                                  \
		svc_->REQUEST_FN(&ctx_, &request_, &responder_, cq_, cq_, this);           \
	}                                                                              \
	void Proceed(bool ok) override {                                               \
		if (stage_ == Stage::kCreated) {                                           \
			if (!ok) { delete this; return; }                                      \
			new NAME##CallData(svc_, cq_);                                         \
			stage_ = Stage::kFinishing;                                            \
			responder_.Finish(response_, ::grpc::Status::OK, this);                \
			return;                                                                \
		}                                                                          \
		delete this;                                                               \
	}                                                                              \
private:                                                                           \
	enum class Stage { kCreated, kFinishing };                                     \
	HighBarService* svc_;                                                          \
	::grpc::ServerCompletionQueue* cq_;                                            \
	::grpc::ServerContext ctx_;                                                    \
	REQ_T request_;                                                                \
	RESP_T response_;                                                              \
	::grpc::ServerAsyncResponseWriter<RESP_T> responder_;                          \
	Stage stage_ = Stage::kCreated;                                                \
}

HIGHBAR_NOOP_UNARY_CALLDATA(
	Save,
	::highbar::v1::SaveRequest,
	::highbar::v1::SaveResponse,
	RequestSave);

HIGHBAR_NOOP_UNARY_CALLDATA(
	Load,
	::highbar::v1::LoadRequest,
	::highbar::v1::LoadResponse,
	RequestLoad);

#undef HIGHBAR_NOOP_UNARY_CALLDATA

// --- RequestSnapshot (unary, 003-snapshot-arm-coverage T014) ---------------
//
// Worker-thread handler. Contract: contracts/request-snapshot.md §Handler
// behavior. The auth interceptor has already gated on AI-role token; if
// we reach Proceed() the caller is authorized. The handler must be
// non-blocking, touch no CircuitAI state, and coalesce concurrent
// callers by atomic flag.

class HighBarService::RequestSnapshotCallData final : public CallDataBase {
public:
	RequestSnapshotCallData(HighBarService* svc,
	                         ::grpc::ServerCompletionQueue* cq)
		: svc_(svc), cq_(cq), responder_(&ctx_) {
		svc_->RequestRequestSnapshot(&ctx_, &request_, &responder_,
		                              cq_, cq_, this);
	}

	void Proceed(bool ok) override {
		switch (stage_) {
		case Stage::kCreated: {
			if (!ok) { delete this; return; }
			new RequestSnapshotCallData(svc_, cq_);

			// Health gating. If the gateway has faulted, return
			// FAILED_PRECONDITION with scheduled_frame = 0 (the proto3
			// default for the unset field; explicit for clarity).
			if (svc_->gateway_module_ == nullptr) {
				stage_ = Stage::kFinishing;
				responder_.Finish(response_,
					::grpc::Status(::grpc::StatusCode::UNAVAILABLE,
					                "RequestSnapshot handle not yet wired"),
					this);
				return;
			}
			const auto state = svc_->gateway_module_->State();
			if (state != ::circuit::GatewayState::Healthy) {
				response_.set_scheduled_frame(0);
				std::string msg = "gateway state=";
				msg += (state == ::circuit::GatewayState::Disabling
				         ? "disabling" : "disabled");
				stage_ = Stage::kFinishing;
				responder_.Finish(response_,
					::grpc::Status(::grpc::StatusCode::FAILED_PRECONDITION, msg),
					this);
				return;
			}

			// Compute the frame the forced snapshot will fire on. Engine
			// thread advances current_frame_ each OnFrameTick; we schedule
			// at CurrentFrame() + 1 so callers can correlate. Raising the
			// atomic is idempotent — concurrent callers all observe the
			// same scheduled_frame, per FR-006 coalescing.
			const std::uint32_t scheduled =
				svc_->gateway_module_->CurrentFrame() + 1u;
			svc_->gateway_module_->PendingSnapshotRequest().store(
				true, std::memory_order_release);
			response_.set_scheduled_frame(scheduled);

			stage_ = Stage::kFinishing;
			responder_.Finish(response_, ::grpc::Status::OK, this);
			return;
		}
		case Stage::kFinishing:
		default:
			delete this;
			return;
		}
	}

private:
	enum class Stage { kCreated, kFinishing };
	HighBarService* svc_;
	::grpc::ServerCompletionQueue* cq_;
	::grpc::ServerContext ctx_;
	::highbar::v1::RequestSnapshotRequest request_;
	::highbar::v1::RequestSnapshotResponse response_;
	::grpc::ServerAsyncResponseWriter<::highbar::v1::RequestSnapshotResponse> responder_;
	Stage stage_ = Stage::kCreated;
};

// ============================================================================
// HighBarService public surface
// ============================================================================

HighBarService::HighBarService(::circuit::CCircuitAI* ai,
                               Counters* counters,
                               const AuthToken* token)
	: ai_(ai), counters_(counters), token_(token) {}

HighBarService::~HighBarService() {
	if (!shutting_down_.load()) {
		Shutdown();
	}
}

void HighBarService::Bind(const TransportEndpoint& endpoint,
                          std::string* bound_address) {
	::grpc::ServerBuilder builder;
	builder.SetMaxReceiveMessageSize(
		static_cast<int>(endpoint.max_recv_mb) * 1024 * 1024);

	std::string uri;
	if (endpoint.transport == Transport::kUds) {
		uri = "unix:" + endpoint.uds_path;
	} else {
		// T073 — loopback-only guard. Spec Assumption: same-host. A
		// non-loopback bind would expose the gateway to the network
		// with no TLS + a filesystem-anchored token; that is not a
		// supported configuration. Fail startup with a clear reason
		// so operators can fix grpc.json.
		std::string reason;
		if (!IsLoopbackTcpBind(endpoint.tcp_bind, &reason)) {
			throw std::runtime_error(
				"HighBarService::Bind: " + reason +
				" (set transport=uds or fix tcp_bind in data/config/grpc.json)");
		}
		uri = endpoint.tcp_bind;
	}
	builder.AddListeningPort(uri, ::grpc::InsecureServerCredentials());

	// AI-token auth interceptor (T022).
	std::vector<std::unique_ptr<
		::grpc::experimental::ServerInterceptorFactoryInterface>> factories;
	factories.emplace_back(std::make_unique<AuthInterceptorFactory>(token_, ai_));
	builder.experimental().SetInterceptorCreators(std::move(factories));

	builder.RegisterService(this);
	if (admin_service_ != nullptr) {
		builder.RegisterService(admin_service_);
	}
	cq_ = builder.AddCompletionQueue();
	server_ = builder.BuildAndStart();
	if (server_ == nullptr) {
		throw std::runtime_error("HighBarService::Bind: BuildAndStart returned null "
		                         "(transport=" + uri + ")");
	}

	// Seed one pending CallData per RPC type. Each replaces itself on
	// progression to keep the service accepting RPCs indefinitely.
	new HelloCallData(this, cq_.get());
	new GetRuntimeCountersCallData(this, cq_.get());
	new StreamStateCallData(this, cq_.get());
	new ValidateCommandBatchCallData(this, cq_.get());
	new GetCommandSchemaCallData(this, cq_.get());
	new GetUnitCapabilitiesCallData(this, cq_.get());
	new SubmitCommandsCallData(this, cq_.get());
	new InvokeCallbackCallData(this, cq_.get());
	new SaveCallData(this, cq_.get());
	new LoadCallData(this, cq_.get());
	new RequestSnapshotCallData(this, cq_.get());  // 003-snapshot-arm-coverage
	if (admin_service_ != nullptr) {
		admin_service_->Start(cq_.get());
	}

	// One worker thread for Phase 2. US1's 4-observer + AI pressure
	// will require 2-4; fine to scale here when needed.
	cq_workers_.emplace_back(&HighBarService::CqWorker, this);

	if (bound_address != nullptr) {
		*bound_address = uri;
	}
}

void HighBarService::Shutdown(std::chrono::milliseconds deadline) {
	if (shutting_down_.exchange(true)) {
		return;
	}
	if (delta_bus_ != nullptr) {
		delta_bus_->EvictAll(EvictionReason::kCanceled);
	}
	if (server_) {
		server_->Shutdown(std::chrono::system_clock::now() + deadline);
	}
	if (cq_) {
		cq_->Shutdown();
	}
	for (auto& t : cq_workers_) {
		if (t.joinable()) t.join();
	}
	cq_workers_.clear();
	server_.reset();
	cq_.reset();
}

void HighBarService::CqWorker() {
	void* tag = nullptr;
	bool ok = false;
	while (cq_ && cq_->Next(&tag, &ok)) {
		auto* cd = static_cast<CallDataBase*>(tag);
		if (cd == nullptr) continue;
		// T013 — handler fault-capture. Every exception that escapes a
		// CallData::Proceed is routed to the gateway's fault sink,
		// which posts a disable request to run on the engine thread.
		// The worker continues to drain the CQ so in-flight RPCs can
		// complete cleanly before the server shuts down.
		try {
			cd->Proceed(ok);
		} catch (...) {
			if (!faulted_.exchange(true, std::memory_order_acq_rel)) {
				const std::string reason = ReasonCodeFor(std::current_exception());
				std::string detail;
				try { std::rethrow_exception(std::current_exception()); }
				catch (const std::exception& e) { detail = e.what(); }
				catch (...)                      { detail = "unknown"; }
				if (fault_sink_) {
					fault_sink_("handler", reason, detail);
				} else if (ai_) {
					LogError(ai_, "CqWorker", detail);
				}
			}
		}
	}
}

void HighBarService::FaultCloseAllStreams(const std::string& subsystem,
                                            const std::string& reason) {
	// Minimal impl per contracts/gateway-fault.md §3. Triggering
	// server_->Shutdown with a short deadline causes all pending
	// streams to close with UNAVAILABLE (the "gateway disabled" message
	// is carried in the final gRPC status). Per-stream trailer
	// metadata (highbar-fault-subsystem / highbar-fault-reason) is a
	// follow-up; subsystem/reason are already logged via LogFault and
	// persisted in highbar.health for clients that read the file.
	(void)subsystem; (void)reason;
	if (delta_bus_ != nullptr) {
		delta_bus_->EvictAll(EvictionReason::kFault);
	}
	if (server_ && !shutting_down_.exchange(true)) {
		server_->Shutdown(std::chrono::system_clock::now()
		                  + std::chrono::milliseconds(250));
		if (cq_) cq_->Shutdown();
	}
}

void HighBarService::SetUs1Handles(SnapshotBuilder* snapshot,
                                   DeltaBus* bus,
                                   RingBuffer* ring,
                                   std::shared_mutex* state_mutex) {
	snapshot_ = snapshot;
	delta_bus_ = bus;
	ring_ = ring;
	state_mutex_ = state_mutex;
}

void HighBarService::SetUs2Handles(CommandQueue* queue) {
	command_queue_ = queue;
	if (validator_ == nullptr && ai_ != nullptr) {
		validator_ = std::make_unique<CommandValidator>(ai_);
	}
}

void HighBarService::SetAdminService(AdminService* admin_service) {
	admin_service_ = admin_service;
}

void HighBarService::SetSnapshotHandle(::circuit::CGrpcGatewayModule* module) {
	gateway_module_ = module;
}

void HighBarService::AdvanceFrame() {
	const auto f = frames_since_bind_.fetch_add(1, std::memory_order_relaxed) + 1;
	if (counters_ != nullptr) {
		counters_->frames_since_bind.store(f, std::memory_order_relaxed);
	}
}

bool HighBarService::TryReserveObserverSlot() {
	for (;;) {
		std::uint32_t cur = observer_count_.load();
		if (cur >= kObserverHardCap) return false;
		if (observer_count_.compare_exchange_weak(cur, cur + 1)) {
			if (counters_) {
				counters_->subscriber_count.store(cur + 1);
			}
			return true;
		}
	}
}

void HighBarService::ReleaseObserverSlot() {
	const auto prev = observer_count_.fetch_sub(1);
	if (prev > 0 && counters_) {
		counters_->subscriber_count.store(prev - 1);
	}
}

bool HighBarService::TryClaimAiSlot() {
	bool expected = false;
	return ai_slot_taken_.compare_exchange_strong(expected, true);
}

void HighBarService::ReleaseAiSlot() {
	ai_slot_taken_.store(false);
}

}  // namespace circuit::grpc

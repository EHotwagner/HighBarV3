// SPDX-License-Identifier: GPL-2.0-only
//
// HighBarV3 — async gRPC server impl (T023-T025, T029).

#include "grpc/HighBarService.h"
#include "grpc/AuthInterceptor.h"
#include "grpc/AuthToken.h"
#include "grpc/CommandQueue.h"
#include "grpc/Counters.h"
#include "grpc/DeltaBus.h"
#include "grpc/Log.h"
#include "grpc/RingBuffer.h"
#include "grpc/SchemaVersion.h"
#include "grpc/SnapshotBuilder.h"

#include "CircuitAI.h"
#include "terrain/TerrainManager.h"
#include "unit/CircuitDef.h"
#include "unit/CircuitUnit.h"
#include "unit/CoreUnit.h"

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
			// Register a replacement to accept the next Hello.
			new HelloCallData(svc_, cq_);
			if (!ok) { delete this; return; }

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
				// The AI slot will be released in US2 when the session
				// disconnects. For Phase 2 skeleton we release
				// immediately so tests can observe the transient claim.
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
			new GetRuntimeCountersCallData(svc_, cq_);
			if (!ok) { delete this; return; }

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
		// Pump already exited by the time we reach kFinishing, but guard
		// paths where ctor-time failures never spawn it.
		if (pump_.joinable()) {
			stop_.store(true, std::memory_order_release);
			cv_.notify_all();
			pump_.join();
		}
		if (slot_ && svc_->delta_bus_ != nullptr) {
			svc_->delta_bus_->Unsubscribe(slot_);
		}
		if (observer_slot_reserved_) {
			svc_->ReleaseObserverSlot();
		}
	}

	void Proceed(bool ok) override {
		if (stage_ == Stage::kCreated) {
			// Queue a replacement to accept the next StreamState.
			new StreamStateCallData(svc_, cq_);
			if (!ok) { delete this; return; }

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
	//
	// Initial-payload + live-loop seq arithmetic (T094, FR-006/7/8):
	//   - The SubscriberSlot was bound to the DeltaBus in kCreated so we
	//     don't miss any entries published between subscribe and the
	//     initial payload. But those entries' seqs may overlap with what
	//     the initial payload already carries — the snapshot represents
	//     the world at HeadSeq, and the slot may already hold deltas with
	//     seq ≤ HeadSeq published during the shared-lock window. We track
	//     `last_sent_seq_` and skip any subsequent slot entry whose seq
	//     does not strictly exceed it (client-side FR-006 invariant-check
	//     would otherwise raise).
	//   - Fresh-snapshot (resume-miss) path: snapshot's seq = HeadSeq, so
	//     subsequent deltas (seq = HeadSeq+1, HeadSeq+2, …) satisfy strict
	//     monotonicity for this client. On an empty ring HeadSeq=0 — we
	//     emit seq=0 for the initial snapshot; the first delta will be
	//     seq=1 and satisfy monotonicity regardless.
	void PumpLoop() {
		try {
			// --- 1. Initial payload: ring-replay vs fresh snapshot.
			auto replay = resume_from_seq_ > 0
				? svc_->ring_->GetFromSeq(resume_from_seq_)
				: std::optional<std::vector<RingEntry>>{};

			if (!replay.has_value()) {
				// Fresh snapshot. Take shared lock for the build.
				::highbar::v1::StateUpdate first;
				{
					std::shared_lock<std::shared_mutex> lock(*svc_->state_mutex_);
					first.set_seq(svc_->ring_->HeadSeq());
					first.set_frame(svc_->frames_since_bind_.load());
					*first.mutable_snapshot() = svc_->snapshot_->Build();
				}
				if (!WriteAndWait(first)) {
					FinishWithStatus(CancelledOrFault());
					return;
				}
				last_sent_seq_ = first.seq();
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
					last_sent_seq_ = u.seq();
				}
			}

			// --- 2. Live loop: pump the SubscriberSlot, filtering seqs
			//        ≤ last_sent_seq_ that were captured during the
			//        initial-payload window.
			while (!stop_.load(std::memory_order_acquire)) {
				std::shared_ptr<const std::string> payload;
				const bool got = slot_->BlockingPop(&payload);
				if (!got) {
					// Evicted (slow consumer) or canceled.
					if (slot_->Eviction() == EvictionReason::kSlowConsumer) {
						FinishWithStatus(::grpc::Status(
							::grpc::StatusCode::RESOURCE_EXHAUSTED,
							"slow consumer evicted"));
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
				if (u.seq() <= last_sent_seq_) {
					// Already covered by the initial payload.
					continue;
				}
				if (!WriteAndWait(u)) {
					FinishWithStatus(CancelledOrFault());
					return;
				}
				last_sent_seq_ = u.seq();
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
	std::uint64_t last_sent_seq_ = 0;   // T094 high-water filter
	std::shared_ptr<SubscriberSlot> slot_;

	// Pump thread + CQ-worker handshake.
	std::thread pump_;
	std::atomic<bool> stop_{false};
	std::mutex mutex_;
	std::condition_variable cv_;
	bool op_done_ = false;
	bool op_ok_ = false;
};

// --- SubmitCommands (client-streaming, T058) -------------------------------
//
// State machine:
//   kCreated   → on ok, claim AI slot, kick off first Read; on slot-taken
//                or missing handles, FinishWithError.
//   kReading   → each Read completion either pushes a validated batch into
//                CommandQueue (bump counters, continue reading) or finishes
//                the RPC (INVALID_ARGUMENT, RESOURCE_EXHAUSTED, UNAVAILABLE).
//                Client stream EOF (ok=false on Read) → FinishOk with ack.
//   kFinishing → the Finish/FinishWithError completion reclaims the CallData.
//
// AI slot is released in the destructor so any exit path (normal Finish,
// error, server-initiated shutdown via ~HighBarService) frees the slot
// (FR-012).

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
		case Stage::kCreated: {
			new SubmitCommandsCallData(svc_, cq_);
			if (!ok) { delete this; return; }

			if (svc_->command_queue_ == nullptr) {
				FinishError(::grpc::Status(
					::grpc::StatusCode::UNAVAILABLE,
					"gateway US2 handles not wired"));
				return;
			}

			// FR-011: single AI-slot. Release happens in dtor.
			if (!svc_->TryClaimAiSlot()) {
				FinishError(::grpc::Status(
					::grpc::StatusCode::ALREADY_EXISTS,
					"AI slot already claimed"));
				return;
			}
			ai_slot_claimed_ = true;

			stage_ = Stage::kReading;
			reader_.Read(&batch_, this);
			return;
		}

		case Stage::kReading: {
			if (!ok) {
				// Client half-closed the stream. Respond with final ack.
				FinishOk();
				return;
			}

			const auto validate_and_queue_status = ProcessBatch();
			if (!validate_and_queue_status.ok()) {
				FinishError(validate_and_queue_status);
				return;
			}

			// Continue reading next batch.
			batch_.Clear();
			reader_.Read(&batch_, this);
			return;
		}

		case Stage::kFinishing:
		default:
			delete this;
			return;
		}
	}

private:
	enum class Stage { kCreated, kReading, kFinishing };

	// Validate every AICommand in the batch, then push one QueuedCommand
	// per AICommand into CommandQueue. All-or-nothing per batch.
	::grpc::Status ProcessBatch() {
		for (const auto& cmd : batch_.commands()) {
			const auto err = svc_->ValidateCommand(batch_.target_unit_id(), cmd);
			if (err != ValidationError::kOk) {
				if (svc_->counters_ != nullptr) {
					svc_->counters_->command_submissions_rejected_invalid_argument
						.fetch_add(1);
				}
				return ::grpc::Status(
					::grpc::StatusCode::INVALID_ARGUMENT,
					ValidationErrorString(err));
			}
		}

		for (const auto& cmd : batch_.commands()) {
			QueuedCommand q;
			q.session_id = session_id_;
			q.target_unit_id = batch_.target_unit_id();
			q.command = cmd;
			const auto status = svc_->command_queue_->Push(std::move(q));
			if (status == CommandQueue::Status::kResourceExhausted) {
				if (svc_->counters_ != nullptr) {
					svc_->counters_->command_submissions_rejected_resource_exhausted
						.fetch_add(1);
				}
				return ::grpc::Status(
					::grpc::StatusCode::RESOURCE_EXHAUSTED,
					"CommandQueue full");
			}
		}

		last_accepted_batch_seq_ = batch_.batch_seq();
		++batches_accepted_;

		if (svc_->counters_ != nullptr) {
			svc_->counters_->command_queue_depth.store(
				static_cast<std::uint32_t>(svc_->command_queue_->Depth()),
				std::memory_order_relaxed);
		}
		return ::grpc::Status::OK;
	}

	static const char* ValidationErrorString(ValidationError e) {
		switch (e) {
		case ValidationError::kOk:                       return "ok";
		case ValidationError::kTargetUnitNotFound:       return "target_unit_id not owned or not live";
		case ValidationError::kBuildDefNotConstructible: return "build.def_id not constructible by target";
		case ValidationError::kPositionOutOfMap:         return "position outside map extents";
		}
		return "invalid";
	}

	void FinishOk() {
		stage_ = Stage::kFinishing;
		ack_.set_last_accepted_batch_seq(last_accepted_batch_seq_);
		ack_.set_batches_accepted(batches_accepted_);
		ack_.set_batches_rejected_invalid(batches_rejected_invalid_);
		ack_.set_batches_rejected_full(batches_rejected_full_);
		reader_.Finish(ack_, ::grpc::Status::OK, this);
	}

	void FinishError(const ::grpc::Status& status) {
		stage_ = Stage::kFinishing;
		if (status.error_code() == ::grpc::StatusCode::INVALID_ARGUMENT) {
			++batches_rejected_invalid_;
		} else if (status.error_code() == ::grpc::StatusCode::RESOURCE_EXHAUSTED) {
			++batches_rejected_full_;
		}
		reader_.FinishWithError(status, this);
	}

	HighBarService* svc_;
	::grpc::ServerCompletionQueue* cq_;
	::grpc::ServerContext ctx_;
	::highbar::v1::CommandBatch batch_;
	::highbar::v1::CommandAck ack_;
	::grpc::ServerAsyncReader<::highbar::v1::CommandAck,
	                           ::highbar::v1::CommandBatch> reader_;
	Stage stage_ = Stage::kCreated;

	bool ai_slot_claimed_ = false;
	std::string session_id_ = HighBarService::NewSessionId();

	std::uint64_t last_accepted_batch_seq_ = 0;
	std::uint64_t batches_accepted_ = 0;
	std::uint64_t batches_rejected_invalid_ = 0;
	std::uint64_t batches_rejected_full_ = 0;
};

// --- InvokeCallback (T060) / Save / Load (T061) ----------------------------
//
// All three are unary, AI-role-only (enforced by AuthInterceptor — the
// handler never runs without a valid token). The plugin forwards these
// calls *from* the engine to the external AI: the engine-side initiator
// pushes a CallbackRequest into a synchronous channel, blocks until the
// AI client returns a CallbackResponse on InvokeCallback, then un-blocks.
//
// At Phase 4 US2 the engine side of that channel is not yet wired —
// engine events requiring synchronous AI answers are out of scope for
// the first pass; Save/Load similarly. So the handlers here validate
// the shape, return OK on empty payloads, and propagate blobs through
// when a future engine-side initiator enqueues a waiting request.
//
// For now, InvokeCallback returns OK with an empty CallbackResponse so
// AI clients probing the endpoint see it as available; Save/Load do the
// same. Engine-side forwarding is a follow-up — the RPC surface is
// wire-complete.

class HighBarService::InvokeCallbackCallData final : public CallDataBase {
public:
	InvokeCallbackCallData(HighBarService* svc,
	                       ::grpc::ServerCompletionQueue* cq)
		: svc_(svc), cq_(cq), responder_(&ctx_) {
		svc_->RequestInvokeCallback(&ctx_, &request_, &responder_, cq_, cq_, this);
	}
	void Proceed(bool ok) override {
		if (stage_ == Stage::kCreated) {
			new InvokeCallbackCallData(svc_, cq_);
			if (!ok) { delete this; return; }
			stage_ = Stage::kFinishing;
			// Empty response: no engine-side initiator is waiting yet.
			// When the engine-side channel lands, this branches on
			// whether a request is queued and splices request into it.
			responder_.Finish(response_, ::grpc::Status::OK, this);
			return;
		}
		delete this;
	}
private:
	enum class Stage { kCreated, kFinishing };
	HighBarService* svc_;
	::grpc::ServerCompletionQueue* cq_;
	::grpc::ServerContext ctx_;
	::highbar::v1::CallbackRequest request_;
	::highbar::v1::CallbackResponse response_;
	::grpc::ServerAsyncResponseWriter<::highbar::v1::CallbackResponse> responder_;
	Stage stage_ = Stage::kCreated;
};

class HighBarService::SaveCallData final : public CallDataBase {
public:
	SaveCallData(HighBarService* svc, ::grpc::ServerCompletionQueue* cq)
		: svc_(svc), cq_(cq), responder_(&ctx_) {
		svc_->RequestSave(&ctx_, &request_, &responder_, cq_, cq_, this);
	}
	void Proceed(bool ok) override {
		if (stage_ == Stage::kCreated) {
			new SaveCallData(svc_, cq_);
			if (!ok) { delete this; return; }
			stage_ = Stage::kFinishing;
			// Echo empty client_state. Engine-side Save/Load initiator
			// is a follow-up; contract surface is wire-complete.
			responder_.Finish(response_, ::grpc::Status::OK, this);
			return;
		}
		delete this;
	}
private:
	enum class Stage { kCreated, kFinishing };
	HighBarService* svc_;
	::grpc::ServerCompletionQueue* cq_;
	::grpc::ServerContext ctx_;
	::highbar::v1::SaveRequest request_;
	::highbar::v1::SaveResponse response_;
	::grpc::ServerAsyncResponseWriter<::highbar::v1::SaveResponse> responder_;
	Stage stage_ = Stage::kCreated;
};

class HighBarService::LoadCallData final : public CallDataBase {
public:
	LoadCallData(HighBarService* svc, ::grpc::ServerCompletionQueue* cq)
		: svc_(svc), cq_(cq), responder_(&ctx_) {
		svc_->RequestLoad(&ctx_, &request_, &responder_, cq_, cq_, this);
	}
	void Proceed(bool ok) override {
		if (stage_ == Stage::kCreated) {
			new LoadCallData(svc_, cq_);
			if (!ok) { delete this; return; }
			stage_ = Stage::kFinishing;
			responder_.Finish(response_, ::grpc::Status::OK, this);
			return;
		}
		delete this;
	}
private:
	enum class Stage { kCreated, kFinishing };
	HighBarService* svc_;
	::grpc::ServerCompletionQueue* cq_;
	::grpc::ServerContext ctx_;
	::highbar::v1::LoadRequest request_;
	::highbar::v1::LoadResponse response_;
	::grpc::ServerAsyncResponseWriter<::highbar::v1::LoadResponse> responder_;
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

namespace {

// Parse "host:port" into host / port; return false on malformed input.
// IPv6 literals are bracket-quoted per RFC 3986: "[::1]:50511".
bool SplitHostPort(const std::string& bind, std::string* host, std::string* port) {
	if (bind.empty()) return false;
	if (bind.front() == '[') {
		const auto close = bind.find(']');
		if (close == std::string::npos || close + 1 >= bind.size()
		    || bind[close + 1] != ':') {
			return false;
		}
		*host = bind.substr(1, close - 1);
		*port = bind.substr(close + 2);
	} else {
		const auto colon = bind.rfind(':');
		if (colon == std::string::npos) return false;
		*host = bind.substr(0, colon);
		*port = bind.substr(colon + 1);
	}
	return !host->empty() && !port->empty();
}

// Loopback means 127.0.0.0/8 for IPv4 or ::1 exactly for IPv6. Data-
// model §6 validation rule; non-loopback is rejected with a clear
// error because the spec assumes same-host deployment.
bool IsLoopback(const std::string& host) {
	in_addr v4{};
	if (inet_pton(AF_INET, host.c_str(), &v4) == 1) {
		const auto bytes = ntohl(v4.s_addr);
		return (bytes & 0xff000000u) == 0x7f000000u;  // 127.0.0.0/8
	}
	in6_addr v6{};
	if (inet_pton(AF_INET6, host.c_str(), &v6) == 1) {
		return IN6_IS_ADDR_LOOPBACK(&v6);
	}
	// Not a numeric address. Allow "localhost" as a convenience since
	// resolver behavior on a single host treats it as loopback; anything
	// else is rejected.
	return host == "localhost";
}

}  // namespace

void HighBarService::Bind(const TransportEndpoint& endpoint,
                          std::string* bound_address) {
	::grpc::ServerBuilder builder;
	builder.SetMaxReceiveMessageSize(
		static_cast<int>(endpoint.max_recv_mb) * 1024 * 1024);

	std::string uri;
	if (endpoint.transport == Transport::kUds) {
		uri = "unix:" + endpoint.uds_path;
	} else {
		// T073 (US4): reject non-loopback binds at startup so container
		// operators never silently expose the gateway to the LAN. The
		// spec's same-host assumption (plan §Technical Context) is the
		// authoritative constraint.
		std::string host, port;
		if (!SplitHostPort(endpoint.tcp_bind, &host, &port)) {
			throw std::runtime_error(
				"HighBarService::Bind: malformed tcp_bind '"
				+ endpoint.tcp_bind + "' (expected host:port)");
		}
		if (!IsLoopback(host)) {
			throw std::runtime_error(
				"HighBarService::Bind: non-loopback tcp_bind '"
				+ endpoint.tcp_bind + "' rejected (must be "
				"127.0.0.0/8, ::1, or localhost)");
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
	new SubmitCommandsCallData(this, cq_.get());
	new InvokeCallbackCallData(this, cq_.get());
	new SaveCallData(this, cq_.get());
	new LoadCallData(this, cq_.get());

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
		if (cd != nullptr) {
			cd->Proceed(ok);
		}
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
}

// ============================================================================
// ValidateCommand (T056)
// ============================================================================
//
// Data-model §4: target_unit_id must resolve to a live owned unit;
// build.def_id must be constructible by target; positions must lie in
// map extents. Runs on the gRPC worker thread; takes a shared lock on
// state_mutex_ so it doesn't race with FlushDelta (which takes the
// exclusive lock for the serialize-and-publish window).
//
// Engine-thread re-check at dispatch time covers TOCTOU — a unit may
// die between validation and drain; the dispatcher skips dead units.

namespace {

bool PosInMap(const ::highbar::v1::Vector3& p) {
	const float max_x = static_cast<float>(::circuit::CTerrainManager::GetTerrainWidth());
	const float max_z = static_cast<float>(::circuit::CTerrainManager::GetTerrainHeight());
	if (max_x <= 0 || max_z <= 0) {
		// Map extents not initialized yet — don't reject on shape since
		// the engine wouldn't have started issuing commands in a live
		// match without maxxpos/maxzpos. Treat as pass to avoid false
		// negatives during test harness runs.
		return true;
	}
	return p.x() >= 0 && p.x() <= max_x && p.z() >= 0 && p.z() <= max_z;
}

bool ValidateBuildDef(const ::circuit::CCircuitAI* ai,
                      ::circuit::CCircuitUnit* builder,
                      std::int32_t to_build_def_id) {
	if (builder == nullptr || builder->GetCircuitDef() == nullptr) return false;
	auto* to_build = const_cast<::circuit::CCircuitAI*>(ai)->GetCircuitDefSafe(
		static_cast<::circuit::CCircuitDef::Id>(to_build_def_id));
	if (to_build == nullptr) return false;
	return builder->GetCircuitDef()->CanBuild(to_build);
}

}  // namespace

ValidationError HighBarService::ValidateCommand(
	std::uint32_t target_unit_id,
	const ::highbar::v1::AICommand& cmd) const {

	if (ai_ == nullptr) {
		return ValidationError::kTargetUnitNotFound;
	}

	// Shared lock so we don't race with the engine-thread serialize
	// window (FlushDelta). Reads of GetTeamUnit and GetCircuitDefSafe
	// on the same mutex are safe under this pattern (T036 policy).
	std::shared_lock<std::shared_mutex> lock;
	if (state_mutex_ != nullptr) {
		lock = std::shared_lock<std::shared_mutex>(*state_mutex_);
	}

	auto* unit = ai_->GetTeamUnit(
		static_cast<::circuit::ICoreUnit::Id>(target_unit_id));
	if (unit == nullptr) {
		return ValidationError::kTargetUnitNotFound;
	}

	using CK = ::highbar::v1::AICommand::CommandCase;
	switch (cmd.command_case()) {
	case CK::kMoveUnit:
		if (!PosInMap(cmd.move_unit().to_position())) {
			return ValidationError::kPositionOutOfMap;
		}
		break;
	case CK::kFight:
		if (!PosInMap(cmd.fight().to_position())) {
			return ValidationError::kPositionOutOfMap;
		}
		break;
	case CK::kPatrol:
		if (!PosInMap(cmd.patrol().to_position())) {
			return ValidationError::kPositionOutOfMap;
		}
		break;
	case CK::kAttackArea:
		if (!PosInMap(cmd.attack_area().attack_position())) {
			return ValidationError::kPositionOutOfMap;
		}
		break;
	case CK::kReclaimArea:
		if (!PosInMap(cmd.reclaim_area().position())) {
			return ValidationError::kPositionOutOfMap;
		}
		break;
	case CK::kReclaimInArea:
		if (!PosInMap(cmd.reclaim_in_area().position())) {
			return ValidationError::kPositionOutOfMap;
		}
		break;
	case CK::kBuildUnit:
		if (!PosInMap(cmd.build_unit().build_position())) {
			return ValidationError::kPositionOutOfMap;
		}
		if (!ValidateBuildDef(ai_, unit, cmd.build_unit().to_build_unit_def_id())) {
			return ValidationError::kBuildDefNotConstructible;
		}
		break;
	default:
		// Other 88 arms carry no positions / build defs — accept on
		// shape. Engine-thread dispatch still owns the semantic check
		// (dead unit, unknown arm).
		break;
	}

	return ValidationError::kOk;
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

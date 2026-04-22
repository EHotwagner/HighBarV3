// SPDX-License-Identifier: GPL-2.0-only

#include "grpc/CoordinatorClient.h"
#include "grpc/CommandQueue.h"
#include "grpc/GrpcLog.h"
#include "grpc/SchemaVersion.h"

#include "CircuitAI.h"

#include <grpcpp/create_channel.h>
#include <grpcpp/security/credentials.h>

#include <chrono>
#include <cstdio>
#include <cstdlib>
#include <ctime>
#include <mutex>

namespace {

std::mutex& CoordinatorTraceMutex() {
	static std::mutex m;
	return m;
}

void AppendCoordinatorTrace(const std::string& plugin_id, const std::string& message) {
	const char* path = std::getenv("HIGHBAR_COORDINATOR_TRACE");
	if (path == nullptr || path[0] == '\0') return;

	std::lock_guard<std::mutex> lock(CoordinatorTraceMutex());
	FILE* f = std::fopen(path, "a");
	if (f == nullptr) return;

	const auto now = std::chrono::system_clock::now();
	const auto micros = std::chrono::duration_cast<std::chrono::microseconds>(
		now.time_since_epoch()).count();
	std::fprintf(f, "%lld plugin=%s %s\n",
	             static_cast<long long>(micros),
	             plugin_id.c_str(),
	             message.c_str());
	std::fclose(f);
}

const char* ConnectivityStateName(::grpc_connectivity_state state) {
	switch (state) {
	case GRPC_CHANNEL_IDLE:
		return "IDLE";
	case GRPC_CHANNEL_CONNECTING:
		return "CONNECTING";
	case GRPC_CHANNEL_READY:
		return "READY";
	case GRPC_CHANNEL_TRANSIENT_FAILURE:
		return "TRANSIENT_FAILURE";
	case GRPC_CHANNEL_SHUTDOWN:
		return "SHUTDOWN";
	}
	return "UNKNOWN";
}

}  // namespace

namespace circuit::grpc {

CoordinatorClient::CoordinatorClient(::circuit::CCircuitAI* ai,
                                       const std::string& endpoint,
                                       const std::string& plugin_id,
                                       const std::string& engine_sha256)
	: ai_(ai)
	, endpoint_(endpoint)
	, plugin_id_(plugin_id)
	, engine_sha256_(engine_sha256)
	, channel_(::grpc::CreateChannel(endpoint, ::grpc::InsecureChannelCredentials()))
	, stub_(::highbar::v1::HighBarCoordinator::NewStub(channel_)) {
	cmd_channel_ = ::grpc::CreateChannel(endpoint, ::grpc::InsecureChannelCredentials());
	cmd_stub_ = ::highbar::v1::HighBarCoordinator::NewStub(cmd_channel_);
	AppendCoordinatorTrace(plugin_id_, "ctor connected");
	LogConnect(ai_, plugin_id_, endpoint_, "client-mode");
}

CoordinatorClient::~CoordinatorClient() {
	AppendCoordinatorTrace(plugin_id_, "dtor begin");
	ClosePushStateStream();

	// Cancel + join the command reader if running.
	cmd_stopping_.store(true, std::memory_order_release);
	if (cmd_ctx_) cmd_ctx_->TryCancel();
	if (cmd_thread_.joinable()) cmd_thread_.join();
	AppendCoordinatorTrace(plugin_id_, "dtor end");
}

bool CoordinatorClient::SendHeartbeat(std::uint32_t frame) {
	AppendCoordinatorTrace(
		plugin_id_,
		"heartbeat attempt frame=" + std::to_string(frame)
		+ " hb_state=" + ConnectivityStateName(channel_->GetState(false))
		+ " cmd_state=" + ConnectivityStateName(cmd_channel_->GetState(false))
		+ " pushed=" + std::to_string(pushed_count_.load(std::memory_order_relaxed))
		+ " cmd_batches=" + std::to_string(cmd_batches_received_.load(std::memory_order_relaxed))
		+ " cmd_commands=" + std::to_string(cmd_commands_received_.load(std::memory_order_relaxed)));
	::highbar::v1::HeartbeatRequest req;
	req.set_plugin_id(plugin_id_);
	req.set_frame(frame);
	req.set_engine_sha256(engine_sha256_);
	req.set_schema_version(::highbar::v1::kSchemaVersion);

	::highbar::v1::HeartbeatResponse resp;
	::grpc::ClientContext ctx;
	ctx.set_deadline(std::chrono::system_clock::now()
	                 + std::chrono::milliseconds(250));

	const ::grpc::Status status = stub_->Heartbeat(&ctx, req, &resp);
	if (status.ok()) {
		connected_.store(true, std::memory_order_release);
		ok_count_.fetch_add(1, std::memory_order_relaxed);
		return true;
	}
	AppendCoordinatorTrace(plugin_id_,
	                      "heartbeat failed code=" + std::to_string(status.error_code())
	                      + " msg=" + status.error_message());
	connected_.store(false, std::memory_order_release);
	err_count_.fetch_add(1, std::memory_order_relaxed);
	// Rate-limit: only log the first failure per streak.
	const std::uint64_t errs = err_count_.load(std::memory_order_relaxed);
	if (errs == 1 || (errs & (errs - 1)) == 0) {
		// Powers of two: log 1, 2, 4, 8, 16 etc.
		LogError(ai_, "CoordinatorClient",
		         "Heartbeat failed code=" + std::to_string(status.error_code())
		         + " msg=" + status.error_message()
		         + " err_streak=" + std::to_string(errs));
	}
	return false;
}

void CoordinatorClient::OpenPushStateStream() {
	if (push_stream_open_.load(std::memory_order_acquire)) return;
	push_ctx_ = std::make_unique<::grpc::ClientContext>();
	// Unlike unary Heartbeat, the stream is long-lived. We only set a
	// generous per-write deadline (60 min); a hard deadline would have
	// to be refreshed every match.
	push_ctx_->set_deadline(std::chrono::system_clock::now()
	                        + std::chrono::minutes(60));
	push_writer_ = stub_->PushState(push_ctx_.get(), &push_ack_);
	push_stream_open_.store(true, std::memory_order_release);
	AppendCoordinatorTrace(plugin_id_, "push open");
	LogConnect(ai_, plugin_id_, endpoint_, "client-mode-push-stream");
}

void CoordinatorClient::ClosePushStateStream() {
	if (!push_stream_open_.exchange(false, std::memory_order_acq_rel)) return;
	if (push_writer_) {
		AppendCoordinatorTrace(plugin_id_, "push close begin");
		push_writer_->WritesDone();
		::grpc::Status status = push_writer_->Finish();
		if (status.ok()) {
			AppendCoordinatorTrace(plugin_id_,
			                      "push close ok msgs_rx="
			                      + std::to_string(push_ack_.messages_received())
			                      + " max_seq=" + std::to_string(push_ack_.max_seq_seen()));
			LogError(ai_, "CoordinatorClient",
			         "PushState closed ok msgs_rx="
			         + std::to_string(push_ack_.messages_received())
			         + " max_seq=" + std::to_string(push_ack_.max_seq_seen()));
		} else {
			AppendCoordinatorTrace(plugin_id_,
			                      "push close err code="
			                      + std::to_string(status.error_code())
			                      + " msg=" + status.error_message());
			LogError(ai_, "CoordinatorClient",
			         "PushState closed err code="
			         + std::to_string(status.error_code())
			         + " msg=" + status.error_message());
		}
	}
	push_writer_.reset();
	push_ctx_.reset();
}

void CoordinatorClient::StartCommandChannel(CommandQueue* sink) {
	if (sink == nullptr) return;
	if (cmd_thread_.joinable()) return;  // already started
	AppendCoordinatorTrace(plugin_id_, "cmd thread start requested");
	cmd_thread_ = std::thread(&CoordinatorClient::CommandReaderLoop, this, sink);
}

void CoordinatorClient::CommandReaderLoop(CommandQueue* sink) {
	using ::highbar::v1::CommandBatch;
	using ::highbar::v1::CommandChannelSubscribe;

	// Long-lived read loop. If the server closes the stream (for
	// example during coordinator restart), we attempt a reconnect with
	// exponential backoff up to 5 s. Stops when cmd_stopping_ is set.
	std::uint32_t backoff_ms = 200;
	while (!cmd_stopping_.load(std::memory_order_acquire)) {
		AppendCoordinatorTrace(plugin_id_,
		                      "cmd loop connect attempt backoff_ms="
		                      + std::to_string(backoff_ms));
		cmd_ctx_ = std::make_unique<::grpc::ClientContext>();
		cmd_ctx_->set_deadline(std::chrono::system_clock::now()
		                       + std::chrono::minutes(60));

		CommandChannelSubscribe sub;
		sub.set_plugin_id(plugin_id_);
		sub.set_schema_version(::highbar::v1::kSchemaVersion);

		auto reader = cmd_stub_->OpenCommandChannel(cmd_ctx_.get(), sub);
		if (!reader) {
			AppendCoordinatorTrace(plugin_id_, "cmd loop null reader");
			LogError(ai_, "CoordinatorClient",
			         "OpenCommandChannel returned null reader");
		} else {
			AppendCoordinatorTrace(plugin_id_, "cmd loop reader opened");
			LogConnect(ai_, plugin_id_, endpoint_, "client-mode-cmd-channel");
			CommandBatch batch;
			while (reader->Read(&batch)) {
				AppendCoordinatorTrace(plugin_id_,
				                      "cmd batch read seq="
				                      + std::to_string(batch.batch_seq())
				                      + " ncmds=" + std::to_string(batch.commands_size()));
				cmd_batches_received_.fetch_add(1, std::memory_order_relaxed);
				// Drop each AICommand inside the batch onto the
				// engine-thread queue. The batch carries target_unit_id
				// at the top level AND optionally per-arm — DrainCommandQueue
				// prefers the per-arm when present.
				for (const auto& cmd : batch.commands()) {
					QueuedCommand q;
					q.session_id = plugin_id_ + "-cmd-ch";
					q.authoritative_target_unit_id =
						static_cast<std::int32_t>(batch.target_unit_id());
					q.command = cmd;
					if (!sink->TryPush(std::move(q))) {
						AppendCoordinatorTrace(plugin_id_, "cmd queue full drop");
						// Queue full — drop and log.
						LogError(ai_, "CoordinatorClient",
						         "CommandQueue full; dropping command");
						break;
					}
					cmd_commands_received_.fetch_add(1, std::memory_order_relaxed);
				}
				AppendCoordinatorTrace(plugin_id_,
				                      "cmd batch processed seq="
				                      + std::to_string(batch.batch_seq()));
			}
			AppendCoordinatorTrace(plugin_id_, "cmd read loop ended");
			LogDisconnect(ai_, plugin_id_, "cmd-channel-read-closed");
			::grpc::Status st = reader->Finish();
			if (st.ok()) {
				AppendCoordinatorTrace(plugin_id_, "cmd finish ok");
				LogDisconnect(ai_, plugin_id_, "cmd-channel-finish-ok");
			} else if (st.error_code() == ::grpc::StatusCode::CANCELLED) {
				AppendCoordinatorTrace(plugin_id_, "cmd finish cancelled");
				LogDisconnect(ai_, plugin_id_, "cmd-channel-finish-cancelled");
				break;  // shutdown — stop the loop
			} else {
				AppendCoordinatorTrace(plugin_id_,
				                      "cmd finish err code="
				                      + std::to_string(st.error_code())
				                      + " msg=" + st.error_message());
				LogDisconnect(ai_, plugin_id_,
				              "cmd-channel-finish-code="
				              + std::to_string(st.error_code()));
				LogError(ai_, "CoordinatorClient",
				         "cmd channel err code="
				         + std::to_string(st.error_code())
				         + " msg=" + st.error_message());
			}
		}

		if (cmd_stopping_.load(std::memory_order_acquire)) break;
		AppendCoordinatorTrace(plugin_id_,
		                      "cmd loop sleeping backoff_ms="
		                      + std::to_string(backoff_ms));
		// Sleep backoff before retry (but check stopping again).
		for (std::uint32_t i = 0;
		     i < backoff_ms && !cmd_stopping_.load(std::memory_order_acquire);
		     i += 50) {
			std::this_thread::sleep_for(std::chrono::milliseconds(50));
		}
		backoff_ms = std::min<std::uint32_t>(backoff_ms * 2, 5000);
	}
	AppendCoordinatorTrace(plugin_id_, "cmd loop exit");
}

bool CoordinatorClient::PushStateUpdate(const ::highbar::v1::StateUpdate& update) {
	if (!push_stream_open_.load(std::memory_order_acquire)) {
		OpenPushStateStream();
	}
	if (!push_writer_) return false;

	// Constitution V instrumentation: stamp CLOCK_MONOTONIC_ns at the
	// moment we hand the frame to gRPC. The proto field is uint64
	// send_monotonic_ns; external clients diff against their recv
	// time for p99 round-trip (tests/bench/latency-*.sh).
	::highbar::v1::StateUpdate stamped(update);
	{
		struct timespec ts;
		clock_gettime(CLOCK_MONOTONIC, &ts);
		stamped.set_send_monotonic_ns(
			static_cast<std::uint64_t>(ts.tv_sec) * 1000000000ULL
			+ static_cast<std::uint64_t>(ts.tv_nsec));
	}

	// gRPC ClientWriter::Write returns false if the RPC is already
	// broken; handle by closing the stream and letting the caller's
	// next frame re-open lazily (if endpoint is back up).
	if (!push_writer_->Write(stamped)) {
		const std::uint64_t pushed = pushed_count_.load();
		AppendCoordinatorTrace(plugin_id_,
		                      "push write failed after="
		                      + std::to_string(pushed));
		ClosePushStateStream();
		LogError(ai_, "CoordinatorClient",
		         "PushState stream broken after "
		         + std::to_string(pushed) + " messages");
		return false;
	}
	pushed_count_.fetch_add(1, std::memory_order_relaxed);
	return true;
}

}  // namespace circuit::grpc

// SPDX-License-Identifier: GPL-2.0-only
//
// Client-mode gRPC surface: the plugin opens a channel to an external
// coordinator and sends heartbeats. Sidesteps the gRPC 1.76 EventEngine
// listener bug inside spring-headless (see
// specs/002-live-headless-e2e/investigations/hello-rpc-deadline-exceeded.md).

#pragma once

#include <grpcpp/grpcpp.h>

#include "highbar/coordinator.grpc.pb.h"
#include "highbar/state.pb.h"
#include "highbar/commands.pb.h"

#include <atomic>
#include <memory>
#include <string>
#include <thread>

namespace circuit {
class CCircuitAI;
}  // namespace circuit

namespace circuit::grpc {

class CommandQueue;

class CoordinatorClient {
public:
	// `endpoint` is a gRPC URI: "unix:/path" or "localhost:port".
	// `plugin_id` is a per-match identifier (e.g., the gameseed).
	CoordinatorClient(::circuit::CCircuitAI* ai,
	                  const std::string& endpoint,
	                  const std::string& plugin_id,
	                  const std::string& engine_sha256);
	~CoordinatorClient();

	CoordinatorClient(const CoordinatorClient&) = delete;
	CoordinatorClient& operator=(const CoordinatorClient&) = delete;

	// Call from OnFrameTick every N frames. Blocking-but-fast:
	// 250ms deadline. Returns true on OK reply, false on RPC error.
	// Engine-thread-only — no background threads.
	bool SendHeartbeat(std::uint32_t frame);

	// Phase B — stream a StateUpdate to the coordinator. Lazily opens
	// the client-streaming RPC on first call. Non-blocking (as
	// non-blocking as gRPC's client writer; flow-control may pause
	// briefly under extreme backpressure — call from the engine thread
	// but don't rely on bounded completion time).
	bool PushStateUpdate(const ::highbar::v1::StateUpdate& update);

	// Phase C — open the server-streaming command channel. Spawns a
	// background reader thread that calls `sink->TryPush(QueuedCommand)`
	// for every AICommand inside every CommandBatch the coordinator
	// sends. Sink is the engine-thread CommandQueue; DrainCommandQueue
	// picks commands up at the top of each frame tick.
	void StartCommandChannel(CommandQueue* sink);

	bool IsConnected() const { return connected_.load(std::memory_order_acquire); }
	std::uint64_t OkCount() const { return ok_count_.load(std::memory_order_acquire); }
	std::uint64_t ErrCount() const { return err_count_.load(std::memory_order_acquire); }
	std::uint64_t PushedCount() const { return pushed_count_.load(std::memory_order_acquire); }

private:
	void OpenPushStateStream();   // lazy; idempotent.
	void ClosePushStateStream();  // called from dtor; safe if stream never opened.

	::circuit::CCircuitAI* ai_;
	std::string endpoint_;
	std::string plugin_id_;
	std::string engine_sha256_;
	std::shared_ptr<::grpc::Channel> channel_;
	std::unique_ptr<::highbar::v1::HighBarCoordinator::Stub> stub_;
	std::atomic<bool> connected_{false};
	std::atomic<std::uint64_t> ok_count_{0};
	std::atomic<std::uint64_t> err_count_{0};

	// PushState stream — one per lifetime, opened lazily.
	std::unique_ptr<::grpc::ClientContext> push_ctx_;
	::highbar::v1::PushAck push_ack_;
	std::unique_ptr<::grpc::ClientWriter<::highbar::v1::StateUpdate>> push_writer_;
	std::atomic<bool> push_stream_open_{false};
	std::atomic<std::uint64_t> pushed_count_{0};

	// OpenCommandChannel reader — background thread. Owned lifetime
	// flows: StartCommandChannel starts it, dtor cancels + joins.
	void CommandReaderLoop(CommandQueue* sink);
	std::unique_ptr<::grpc::ClientContext> cmd_ctx_;
	std::thread cmd_thread_;
	std::atomic<bool> cmd_stopping_{false};
	std::atomic<std::uint64_t> cmd_batches_received_{0};
	std::atomic<std::uint64_t> cmd_commands_received_{0};
};

}  // namespace circuit::grpc

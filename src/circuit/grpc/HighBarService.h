// SPDX-License-Identifier: GPL-2.0-only
//
// HighBarV3 — async gRPC server (T023-T025, T029).
//
// Wraps the generated HighBarProxy::AsyncService with a Bind() entry
// point, a completion-queue worker pool, and CallData state machines
// for the 7 RPCs. Hello (T025) and GetRuntimeCounters (T029) are
// functionally implemented; StreamState, SubmitCommands,
// InvokeCallback, Save, Load return UNIMPLEMENTED until US1/US2 fill
// them. AuthInterceptorFactory is installed at Bind time so the
// AI-token gate applies even to UNIMPLEMENTED stubs.

#pragma once

#include <grpcpp/grpcpp.h>

#include "highbar/service.grpc.pb.h"
#include "grpc/Config.h"

#include <atomic>
#include <memory>
#include <shared_mutex>
#include <string>
#include <thread>
#include <vector>

namespace circuit {
class CCircuitAI;
}  // namespace circuit

namespace highbar::v1 {
class AICommand;
class CommandBatch;
}  // namespace highbar::v1

namespace circuit::grpc {

class AuthToken;
class CommandQueue;
class Counters;
class SnapshotBuilder;
class DeltaBus;
class RingBuffer;

// Outcome of server-side AICommand validation (T056).
enum class ValidationError {
	kOk,
	kTargetUnitNotFound,
	kBuildDefNotConstructible,
	kPositionOutOfMap,
};

class HighBarService final : public ::highbar::v1::HighBarProxy::AsyncService {
public:
	HighBarService(::circuit::CCircuitAI* ai,
	               Counters* counters,
	               const AuthToken* token);
	~HighBarService();

	HighBarService(const HighBarService&) = delete;
	HighBarService& operator=(const HighBarService&) = delete;

	// Binds the service on the configured transport. UDS at
	// foundational (T024); TCP lands in US4 (T073). Starts one CQ
	// worker thread. Returns when the server is accepting connections
	// or throws std::runtime_error on failure (fail-closed FR-003a).
	//
	// `bound_address` is an out-param receiving the resolved bind
	// address for logging (e.g., `unix:/run/user/1000/highbar-42.sock`).
	void Bind(const TransportEndpoint& endpoint,
	          std::string* bound_address);

	// Graceful shutdown. Blocks until all in-flight RPCs drain or the
	// deadline expires. Called from CGrpcGatewayModule::Release.
	void Shutdown(std::chrono::milliseconds deadline
	              = std::chrono::milliseconds(2000));

	// Wire the US1 handles post-Bind. Called once by
	// CGrpcGatewayModule's ctor after both this service and the US1
	// pieces are alive. All pointers must outlive this service.
	void SetUs1Handles(SnapshotBuilder* snapshot,
	                   DeltaBus* bus,
	                   RingBuffer* ring,
	                   std::shared_mutex* state_mutex);

	// Wire the US2 handle (CommandQueue, T055). Producers are gRPC
	// workers inside SubmitCommandsCallData; the consumer is the engine
	// thread via CGrpcGatewayModule::OnFrameTick.
	void SetUs2Handles(CommandQueue* queue);

	// Server-side validation for a single AICommand (T056). Called from
	// SubmitCommandsCallData's Read loop — the gRPC worker thread.
	// Takes a shared_lock on state_mutex_ internally.
	ValidationError ValidateCommand(std::uint32_t target_unit_id,
	                                const ::highbar::v1::AICommand& cmd) const;

	// Framesince-bind counter is bumped by CGrpcGatewayModule's
	// frame-update hook (T026). The service reads it for
	// GetRuntimeCounters and advancing-uptime logic in Hello.
	void AdvanceFrame();

	// Observer cap / AI-slot accessors. Full enforcement lands in
	// US1 (T040) and US2 (T059). For Phase 2 they short-circuit
	// to always-accept; the structure is here so CallData classes
	// call them consistently.
	bool TryReserveObserverSlot();
	void ReleaseObserverSlot();
	bool TryClaimAiSlot();
	void ReleaseAiSlot();

private:
	// ---- Async RPC dispatch ----
	//
	// Each RPC has a CallData subclass that owns its ServerContext,
	// responders, and tag lifecycle. We register ONE pending instance
	// of each unary RPC at Bind time; each instance replaces itself
	// once it progresses from PROCESSING → FINISHING.

	class CallDataBase;
	template <class Derived> class UnaryCallData;

	class HelloCallData;
	class GetRuntimeCountersCallData;
	class StreamStateCallData;
	class SubmitCommandsCallData;
	class InvokeCallbackCallData;
	class SaveCallData;
	class LoadCallData;

	void CqWorker();
	static std::string NewSessionId();

	::circuit::CCircuitAI* ai_;
	Counters* counters_;
	const AuthToken* token_;

	// US1 handles (set via SetUs1Handles; null until the gateway
	// wires them in post-Bind). HelloCallData reads SnapshotBuilder
	// under `*state_mutex_` (shared lock) to populate StaticMap.
	// StreamStateCallData (T040, follow-up) consumes all four.
	SnapshotBuilder* snapshot_ = nullptr;
	DeltaBus* delta_bus_ = nullptr;
	RingBuffer* ring_ = nullptr;
	std::shared_mutex* state_mutex_ = nullptr;

	// US2 handles (set via SetUs2Handles; null until wired post-Bind).
	CommandQueue* command_queue_ = nullptr;

	std::unique_ptr<::grpc::ServerCompletionQueue> cq_;
	std::unique_ptr<::grpc::Server> server_;
	std::vector<std::thread> cq_workers_;
	std::atomic<bool> shutting_down_{false};

	// Session tracking (skeletal — filled in by US1/US2).
	std::atomic<std::uint32_t> observer_count_{0};
	std::atomic<bool> ai_slot_taken_{false};
	std::atomic<std::uint32_t> frames_since_bind_{0};

	static constexpr std::uint32_t kObserverHardCap = 4;  // FR-015a
};

}  // namespace circuit::grpc

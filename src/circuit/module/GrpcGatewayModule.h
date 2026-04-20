// SPDX-License-Identifier: GPL-2.0-only
//
// HighBarV3 — IModule wrapper that owns the gRPC gateway (T016, plus
// US1 extensions T036/T037/T038/T039/T042).
//
// Construction loads data/config/grpc.json, generates and writes the
// AI auth token, binds the gRPC server, and wires:
//   * SnapshotBuilder     — materializes StateSnapshot on subscribe.
//   * DeltaBus + SubscriberSlot — per-subscriber fan-out rings.
//   * RingBuffer          — 2048-entry resume-history buffer.
//   * state_mutex_        — shared/exclusive lock separating engine
//                           writers from worker snapshot reads (T036).
//   * current_frame_delta_ — per-frame StateDelta accumulator.
//
// IModule event handlers (UnitCreated, UnitDamaged, …) and the
// non-virtual On*Event methods append typed DeltaEvents to
// current_frame_delta_ on the engine thread (T037). OnFrameTick
// serializes the delta, pushes to RingBuffer, publishes through
// DeltaBus, clears the accumulator (T038). If no delta flushed for
// `kKeepAliveFrames` frames the tick emits a KeepAlive instead
// (T039, data-model §2).

#pragma once

#include "module/Module.h"

#include <cstdint>
#include <memory>
#include <shared_mutex>
#include <string>

#include "highbar/state.pb.h"

namespace circuit::grpc {
class HighBarService;
class Counters;
class AuthToken;
class CommandQueue;
class SnapshotBuilder;
class DeltaBus;
class RingBuffer;
}  // namespace circuit::grpc

namespace circuit {

class CGrpcGatewayModule final : public IModule {
public:
	explicit CGrpcGatewayModule(CCircuitAI* circuit);
	~CGrpcGatewayModule() override;

	CGrpcGatewayModule(const CGrpcGatewayModule&) = delete;
	CGrpcGatewayModule& operator=(const CGrpcGatewayModule&) = delete;

	// IModule event hooks (T037 — append to current_frame_delta_).
	int UnitCreated(CCircuitUnit* unit, CCircuitUnit* builder) override;
	int UnitFinished(CCircuitUnit* unit) override;
	int UnitIdle(CCircuitUnit* unit) override;
	int UnitDamaged(CCircuitUnit* unit, CEnemyInfo* attacker) override;
	int UnitDestroyed(CCircuitUnit* unit, CEnemyInfo* attacker) override;
	int UnitGiven(CCircuitUnit* unit, int oldTeamId, int newTeamId) override;
	int UnitCaptured(CCircuitUnit* unit, int oldTeamId, int newTeamId) override;

	// Non-virtual on CircuitAI side (invoked from CircuitAI.cpp's
	// event dispatch — wiring of those call sites is a follow-up
	// upstream-shared edit; at Phase 2 the gateway simply provides
	// the hook points).
	void OnUnitMoveFailed(CCircuitUnit* unit);
	void OnEnemyEnterLOS(CEnemyInfo* enemy);
	void OnEnemyLeaveLOS(CEnemyInfo* enemy);
	void OnEnemyEnterRadar(CEnemyInfo* enemy);
	void OnEnemyLeaveRadar(CEnemyInfo* enemy);
	void OnEnemyDamaged(CEnemyInfo* enemy);
	void OnEnemyDestroyed(CEnemyInfo* enemy);
	void OnFeatureCreated(int feature_id, int def_id,
	                      float px, float py, float pz);
	void OnFeatureDestroyed(int feature_id);
	void OnEconomyTick();  // called from OnFrameTick every kEconomyEveryNFrames

	// Frame tick — registered in ctor via CScheduler::RunJobEvery. On
	// every frame: drains (future) CommandQueue, serializes delta,
	// publishes, emits KeepAlive on quiet, advances counters.
	void OnFrameTick();

	// Accessors for HighBarService (Hello's StaticMap + StreamState's
	// subscribe). Non-null for the lifetime of the module.
	::circuit::grpc::SnapshotBuilder* GetSnapshotBuilder() { return snapshot_.get(); }
	::circuit::grpc::DeltaBus*        GetDeltaBus()        { return delta_bus_.get(); }
	::circuit::grpc::RingBuffer*      GetRingBuffer()      { return ring_.get(); }
	std::shared_mutex&                StateMutex()         { return state_mutex_; }
	std::uint64_t                     HeadSeq() const;

private:
	// Per-frame delta accumulator (T037/T038). Mutated on engine
	// thread only, so no lock needed for reads/writes from handlers.
	::highbar::v1::StateDelta current_frame_delta_;

	// Monotonic sequence across snapshot resets (data-model §2
	// invariants). Engine-thread only.
	std::uint64_t seq_ = 0;

	// KeepAlive quiet window: emit KeepAlive if no delta flushed for
	// this many frames. Default 1 second at 30Hz sim.
	static constexpr std::uint32_t kKeepAliveFrames = 30;
	std::uint32_t frames_since_last_flush_ = 0;

	// Shared/exclusive lock separating engine-thread delta publish
	// (exclusive) from worker-thread snapshot builds (shared). Writers
	// never block on gRPC I/O (research §3).
	std::shared_mutex state_mutex_;

	// Owning pointers. unique_ptr keeps gRPC headers out of this one.
	std::unique_ptr<grpc::AuthToken> token_;
	std::unique_ptr<grpc::Counters> counters_;
	std::unique_ptr<grpc::SnapshotBuilder> snapshot_;
	std::unique_ptr<grpc::DeltaBus> delta_bus_;
	std::unique_ptr<grpc::RingBuffer> ring_;
	std::unique_ptr<grpc::CommandQueue> command_queue_;
	std::unique_ptr<grpc::HighBarService> service_;

	std::string bound_address_;

	// T038 helper: serialize + publish current_frame_delta_.
	// Called from OnFrameTick under the exclusive lock.
	void FlushDelta();
	// T039 helper: emit a KeepAlive StateUpdate on the bus + ring.
	void EmitKeepAlive();
	// T057: drain the CommandQueue and dispatch each AICommand to the
	// matching CCircuitUnit::Cmd* method. Engine-thread only.
	void DrainCommandQueue();
};

}  // namespace circuit

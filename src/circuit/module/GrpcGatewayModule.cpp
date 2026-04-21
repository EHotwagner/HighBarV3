// SPDX-License-Identifier: GPL-2.0-only
//
// HighBarV3 — GrpcGatewayModule impl (T016, T017, T026, T030,
// plus US1 extensions T036/T037/T038/T039/T042).

#include "module/GrpcGatewayModule.h"

#include "grpc/AuthToken.h"
#include "grpc/CommandDispatch.h"
#include "grpc/CommandQueue.h"
#include "grpc/Config.h"
#include "grpc/Counters.h"
#include "grpc/DeltaBus.h"
#include "grpc/HighBarService.h"
#include "grpc/Log.h"
#include "grpc/RingBuffer.h"
#include "grpc/SchemaVersion.h"
#include "grpc/SnapshotBuilder.h"

#include "CircuitAI.h"
#include "scheduler/Scheduler.h"
#include "unit/CircuitUnit.h"
#include "unit/CircuitDef.h"
#include "unit/enemy/EnemyInfo.h"
#include "util/FileSystem.h"

#include <chrono>
#include <exception>
#include <memory>
#include <stdexcept>
#include <string>

namespace circuit {

namespace {

std::string ResolveTokenPath(CCircuitAI* ai, const std::string& template_path) {
	constexpr const char* kMarker = "$writeDir/";
	const auto pos = template_path.find(kMarker);
	if (pos != 0) {
		return template_path;
	}
	std::string rel = template_path.substr(std::char_traits<char>::length(kMarker));
	if (utils::LocatePath(ai->GetCallback(), rel)) {
		return rel;
	}
	const char* tmp = std::getenv("TMPDIR");
	return (tmp != nullptr ? std::string(tmp) : std::string("/tmp"))
	       + "/highbar.token";
}

std::uint64_t NowMicros() {
	using namespace std::chrono;
	return static_cast<std::uint64_t>(
		duration_cast<microseconds>(steady_clock::now().time_since_epoch()).count());
}

}  // namespace

CGrpcGatewayModule::CGrpcGatewayModule(CCircuitAI* ai)
	: IModule(ai, /*script=*/nullptr) {

	try {
		auto endpoint = grpc::LoadTransportConfig(ai);
		if (endpoint.transport == grpc::Transport::kUds) {
			grpc::ResolveUdsPath(endpoint, ai);
		}

		const std::string token_path = ResolveTokenPath(ai, endpoint.ai_token_path);
		token_ = std::make_unique<grpc::AuthToken>(
			grpc::AuthToken::Generate(token_path));

		counters_ = std::make_unique<grpc::Counters>();

		// US1 pieces.
		snapshot_ = std::make_unique<grpc::SnapshotBuilder>(ai);
		delta_bus_ = std::make_unique<grpc::DeltaBus>(counters_.get());
		ring_ = std::make_unique<grpc::RingBuffer>(endpoint.ring_size);

		// US2 pieces (T055 + T057 command path).
		command_queue_ = std::make_unique<grpc::CommandQueue>(counters_.get());

		service_ = std::make_unique<grpc::HighBarService>(
			ai, counters_.get(), token_.get());
		// HighBarService needs the US1 handles. Public setters wire
		// them post-construction so the ctor stays non-failing for
		// environments where the gateway runs without a full US1
		// implementation (see HighBarService::SetUs1Handles).
		service_->SetUs1Handles(snapshot_.get(), delta_bus_.get(),
		                        ring_.get(), &state_mutex_);
		service_->SetUs2Handles(command_queue_.get());
		service_->Bind(endpoint, &bound_address_);

		const std::string transport_name =
			endpoint.transport == grpc::Transport::kUds ? "uds" : "tcp";
		grpc::LogStartup(ai, transport_name, bound_address_,
		                 ::highbar::v1::kSchemaVersion);

		ai->GetScheduler()->RunJobEvery(
			CScheduler::GameJob(&CGrpcGatewayModule::OnFrameTick, this),
			/*frameInterval=*/1, /*frameOffset=*/0);

	} catch (const std::exception& e) {
		grpc::LogFatalAndFailClosed(ai, "CGrpcGatewayModule::ctor", e.what());
		throw;
	}
}

CGrpcGatewayModule::~CGrpcGatewayModule() {
	try {
		if (service_) service_->Shutdown();
		if (counters_ && circuit != nullptr) {
			grpc::LogShutdown(circuit, counters_->frames_since_bind.load());
		}
		if (token_) token_->Unlink();
	} catch (const std::exception& e) {
		if (circuit != nullptr) {
			grpc::LogError(circuit, "CGrpcGatewayModule::dtor", e.what());
		}
	} catch (...) {
		if (circuit != nullptr) {
			grpc::LogError(circuit, "CGrpcGatewayModule::dtor", "unknown exception");
		}
	}
}

// ============================================================================
// IModule event hooks (T037)
// ============================================================================
//
// All hooks run on the engine thread. They append typed DeltaEvents
// to current_frame_delta_ without locking — current_frame_delta_ is
// engine-thread-owned. The shared/exclusive lock is taken in
// OnFrameTick, not here.

namespace {

void SetVec3(::highbar::v1::Vector3* dst, const springai::AIFloat3& src) {
	dst->set_x(src.x);
	dst->set_y(src.y);
	dst->set_z(src.z);
}

}  // namespace

int CGrpcGatewayModule::UnitCreated(CCircuitUnit* unit, CCircuitUnit* builder) {
	if (unit == nullptr) return 0;
	auto* ev = current_frame_delta_.add_events()->mutable_unit_created();
	ev->set_unit_id(static_cast<std::int32_t>(unit->GetId()));
	ev->set_builder_id(
		builder != nullptr ? static_cast<std::int32_t>(builder->GetId()) : 0);
	return 0;
}

int CGrpcGatewayModule::UnitFinished(CCircuitUnit* unit) {
	if (unit == nullptr) return 0;
	auto* ev = current_frame_delta_.add_events()->mutable_unit_finished();
	ev->set_unit_id(static_cast<std::int32_t>(unit->GetId()));
	return 0;
}

int CGrpcGatewayModule::UnitIdle(CCircuitUnit* unit) {
	if (unit == nullptr) return 0;
	auto* ev = current_frame_delta_.add_events()->mutable_unit_idle();
	ev->set_unit_id(static_cast<std::int32_t>(unit->GetId()));
	return 0;
}

int CGrpcGatewayModule::UnitDamaged(CCircuitUnit* unit, CEnemyInfo* attacker) {
	if (unit == nullptr) return 0;
	auto* ev = current_frame_delta_.add_events()->mutable_unit_damaged();
	ev->set_unit_id(static_cast<std::int32_t>(unit->GetId()));
	if (attacker != nullptr) {
		ev->set_attacker_id(static_cast<std::int32_t>(attacker->GetId()));
	}
	// damage / direction / weapon_def_id / is_paralyzer: IModule's
	// UnitDamaged(unit, attacker) signature doesn't carry these; the
	// richer signature lives on CCircuitAI::UnitDamaged. US1 T037
	// follow-up routes the richer event via an On*Event method if
	// observers need the full payload.
	return 0;
}

int CGrpcGatewayModule::UnitDestroyed(CCircuitUnit* unit, CEnemyInfo* attacker) {
	if (unit == nullptr) return 0;
	auto* ev = current_frame_delta_.add_events()->mutable_unit_destroyed();
	ev->set_unit_id(static_cast<std::int32_t>(unit->GetId()));
	if (attacker != nullptr) {
		ev->set_attacker_id(static_cast<std::int32_t>(attacker->GetId()));
	}
	return 0;
}

int CGrpcGatewayModule::UnitGiven(CCircuitUnit* unit, int oldTeam, int newTeam) {
	if (unit == nullptr) return 0;
	auto* ev = current_frame_delta_.add_events()->mutable_unit_given();
	ev->set_unit_id(static_cast<std::int32_t>(unit->GetId()));
	ev->set_old_team_id(oldTeam);
	ev->set_new_team_id(newTeam);
	return 0;
}

int CGrpcGatewayModule::UnitCaptured(CCircuitUnit* unit, int oldTeam, int newTeam) {
	if (unit == nullptr) return 0;
	auto* ev = current_frame_delta_.add_events()->mutable_unit_captured();
	ev->set_unit_id(static_cast<std::int32_t>(unit->GetId()));
	ev->set_old_team_id(oldTeam);
	ev->set_new_team_id(newTeam);
	return 0;
}

void CGrpcGatewayModule::OnUnitMoveFailed(CCircuitUnit* unit) {
	if (unit == nullptr) return;
	auto* ev = current_frame_delta_.add_events()->mutable_unit_move_failed();
	ev->set_unit_id(static_cast<std::int32_t>(unit->GetId()));
}

void CGrpcGatewayModule::OnEnemyEnterLOS(CEnemyInfo* enemy) {
	if (enemy == nullptr) return;
	auto* ev = current_frame_delta_.add_events()->mutable_enemy_enter_los();
	ev->set_enemy_id(static_cast<std::int32_t>(enemy->GetId()));
}

void CGrpcGatewayModule::OnEnemyLeaveLOS(CEnemyInfo* enemy) {
	if (enemy == nullptr) return;
	auto* ev = current_frame_delta_.add_events()->mutable_enemy_leave_los();
	ev->set_enemy_id(static_cast<std::int32_t>(enemy->GetId()));
}

void CGrpcGatewayModule::OnEnemyEnterRadar(CEnemyInfo* enemy) {
	if (enemy == nullptr) return;
	auto* ev = current_frame_delta_.add_events()->mutable_enemy_enter_radar();
	ev->set_enemy_id(static_cast<std::int32_t>(enemy->GetId()));
}

void CGrpcGatewayModule::OnEnemyLeaveRadar(CEnemyInfo* enemy) {
	if (enemy == nullptr) return;
	auto* ev = current_frame_delta_.add_events()->mutable_enemy_leave_radar();
	ev->set_enemy_id(static_cast<std::int32_t>(enemy->GetId()));
}

void CGrpcGatewayModule::OnEnemyDamaged(CEnemyInfo* enemy) {
	if (enemy == nullptr) return;
	auto* ev = current_frame_delta_.add_events()->mutable_enemy_damaged();
	ev->set_enemy_id(static_cast<std::int32_t>(enemy->GetId()));
}

void CGrpcGatewayModule::OnEnemyDestroyed(CEnemyInfo* enemy) {
	if (enemy == nullptr) return;
	auto* ev = current_frame_delta_.add_events()->mutable_enemy_destroyed();
	ev->set_enemy_id(static_cast<std::int32_t>(enemy->GetId()));
}

void CGrpcGatewayModule::OnFeatureCreated(int feature_id, int def_id,
                                           float px, float py, float pz) {
	auto* ev = current_frame_delta_.add_events()->mutable_feature_created();
	ev->set_feature_id(static_cast<std::uint32_t>(feature_id));
	ev->set_def_id(static_cast<std::uint32_t>(def_id));
	ev->mutable_position()->set_x(px);
	ev->mutable_position()->set_y(py);
	ev->mutable_position()->set_z(pz);
}

void CGrpcGatewayModule::OnFeatureDestroyed(int feature_id) {
	auto* ev = current_frame_delta_.add_events()->mutable_feature_destroyed();
	ev->set_feature_id(static_cast<std::uint32_t>(feature_id));
}

void CGrpcGatewayModule::OnEconomyTick() {
	// Aggregate economy into a single EconomyTick event. Called from
	// OnFrameTick so the rate is bounded.
	auto* ev = current_frame_delta_.add_events()->mutable_economy_tick();
	auto* em = circuit->GetEconomyManager();
	if (em == nullptr) return;
	ev->set_metal(em->GetMetalCur());
	ev->set_metal_storage(em->GetMetalStore());
	ev->set_metal_usage(em->GetMetalPull());
	ev->set_energy(em->GetEnergyCur());
	ev->set_energy_storage(em->GetEnergyStore());
	ev->set_energy_usage(em->GetEnergyPull());
	// income fields: left 0 until verified accessor lands.
}

// ============================================================================
// Frame tick (T026 + T038 + T039)
// ============================================================================

void CGrpcGatewayModule::OnFrameTick() {
	if (service_) service_->AdvanceFrame();

	// T057: drain external-AI commands at the top of the frame so
	// they land in the engine this tick. Engine-thread only.
	DrainCommandQueue();

	// Emit an EconomyTick every 30 frames (1s at 30Hz). Keeps the
	// observers' economy plot moving without flooding the delta stream.
	static constexpr std::uint32_t kEconomyEveryNFrames = 30;
	const auto frames = counters_ != nullptr
		? counters_->frames_since_bind.load() : 0u;
	if (frames > 0 && frames % kEconomyEveryNFrames == 0) {
		OnEconomyTick();
	}

	// T038: flush accumulated delta. Take the exclusive lock only for
	// the serialize-and-publish step; the append path above is
	// engine-thread-owned and holds nothing.
	if (current_frame_delta_.events_size() > 0) {
		FlushDelta();
		frames_since_last_flush_ = 0;
	} else {
		++frames_since_last_flush_;
		if (frames_since_last_flush_ >= kKeepAliveFrames) {
			EmitKeepAlive();
			frames_since_last_flush_ = 0;
		}
	}
}

void CGrpcGatewayModule::FlushDelta() {
	const std::uint64_t t0 = NowMicros();

	::highbar::v1::StateUpdate update;
	update.set_seq(++seq_);
	update.set_frame(static_cast<std::uint32_t>(circuit->GetLastFrame()));
	*update.mutable_delta() = std::move(current_frame_delta_);
	current_frame_delta_.Clear();

	auto payload = std::make_shared<std::string>();
	update.SerializeToString(payload.get());
	auto frozen = std::const_pointer_cast<const std::string>(payload);

	{
		std::unique_lock<std::shared_mutex> lock(state_mutex_);
		ring_->Push(seq_, frozen);
	}
	delta_bus_->Publish(frozen);

	if (counters_ != nullptr) {
		counters_->RecordFrameFlushUs(NowMicros() - t0);
	}
}

void CGrpcGatewayModule::EmitKeepAlive() {
	::highbar::v1::StateUpdate update;
	update.set_seq(++seq_);
	update.set_frame(static_cast<std::uint32_t>(circuit->GetLastFrame()));
	update.mutable_keepalive();

	auto payload = std::make_shared<std::string>();
	update.SerializeToString(payload.get());
	auto frozen = std::const_pointer_cast<const std::string>(payload);

	{
		std::unique_lock<std::shared_mutex> lock(state_mutex_);
		ring_->Push(seq_, frozen);
	}
	delta_bus_->Publish(frozen);
}

std::uint64_t CGrpcGatewayModule::HeadSeq() const {
	return ring_ ? ring_->HeadSeq() : 0;
}

// ============================================================================
// Command drain (T057)
// ============================================================================
//
// Called from OnFrameTick at the top of every frame. Pulls queued
// commands out of the MPSC CommandQueue and dispatches each to the
// matching CCircuitUnit::Cmd*. Re-resolves the target unit here
// rather than trusting the worker-thread validation result — a unit
// can die between validate-at-submission and drain-at-frame.
void CGrpcGatewayModule::DrainCommandQueue() {
	if (command_queue_ == nullptr || circuit == nullptr) return;

	std::vector<grpc::QueuedCommand> batch;
	const std::size_t drained = command_queue_->Drain(&batch);
	if (drained == 0) return;

	for (auto& entry : batch) {
		// The proto CommandBatch carried target_unit_id; the per-command
		// proto arms redundantly re-carry unit_id. We prefer the
		// sub-command's unit_id when the arm has one (covers the
		// heterogeneous-batch escape hatch).
		const auto& cmd = entry.command;
		std::int32_t target_id = 0;
		using C = ::highbar::v1::AICommand;
		switch (cmd.command_case()) {
		case C::kBuildUnit:       target_id = cmd.build_unit().unit_id(); break;
		case C::kStop:            target_id = cmd.stop().unit_id(); break;
		case C::kWait:            target_id = cmd.wait().unit_id(); break;
		case C::kMoveUnit:        target_id = cmd.move_unit().unit_id(); break;
		case C::kPatrol:          target_id = cmd.patrol().unit_id(); break;
		case C::kFight:           target_id = cmd.fight().unit_id(); break;
		case C::kAttack:          target_id = cmd.attack().unit_id(); break;
		case C::kAttackArea:      target_id = cmd.attack_area().unit_id(); break;
		case C::kGuard:           target_id = cmd.guard().unit_id(); break;
		case C::kRepair:          target_id = cmd.repair().unit_id(); break;
		case C::kReclaimUnit:     target_id = cmd.reclaim_unit().unit_id(); break;
		case C::kReclaimInArea:   target_id = cmd.reclaim_in_area().unit_id(); break;
		case C::kResurrectInArea: target_id = cmd.resurrect_in_area().unit_id(); break;
		case C::kSelfDestruct:    target_id = cmd.self_destruct().unit_id(); break;
		case C::kSetWantedMaxSpeed: target_id = cmd.set_wanted_max_speed().unit_id(); break;
		case C::kSetFireState:    target_id = cmd.set_fire_state().unit_id(); break;
		case C::kSetMoveState:    target_id = cmd.set_move_state().unit_id(); break;
		default: break;
		}
		if (target_id <= 0) continue;

		auto* unit = circuit->GetTeamUnit(target_id);
		if (unit == nullptr || unit->IsDead()) continue;

		grpc::DispatchCommand(circuit, unit, cmd);
	}
}

}  // namespace circuit

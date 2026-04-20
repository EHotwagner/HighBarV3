// SPDX-License-Identifier: GPL-2.0-only
//
// HighBarV3 — GrpcGatewayModule impl (T016, T017, T026, T030,
// plus US1 extensions T036/T037/T038/T039/T042).

#include "module/GrpcGatewayModule.h"

#include "grpc/AuthToken.h"
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

		// US2: command path (T055/T057).
		command_queue_ = std::make_unique<grpc::CommandQueue>();

		service_ = std::make_unique<grpc::HighBarService>(
			ai, counters_.get(), token_.get());
		// HighBarService needs the US1/US2 handles. Public setters wire
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

	// T057: drain command queue first — each queued AICommand dispatches
	// through CCircuitUnit::Cmd*. Engine-thread only.
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
// Command dispatch (T057)
// ============================================================================
//
// DrainAll() runs on the engine thread. For each queued command we
//   (1) re-resolve target_unit_id under ownership (TOCTOU guard — the
//       gRPC-worker validate could observe a unit that dies before the
//       frame ticks), and
//   (2) translate the AICommand oneof arm to the matching CCircuitUnit::Cmd*
//       call. Non-unit arms (drawing, chat, pathfinding, lua, groups) are
//       silently skipped — those carry no engine-thread unit-scope side
//       effect to dispatch.
//
// Engine-thread only. No locks needed: teamUnits / CircuitDef lookups
// are pure engine state, and the queue itself is MPSC-safe via its own
// mutex.

namespace {

using ::springai::AIFloat3;

inline AIFloat3 ToAIFloat3(const ::highbar::v1::Vector3& v) {
	return AIFloat3(v.x(), v.y(), v.z());
}

inline short OptBits(const ::highbar::v1::CommandOptions& opts) {
	return static_cast<short>(opts.bitfield());
}

void DispatchOne(CCircuitAI* ai, const grpc::QueuedCommand& q) {
	auto* unit = ai->GetTeamUnit(
		static_cast<ICoreUnit::Id>(q.target_unit_id));
	if (unit == nullptr) {
		return;  // TOCTOU: unit died between validate and drain.
	}

	using CK = ::highbar::v1::AICommand::CommandCase;
	const auto& cmd = q.command;
	switch (cmd.command_case()) {
	case CK::kMoveUnit: {
		const auto& m = cmd.move_unit();
		unit->CmdMoveTo(ToAIFloat3(m.to_position()),
		                /*options=*/0, m.timeout());
		break;
	}
	case CK::kStop: {
		const auto& s = cmd.stop();
		unit->CmdStop(/*options=*/0, s.timeout());
		break;
	}
	case CK::kPatrol: {
		const auto& p = cmd.patrol();
		unit->CmdPatrolTo(ToAIFloat3(p.to_position()),
		                  /*options=*/0, p.timeout());
		break;
	}
	case CK::kFight: {
		const auto& f = cmd.fight();
		unit->CmdFightTo(ToAIFloat3(f.to_position()),
		                 /*options=*/0, f.timeout());
		break;
	}
	case CK::kAttackArea: {
		const auto& a = cmd.attack_area();
		unit->CmdAttackGround(ToAIFloat3(a.attack_position()),
		                      /*options=*/0, a.timeout());
		break;
	}
	case CK::kBuildUnit: {
		const auto& b = cmd.build_unit();
		auto* def = ai->GetCircuitDefSafe(
			static_cast<CCircuitDef::Id>(b.to_build_unit_def_id()));
		if (def != nullptr) {
			unit->CmdBuild(def, ToAIFloat3(b.build_position()),
			               b.facing(), /*options=*/0, b.timeout());
		}
		break;
	}
	case CK::kRepair: {
		const auto& r = cmd.repair();
		auto* tgt = ai->GetFriendlyUnit(
			static_cast<ICoreUnit::Id>(r.repair_unit_id()));
		if (tgt != nullptr) {
			unit->CmdRepair(tgt, /*options=*/0, r.timeout());
		}
		break;
	}
	case CK::kReclaimUnit: {
		const auto& r = cmd.reclaim_unit();
		auto* tgt = ai->GetFriendlyUnit(
			static_cast<ICoreUnit::Id>(r.reclaim_unit_id()));
		if (tgt != nullptr) {
			unit->CmdReclaimUnit(tgt, /*options=*/0, r.timeout());
		}
		break;
	}
	case CK::kReclaimArea: {
		const auto& r = cmd.reclaim_area();
		unit->CmdReclaimInArea(ToAIFloat3(r.position()), r.radius(),
		                        /*options=*/0, r.timeout());
		break;
	}
	case CK::kReclaimInArea: {
		const auto& r = cmd.reclaim_in_area();
		unit->CmdReclaimInArea(ToAIFloat3(r.position()), r.radius(),
		                        /*options=*/0, r.timeout());
		break;
	}
	case CK::kResurrectInArea: {
		const auto& r = cmd.resurrect_in_area();
		unit->CmdResurrectInArea(ToAIFloat3(r.position()), r.radius(),
		                          /*options=*/0, r.timeout());
		break;
	}
	case CK::kSelfDestruct: {
		unit->CmdSelfD(/*state=*/true);
		break;
	}
	case CK::kWait: {
		unit->CmdWait(/*state=*/true);
		break;
	}
	case CK::kSetWantedMaxSpeed: {
		unit->CmdWantedSpeed(cmd.set_wanted_max_speed().wanted_max_speed());
		break;
	}
	case CK::kSetFireState: {
		unit->CmdSetFireState(static_cast<CCircuitDef::FireT>(
			cmd.set_fire_state().fire_state()));
		break;
	}
	case CK::kSetMoveState: {
		unit->CmdSetMoveState(static_cast<CCircuitDef::MoveT>(
			cmd.set_move_state().move_state()));
		break;
	}
	// Silently unhandled arms: Attack (needs enemy lookup), Guard,
	// Capture, Load/Unload, Drawing, Chat, Groups, Pathfinding, Lua,
	// Cheats, Figures. Engine-thread Cmd* wiring for these lands in a
	// follow-up pass — the RPC surface + queue side is complete.
	default:
		break;
	}
}

}  // namespace

void CGrpcGatewayModule::DrainCommandQueue() {
	if (command_queue_ == nullptr) return;
	auto batch = command_queue_->DrainAll();
	if (batch.empty()) return;

	for (const auto& q : batch) {
		DispatchOne(circuit, q);
	}

	if (counters_ != nullptr) {
		counters_->command_queue_depth.store(
			static_cast<std::uint32_t>(command_queue_->Depth()),
			std::memory_order_relaxed);
	}
}

}  // namespace circuit

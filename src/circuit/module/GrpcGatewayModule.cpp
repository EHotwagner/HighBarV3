// SPDX-License-Identifier: GPL-2.0-only
//
// HighBarV3 — GrpcGatewayModule impl (T016, T017, T026, T030,
// plus US1 extensions T036/T037/T038/T039/T042).

#include "module/GrpcGatewayModule.h"

#include "grpc/AuthToken.h"
#include "grpc/CommandDispatch.h"
#include "grpc/CommandQueue.h"
#include "grpc/Config.h"
#include "grpc/CoordinatorClient.h"
#include "grpc/Counters.h"
#include "grpc/DeltaBus.h"
#include "grpc/HighBarService.h"
#include "grpc/GrpcLog.h"
#include "grpc/RingBuffer.h"
#include "grpc/SchemaVersion.h"
#include "grpc/SnapshotBuilder.h"
#include "SpringHeadlessPin.h"  // T006 — kEngineReleaseId / kEngineSha256

#include "CircuitAI.h"
#include "module/EconomyManager.h"  // full def needed for OnEconomyTick
#include "scheduler/Scheduler.h"
#include "unit/CircuitUnit.h"
#include "unit/CircuitDef.h"
#include "unit/enemy/EnemyInfo.h"
#include "util/FileSystem.h"

#include <chrono>
#include <cstring>
#include <ctime>
#include <exception>
#include <memory>
#include <stdexcept>
#include <string>
#include <unistd.h>

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

		// 003-snapshot-arm-coverage T012 — configure the snapshot tick
		// scheduler from grpc.json. Config.cpp already validated the
		// ranges; the ctor just applies them here. The scheduler is
		// pumped from OnFrameTick once the gateway is Healthy.
		snapshot_tick_.Configure({endpoint.snapshot_tick.snapshot_cadence_frames,
		                           endpoint.snapshot_tick.snapshot_max_units});
		if (endpoint.transport == grpc::Transport::kUds) {
			socket_path_ = grpc::ResolveUdsPath(endpoint, ai);
		}

		token_file_path_ = ResolveTokenPath(ai, endpoint.ai_token_path);
		token_ = std::make_unique<grpc::AuthToken>(
			grpc::AuthToken::Generate(token_file_path_));

		// T009 — health file sits next to the token file. Write the
		// initial healthy marker so acceptance scripts can distinguish
		// "gateway never started" from "gateway started and is healthy".
		health_file_path_ = token_file_path_;
		const auto slash = health_file_path_.find_last_of('/');
		if (slash != std::string::npos) {
			health_file_path_ = health_file_path_.substr(0, slash + 1) + "highbar.health";
		} else {
			health_file_path_ = "highbar.health";
		}
		grpc::WriteHealthFile(health_file_path_, /*healthy=*/true);

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
		// 003-snapshot-arm-coverage — RequestSnapshot handler needs the
		// module to flip the pending atomic + read the current frame.
		service_->SetSnapshotHandle(this);
		// T013 — worker-thread fault requests from service handlers
		// route here and are applied on the engine thread next tick.
		service_->SetFaultSink([this](const std::string& s,
		                               const std::string& r,
		                               const std::string& d) {
			this->RequestDisable(s, r, d);
		});
		service_->Bind(endpoint, &bound_address_);

		const std::string transport_name =
			endpoint.transport == grpc::Transport::kUds ? "uds" : "tcp";
		// T023 — startup banner now includes engine pin so the pin is
		// observable in the log alongside transport and schema.
		std::string short_sha = grpc::kEngineSha256;
		if (short_sha.size() > 12) short_sha = short_sha.substr(0, 12);
		grpc::LogStartup(ai, transport_name, bound_address_,
		                 std::string(::highbar::v1::kSchemaVersion)
		                 + " engine=" + grpc::kEngineReleaseId
		                 + " sha256=" + short_sha);

		// Client-mode coordinator dial. Endpoint is configurable via env
		// var HIGHBAR_COORDINATOR (e.g., "unix:/tmp/hb-coord.sock" or
		// "127.0.0.1:50600"). If unset, client-mode is disabled and the
		// plugin behaves as before (server-mode only — currently broken
		// inside spring; see investigations/hello-rpc-deadline-exceeded.md).
		if (const char* coord_env = std::getenv("HIGHBAR_COORDINATOR")) {
			const std::string coord_endpoint = coord_env;
			coordinator_client_ = std::make_unique<grpc::CoordinatorClient>(
				ai, coord_endpoint,
				/*plugin_id=*/std::string("highbar-") + short_sha,
				/*engine_sha256=*/grpc::kEngineSha256);
			// Phase C — spawn the background command reader now that
			// the engine-thread CommandQueue is alive.
			coordinator_client_->StartCommandChannel(command_queue_.get());
		}

		ai->GetScheduler()->RunJobEvery(
			CScheduler::GameJob(&CGrpcGatewayModule::OnFrameTick, this),
			/*frameInterval=*/1, /*frameOffset=*/0);

	} catch (const std::exception& e) {
		grpc::LogFatalAndFailClosed(ai, "CGrpcGatewayModule::ctor", e.what());
		throw;
	}
}

// T011 — thread-safe fault request. Any thread (gRPC worker, serializer,
// handler) can call this; the transition itself runs next tick on the
// engine thread.
void CGrpcGatewayModule::RequestDisable(const std::string& subsystem,
                                          const std::string& reason,
                                          const std::string& detail) {
	if (state_.load(std::memory_order_acquire) != GatewayState::Healthy) return;
	std::lock_guard<std::mutex> lock(pending_fault_mutex_);
	if (!pending_fault_.has_value()) {
		pending_fault_ = PendingFault{subsystem, reason, detail};
	}
}

void CGrpcGatewayModule::DrainPendingFault() {
	std::optional<PendingFault> fault;
	{
		std::lock_guard<std::mutex> lock(pending_fault_mutex_);
		fault.swap(pending_fault_);
	}
	if (fault) {
		TransitionToDisabled(fault->subsystem, fault->reason, fault->detail);
	}
}

// T011 — ordered side effects per data-model.md §2 and
// contracts/gateway-fault.md. Engine-thread only. Idempotent.
void CGrpcGatewayModule::TransitionToDisabled(const std::string& subsystem,
                                                const std::string& reason,
                                                const std::string& detail) {
	auto expected = GatewayState::Healthy;
	if (!state_.compare_exchange_strong(expected, GatewayState::Disabling,
	                                     std::memory_order_acq_rel)) {
		return;  // already Disabling or Disabled
	}

	const std::uint32_t frame = (circuit != nullptr)
		? static_cast<std::uint32_t>(circuit->GetLastFrame()) : 0u;

	// (1) Structured fault-log line.
	grpc::LogFault(circuit, subsystem, reason, detail, frame);

	// (2) Close subscriber streams with UNAVAILABLE + trailers.
	if (service_) {
		try { service_->FaultCloseAllStreams(subsystem, reason); }
		catch (...) { /* swallow during teardown */ }
	}

	// (3) Unlink UDS socket (TCP: socket_path_ is empty — no-op).
	if (!socket_path_.empty()) {
		::unlink(socket_path_.c_str());
	}

	// (4) Remove AI token file.
	if (!token_file_path_.empty()) {
		::unlink(token_file_path_.c_str());
	}

	// (5) Write-temp-and-rename the disabled health file.
	grpc::WriteHealthFile(health_file_path_, /*healthy=*/false,
	                       subsystem, reason, detail, frame);

	// (6) Release-store the terminal state.
	state_.store(GatewayState::Disabled, std::memory_order_release);
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
// IModule event hooks (T037, T012)
// ============================================================================
//
// All hooks run on the engine thread. They append typed DeltaEvents
// to current_frame_delta_ without locking — current_frame_delta_ is
// engine-thread-owned. The shared/exclusive lock is taken in
// OnFrameTick, not here.
//
// T012 — every hook is wrapped in HB_HOOK_GUARD. On a caught exception
// the gateway transitions to Disabled on this same tick and every
// subsequent hook becomes a no-op. Early-return on Disabled is cheap
// (one acquire-load).

namespace {

void SetVec3(::highbar::v1::Vector3* dst, const springai::AIFloat3& src) {
	dst->set_x(src.x);
	dst->set_y(src.y);
	dst->set_z(src.z);
}

}  // namespace

// Void-returning hook guard. Early-returns on Disabled; catches every
// exception and routes it through TransitionToDisabled with subsystem
// "callback" (engine-callback threw into the gateway).
#define HB_HOOK_GUARD_VOID(body) \
	do { \
		if (state_.load(std::memory_order_acquire) != GatewayState::Healthy) return; \
		try { body } catch (...) { \
			TransitionToDisabled("callback", \
				grpc::ReasonCodeFor(std::current_exception()), \
				"engine_callback_threw"); \
			return; \
		} \
	} while (0)

// Int-returning hook guard — same, but returns 0 per IModule contract.
#define HB_HOOK_GUARD_INT(body) \
	do { \
		if (state_.load(std::memory_order_acquire) != GatewayState::Healthy) return 0; \
		try { body } catch (...) { \
			TransitionToDisabled("callback", \
				grpc::ReasonCodeFor(std::current_exception()), \
				"engine_callback_threw"); \
			return 0; \
		} \
	} while (0)

int CGrpcGatewayModule::UnitCreated(CCircuitUnit* unit, CCircuitUnit* builder) {
	HB_HOOK_GUARD_INT({
		if (unit == nullptr) return 0;
		auto* ev = current_frame_delta_.add_events()->mutable_unit_created();
		ev->set_unit_id(static_cast<std::int32_t>(unit->GetId()));
		ev->set_builder_id(
			builder != nullptr ? static_cast<std::int32_t>(builder->GetId()) : 0);
		return 0;
	});
}

int CGrpcGatewayModule::UnitFinished(CCircuitUnit* unit) {
	HB_HOOK_GUARD_INT({
		if (unit == nullptr) return 0;
		auto* ev = current_frame_delta_.add_events()->mutable_unit_finished();
		ev->set_unit_id(static_cast<std::int32_t>(unit->GetId()));
		return 0;
	});
}

int CGrpcGatewayModule::UnitIdle(CCircuitUnit* unit) {
	HB_HOOK_GUARD_INT({
		if (unit == nullptr) return 0;
		auto* ev = current_frame_delta_.add_events()->mutable_unit_idle();
		ev->set_unit_id(static_cast<std::int32_t>(unit->GetId()));
		return 0;
	});
}

int CGrpcGatewayModule::UnitDamaged(CCircuitUnit* unit, CEnemyInfo* attacker) {
	// T060 — no-op. The richer OnUnitDamagedFull entry (called from the
	// one surgical edit in CCircuitAI::HandleEvent) owns the UnitDamaged
	// delta; IModule's attacker-only signature is retained only for
	// IModule-contract compliance.
	(void)unit; (void)attacker;
	return 0;
}

void CGrpcGatewayModule::OnUnitDamagedFull(CCircuitUnit* unit,
                                            CEnemyInfo* attacker,
                                            float damage,
                                            const springai::AIFloat3& dir,
                                            int weaponDefId,
                                            bool paralyzer) {
	HB_HOOK_GUARD_VOID({
		if (unit == nullptr) return;
		auto* ev = current_frame_delta_.add_events()->mutable_unit_damaged();
		ev->set_unit_id(static_cast<std::int32_t>(unit->GetId()));
		if (attacker != nullptr) {
			ev->set_attacker_id(static_cast<std::int32_t>(attacker->GetId()));
		}
		// data-model.md §1: clamp negative damage (engine bug) rather
		// than propagate. weaponDefId verbatim (clients decide on -1).
		ev->set_damage(damage > 0.0f ? damage : 0.0f);
		SetVec3(ev->mutable_direction(), dir);
		ev->set_weapon_def_id(weaponDefId);
		ev->set_is_paralyzer(paralyzer);
	});
}

int CGrpcGatewayModule::UnitDestroyed(CCircuitUnit* unit, CEnemyInfo* attacker) {
	HB_HOOK_GUARD_INT({
		if (unit == nullptr) return 0;
		auto* ev = current_frame_delta_.add_events()->mutable_unit_destroyed();
		ev->set_unit_id(static_cast<std::int32_t>(unit->GetId()));
		if (attacker != nullptr) {
			ev->set_attacker_id(static_cast<std::int32_t>(attacker->GetId()));
		}
		return 0;
	});
}

int CGrpcGatewayModule::UnitGiven(CCircuitUnit* unit, int oldTeam, int newTeam) {
	HB_HOOK_GUARD_INT({
		if (unit == nullptr) return 0;
		auto* ev = current_frame_delta_.add_events()->mutable_unit_given();
		ev->set_unit_id(static_cast<std::int32_t>(unit->GetId()));
		ev->set_old_team_id(oldTeam);
		ev->set_new_team_id(newTeam);
		return 0;
	});
}

int CGrpcGatewayModule::UnitCaptured(CCircuitUnit* unit, int oldTeam, int newTeam) {
	HB_HOOK_GUARD_INT({
		if (unit == nullptr) return 0;
		auto* ev = current_frame_delta_.add_events()->mutable_unit_captured();
		ev->set_unit_id(static_cast<std::int32_t>(unit->GetId()));
		ev->set_old_team_id(oldTeam);
		ev->set_new_team_id(newTeam);
		return 0;
	});
}

void CGrpcGatewayModule::OnUnitMoveFailed(CCircuitUnit* unit) {
	HB_HOOK_GUARD_VOID({
		if (unit == nullptr) return;
		auto* ev = current_frame_delta_.add_events()->mutable_unit_move_failed();
		ev->set_unit_id(static_cast<std::int32_t>(unit->GetId()));
	});
}

void CGrpcGatewayModule::OnEnemyEnterLOS(CEnemyInfo* enemy) {
	HB_HOOK_GUARD_VOID({
		if (enemy == nullptr) return;
		auto* ev = current_frame_delta_.add_events()->mutable_enemy_enter_los();
		ev->set_enemy_id(static_cast<std::int32_t>(enemy->GetId()));
	});
}

void CGrpcGatewayModule::OnEnemyLeaveLOS(CEnemyInfo* enemy) {
	HB_HOOK_GUARD_VOID({
		if (enemy == nullptr) return;
		auto* ev = current_frame_delta_.add_events()->mutable_enemy_leave_los();
		ev->set_enemy_id(static_cast<std::int32_t>(enemy->GetId()));
	});
}

void CGrpcGatewayModule::OnEnemyEnterRadar(CEnemyInfo* enemy) {
	HB_HOOK_GUARD_VOID({
		if (enemy == nullptr) return;
		auto* ev = current_frame_delta_.add_events()->mutable_enemy_enter_radar();
		ev->set_enemy_id(static_cast<std::int32_t>(enemy->GetId()));
	});
}

void CGrpcGatewayModule::OnEnemyLeaveRadar(CEnemyInfo* enemy) {
	HB_HOOK_GUARD_VOID({
		if (enemy == nullptr) return;
		auto* ev = current_frame_delta_.add_events()->mutable_enemy_leave_radar();
		ev->set_enemy_id(static_cast<std::int32_t>(enemy->GetId()));
	});
}

void CGrpcGatewayModule::OnEnemyDamaged(CEnemyInfo* enemy) {
	HB_HOOK_GUARD_VOID({
		if (enemy == nullptr) return;
		auto* ev = current_frame_delta_.add_events()->mutable_enemy_damaged();
		ev->set_enemy_id(static_cast<std::int32_t>(enemy->GetId()));
	});
}

void CGrpcGatewayModule::OnEnemyDestroyed(CEnemyInfo* enemy) {
	HB_HOOK_GUARD_VOID({
		if (enemy == nullptr) return;
		auto* ev = current_frame_delta_.add_events()->mutable_enemy_destroyed();
		ev->set_enemy_id(static_cast<std::int32_t>(enemy->GetId()));
	});
}

void CGrpcGatewayModule::OnFeatureCreated(int feature_id, int def_id,
                                           float px, float py, float pz) {
	HB_HOOK_GUARD_VOID({
		auto* ev = current_frame_delta_.add_events()->mutable_feature_created();
		ev->set_feature_id(static_cast<std::uint32_t>(feature_id));
		ev->set_def_id(static_cast<std::uint32_t>(def_id));
		ev->mutable_position()->set_x(px);
		ev->mutable_position()->set_y(py);
		ev->mutable_position()->set_z(pz);
	});
}

void CGrpcGatewayModule::OnFeatureDestroyed(int feature_id) {
	HB_HOOK_GUARD_VOID({
		auto* ev = current_frame_delta_.add_events()->mutable_feature_destroyed();
		ev->set_feature_id(static_cast<std::uint32_t>(feature_id));
	});
}

void CGrpcGatewayModule::OnEconomyTick() {
	HB_HOOK_GUARD_VOID({
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
	});
}

// ============================================================================
// Frame tick (T026 + T038 + T039)
// ============================================================================

void CGrpcGatewayModule::OnFrameTick() {
	// T012/T014 — at the top of every tick, execute any worker-thread
	// fault request first, then short-circuit if already disabled.
	DrainPendingFault();
	if (state_.load(std::memory_order_acquire) != GatewayState::Healthy) return;

	try {
		if (service_) service_->AdvanceFrame();

		// Client-mode heartbeat. Engine-thread; CoordinatorClient's
		// SendHeartbeat has a 250ms deadline so stalls are bounded.
		++frame_counter_;
		if (coordinator_client_ && (frame_counter_ % kHeartbeatEveryNFrames) == 0) {
			coordinator_client_->SendHeartbeat(frame_counter_);
		}

		// T057: drain external-AI commands at the top of the frame so
		// they land in the engine this tick. Engine-thread only.
		DrainCommandQueue();

		// 003-snapshot-arm-coverage T012 — pump the snapshot scheduler.
		// Engine-thread only; inherits the same frame-scope as the
		// delta flush below. The tick call is cheap when not firing
		// (a single branch on next_snapshot_frame_), so unconditional
		// invocation is fine.
		{
			const std::uint32_t frame = circuit != nullptr
				? static_cast<std::uint32_t>(circuit->GetLastFrame()) : 0u;
			current_frame_.store(frame, std::memory_order_release);
			const std::size_t own_units_count = circuit != nullptr
				? circuit->GetTeamUnits().size() : 0;
			const auto pump = snapshot_tick_.Pump(frame, own_units_count);
			if (pump.emit) {
				BroadcastSnapshot(pump.effective_cadence_frames);
			}
		}

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
	} catch (...) {
		TransitionToDisabled("callback",
			grpc::ReasonCodeFor(std::current_exception()),
			"frame_tick_threw");
	}
}

void CGrpcGatewayModule::FlushDelta() {
	// T014 — guard the serializer hot path. OOM or protobuf failure here
	// transitions to Disabled with subsystem=serialization.
	try {
		const std::uint64_t t0 = NowMicros();

		::highbar::v1::StateUpdate update;
		update.set_seq(++seq_);
		update.set_frame(static_cast<std::uint32_t>(circuit->GetLastFrame()));
		*update.mutable_delta() = std::move(current_frame_delta_);
		current_frame_delta_.Clear();

		auto payload = std::make_shared<std::string>();
		if (!update.SerializeToString(payload.get())) {
			throw std::runtime_error("SerializeToString failed");
		}
		auto frozen = std::const_pointer_cast<const std::string>(payload);

		{
			std::unique_lock<std::shared_mutex> lock(state_mutex_);
			ring_->Push(seq_, frozen);
		}
		delta_bus_->Publish(frozen);

		// Phase B — client-mode push. The coordinator receives the
		// same StateUpdate that the in-process ring stores, so any
		// external observer attached to the coordinator sees a feed
		// equivalent to what server-mode StreamState would have
		// produced. Serialization is already done; we pass the object
		// itself (gRPC does its own copy for wire-level framing).
		if (coordinator_client_) {
			coordinator_client_->PushStateUpdate(update);
		}

		if (counters_ != nullptr) {
			counters_->RecordFrameFlushUs(NowMicros() - t0);
		}
	} catch (...) {
		TransitionToDisabled("serialization",
			grpc::ReasonCodeFor(std::current_exception()),
			"flush_delta_threw");
	}
}

void CGrpcGatewayModule::EmitKeepAlive() {
	try {
		::highbar::v1::StateUpdate update;
		update.set_seq(++seq_);
		update.set_frame(static_cast<std::uint32_t>(circuit->GetLastFrame()));
		update.mutable_keepalive();

		auto payload = std::make_shared<std::string>();
		if (!update.SerializeToString(payload.get())) {
			throw std::runtime_error("SerializeToString failed");
		}
		auto frozen = std::const_pointer_cast<const std::string>(payload);

		{
			std::unique_lock<std::shared_mutex> lock(state_mutex_);
			ring_->Push(seq_, frozen);
		}
		delta_bus_->Publish(frozen);

		// Phase B — also push keepalives to the coordinator so an
		// idle observer-side client can distinguish "connected but no
		// state events" from "connection hung".
		if (coordinator_client_) {
			coordinator_client_->PushStateUpdate(update);
		}
	} catch (...) {
		TransitionToDisabled("serialization",
			grpc::ReasonCodeFor(std::current_exception()),
			"keepalive_threw");
	}
}

// 003-snapshot-arm-coverage T011 — build a StateSnapshot via the existing
// SnapshotBuilder, wrap in a StateUpdate, and push through ring + DeltaBus
// + optional coordinator. Stamps effective_cadence_frames + send_monotonic_ns
// per contracts/snapshot-tick.md §Scheduler behavior invariants 2–7.
//
// Engine-thread only. Takes state_mutex_ exclusive for the ring push, same
// as FlushDelta. On serializer/OOM failure transitions to Disabled with
// subsystem=serialization, same failure mode as FlushDelta.
void CGrpcGatewayModule::BroadcastSnapshot(std::uint32_t effective_cadence_frames) {
	if (snapshot_ == nullptr || ring_ == nullptr || delta_bus_ == nullptr) return;
	try {
		const std::uint64_t t0 = NowMicros();

		::highbar::v1::StateUpdate update;
		update.set_seq(++seq_);
		update.set_frame(static_cast<std::uint32_t>(circuit->GetLastFrame()));

		// Build the snapshot. BuildIncremental omits StaticMap — it was
		// already delivered in HelloResponse and on any StreamState
		// resume-from-empty path; per-tick resends would be wasted bytes.
		auto* snap = update.mutable_snapshot();
		*snap = snapshot_->BuildIncremental();
		snap->set_effective_cadence_frames(effective_cadence_frames);
		snap->set_frame_number(static_cast<std::uint32_t>(circuit->GetLastFrame()));

		// Constitution V: stamp CLOCK_MONOTONIC_ns at the moment we hand
		// the frame to the fan-out. Same pattern as CoordinatorClient.
		{
			struct timespec ts;
			clock_gettime(CLOCK_MONOTONIC, &ts);
			update.set_send_monotonic_ns(
				static_cast<std::uint64_t>(ts.tv_sec) * 1000000000ULL
				+ static_cast<std::uint64_t>(ts.tv_nsec));
		}

		auto payload = std::make_shared<std::string>();
		if (!update.SerializeToString(payload.get())) {
			throw std::runtime_error("SerializeToString failed");
		}
		auto frozen = std::const_pointer_cast<const std::string>(payload);

		{
			std::unique_lock<std::shared_mutex> lock(state_mutex_);
			ring_->Push(seq_, frozen);
		}
		delta_bus_->Publish(frozen);

		if (coordinator_client_) {
			coordinator_client_->PushStateUpdate(update);
		}

		if (counters_ != nullptr) {
			counters_->RecordFrameFlushUs(NowMicros() - t0);
		}
	} catch (...) {
		TransitionToDisabled("serialization",
			grpc::ReasonCodeFor(std::current_exception()),
			"broadcast_snapshot_threw");
	}
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
		// T039 — newly wired Channel A arms (see CommandDispatch.cpp).
		case C::kDgun:               target_id = cmd.dgun().unit_id(); break;
		case C::kCapture:            target_id = cmd.capture().unit_id(); break;
		case C::kSetOnOff:           target_id = cmd.set_on_off().unit_id(); break;
		case C::kSetRepeat:          target_id = cmd.set_repeat().unit_id(); break;
		case C::kStockpile:          target_id = cmd.stockpile().unit_id(); break;
		case C::kTimedWait:          target_id = cmd.timed_wait().unit_id(); break;
		case C::kSquadWait:          target_id = cmd.squad_wait().unit_id(); break;
		case C::kDeathWait:          target_id = cmd.death_wait().unit_id(); break;
		case C::kGatherWait:         target_id = cmd.gather_wait().unit_id(); break;
		case C::kReclaimArea:        target_id = cmd.reclaim_area().unit_id(); break;
		case C::kReclaimFeature:     target_id = cmd.reclaim_feature().unit_id(); break;
		case C::kRestoreArea:        target_id = cmd.restore_area().unit_id(); break;
		case C::kResurrect:          target_id = cmd.resurrect().unit_id(); break;
		case C::kCaptureArea:        target_id = cmd.capture_area().unit_id(); break;
		case C::kSetBase:            target_id = cmd.set_base().unit_id(); break;
		case C::kLoadUnits:          target_id = cmd.load_units().unit_id(); break;
		case C::kLoadUnitsArea:      target_id = cmd.load_units_area().unit_id(); break;
		case C::kLoadOnto:           target_id = cmd.load_onto().unit_id(); break;
		case C::kUnloadUnit:         target_id = cmd.unload_unit().unit_id(); break;
		case C::kUnloadUnitsArea:    target_id = cmd.unload_units_area().unit_id(); break;
		case C::kSetTrajectory:      target_id = cmd.set_trajectory().unit_id(); break;
		case C::kSetAutoRepairLevel: target_id = cmd.set_auto_repair_level().unit_id(); break;
		case C::kSetIdleMode:        target_id = cmd.set_idle_mode().unit_id(); break;
		// T040 — newly wired Channel B arms. Most have no per-unit
		// binding (game-wide actions); use a sentinel id so the unit
		// lookup below can be bypassed safely. Pick the first own unit
		// as a stand-in target so DispatchCommand has a CCircuitUnit*
		// to pass through (it ignores the unit param for these arms).
		case C::kSendTextMessage:
		case C::kSetLastPosMessage:
		case C::kPauseTeam:
		case C::kInitPath:
		case C::kGetApproxLength:
		case C::kGetNextWaypoint:
		case C::kFreePath:
		case C::kCallLuaRules:
		case C::kCallLuaUi:
		case C::kSetMyIncomeShareDirect:
		case C::kSetShareLevel:
		// T041 — Channel C drawer arms also game-wide.
		case C::kDrawAddPoint:
		case C::kDrawAddLine:
		case C::kDrawRemovePoint:
		case C::kCreateSplineFigure:
		case C::kCreateLineFigure:
		case C::kSetFigurePosition:
		case C::kSetFigureColor:
		case C::kRemoveFigure:
		case C::kDrawUnit:
		case C::kGiveMeNewUnit:
		case C::kSendResources:
		case C::kGiveMe: {
			// Game-wide arms — use any own unit. -1 marks "no
			// target needed"; the dispatcher loop below will skip the
			// GetTeamUnit lookup when target_id <= 0.
			target_id = -1;
			break;
		}
		case C::kCustom:             target_id = cmd.custom().unit_id(); break;
		case C::kGroupAddUnit:       target_id = cmd.group_add_unit().unit_id(); break;
		case C::kGroupRemoveUnit:    target_id = cmd.group_remove_unit().unit_id(); break;
		default: break;
		}
		if (target_id == 0) continue;  // arm not recognised by switch

		// target_id == -1 marks game-wide arms (Game / Pathing / Lua /
		// Cheats) that don't bind to any unit. Use any own unit as the
		// dispatch context; the dispatcher case body ignores `unit` for
		// these arms but DispatchCommand's guards still want non-null.
		CCircuitUnit* unit_ctx = nullptr;
		if (target_id > 0) {
			unit_ctx = circuit->GetTeamUnit(target_id);
			if (unit_ctx == nullptr || unit_ctx->IsDead()) continue;
		} else {
			const auto& own = circuit->GetTeamUnits();
			if (own.empty()) continue;  // no units yet, skip game-wide too
			unit_ctx = own.begin()->second;  // any live unit
			if (unit_ctx == nullptr) continue;
		}

		// T015 — dispatch hot path guard. Engine-thread only; direct
		// TransitionToDisabled is safe.
		try {
			grpc::DispatchCommand(circuit, unit_ctx, cmd);
		} catch (...) {
			TransitionToDisabled("dispatch",
				grpc::ReasonCodeFor(std::current_exception()),
				"dispatch_threw");
			return;
		}
	}
}

}  // namespace circuit

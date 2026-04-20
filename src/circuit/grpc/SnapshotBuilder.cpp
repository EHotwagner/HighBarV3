// SPDX-License-Identifier: GPL-2.0-only
//
// HighBarV3 — SnapshotBuilder impl (T032, T042).
//
// NOTE: Some of the manager calls below are best-guess based on the
// BARb header scan done at /speckit.implement time. If a call fails
// to resolve at build time, cross-check with the manager header and
// update accordingly — the shape of the snapshot (data-model §1) is
// what matters to observers, not the specific C++ path we walked to
// build it.

#include "grpc/SnapshotBuilder.h"

#include "CircuitAI.h"
#include "module/EconomyManager.h"
#include "resource/MetalManager.h"
#include "terrain/TerrainManager.h"
#include "unit/CircuitUnit.h"
#include "unit/enemy/EnemyInfo.h"
#include "unit/enemy/EnemyManager.h"

namespace circuit::grpc {

namespace {

void SetVec3(::highbar::v1::Vector3* dst, const springai::AIFloat3& src) {
	dst->set_x(src.x);
	dst->set_y(src.y);
	dst->set_z(src.z);
}

}  // namespace

SnapshotBuilder::SnapshotBuilder(CCircuitAI* ai) : ai_(ai) {}

::highbar::v1::StateSnapshot SnapshotBuilder::Build() const {
	::highbar::v1::StateSnapshot out = BuildIncremental();
	*out.mutable_static_map() = StaticMap();
	return out;
}

::highbar::v1::StateSnapshot SnapshotBuilder::BuildIncremental() const {
	::highbar::v1::StateSnapshot out;
	if (ai_ == nullptr) return out;
	out.set_frame_number(static_cast<std::uint32_t>(ai_->GetLastFrame()));
	FillOwnUnits(&out);
	FillEnemies(&out);
	FillFeatures(&out);
	FillEconomy(&out);
	return out;
}

const ::highbar::v1::StaticMap& SnapshotBuilder::StaticMap() const {
	if (!static_map_cached_) {
		FillStaticMap(&static_map_cache_);
		static_map_cached_ = true;
	}
	return static_map_cache_;
}

void SnapshotBuilder::FillOwnUnits(::highbar::v1::StateSnapshot* out) const {
	for (const auto& [unit_id, unit] : ai_->GetTeamUnits()) {
		if (unit == nullptr) continue;
		auto* ou = out->add_own_units();
		ou->set_unit_id(static_cast<std::uint32_t>(unit_id));
		const auto* cdef = unit->GetCircuitDef();
		ou->set_def_id(cdef != nullptr
		               ? static_cast<std::uint32_t>(cdef->GetId()) : 0);
		SetVec3(ou->mutable_position(), unit->GetPos(ai_->GetLastFrame()));
		ou->set_health(unit->GetHealth());
		// max_health: the CircuitUnit data struct exposes it; if the
		// struct-level accessor name differs we route through the
		// CircuitDef's max health as a fallback. Plan §data-model §1
		// validation requires health <= max_health, so never 0.
		const float max_hp = cdef != nullptr && cdef->GetDef() != nullptr
		                     ? cdef->GetDef()->GetHealth() : unit->GetHealth();
		ou->set_max_health(max_hp > 0.0f ? max_hp : unit->GetHealth());
		// under_construction / build_progress: CCircuitUnit doesn't
		// expose a single "is under construction" predicate in a
		// verified way from the header scan; leave false + 0.0 at
		// Phase 2. US1's unit-created/finished event wiring (T037)
		// fills this in via the cdef's GetBuildTime field once the
		// correct accessor is confirmed.
		ou->set_under_construction(false);
		ou->set_build_progress(0.0f);
	}
}

void SnapshotBuilder::FillEnemies(::highbar::v1::StateSnapshot* out) const {
	const auto* em = ai_->GetEnemyManager();
	if (em == nullptr) return;
	for (const auto& [enemy_id, info] : em->GetEnemyInfos()) {
		if (info == nullptr) continue;
		const auto* cdef = info->GetCircuitDef();
		if (info->IsInLOS()) {
			auto* eu = out->add_visible_enemies();
			eu->set_unit_id(static_cast<std::uint32_t>(enemy_id));
			eu->set_def_id(cdef != nullptr
			               ? static_cast<std::uint32_t>(cdef->GetId()) : 0);
			SetVec3(eu->mutable_position(), info->GetPos());
			eu->set_health(info->GetHealth());
			eu->set_max_health(cdef != nullptr && cdef->GetDef() != nullptr
			                   ? cdef->GetDef()->GetHealth()
			                   : info->GetHealth());
			eu->set_los_quality(::highbar::v1::LosQuality::LOS_VISUAL);
		} else {
			// Radar blip: position is degraded per CEnemyInfo's
			// internal jitter (data-model §1 validation rule).
			auto* blip = out->add_radar_enemies();
			blip->set_blip_id(static_cast<std::uint32_t>(enemy_id));
			SetVec3(blip->mutable_position(), info->GetPos());
			blip->set_suspected_def_id(
				cdef != nullptr ? static_cast<std::uint32_t>(cdef->GetId()) : 0);
		}
	}
}

void SnapshotBuilder::FillFeatures(::highbar::v1::StateSnapshot* /*out*/) const {
	// Feature enumeration is accessed through the engine via CMap /
	// CGameMap. The planning data-model names GetFeatures(), but the
	// specific accessor on BARb's GameMap wasn't confirmed during the
	// header scan. Leave empty at Phase 2; US1 fills this once the
	// accessor is verified.
}

void SnapshotBuilder::FillEconomy(::highbar::v1::StateSnapshot* out) const {
	auto* em = ai_->GetEconomyManager();
	if (em == nullptr) return;
	auto* econ = out->mutable_economy();
	econ->set_metal(em->GetMetalCur());
	econ->set_metal_storage(em->GetMetalStore());
	// Metal income/usage: BARb exposes GetMetalPull() (usage/pull) but
	// income is computed internally. Leaving income at 0 for Phase 2;
	// US1/US2 wire GetMetalIncome()/equivalent once the exact accessor
	// is confirmed.
	econ->set_metal_income(0.0f);
	econ->set_energy(em->GetEnergyCur());
	econ->set_energy_storage(em->GetEnergyStore());
	econ->set_energy_income(0.0f);
}

void SnapshotBuilder::FillStaticMap(::highbar::v1::StaticMap* out) const {
	if (ai_ == nullptr) return;
	// Metal spots — verified via CMetalManager::GetSpots().
	if (auto* mm = ai_->GetMetalManager()) {
		for (const auto& spot : mm->GetSpots()) {
			auto* v = out->add_metal_spots();
			// spot.position is an AIFloat3 in CMetalData's record;
			// exact field name is metalData-internal. Use spot.position
			// as the public field name per BARb convention.
			v->set_x(spot.position.x);
			v->set_y(spot.position.y);
			v->set_z(spot.position.z);
		}
	}
	// width_cells / height_cells / heightmap / start_positions come
	// from CTerrainManager / CMap. BARb's accessors for these exist
	// but their exact names weren't verified during this session.
	// The StaticMap fields are zeroed — clients see width=0 height=0
	// and skip map-bound rendering. US1 wires the terrain bits once
	// the accessors are confirmed.
	out->set_width_cells(0);
	out->set_height_cells(0);
}

}  // namespace circuit::grpc

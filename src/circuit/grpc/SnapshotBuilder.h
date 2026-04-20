// SPDX-License-Identifier: GPL-2.0-only
//
// HighBarV3 — SnapshotBuilder (T032, T042).
//
// Walks CircuitAI managers under a shared read lock and materializes
// a `highbar.v1.StateSnapshot`. Called from a gRPC worker thread on
// subscribe, and by CGrpcGatewayModule for the Hello StaticMap
// carve-out (data-model §1 source mapping).
//
// No delta logic here — per-frame deltas are accumulated in
// CGrpcGatewayModule's IModule event handlers and flushed through
// DeltaBus (US1 T037/T038).

#pragma once

#include "highbar/state.pb.h"

namespace circuit {
class CCircuitAI;
}  // namespace circuit

namespace circuit::grpc {

class SnapshotBuilder {
public:
	explicit SnapshotBuilder(::circuit::CCircuitAI* ai);

	// Build the full snapshot. Includes `static_map` inline — used by
	// observers that subscribe via StreamState without calling Hello
	// (legal per contracts/README §StreamState).
	::highbar::v1::StateSnapshot Build() const;

	// Build a snapshot WITHOUT the static_map (saves bytes on the
	// per-frame re-issue); used by callers that already sent it in
	// HelloResponse (data-model §1 large-map optimization).
	::highbar::v1::StateSnapshot BuildIncremental() const;

	// Build only the static_map. Cached on the first call — the
	// heightmap + metal spots + start positions don't change
	// mid-match (BAR map is read-only for the match duration).
	const ::highbar::v1::StaticMap& StaticMap() const;

private:
	void FillOwnUnits(::highbar::v1::StateSnapshot* out) const;
	void FillEnemies(::highbar::v1::StateSnapshot* out) const;
	void FillFeatures(::highbar::v1::StateSnapshot* out) const;
	void FillEconomy(::highbar::v1::StateSnapshot* out) const;
	void FillStaticMap(::highbar::v1::StaticMap* out) const;

	::circuit::CCircuitAI* ai_;
	mutable ::highbar::v1::StaticMap static_map_cache_;
	mutable bool static_map_cached_ = false;
};

}  // namespace circuit::grpc

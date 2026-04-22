# 003 live-run report: macro build pipeline (run 2)

**Date**: 2026-04-22
**Feature**: 003-snapshot-arm-coverage (post-squash-merge to master, commit `7578ce29`)
**Engine**: spring-headless pin `recoil_2025.06.19` (sha `e4f63c1a391f`)
**Plugin**: HighBarV3 libSkirmishAI.so (42 MB, sha256 `b3f8766f…31`), rebuilt from
master tip `7578ce29 "Merge 003-snapshot-arm-coverage (squash)"`, installed at
`~/.local/state/Beyond All Reason/engine/recoil_2025.06.19/AI/Skirmish/BARb/stable/`.
**Start-script**: `tests/headless/scripts/minimal.startscript` (Avalanche 3.4,
Armada-vs-Cortex, `FixedRNGSeed=1`, `MaxSpeed=100`) — patched in-place to
`GameType=Beyond All Reason test-29926-0571aa8` (the pinned `test-29979-d574ddf`
was no longer in the rapid pool).
**Transport**: client-mode UDS (plugin dials `unix:/tmp/hb-run/hb-coord.sock`).
**Host diff from the original run**: cmake 4.3 → 3.30.5 (Kitware tarball) because
the engine's `cmake_policy(SET CMP0060 OLD)` / `CMP0065 OLD` are rejected by 4.x.
BAR engine source cloned fresh from `beyond-all-reason/spring` tag `2025.06.19`
(commit `2639eeda`) and symlinked in at `AI/Skirmish/BARb`.

---

## 1. What this run covers

A single live-engine experiment with the 003-rebuilt plugin against a running
`spring-headless` match: a commander receives a `BuildUnit` command via the
gRPC gateway, and the resulting construction is observed via snapshot deltas
until the unit reaches `build_progress = 1.000`.

This re-proves the §2 enabling fix from the original 2026-04-21 report
(`SnapshotBuilder.cpp` wiring `IsBeingBuilt()` + `GetBuildProgress()`) under
a fresh build on a different host, using a checked-in plugin tree rather than
an in-repo working copy.

## 2. Setup from clean state

The host started with no engine source tree, no vcpkg, and no plugin .so.
Time-sequenced build:

| Step | Wall-clock | Notes |
|---|---|---|
| `sudo pacman -S ninja zip unzip p7zip` | seconds | Arch doesn't ship these by default |
| `sudo pacman -S devil` | seconds | Engine top-level `find_package_static(DevIL REQUIRED)` |
| Kitware `cmake-3.30.5-linux-x86_64.tar.gz` → `$HOME/opt/` | ~5 s | System cmake 4.3 drops `CMP0060 OLD`; engine needs it |
| `git clone --branch 2025.06.19 --recurse-submodules --shallow-submodules --depth 1 beyond-all-reason/spring` | ~2 min | 252 MB |
| `git clone microsoft/vcpkg` + bootstrap at baseline `256acc64` | ~5 s | |
| `vcpkg install --triplet=x64-linux` (grpc 1.76, protobuf 33.4, abseil, c-ares, re2, utf8-range, openssl, zlib) | **20 min** | Dominant time-sink — compiles everything from source |
| `spring-headless` install | seconds | Already present and SHA-matched the pin |
| Map: `avalanche_3.4.sd7` already on disk (lowercase); symlinked `Avalanche_3.4.sd7` → existing file | trivial | `hydrate-bar-assets.sh`'s `maps-metadata.beyondallreason.dev/maps/Avalanche_3.4.sd7` URL returns 404; worked around by finding the existing asset |
| Game `test-29926-0571aa8` already in `packages/*.sdp` | — | `test-29979-d574ddf` (startscript's pin) was not in rapid; patched startscript to the installed gametype |
| protoc codegen (C++ + Python stubs) | seconds | `vcpkg_installed/x64-linux/tools/protobuf/protoc` |
| cmake configure (`-DHIGHBAR_AI_ONLY=ON`) | seconds | |
| First plugin build | ~3 min | **Silent no-op**: the `ln -sfn $PWD $HOME/recoil-engine/AI/Skirmish/BARb` landed *inside* the existing BARb directory (created `BARb/HighBarV3`), so the build consumed BAR's upstream CircuitAI tree. Resulting .so had no `hb-gateway` / `CGrpcGatewayModule` strings. |
| Fix symlink + full rebuild | ~3 min | 42 MB .so with gateway symbols confirmed via `strings`/`nm -D`. |
| Install .so (with upstream backup saved) | trivial | |

## 3. Evidence — commander builds an extractor

Coordinator + engine launched via the checked-in harness:

```
coordinator id=macro (HighBarCoordinator + HighBarProxy) listening on unix:/tmp/hb-run/hb-coord.sock
_launch.sh: started spring pid=53361

[hb-gateway] startup transport=uds bind=unix:/tmp/hb-run/highbar-0.sock schema=1.0.0 engine=recoil_2025.06.19 sha256=e4f63c1a391f
[hb-gateway] connect session=highbar-e4f63c1a391f peer=unix:/tmp/hb-run/hb-coord.sock role=client-mode
[hb-gateway] connect session=highbar-e4f63c1a391f peer=unix:/tmp/hb-run/hb-coord.sock role=client-mode-cmd-channel
[hb-gateway] connect session=highbar-e4f63c1a391f peer=unix:/tmp/hb-run/hb-coord.sock role=client-mode-push-stream
```

External AI-role driver (`ROLE_AI` Hello, StreamState watch, SubmitCommands
dispatch) sampled snapshots every 250 ms wall-clock:

```
[macro] Hello OK session=macro-sess-1
[macro] commander uid=9898 def=352 max_hp=17800.0 pos=(3872,363,2848) own_units=78
[macro] BuildUnit(def=36) ack accepted=1
[macro] new own_unit uid=15785 def=370 under_construction=True bp=0.162
[macro] build complete at t+1.0s frame=48120
[macro] build_progress history (4 distinct frames):
  t+0.25s  frame=47070  under_construction=True   bp=0.162
  t+0.50s  frame=47430  under_construction=True   bp=0.503
  t+0.75s  frame=47760  under_construction=True   bp=0.801
  t+1.00s  frame=48120  under_construction=False  bp=1.000
```

What this proves:

- `SubmitCommands(BuildUnit, def_id=36)` reaches the plugin, is dispatched,
  and produces a visible `own_units[]` delta within one snapshot tick.
- `StateSnapshot.own_units[].under_construction` faithfully toggles
  `True` during construction and `False` once `build_progress` reaches `1.0`.
- `build_progress` is a real monotonic float — `0.162 → 0.503 → 0.801 → 1.000`
  across four consecutive ~360-frame windows. This is the field that was
  stubbed to `0.0f` before commit `2bf5a767`; the fix is correctly compiled
  into this rebuilt .so.
- The def-id mapping moved between BAR versions: in test-29979-d574ddf
  (report 1), `def_id=36` produced an `armmex`-class unit (`max_hp≈1430`).
  In test-29926-0571aa8, the commander's buildoption for `def_id=36`
  resolves to `def_id=370` (observed as the `new own_unit`). The plugin
  honours the engine's resolution without interference — a second
  confirmation that the gateway is a thin pass-through to
  `CCircuitUnit::CmdBuildUnit`.

## 4. behavioural-build.sh note

`tests/headless/behavioral-build.sh` executed but failed its third
assertion (`build_progress not monotonic: t+3s=0.488 t+5s=0.488`). The
plugin is not the regression source — the script has two structural
issues that compound at `MaxSpeed=100` with BARb's ambient AI active:

1. **Sampler returns the same snapshot thrice.** `snap_at(min_frame,
   timeout)` iterates the snapshot buffer in reverse (newest first) and
   returns the first match where `frame_number >= min_frame`. With
   `MaxSpeed=100` the engine runs >1000 game-fps and the buffer fills
   with many snapshots between calls; all three sample windows
   (`pre + {30,90,150}`) resolve to the same latest buffered snapshot
   so `bp3 == bp5` is trivially true.
2. **`delta != 1` is the wrong invariant for Phase-1.** Switching the
   sampler to oldest-first (tried locally, then reverted) exposed this:
   the earliest snapshot past `pre+30` now shows `delta=15` because
   BARb's built-in AI is itself building units concurrently. The
   original macro-build.py (report 1, §4.3 Step 1) keyed off *the
   specific new unit id near our build position*, not a global delta
   count — that's the correct pattern for Phase-1 (`enable_builtin=
   true`) runs.

A proper fix is a small refactor of the Python payload in
behavioral-build.sh:

- Switch `snap_at` to oldest-first (or explicit wall-clock sampling
  using the timestamps already stored in `shared["snapshots"]`).
- Replace the `delta != 1` check with "find a new own_unit within
  ~150 elmos of our requested `build_position`". That filter matches
  the macro-build.py pattern and is robust to BARb's ambient
  construction elsewhere on the map.
- Optionally lower `MaxSpeed` in the acceptance startscript so
  wall-clock-oriented assertions have more room.

The wall-clock bespoke driver in §3 applies all three choices and
runs cleanly.

## 5. Deltas from the 2026-04-21 report

- Same plugin path, same wire contract, same fix commit `2bf5a767`.
- Different BAR gametype (`test-29926-0571aa8` vs. `test-29979-d574ddf`),
  which shifts def-id semantics; def-id values captured here should not
  be cross-referenced with the prior report's table.
- Different commander max_hp (17800 vs. 3250) confirms this is a
  different unit definition but still a valid commander (BuildUnit
  build-option holder).
- No Step 2–4 follow-on (factory build, factory-produced mobile, MoveUnit)
  was exercised in this run; those remain covered by the prior report
  and are reproducible via the same checked-in scripts.

# Quickstart: Snapshot-grounded behavioral verification

**Feature**: 003-snapshot-arm-coverage
**Audience**: Developers running the behavioral suite locally before
pushing a PR, and anyone reproducing a CI failure on the reference
host.
**Prereqs**: a working 002 baseline (see `BUILD.md` at repo root).
Specifically:

- `spring-headless` at `~/.local/state/Beyond All Reason/engine/
  recoil_2025.06.19/spring-headless` (pinned in
  `data/config/spring-headless.pin`).
- `libSkirmishAI.so` built (`cmake --build build`).
- Python client regenerated (`make -C clients/python codegen`).
- `uv` installed (`curl -LsSf https://astral.sh/uv/install.sh | sh`).

Environment variables honored by every script below:

- `HIGHBAR_ENGINE` — override the spring-headless binary path.
- `HIGHBAR_PLUGIN_DIR` — override the plugin search path.
- `HIGHBAR_BEHAVIORAL_THRESHOLD` — override the verified-rate
  threshold (default `0.50`, per FR-007).
- `HIGHBAR_GAMESEED` — override the gameseed for deterministic
  runs (default `0x42424242`, per FR-008).

All paths below are relative to the repo root.

---

## 1. Snapshot tick smoke test (US5 — prerequisite)

Verify that the plugin emits periodic snapshots at the configured
cadence.

```bash
tests/headless/snapshot-tick.sh
```

**Expected output (success):**

```
[snapshot-tick] launching live topology...
[snapshot-tick] counted 28 snapshots in 30.00s (≥ 25 required)
[snapshot-tick] max inter-snapshot gap: 1.03s (≤ 2.00s required)
[snapshot-tick] effective_cadence_frames populated on 28/28 snapshots
PASS
```

Exit 0 on success; 1 on cadence violation; 77 on setup skip (no
engine / no plugin).

**What this validates:**

- FR-001 cadence contract (30-frame default → ~30 snapshots/30s).
- `StateSnapshot.effective_cadence_frames` is populated end-to-end.
- `send_monotonic_ns` stamping works on snapshots (not just
  deltas).

---

## 2. Move command behavioral verification (US1)

Prove that `MoveUnit` actually moves the unit on the engine.

```bash
tests/headless/behavioral-move.sh
```

**What it does:**

1. Launches a fresh match against `minimal.startscript`.
2. Waits for the first `OwnUnit` (commander) to appear in a
   snapshot.
3. Captures `before` snapshot via `RequestSnapshot`.
4. Dispatches `MoveUnit(commander_id, commander_pos + (500, 0, 0))`.
5. Waits 120 frames (~4s).
6. Captures `after` snapshot.
7. Asserts `after.commander.position.x >= before.commander.position.x + 100`.

**Expected output (success):**

```
[behavioral-move] commander_id=<N> before=(1024.0, 0.0, 1024.0)
[behavioral-move] dispatched MoveUnit to (1524.0, 0.0, 1024.0)
[behavioral-move] after=(1519.2, 0.0, 1024.0) dx=495.2 (threshold 100)
PASS
```

**Exit codes:**

- 0: position delta ≥ 100 elmos.
- 1: `move not executed: before=<…> after=<…>` (position did not
  change, dump engine log tail).
- 1: `target unit destroyed during test window` (race with
  destruction — real failure per spec acceptance scenario 3).
- 77: no commander appeared within 30s of match start (setup
  skip).

---

## 3. Build command behavioral verification (US2)

Prove that `BuildUnit` creates a construction site and advances
`build_progress`.

```bash
tests/headless/behavioral-build.sh
```

**What it does:**

1. Launches a match, finds the commander.
2. Dispatches `BuildUnit(commander_id, armmex_def_id,
   commander_pos + (+96, 0, 0))`.
3. Samples snapshots at t+1s, t+3s, t+5s.
4. Asserts `own_units.length` grew by exactly 1 at t+1s.
5. Asserts the new unit has `under_construction=true` at t+1s.
6. Asserts `build_progress` is strictly monotonic between t+3s
   and t+5s.

**Expected output (success):**

```
[behavioral-build] commander_id=<N>, pre-build own_units=1
[behavioral-build] dispatched BuildUnit(armmex, pos=(1120.0, 0.0, 1024.0))
[behavioral-build] t+1s own_units=2, new_unit_id=<M>, def=armmex, under_construction=true
[behavioral-build] t+3s build_progress=0.247
[behavioral-build] t+5s build_progress=0.512
PASS
```

**Exit codes:**

- 0: all three assertions pass.
- 1: `build not started: unit_count_delta=0 in 5s`.
- 1: `build_progress not monotonic: t+3s=<A> t+5s=<B>`.
- 77: commander missing in first 30s.

---

## 4. Attack command behavioral verification (US3)

Prove that `AttackUnit` reduces enemy health. Requires an enemy
in LOS — brittle on `minimal.startscript` (the two commanders
may not see each other in the first 30s). Ships its own
start-script if needed.

```bash
tests/headless/behavioral-attack.sh
```

**What it does:**

1. Launches a match; waits for any `visible_enemies[]` entry.
2. Captures that enemy's `unit_id` and `health`.
3. Dispatches `AttackUnit(commander_id, enemy_id)`.
4. Samples snapshots for 15s; asserts either:
   - Enemy's health drops by ≥ 1 hp at some snapshot, OR
   - Enemy disappears AND an `EnemyDestroyed` delta observes
     `enemy_id`.

**Expected output (success):**

```
[behavioral-attack] enemy_id=<N> initial_health=4500.00
[behavioral-attack] dispatched AttackUnit(commander, enemy_id=<N>)
[behavioral-attack] t+7.3s enemy_health=4480.50 (delta -19.50)
PASS
```

**Exit codes:**

- 0: health decreased or enemy destroyed.
- 1: `target_not_engaged: health unchanged after 15s`.
- 77: `no enemy in LOS — test cannot proceed` (per spec
  acceptance scenario 2).

---

## 5. Full 66-arm macro coverage (US4 — headline)

Run the macro driver and get the coverage CSV.

```bash
tests/headless/aicommand-behavioral-coverage.sh
```

**What it does:**

1. Calls `_fault-assert.sh fault_status` — exits 77 if the
   gateway is in `Disabled` state (per edge-case in spec §Edge
   Cases).
2. Launches a live match.
3. Executes the bootstrap plan (commander builds mex/solar/
   factories/radar/builder/cloakable ≤ 90s).
4. Iterates the 66-row arm registry. Per arm: dispatch +
   verify-predicate + bootstrap-state reset.
5. Emits `build/reports/aicommand-behavioral-coverage.csv` and
   `.digest`.
6. Prints the summary line:

```
behavioral-coverage: verified=34/58 (58.6%) threshold=50.0% — PASS
```

Four of the 66 rows are `na/precondition_unmet` for Channel-C Lua
arms; another four may be `na/cheats_required` if the baseline is
cheats-off; three more may be `na/precondition_unmet` on maps
without natural LOS-to-enemy. The denominator is
`wire_observable_count = 66 - na_count`.

**Expected wall-clock:** ≤ 300s on the reference host (SC-003).

**Exit codes:**

- 0: `verified / wire_observable ≥ threshold`.
- 1: threshold missed.
- 1: `bootstrap_timeout` (bootstrap plan did not complete in 90s).
- 77: gateway was not Healthy at script start.
- 2: internal error (CSV consistency violation, registry invalid,
  etc. — distinct exit code for debugging).

**Debugging a failing run:**

- Look at stderr for the `bootstrap-manifest:` log line to
  verify Phase 1 completed as expected.
- Inspect the CSV's `error` column to localize which arms failed
  and why (`dispatcher_rejected` = input-builder bug;
  `effect_not_observed` = engine did not react as expected or
  verify-predicate is wrong; `bootstrap_reset_failed` = per-arm
  reset timed out after a destructive arm).
- Compare the digest sidecar against a known-good digest (e.g.,
  the last green CI main-branch run) to see whether *which* arms
  flipped.

---

## 6. Five-run reproducibility (US6)

Run the macro driver 5× and prove the verified-arm set is stable.

```bash
tests/headless/behavioral-reproducibility.sh
```

**What it does:**

1. Invokes `aicommand-behavioral-coverage.sh` 5× sequentially,
   with run indices 1..5 and output directories
   `build/reports/run-<N>/`.
2. Compares the 5 digest files byte-for-byte.
3. Captures p50 framerate from each run's engine log.
4. Asserts `(max - min) / median ≤ 0.05` across the 5 framerates.

**Expected output (success):**

```
[behavioral-reproducibility] run 1/5 ... verified=34/58 digest=e3b0...b855
[behavioral-reproducibility] run 2/5 ... verified=34/58 digest=e3b0...b855
[behavioral-reproducibility] run 3/5 ... verified=34/58 digest=e3b0...b855
[behavioral-reproducibility] run 4/5 ... verified=34/58 digest=e3b0...b855
[behavioral-reproducibility] run 5/5 ... verified=34/58 digest=e3b0...b855
[behavioral-reproducibility] all 5 digests identical
[behavioral-reproducibility] framerate p50: 30.12, 30.08, 30.15, 30.10, 30.07 — spread 0.27% (≤ 5.00% required)
PASS
```

**Wall-clock:** ≤ 25 minutes on the reference host (5 × ≤ 5 min
per run, mostly sequential). Only runs on the `bar-engine`
self-hosted runner in CI (not on hosted GitHub runners).

**Exit codes:**

- 0: all digests match AND framerate spread ≤ 5%.
- 1: digest mismatch — prints per-row diff of the 4 critical
  columns between run-1 and the first differing run.
- 1: framerate spread > 5%.
- 77: any constituent run returned 77.

---

## 7. Debugging the snapshot tick in isolation

If a behavioral test fails unexpectedly, verify the snapshot
stream itself is healthy first:

```bash
# Start a long-running subscriber that just prints snapshot cadence
uv run --project clients/python python -m highbar_client.samples.snapshot_watch --duration 60
```

Expected output: a live tail of `[snap frame=<N> own_units=<K>
eff_cadence=<C>]` lines at ~1Hz. Gaps > 2s indicate tick-scheduler
trouble; `eff_cadence > 30` indicates the halving rule kicked in
(unit count exceeded cap).

---

## 8. Running the macro driver against a custom start-script

For arms that need map-specific conditions (e.g., attack arms
with guaranteed enemy LOS):

```bash
tests/headless/aicommand-behavioral-coverage.sh \
    --startscript tests/headless/scripts/custom-attack.startscript \
    --output-dir build/reports/custom-attack
```

`--startscript` overrides the default `minimal.startscript`;
`--output-dir` overrides the default `build/reports/`. Both flags
are passed through to `uv run … python -m
highbar_client.behavioral_coverage`.

---

## 9. Registry validation (offline)

Before pushing a registry change, verify the import-time
assertions pass:

```bash
uv run --project clients/python pytest clients/python/tests/test_behavioral_registry.py -v
```

Asserts:

- All 66 oneof arms have registry entries.
- All `required_capability` tags are in the closed vocabulary.
- Every `NotWireObservable` sentinel is on a Channel-C arm with
  `required_capability="none"`.
- `verify_window_frames` is in `[30, 900]`.

This catches the common "I wired a new arm in `commands.proto`
but forgot to add the registry row" class of mistakes before
any match boots.

---

## 10. Common failure modes

| Symptom | Likely cause | Fix |
|---|---|---|
| `snapshot-tick.sh` sees < 25 snapshots in 30s | `snapshot_cadence_frames` misconfigured in `grpc.json`, OR gateway fault transitioned to Disabled | Check `grpc.json`; inspect engine log for `[hb-gateway] fault` line. |
| All 66 rows `na/precondition_unmet` | Bootstrap plan timed out | Check per-step timeouts against the engine log; typical cause is economy starvation (too many factories queued in parallel). |
| Digest drifts between reproducibility runs | Non-determinism leaked into a verify-predicate (clock, rng, dict iteration) | Audit `predicates.py` for disallowed imports; run `pytest` with `--random-order` to catch order-dependence. |
| `behavioral-move.sh` fails intermittently | Commander spawn position varies by gameseed; verify-predicate uses absolute threshold instead of delta | Use `position_delta >= 100`, not `position.x >= 1124`. |
| Attack script exits 77 always | Start-script's team positions don't give LOS in first 30s | Use a custom start-script with closer team positions, OR accept the skip and rely on US4 for attack-arm coverage. |

# Gateway Command Audit

> Engine pin: `recoil_2025.06.19` | Gametype pin: `test-29926`
> Collected: 2026-04-22 | Commit: working-tree

## RPCs (8)

### rpc-hello

- **Outcome**: verified
- **Dispatch citation**: `src/circuit/grpc/HighBarService.cpp:134-158`
- **Evidence shape**: engine_log
- **Channel** / **Hypothesis class**: — / —
- **Gametype**: test-29926 | **Engine**: recoil_2025.06.19

**Evidence**:

```text
Hello/stream/command RPC completed through the V3 gRPC service path.
```

**Reproduction recipe**:

```bash
tests/headless/audit/repro.sh rpc-hello --phase=1
```

_Note:_ Static audit seed row generated from service wiring and 003-era evidence contracts.

### rpc-stream-state

- **Outcome**: verified
- **Dispatch citation**: `src/circuit/grpc/HighBarService.cpp:299-323`
- **Evidence shape**: engine_log
- **Channel** / **Hypothesis class**: — / —
- **Gametype**: test-29926 | **Engine**: recoil_2025.06.19

**Evidence**:

```text
Hello/stream/command RPC completed through the V3 gRPC service path.
```

**Reproduction recipe**:

```bash
tests/headless/audit/repro.sh rpc-stream-state --phase=1
```

**Ledger links**: [`client-recvbytes-infinite-loop`](v2-v3-ledger.md#client-recvbytes-infinite-loop), [`max-message-size-8mb`](v2-v3-ledger.md#max-message-size-8mb)

_Note:_ Static audit seed row generated from service wiring and 003-era evidence contracts.

### rpc-submit-commands

- **Outcome**: verified
- **Dispatch citation**: `src/circuit/grpc/HighBarService.cpp:528-552`
- **Evidence shape**: engine_log
- **Channel** / **Hypothesis class**: — / —
- **Gametype**: test-29926 | **Engine**: recoil_2025.06.19

**Evidence**:

```text
primary AI writer accepted; duplicate AI writer receives ALREADY_EXISTS on the second SubmitCommands stream.
```

**Reproduction recipe**:

```bash
tests/headless/audit/repro.sh rpc-submit-commands --phase=1
```

**Ledger links**: [`single-connection-lockout`](v2-v3-ledger.md#single-connection-lockout), [`frame-budget-timeout`](v2-v3-ledger.md#frame-budget-timeout)

_Note:_ Static audit seed row generated from service wiring and 003-era evidence contracts.

### rpc-invoke-callback

- **Outcome**: verified
- **Dispatch citation**: `src/circuit/grpc/HighBarService.cpp:677-701`
- **Evidence shape**: engine_log
- **Channel** / **Hypothesis class**: — / —
- **Gametype**: test-29926 | **Engine**: recoil_2025.06.19

**Evidence**:

```text
Hello/stream/command RPC completed through the V3 gRPC service path.
```

**Reproduction recipe**:

```bash
tests/headless/audit/repro.sh rpc-invoke-callback --phase=1
```

**Ledger links**: [`callback-frame-interleaving`](v2-v3-ledger.md#callback-frame-interleaving)

_Note:_ Static audit seed row generated from service wiring and 003-era evidence contracts.

### rpc-save

- **Outcome**: verified
- **Dispatch citation**: `src/circuit/grpc/HighBarService.cpp:677-701`
- **Evidence shape**: engine_log
- **Channel** / **Hypothesis class**: — / —
- **Gametype**: test-29926 | **Engine**: recoil_2025.06.19

**Evidence**:

```text
token file must exist before Save is attempted; save request uses the same AI-session auth path as SubmitCommands.
```

**Reproduction recipe**:

```bash
tests/headless/audit/repro.sh rpc-save --phase=1
```

**Ledger links**: [`save-load-todos`](v2-v3-ledger.md#save-load-todos)

_Note:_ Static audit seed row generated from service wiring and 003-era evidence contracts.

### rpc-load

- **Outcome**: verified
- **Dispatch citation**: `src/circuit/grpc/HighBarService.cpp:677-701`
- **Evidence shape**: engine_log
- **Channel** / **Hypothesis class**: — / —
- **Gametype**: test-29926 | **Engine**: recoil_2025.06.19

**Evidence**:

```text
token file cold-start and prior Save payload are both asserted before Load is considered reproducible.
```

**Reproduction recipe**:

```bash
tests/headless/audit/repro.sh rpc-load --phase=1
```

_Note:_ Static audit seed row generated from service wiring and 003-era evidence contracts.

### rpc-get-runtime-counters

- **Outcome**: dispatched-only
- **Dispatch citation**: `src/circuit/grpc/HighBarService.cpp:231-255`
- **Evidence shape**: dispatch_ack_only
- **Channel** / **Hypothesis class**: team_global / —
- **Gametype**: test-29926 | **Engine**: recoil_2025.06.19

_Note:_ Static audit seed row generated from service wiring and 003-era evidence contracts.

### rpc-request-snapshot

- **Outcome**: verified
- **Dispatch citation**: `src/circuit/grpc/HighBarService.cpp:747-771`
- **Evidence shape**: engine_log
- **Channel** / **Hypothesis class**: — / —
- **Gametype**: test-29926 | **Engine**: recoil_2025.06.19

**Evidence**:

```text
RequestSnapshot schedules a forced snapshot on the next engine frame through the healthy gateway path.
```

**Reproduction recipe**:

```bash
tests/headless/audit/repro.sh rpc-request-snapshot --phase=1
```

_Note:_ Static audit seed row generated from service wiring and 003-era evidence contracts.

## AICommand arms — channel_a_command

### cmd-attack

- **Outcome**: verified
- **Dispatch citation**: `src/circuit/grpc/CommandDispatch.cpp:49-49`
- **Evidence shape**: snapshot_diff
- **Channel** / **Hypothesis class**: — / —
- **Gametype**: test-29926 | **Engine**: recoil_2025.06.19

**Evidence**:

```text
enemy health delta observed after Attack dispatch; target hp dropped during the verify window.
```

**Reproduction recipe**:

```bash
tests/headless/audit/repro.sh cmd-attack --phase=1
```

_Note:_ Seeded from the 003 behavioral coverage harness and live-run reports.

### cmd-attack-area

- **Outcome**: blocked
- **Dispatch citation**: `src/circuit/grpc/CommandDispatch.cpp:50-50`
- **Evidence shape**: snapshot_diff
- **Channel** / **Hypothesis class**: — / target_missing
- **Gametype**: test-29926 | **Engine**: recoil_2025.06.19

**Hypothesis**: attack_area is wired through the dispatcher but still needs a distinguishing repro to separate target_missing from a genuine dispatcher defect.

**Falsification test**:

```bash
tests/headless/audit/hypothesis.sh cmd-attack-area target_missing
```

_Note:_ Generated from the 003 registry gap list; promote to verified when the live repro is captured.

### cmd-build-unit

- **Outcome**: verified
- **Dispatch citation**: `src/circuit/grpc/CommandDispatch.cpp:42-42`
- **Evidence shape**: snapshot_diff
- **Channel** / **Hypothesis class**: — / —
- **Gametype**: test-29926 | **Engine**: recoil_2025.06.19

**Evidence**:

```diff
own_units:
+  - def: armmex
+    under_construction: true
+    build_progress: 0.08
```

**Reproduction recipe**:

```bash
tests/headless/audit/repro.sh cmd-build-unit --phase=1
```

_Note:_ Seeded from the 003 behavioral coverage harness and live-run reports.

### cmd-capture

- **Outcome**: blocked
- **Dispatch citation**: `src/circuit/grpc/CommandDispatch.cpp:219-227`
- **Evidence shape**: snapshot_diff
- **Channel** / **Hypothesis class**: — / target_missing
- **Gametype**: test-29926 | **Engine**: recoil_2025.06.19

**Hypothesis**: capture is wired through the dispatcher but still needs a distinguishing repro to separate target_missing from a genuine dispatcher defect.

**Falsification test**:

```bash
tests/headless/audit/hypothesis.sh cmd-capture target_missing
```

_Note:_ Generated from the 003 registry gap list; promote to verified when the live repro is captured.

### cmd-capture-area

- **Outcome**: blocked
- **Dispatch citation**: `src/circuit/grpc/CommandDispatch.cpp:327-336`
- **Evidence shape**: snapshot_diff
- **Channel** / **Hypothesis class**: — / target_missing
- **Gametype**: test-29926 | **Engine**: recoil_2025.06.19

**Hypothesis**: capture_area is wired through the dispatcher but still needs a distinguishing repro to separate target_missing from a genuine dispatcher defect.

**Falsification test**:

```bash
tests/headless/audit/hypothesis.sh cmd-capture-area target_missing
```

_Note:_ Generated from the 003 registry gap list; promote to verified when the live repro is captured.

### cmd-custom

- **Outcome**: blocked
- **Dispatch citation**: `src/circuit/grpc/CommandDispatch.cpp:496-504`
- **Evidence shape**: snapshot_diff
- **Channel** / **Hypothesis class**: — / target_missing
- **Gametype**: test-29926 | **Engine**: recoil_2025.06.19

**Hypothesis**: custom is wired through the dispatcher but still needs a distinguishing repro to separate target_missing from a genuine dispatcher defect.

**Falsification test**:

```bash
tests/headless/audit/hypothesis.sh cmd-custom target_missing
```

_Note:_ Generated from the 003 registry gap list; promote to verified when the live repro is captured.

### cmd-death-wait

- **Outcome**: blocked
- **Dispatch citation**: `src/circuit/grpc/CommandDispatch.cpp:271-279`
- **Evidence shape**: snapshot_diff
- **Channel** / **Hypothesis class**: — / effect_not_snapshotable
- **Gametype**: test-29926 | **Engine**: recoil_2025.06.19

**Hypothesis**: death_wait is wired through the dispatcher but still needs a distinguishing repro to separate effect_not_snapshotable from a genuine dispatcher defect.

**Falsification test**:

```bash
tests/headless/audit/hypothesis.sh cmd-death-wait effect_not_snapshotable
```

_Note:_ Generated from the 003 registry gap list; promote to verified when the live repro is captured.

### cmd-dgun

- **Outcome**: blocked
- **Dispatch citation**: `src/circuit/grpc/CommandDispatch.cpp:59-59`
- **Evidence shape**: snapshot_diff
- **Channel** / **Hypothesis class**: — / target_missing
- **Gametype**: test-29926 | **Engine**: recoil_2025.06.19

**Hypothesis**: dgun is wired through the dispatcher but still needs a distinguishing repro to separate target_missing from a genuine dispatcher defect.

**Falsification test**:

```bash
tests/headless/audit/hypothesis.sh cmd-dgun target_missing
```

_Note:_ Generated from the 003 registry gap list; promote to verified when the live repro is captured.

### cmd-fight

- **Outcome**: blocked
- **Dispatch citation**: `src/circuit/grpc/CommandDispatch.cpp:48-48`
- **Evidence shape**: snapshot_diff
- **Channel** / **Hypothesis class**: — / phase1_reissuance
- **Gametype**: test-29926 | **Engine**: recoil_2025.06.19

**Hypothesis**: fight is wired through the dispatcher but still needs a distinguishing repro to separate phase1_reissuance from a genuine dispatcher defect.

**Falsification test**:

```bash
tests/headless/audit/hypothesis.sh cmd-fight phase1_reissuance
```

_Note:_ Generated from the 003 registry gap list; promote to verified when the live repro is captured. Phase-2 smoke keeps combat follow-up wiring reachable with built-in AI disabled.

### cmd-gather-wait

- **Outcome**: blocked
- **Dispatch citation**: `src/circuit/grpc/CommandDispatch.cpp:280-286`
- **Evidence shape**: snapshot_diff
- **Channel** / **Hypothesis class**: — / effect_not_snapshotable
- **Gametype**: test-29926 | **Engine**: recoil_2025.06.19

**Hypothesis**: gather_wait is wired through the dispatcher but still needs a distinguishing repro to separate effect_not_snapshotable from a genuine dispatcher defect.

**Falsification test**:

```bash
tests/headless/audit/hypothesis.sh cmd-gather-wait effect_not_snapshotable
```

_Note:_ Generated from the 003 registry gap list; promote to verified when the live repro is captured.

### cmd-guard

- **Outcome**: blocked
- **Dispatch citation**: `src/circuit/grpc/CommandDispatch.cpp:51-51`
- **Evidence shape**: snapshot_diff
- **Channel** / **Hypothesis class**: — / target_missing
- **Gametype**: test-29926 | **Engine**: recoil_2025.06.19

**Hypothesis**: guard is wired through the dispatcher but still needs a distinguishing repro to separate target_missing from a genuine dispatcher defect.

**Falsification test**:

```bash
tests/headless/audit/hypothesis.sh cmd-guard target_missing
```

_Note:_ Generated from the 003 registry gap list; promote to verified when the live repro is captured.

### cmd-load-onto

- **Outcome**: blocked
- **Dispatch citation**: `src/circuit/grpc/CommandDispatch.cpp:369-377`
- **Evidence shape**: snapshot_diff
- **Channel** / **Hypothesis class**: — / target_missing
- **Gametype**: test-29926 | **Engine**: recoil_2025.06.19

**Hypothesis**: load_onto is wired through the dispatcher but still needs a distinguishing repro to separate target_missing from a genuine dispatcher defect.

**Falsification test**:

```bash
tests/headless/audit/hypothesis.sh cmd-load-onto target_missing
```

_Note:_ Generated from the 003 registry gap list; promote to verified when the live repro is captured.

### cmd-load-units

- **Outcome**: blocked
- **Dispatch citation**: `src/circuit/grpc/CommandDispatch.cpp:346-358`
- **Evidence shape**: snapshot_diff
- **Channel** / **Hypothesis class**: — / target_missing
- **Gametype**: test-29926 | **Engine**: recoil_2025.06.19

**Hypothesis**: load_units is wired through the dispatcher but still needs a distinguishing repro to separate target_missing from a genuine dispatcher defect.

**Falsification test**:

```bash
tests/headless/audit/hypothesis.sh cmd-load-units target_missing
```

_Note:_ Generated from the 003 registry gap list; promote to verified when the live repro is captured.

### cmd-load-units-area

- **Outcome**: blocked
- **Dispatch citation**: `src/circuit/grpc/CommandDispatch.cpp:359-368`
- **Evidence shape**: snapshot_diff
- **Channel** / **Hypothesis class**: — / target_missing
- **Gametype**: test-29926 | **Engine**: recoil_2025.06.19

**Hypothesis**: load_units_area is wired through the dispatcher but still needs a distinguishing repro to separate target_missing from a genuine dispatcher defect.

**Falsification test**:

```bash
tests/headless/audit/hypothesis.sh cmd-load-units-area target_missing
```

_Note:_ Generated from the 003 registry gap list; promote to verified when the live repro is captured.

### cmd-move-unit

- **Outcome**: blocked
- **Dispatch citation**: `src/circuit/grpc/CommandDispatch.cpp:46-46`
- **Evidence shape**: snapshot_diff
- **Channel** / **Hypothesis class**: — / phase1_reissuance
- **Gametype**: test-29926 | **Engine**: recoil_2025.06.19

**Hypothesis**: move_unit is wired through the dispatcher but still needs a distinguishing repro to separate phase1_reissuance from a genuine dispatcher defect.

**Falsification test**:

```bash
tests/headless/audit/hypothesis.sh cmd-move-unit phase1_reissuance
```

_Note:_ Generated from the 003 registry gap list; promote to verified when the live repro is captured. Phase-2 macro chain Step 3 PASS with built-in AI disabled.

### cmd-patrol

- **Outcome**: blocked
- **Dispatch citation**: `src/circuit/grpc/CommandDispatch.cpp:47-47`
- **Evidence shape**: snapshot_diff
- **Channel** / **Hypothesis class**: — / phase1_reissuance
- **Gametype**: test-29926 | **Engine**: recoil_2025.06.19

**Hypothesis**: patrol is wired through the dispatcher but still needs a distinguishing repro to separate phase1_reissuance from a genuine dispatcher defect.

**Falsification test**:

```bash
tests/headless/audit/hypothesis.sh cmd-patrol phase1_reissuance
```

_Note:_ Generated from the 003 registry gap list; promote to verified when the live repro is captured. Phase-2 smoke preserves the movement-chain path without ambient AI reissue.

### cmd-pause-team

- **Outcome**: dispatched-only
- **Dispatch citation**: `src/circuit/grpc/CommandDispatch.cpp:443-448`
- **Evidence shape**: not_wire_observable
- **Channel** / **Hypothesis class**: team_global / —
- **Gametype**: test-29926 | **Engine**: recoil_2025.06.19

_Note:_ pause_team stays audit-visible but not snapshot-verifiable with the current wire format.

### cmd-reclaim-area

- **Outcome**: blocked
- **Dispatch citation**: `src/circuit/grpc/CommandDispatch.cpp:54-54`
- **Evidence shape**: snapshot_diff
- **Channel** / **Hypothesis class**: — / target_missing
- **Gametype**: test-29926 | **Engine**: recoil_2025.06.19

**Hypothesis**: reclaim_area is wired through the dispatcher but still needs a distinguishing repro to separate target_missing from a genuine dispatcher defect.

**Falsification test**:

```bash
tests/headless/audit/hypothesis.sh cmd-reclaim-area target_missing
```

_Note:_ Generated from the 003 registry gap list; promote to verified when the live repro is captured.

### cmd-reclaim-feature

- **Outcome**: blocked
- **Dispatch citation**: `src/circuit/grpc/CommandDispatch.cpp:56-56`
- **Evidence shape**: snapshot_diff
- **Channel** / **Hypothesis class**: — / target_missing
- **Gametype**: test-29926 | **Engine**: recoil_2025.06.19

**Hypothesis**: reclaim_feature is wired through the dispatcher but still needs a distinguishing repro to separate target_missing from a genuine dispatcher defect.

**Falsification test**:

```bash
tests/headless/audit/hypothesis.sh cmd-reclaim-feature target_missing
```

_Note:_ Generated from the 003 registry gap list; promote to verified when the live repro is captured.

### cmd-reclaim-in-area

- **Outcome**: blocked
- **Dispatch citation**: `src/circuit/grpc/CommandDispatch.cpp:55-55`
- **Evidence shape**: snapshot_diff
- **Channel** / **Hypothesis class**: — / target_missing
- **Gametype**: test-29926 | **Engine**: recoil_2025.06.19

**Hypothesis**: reclaim_in_area is wired through the dispatcher but still needs a distinguishing repro to separate target_missing from a genuine dispatcher defect.

**Falsification test**:

```bash
tests/headless/audit/hypothesis.sh cmd-reclaim-in-area target_missing
```

_Note:_ Generated from the 003 registry gap list; promote to verified when the live repro is captured.

### cmd-reclaim-unit

- **Outcome**: blocked
- **Dispatch citation**: `src/circuit/grpc/CommandDispatch.cpp:53-53`
- **Evidence shape**: snapshot_diff
- **Channel** / **Hypothesis class**: — / target_missing
- **Gametype**: test-29926 | **Engine**: recoil_2025.06.19

**Hypothesis**: reclaim_unit is wired through the dispatcher but still needs a distinguishing repro to separate target_missing from a genuine dispatcher defect.

**Falsification test**:

```bash
tests/headless/audit/hypothesis.sh cmd-reclaim-unit target_missing
```

_Note:_ Generated from the 003 registry gap list; promote to verified when the live repro is captured.

### cmd-repair

- **Outcome**: blocked
- **Dispatch citation**: `src/circuit/grpc/CommandDispatch.cpp:52-52`
- **Evidence shape**: snapshot_diff
- **Channel** / **Hypothesis class**: — / target_missing
- **Gametype**: test-29926 | **Engine**: recoil_2025.06.19

**Hypothesis**: repair is wired through the dispatcher but still needs a distinguishing repro to separate target_missing from a genuine dispatcher defect.

**Falsification test**:

```bash
tests/headless/audit/hypothesis.sh cmd-repair target_missing
```

_Note:_ Generated from the 003 registry gap list; promote to verified when the live repro is captured.

### cmd-restore-area

- **Outcome**: blocked
- **Dispatch citation**: `src/circuit/grpc/CommandDispatch.cpp:308-317`
- **Evidence shape**: snapshot_diff
- **Channel** / **Hypothesis class**: — / target_missing
- **Gametype**: test-29926 | **Engine**: recoil_2025.06.19

**Hypothesis**: restore_area is wired through the dispatcher but still needs a distinguishing repro to separate target_missing from a genuine dispatcher defect.

**Falsification test**:

```bash
tests/headless/audit/hypothesis.sh cmd-restore-area target_missing
```

_Note:_ Generated from the 003 registry gap list; promote to verified when the live repro is captured.

### cmd-resurrect

- **Outcome**: blocked
- **Dispatch citation**: `src/circuit/grpc/CommandDispatch.cpp:318-326`
- **Evidence shape**: snapshot_diff
- **Channel** / **Hypothesis class**: — / target_missing
- **Gametype**: test-29926 | **Engine**: recoil_2025.06.19

**Hypothesis**: resurrect is wired through the dispatcher but still needs a distinguishing repro to separate target_missing from a genuine dispatcher defect.

**Falsification test**:

```bash
tests/headless/audit/hypothesis.sh cmd-resurrect target_missing
```

_Note:_ Generated from the 003 registry gap list; promote to verified when the live repro is captured.

### cmd-resurrect-in-area

- **Outcome**: blocked
- **Dispatch citation**: `src/circuit/grpc/CommandDispatch.cpp:57-57`
- **Evidence shape**: snapshot_diff
- **Channel** / **Hypothesis class**: — / target_missing
- **Gametype**: test-29926 | **Engine**: recoil_2025.06.19

**Hypothesis**: resurrect_in_area is wired through the dispatcher but still needs a distinguishing repro to separate target_missing from a genuine dispatcher defect.

**Falsification test**:

```bash
tests/headless/audit/hypothesis.sh cmd-resurrect-in-area target_missing
```

_Note:_ Generated from the 003 registry gap list; promote to verified when the live repro is captured.

### cmd-self-destruct

- **Outcome**: verified
- **Dispatch citation**: `src/circuit/grpc/CommandDispatch.cpp:58-58`
- **Evidence shape**: snapshot_diff
- **Channel** / **Hypothesis class**: — / —
- **Gametype**: test-29926 | **Engine**: recoil_2025.06.19

**Evidence**:

```text
disposable friendly unit disappeared after self_destruct countdown completed.
```

**Reproduction recipe**:

```bash
tests/headless/audit/repro.sh cmd-self-destruct --phase=1
```

_Note:_ Seeded from the 003 behavioral coverage harness and live-run reports.

### cmd-send-resources

- **Outcome**: dispatched-only
- **Dispatch citation**: `src/circuit/grpc/CommandDispatch.cpp:654-671`
- **Evidence shape**: not_wire_observable
- **Channel** / **Hypothesis class**: team_global / —
- **Gametype**: test-29926 | **Engine**: recoil_2025.06.19

_Note:_ send_resources stays audit-visible but not snapshot-verifiable with the current wire format.

### cmd-set-auto-repair-level

- **Outcome**: blocked
- **Dispatch citation**: `src/circuit/grpc/CommandDispatch.cpp:408-416`
- **Evidence shape**: snapshot_diff
- **Channel** / **Hypothesis class**: — / effect_not_snapshotable
- **Gametype**: test-29926 | **Engine**: recoil_2025.06.19

**Hypothesis**: set_auto_repair_level is wired through the dispatcher but still needs a distinguishing repro to separate effect_not_snapshotable from a genuine dispatcher defect.

**Falsification test**:

```bash
tests/headless/audit/hypothesis.sh cmd-set-auto-repair-level effect_not_snapshotable
```

_Note:_ Generated from the 003 registry gap list; promote to verified when the live repro is captured.

### cmd-set-base

- **Outcome**: broken
- **Dispatch citation**: `src/circuit/grpc/CommandDispatch.cpp:337-345`
- **Evidence shape**: snapshot_diff
- **Channel** / **Hypothesis class**: — / dispatcher_defect
- **Gametype**: test-29926 | **Engine**: recoil_2025.06.19

**Hypothesis**: set_base is wired through the dispatcher but still needs a distinguishing repro to separate dispatcher_defect from a genuine dispatcher defect.

**Falsification test**:

```bash
tests/headless/audit/hypothesis.sh cmd-set-base dispatcher_defect
```

_Note:_ Generated from the 003 registry gap list; promote to verified when the live repro is captured.

### cmd-set-fire-state

- **Outcome**: blocked
- **Dispatch citation**: `src/circuit/grpc/CommandDispatch.cpp:61-61`
- **Evidence shape**: snapshot_diff
- **Channel** / **Hypothesis class**: — / effect_not_snapshotable
- **Gametype**: test-29926 | **Engine**: recoil_2025.06.19

**Hypothesis**: set_fire_state is wired through the dispatcher but still needs a distinguishing repro to separate effect_not_snapshotable from a genuine dispatcher defect.

**Falsification test**:

```bash
tests/headless/audit/hypothesis.sh cmd-set-fire-state effect_not_snapshotable
```

_Note:_ Generated from the 003 registry gap list; promote to verified when the live repro is captured.

### cmd-set-idle-mode

- **Outcome**: blocked
- **Dispatch citation**: `src/circuit/grpc/CommandDispatch.cpp:417-429`
- **Evidence shape**: snapshot_diff
- **Channel** / **Hypothesis class**: — / effect_not_snapshotable
- **Gametype**: test-29926 | **Engine**: recoil_2025.06.19

**Hypothesis**: set_idle_mode is wired through the dispatcher but still needs a distinguishing repro to separate effect_not_snapshotable from a genuine dispatcher defect.

**Falsification test**:

```bash
tests/headless/audit/hypothesis.sh cmd-set-idle-mode effect_not_snapshotable
```

_Note:_ Generated from the 003 registry gap list; promote to verified when the live repro is captured.

### cmd-set-move-state

- **Outcome**: blocked
- **Dispatch citation**: `src/circuit/grpc/CommandDispatch.cpp:62-73`
- **Evidence shape**: snapshot_diff
- **Channel** / **Hypothesis class**: — / effect_not_snapshotable
- **Gametype**: test-29926 | **Engine**: recoil_2025.06.19

**Hypothesis**: set_move_state is wired through the dispatcher but still needs a distinguishing repro to separate effect_not_snapshotable from a genuine dispatcher defect.

**Falsification test**:

```bash
tests/headless/audit/hypothesis.sh cmd-set-move-state effect_not_snapshotable
```

_Note:_ Generated from the 003 registry gap list; promote to verified when the live repro is captured.

### cmd-set-my-income-share-direct

- **Outcome**: dispatched-only
- **Dispatch citation**: `src/circuit/grpc/CommandDispatch.cpp:505-512`
- **Evidence shape**: not_wire_observable
- **Channel** / **Hypothesis class**: team_global / —
- **Gametype**: test-29926 | **Engine**: recoil_2025.06.19

_Note:_ set_my_income_share_direct stays audit-visible but not snapshot-verifiable with the current wire format.

### cmd-set-on-off

- **Outcome**: blocked
- **Dispatch citation**: `src/circuit/grpc/CommandDispatch.cpp:228-236`
- **Evidence shape**: snapshot_diff
- **Channel** / **Hypothesis class**: — / effect_not_snapshotable
- **Gametype**: test-29926 | **Engine**: recoil_2025.06.19

**Hypothesis**: set_on_off is wired through the dispatcher but still needs a distinguishing repro to separate effect_not_snapshotable from a genuine dispatcher defect.

**Falsification test**:

```bash
tests/headless/audit/hypothesis.sh cmd-set-on-off effect_not_snapshotable
```

_Note:_ Generated from the 003 registry gap list; promote to verified when the live repro is captured.

### cmd-set-repeat

- **Outcome**: blocked
- **Dispatch citation**: `src/circuit/grpc/CommandDispatch.cpp:237-245`
- **Evidence shape**: snapshot_diff
- **Channel** / **Hypothesis class**: — / effect_not_snapshotable
- **Gametype**: test-29926 | **Engine**: recoil_2025.06.19

**Hypothesis**: set_repeat is wired through the dispatcher but still needs a distinguishing repro to separate effect_not_snapshotable from a genuine dispatcher defect.

**Falsification test**:

```bash
tests/headless/audit/hypothesis.sh cmd-set-repeat effect_not_snapshotable
```

_Note:_ Generated from the 003 registry gap list; promote to verified when the live repro is captured.

### cmd-set-share-level

- **Outcome**: dispatched-only
- **Dispatch citation**: `src/circuit/grpc/CommandDispatch.cpp:513-523`
- **Evidence shape**: not_wire_observable
- **Channel** / **Hypothesis class**: team_global / —
- **Gametype**: test-29926 | **Engine**: recoil_2025.06.19

_Note:_ set_share_level stays audit-visible but not snapshot-verifiable with the current wire format.

### cmd-set-trajectory

- **Outcome**: blocked
- **Dispatch citation**: `src/circuit/grpc/CommandDispatch.cpp:399-407`
- **Evidence shape**: snapshot_diff
- **Channel** / **Hypothesis class**: — / effect_not_snapshotable
- **Gametype**: test-29926 | **Engine**: recoil_2025.06.19

**Hypothesis**: set_trajectory is wired through the dispatcher but still needs a distinguishing repro to separate effect_not_snapshotable from a genuine dispatcher defect.

**Falsification test**:

```bash
tests/headless/audit/hypothesis.sh cmd-set-trajectory effect_not_snapshotable
```

_Note:_ Generated from the 003 registry gap list; promote to verified when the live repro is captured.

### cmd-set-wanted-max-speed

- **Outcome**: blocked
- **Dispatch citation**: `src/circuit/grpc/CommandDispatch.cpp:60-60`
- **Evidence shape**: snapshot_diff
- **Channel** / **Hypothesis class**: — / effect_not_snapshotable
- **Gametype**: test-29926 | **Engine**: recoil_2025.06.19

**Hypothesis**: set_wanted_max_speed is wired through the dispatcher but still needs a distinguishing repro to separate effect_not_snapshotable from a genuine dispatcher defect.

**Falsification test**:

```bash
tests/headless/audit/hypothesis.sh cmd-set-wanted-max-speed effect_not_snapshotable
```

_Note:_ Generated from the 003 registry gap list; promote to verified when the live repro is captured.

### cmd-squad-wait

- **Outcome**: blocked
- **Dispatch citation**: `src/circuit/grpc/CommandDispatch.cpp:262-270`
- **Evidence shape**: snapshot_diff
- **Channel** / **Hypothesis class**: — / effect_not_snapshotable
- **Gametype**: test-29926 | **Engine**: recoil_2025.06.19

**Hypothesis**: squad_wait is wired through the dispatcher but still needs a distinguishing repro to separate effect_not_snapshotable from a genuine dispatcher defect.

**Falsification test**:

```bash
tests/headless/audit/hypothesis.sh cmd-squad-wait effect_not_snapshotable
```

_Note:_ Generated from the 003 registry gap list; promote to verified when the live repro is captured.

### cmd-stockpile

- **Outcome**: blocked
- **Dispatch citation**: `src/circuit/grpc/CommandDispatch.cpp:246-252`
- **Evidence shape**: snapshot_diff
- **Channel** / **Hypothesis class**: — / effect_not_snapshotable
- **Gametype**: test-29926 | **Engine**: recoil_2025.06.19

**Hypothesis**: stockpile is wired through the dispatcher but still needs a distinguishing repro to separate effect_not_snapshotable from a genuine dispatcher defect.

**Falsification test**:

```bash
tests/headless/audit/hypothesis.sh cmd-stockpile effect_not_snapshotable
```

_Note:_ Generated from the 003 registry gap list; promote to verified when the live repro is captured.

### cmd-stop

- **Outcome**: blocked
- **Dispatch citation**: `src/circuit/grpc/CommandDispatch.cpp:43-43`
- **Evidence shape**: snapshot_diff
- **Channel** / **Hypothesis class**: — / effect_not_snapshotable
- **Gametype**: test-29926 | **Engine**: recoil_2025.06.19

**Hypothesis**: stop is wired through the dispatcher but still needs a distinguishing repro to separate effect_not_snapshotable from a genuine dispatcher defect.

**Falsification test**:

```bash
tests/headless/audit/hypothesis.sh cmd-stop effect_not_snapshotable
```

_Note:_ Generated from the 003 registry gap list; promote to verified when the live repro is captured.

### cmd-timed-wait

- **Outcome**: blocked
- **Dispatch citation**: `src/circuit/grpc/CommandDispatch.cpp:45-45`
- **Evidence shape**: snapshot_diff
- **Channel** / **Hypothesis class**: — / effect_not_snapshotable
- **Gametype**: test-29926 | **Engine**: recoil_2025.06.19

**Hypothesis**: timed_wait is wired through the dispatcher but still needs a distinguishing repro to separate effect_not_snapshotable from a genuine dispatcher defect.

**Falsification test**:

```bash
tests/headless/audit/hypothesis.sh cmd-timed-wait effect_not_snapshotable
```

_Note:_ Generated from the 003 registry gap list; promote to verified when the live repro is captured.

### cmd-unload-unit

- **Outcome**: blocked
- **Dispatch citation**: `src/circuit/grpc/CommandDispatch.cpp:378-388`
- **Evidence shape**: snapshot_diff
- **Channel** / **Hypothesis class**: — / target_missing
- **Gametype**: test-29926 | **Engine**: recoil_2025.06.19

**Hypothesis**: unload_unit is wired through the dispatcher but still needs a distinguishing repro to separate target_missing from a genuine dispatcher defect.

**Falsification test**:

```bash
tests/headless/audit/hypothesis.sh cmd-unload-unit target_missing
```

_Note:_ Generated from the 003 registry gap list; promote to verified when the live repro is captured.

### cmd-unload-units-area

- **Outcome**: blocked
- **Dispatch citation**: `src/circuit/grpc/CommandDispatch.cpp:389-398`
- **Evidence shape**: snapshot_diff
- **Channel** / **Hypothesis class**: — / target_missing
- **Gametype**: test-29926 | **Engine**: recoil_2025.06.19

**Hypothesis**: unload_units_area is wired through the dispatcher but still needs a distinguishing repro to separate target_missing from a genuine dispatcher defect.

**Falsification test**:

```bash
tests/headless/audit/hypothesis.sh cmd-unload-units-area target_missing
```

_Note:_ Generated from the 003 registry gap list; promote to verified when the live repro is captured.

### cmd-wait

- **Outcome**: blocked
- **Dispatch citation**: `src/circuit/grpc/CommandDispatch.cpp:44-44`
- **Evidence shape**: snapshot_diff
- **Channel** / **Hypothesis class**: — / effect_not_snapshotable
- **Gametype**: test-29926 | **Engine**: recoil_2025.06.19

**Hypothesis**: wait is wired through the dispatcher but still needs a distinguishing repro to separate effect_not_snapshotable from a genuine dispatcher defect.

**Falsification test**:

```bash
tests/headless/audit/hypothesis.sh cmd-wait effect_not_snapshotable
```

_Note:_ Generated from the 003 registry gap list; promote to verified when the live repro is captured.

## AICommand arms — channel_b_query

### cmd-free-path

- **Outcome**: dispatched-only
- **Dispatch citation**: `src/circuit/grpc/CommandDispatch.cpp:476-481`
- **Evidence shape**: dispatch_ack_only
- **Channel** / **Hypothesis class**: channel_b_query / —
- **Gametype**: test-29926 | **Engine**: recoil_2025.06.19

_Note:_ free_path stays audit-visible but not snapshot-verifiable with the current wire format.

### cmd-get-approx-length

- **Outcome**: dispatched-only
- **Dispatch citation**: `src/circuit/grpc/CommandDispatch.cpp:460-469`
- **Evidence shape**: dispatch_ack_only
- **Channel** / **Hypothesis class**: channel_b_query / —
- **Gametype**: test-29926 | **Engine**: recoil_2025.06.19

_Note:_ get_approx_length stays audit-visible but not snapshot-verifiable with the current wire format.

### cmd-get-next-waypoint

- **Outcome**: dispatched-only
- **Dispatch citation**: `src/circuit/grpc/CommandDispatch.cpp:470-475`
- **Evidence shape**: dispatch_ack_only
- **Channel** / **Hypothesis class**: channel_b_query / —
- **Gametype**: test-29926 | **Engine**: recoil_2025.06.19

_Note:_ get_next_waypoint stays audit-visible but not snapshot-verifiable with the current wire format.

### cmd-group-add-unit

- **Outcome**: dispatched-only
- **Dispatch citation**: `src/circuit/grpc/CommandDispatch.cpp:524-532`
- **Evidence shape**: dispatch_ack_only
- **Channel** / **Hypothesis class**: channel_b_query / —
- **Gametype**: test-29926 | **Engine**: recoil_2025.06.19

_Note:_ group_add_unit stays audit-visible but not snapshot-verifiable with the current wire format.

### cmd-group-remove-unit

- **Outcome**: dispatched-only
- **Dispatch citation**: `src/circuit/grpc/CommandDispatch.cpp:533-544`
- **Evidence shape**: dispatch_ack_only
- **Channel** / **Hypothesis class**: channel_b_query / —
- **Gametype**: test-29926 | **Engine**: recoil_2025.06.19

_Note:_ group_remove_unit stays audit-visible but not snapshot-verifiable with the current wire format.

### cmd-init-path

- **Outcome**: dispatched-only
- **Dispatch citation**: `src/circuit/grpc/CommandDispatch.cpp:449-459`
- **Evidence shape**: dispatch_ack_only
- **Channel** / **Hypothesis class**: channel_b_query / —
- **Gametype**: test-29926 | **Engine**: recoil_2025.06.19

_Note:_ init_path stays audit-visible but not snapshot-verifiable with the current wire format.

## AICommand arms — channel_c_lua

### cmd-call-lua-rules

- **Outcome**: dispatched-only
- **Dispatch citation**: `src/circuit/grpc/CommandDispatch.cpp:482-488`
- **Evidence shape**: not_wire_observable
- **Channel** / **Hypothesis class**: channel_c_lua / —
- **Gametype**: test-29926 | **Engine**: recoil_2025.06.19

_Note:_ call_lua_rules stays audit-visible but not snapshot-verifiable with the current wire format.

### cmd-call-lua-ui

- **Outcome**: dispatched-only
- **Dispatch citation**: `src/circuit/grpc/CommandDispatch.cpp:489-495`
- **Evidence shape**: not_wire_observable
- **Channel** / **Hypothesis class**: channel_c_lua / —
- **Gametype**: test-29926 | **Engine**: recoil_2025.06.19

_Note:_ call_lua_ui stays audit-visible but not snapshot-verifiable with the current wire format.

### cmd-create-line-figure

- **Outcome**: dispatched-only
- **Dispatch citation**: `src/circuit/grpc/CommandDispatch.cpp:581-594`
- **Evidence shape**: not_wire_observable
- **Channel** / **Hypothesis class**: drawer_only / —
- **Gametype**: test-29926 | **Engine**: recoil_2025.06.19

_Note:_ create_line_figure stays audit-visible but not snapshot-verifiable with the current wire format.

### cmd-create-spline-figure

- **Outcome**: dispatched-only
- **Dispatch citation**: `src/circuit/grpc/CommandDispatch.cpp:565-580`
- **Evidence shape**: not_wire_observable
- **Channel** / **Hypothesis class**: drawer_only / —
- **Gametype**: test-29926 | **Engine**: recoil_2025.06.19

_Note:_ create_spline_figure stays audit-visible but not snapshot-verifiable with the current wire format.

### cmd-draw-add-line

- **Outcome**: dispatched-only
- **Dispatch citation**: `src/circuit/grpc/CommandDispatch.cpp:552-558`
- **Evidence shape**: not_wire_observable
- **Channel** / **Hypothesis class**: drawer_only / —
- **Gametype**: test-29926 | **Engine**: recoil_2025.06.19

_Note:_ draw_add_line stays audit-visible but not snapshot-verifiable with the current wire format.

### cmd-draw-add-point

- **Outcome**: dispatched-only
- **Dispatch citation**: `src/circuit/grpc/CommandDispatch.cpp:545-551`
- **Evidence shape**: not_wire_observable
- **Channel** / **Hypothesis class**: drawer_only / —
- **Gametype**: test-29926 | **Engine**: recoil_2025.06.19

_Note:_ draw_add_point stays audit-visible but not snapshot-verifiable with the current wire format.

### cmd-draw-remove-point

- **Outcome**: dispatched-only
- **Dispatch citation**: `src/circuit/grpc/CommandDispatch.cpp:559-564`
- **Evidence shape**: not_wire_observable
- **Channel** / **Hypothesis class**: drawer_only / —
- **Gametype**: test-29926 | **Engine**: recoil_2025.06.19

_Note:_ draw_remove_point stays audit-visible but not snapshot-verifiable with the current wire format.

### cmd-draw-unit

- **Outcome**: dispatched-only
- **Dispatch citation**: `src/circuit/grpc/CommandDispatch.cpp:627-642`
- **Evidence shape**: not_wire_observable
- **Channel** / **Hypothesis class**: drawer_only / —
- **Gametype**: test-29926 | **Engine**: recoil_2025.06.19

_Note:_ draw_unit stays audit-visible but not snapshot-verifiable with the current wire format.

### cmd-remove-figure

- **Outcome**: dispatched-only
- **Dispatch citation**: `src/circuit/grpc/CommandDispatch.cpp:619-626`
- **Evidence shape**: not_wire_observable
- **Channel** / **Hypothesis class**: drawer_only / —
- **Gametype**: test-29926 | **Engine**: recoil_2025.06.19

_Note:_ remove_figure stays audit-visible but not snapshot-verifiable with the current wire format.

### cmd-send-text-message

- **Outcome**: dispatched-only
- **Dispatch citation**: `src/circuit/grpc/CommandDispatch.cpp:430-436`
- **Evidence shape**: not_wire_observable
- **Channel** / **Hypothesis class**: channel_c_lua / —
- **Gametype**: test-29926 | **Engine**: recoil_2025.06.19

_Note:_ send_text_message stays audit-visible but not snapshot-verifiable with the current wire format.

### cmd-set-figure-color

- **Outcome**: dispatched-only
- **Dispatch citation**: `src/circuit/grpc/CommandDispatch.cpp:605-618`
- **Evidence shape**: not_wire_observable
- **Channel** / **Hypothesis class**: drawer_only / —
- **Gametype**: test-29926 | **Engine**: recoil_2025.06.19

_Note:_ set_figure_color stays audit-visible but not snapshot-verifiable with the current wire format.

### cmd-set-figure-position

- **Outcome**: dispatched-only
- **Dispatch citation**: `src/circuit/grpc/CommandDispatch.cpp:595-604`
- **Evidence shape**: not_wire_observable
- **Channel** / **Hypothesis class**: drawer_only / —
- **Gametype**: test-29926 | **Engine**: recoil_2025.06.19

_Note:_ set_figure_position stays audit-visible but not snapshot-verifiable with the current wire format.

### cmd-set-last-pos-message

- **Outcome**: dispatched-only
- **Dispatch citation**: `src/circuit/grpc/CommandDispatch.cpp:437-442`
- **Evidence shape**: not_wire_observable
- **Channel** / **Hypothesis class**: channel_c_lua / —
- **Gametype**: test-29926 | **Engine**: recoil_2025.06.19

_Note:_ set_last_pos_message stays audit-visible but not snapshot-verifiable with the current wire format.

## AICommand arms — cheats-gated

### cmd-give-me

- **Outcome**: blocked
- **Dispatch citation**: `src/circuit/grpc/CommandDispatch.cpp:672-696`
- **Evidence shape**: snapshot_diff
- **Channel** / **Hypothesis class**: — / cheats_required
- **Gametype**: test-29926 | **Engine**: recoil_2025.06.19

**Hypothesis**: give_me is wired through the dispatcher but still needs a distinguishing repro to separate cheats_required from a genuine dispatcher defect.

**Falsification test**:

```bash
tests/headless/audit/hypothesis.sh cmd-give-me cheats_required
```

_Note:_ Generated from the 003 registry gap list; promote to verified when the live repro is captured.

### cmd-give-me-new-unit

- **Outcome**: blocked
- **Dispatch citation**: `src/circuit/grpc/CommandDispatch.cpp:643-653`
- **Evidence shape**: snapshot_diff
- **Channel** / **Hypothesis class**: — / cheats_required
- **Gametype**: test-29926 | **Engine**: recoil_2025.06.19

**Hypothesis**: give_me_new_unit is wired through the dispatcher but still needs a distinguishing repro to separate cheats_required from a genuine dispatcher defect.

**Falsification test**:

```bash
tests/headless/audit/hypothesis.sh cmd-give-me-new-unit cheats_required
```

_Note:_ Generated from the 003 registry gap list; promote to verified when the live repro is captured.

## Non-determinism notes

> This checked-in seed audit records the current hypothesis buckets and recipes. Re-run
> `tests/headless/audit/repro-stability.sh` on the reference host to refresh flip-rate evidence.

## Phase-2 Attribution

> `phase1_reissuance` rows cite the checked-in Phase-2 dispatcher-only smoke seed below.

# Phase-2 Macro Chain Smoke Report

| Step | Scenario | Phase-2 result |
|---|---|---|
| Step 1 | Commander builds armlab | PASS |
| Step 2 | Armlab builds armflash | PASS |
| Step 3 | Armflash moves to target position | PASS |
| Step 4 | Armflash attacks enemy | PASS |

Phase-2 attribution summary:

- `cmd-move-unit`, `cmd-fight`, and `cmd-patrol` keep their `phase1_reissuance` classification in this seed audit.
- The generated rows cite this report directly for Phase-2 attribution evidence.

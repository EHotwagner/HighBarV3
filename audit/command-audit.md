# Gateway Command Audit

> Latest completed run: `live-audit-20260422T064705Z`
> Deliverables: command-audit=refreshed, hypothesis-plan=refreshed, v2-v3-ledger=refreshed

## Refresh Summary

```text
Run: live-audit-20260422T064705Z
Deliverables: command-audit=refreshed, hypothesis-plan=refreshed, v2-v3-ledger=refreshed
Counts: verified=10, blocked=39, broken=1, drifted=0, not_refreshed=0
```

## RPCs (8)

### rpc-hello

- **Outcome**: verified
- **Freshness**: refreshed-live
- **Dispatch citation**: `src/circuit/grpc/HighBarService.cpp:134-158`
- **Evidence shape**: engine_log
- **Channel** / **Hypothesis class**: — / —
- **Gametype**: test-29926 | **Engine**: recoil_2025.06.19

**Evidence**:

```text
RPC completed through the V3 gRPC service path in the latest refresh run.
```

**Reproduction recipe**:

```bash
tests/headless/audit/repro.sh rpc-hello --phase=1
```

**Latest row report**: `build/reports/repro-rpc-hello.md`

_Note:_ Observed through the manifest-backed refresh workflow.

### rpc-stream-state

- **Outcome**: verified
- **Freshness**: refreshed-live
- **Dispatch citation**: `src/circuit/grpc/HighBarService.cpp:299-323`
- **Evidence shape**: engine_log
- **Channel** / **Hypothesis class**: — / —
- **Gametype**: test-29926 | **Engine**: recoil_2025.06.19

**Evidence**:

```text
RPC completed through the V3 gRPC service path in the latest refresh run.
```

**Reproduction recipe**:

```bash
tests/headless/audit/repro.sh rpc-stream-state --phase=1
```

**Latest row report**: `build/reports/repro-rpc-stream-state.md`

**Ledger links**: [`client-recvbytes-infinite-loop`](v2-v3-ledger.md#client-recvbytes-infinite-loop), [`max-message-size-8mb`](v2-v3-ledger.md#max-message-size-8mb)

_Note:_ Observed through the manifest-backed refresh workflow.

### rpc-submit-commands

- **Outcome**: verified
- **Freshness**: refreshed-live
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

**Latest row report**: `build/reports/repro-rpc-submit-commands.md`

**Ledger links**: [`single-connection-lockout`](v2-v3-ledger.md#single-connection-lockout), [`frame-budget-timeout`](v2-v3-ledger.md#frame-budget-timeout)

_Note:_ Observed through the manifest-backed refresh workflow.

### rpc-invoke-callback

- **Outcome**: verified
- **Freshness**: refreshed-live
- **Dispatch citation**: `src/circuit/grpc/HighBarService.cpp:677-701`
- **Evidence shape**: engine_log
- **Channel** / **Hypothesis class**: — / —
- **Gametype**: test-29926 | **Engine**: recoil_2025.06.19

**Evidence**:

```text
RPC completed through the V3 gRPC service path in the latest refresh run.
```

**Reproduction recipe**:

```bash
tests/headless/audit/repro.sh rpc-invoke-callback --phase=1
```

**Latest row report**: `build/reports/repro-rpc-invoke-callback.md`

**Ledger links**: [`callback-frame-interleaving`](v2-v3-ledger.md#callback-frame-interleaving)

_Note:_ Observed through the manifest-backed refresh workflow.

### rpc-save

- **Outcome**: verified
- **Freshness**: refreshed-live
- **Dispatch citation**: `src/circuit/grpc/HighBarService.cpp:677-701`
- **Evidence shape**: engine_log
- **Channel** / **Hypothesis class**: — / —
- **Gametype**: test-29926 | **Engine**: recoil_2025.06.19

**Evidence**:

```text
Save RPC completed through the authenticated service path during the latest refresh run.
```

**Reproduction recipe**:

```bash
tests/headless/audit/repro.sh rpc-save --phase=1
```

**Latest row report**: `build/reports/repro-rpc-save.md`

**Ledger links**: [`save-load-todos`](v2-v3-ledger.md#save-load-todos)

_Note:_ Observed through the manifest-backed refresh workflow.

### rpc-load

- **Outcome**: verified
- **Freshness**: refreshed-live
- **Dispatch citation**: `src/circuit/grpc/HighBarService.cpp:677-701`
- **Evidence shape**: engine_log
- **Channel** / **Hypothesis class**: — / —
- **Gametype**: test-29926 | **Engine**: recoil_2025.06.19

**Evidence**:

```text
Load RPC completed through the authenticated service path during the latest refresh run.
```

**Reproduction recipe**:

```bash
tests/headless/audit/repro.sh rpc-load --phase=1
```

**Latest row report**: `build/reports/repro-rpc-load.md`

_Note:_ Observed through the manifest-backed refresh workflow.

### rpc-get-runtime-counters

- **Outcome**: dispatched-only
- **Freshness**: refreshed-live
- **Dispatch citation**: `src/circuit/grpc/HighBarService.cpp:231-255`
- **Evidence shape**: dispatch_ack_only
- **Channel** / **Hypothesis class**: team_global / —
- **Gametype**: test-29926 | **Engine**: recoil_2025.06.19

**Reproduction recipe**:

```bash
tests/headless/audit/repro.sh rpc-get-runtime-counters --phase=1
```

**Latest row report**: `build/reports/repro-rpc-get-runtime-counters.md`

_Note:_ Observed through the manifest-backed refresh workflow.

### rpc-request-snapshot

- **Outcome**: verified
- **Freshness**: refreshed-live
- **Dispatch citation**: `src/circuit/grpc/HighBarService.cpp:747-771`
- **Evidence shape**: engine_log
- **Channel** / **Hypothesis class**: — / —
- **Gametype**: test-29926 | **Engine**: recoil_2025.06.19

**Evidence**:

```text
RequestSnapshot scheduled a forced snapshot on the next engine frame during the latest refresh run.
```

**Reproduction recipe**:

```bash
tests/headless/audit/repro.sh rpc-request-snapshot --phase=1
```

**Latest row report**: `build/reports/repro-rpc-request-snapshot.md`

_Note:_ Observed through the manifest-backed refresh workflow.

## AICommand arms — channel_a_command

### cmd-attack

- **Outcome**: verified
- **Freshness**: refreshed-live
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

**Latest row report**: `build/reports/repro-cmd-attack.md`

_Note:_ Observed through the manifest-backed refresh workflow.

### cmd-attack-area

- **Outcome**: blocked
- **Freshness**: refreshed-live
- **Dispatch citation**: `src/circuit/grpc/CommandDispatch.cpp:50-50`
- **Evidence shape**: snapshot_diff
- **Channel** / **Hypothesis class**: — / target_missing
- **Gametype**: test-29926 | **Engine**: recoil_2025.06.19

**Hypothesis**: attack_area still needs a distinguishing live repro to separate target_missing from a genuine dispatcher defect.

**Falsification test**:

```bash
tests/headless/audit/hypothesis.sh cmd-attack-area target_missing
```

**Reproduction recipe**:

```bash
tests/headless/audit/repro.sh cmd-attack-area --phase=1
```

**Latest row report**: `build/reports/repro-cmd-attack-area.md`

_Note:_ Classified from the latest manifest-backed refresh.

### cmd-build-unit

- **Outcome**: verified
- **Freshness**: refreshed-live
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

**Latest row report**: `build/reports/repro-cmd-build-unit.md`

_Note:_ Observed through the manifest-backed refresh workflow.

### cmd-capture

- **Outcome**: blocked
- **Freshness**: refreshed-live
- **Dispatch citation**: `src/circuit/grpc/CommandDispatch.cpp:219-227`
- **Evidence shape**: snapshot_diff
- **Channel** / **Hypothesis class**: — / target_missing
- **Gametype**: test-29926 | **Engine**: recoil_2025.06.19

**Hypothesis**: capture still needs a distinguishing live repro to separate target_missing from a genuine dispatcher defect.

**Falsification test**:

```bash
tests/headless/audit/hypothesis.sh cmd-capture target_missing
```

**Reproduction recipe**:

```bash
tests/headless/audit/repro.sh cmd-capture --phase=1
```

**Latest row report**: `build/reports/repro-cmd-capture.md`

_Note:_ Classified from the latest manifest-backed refresh.

### cmd-capture-area

- **Outcome**: blocked
- **Freshness**: refreshed-live
- **Dispatch citation**: `src/circuit/grpc/CommandDispatch.cpp:327-336`
- **Evidence shape**: snapshot_diff
- **Channel** / **Hypothesis class**: — / target_missing
- **Gametype**: test-29926 | **Engine**: recoil_2025.06.19

**Hypothesis**: capture_area still needs a distinguishing live repro to separate target_missing from a genuine dispatcher defect.

**Falsification test**:

```bash
tests/headless/audit/hypothesis.sh cmd-capture-area target_missing
```

**Reproduction recipe**:

```bash
tests/headless/audit/repro.sh cmd-capture-area --phase=1
```

**Latest row report**: `build/reports/repro-cmd-capture-area.md`

_Note:_ Classified from the latest manifest-backed refresh.

### cmd-custom

- **Outcome**: blocked
- **Freshness**: refreshed-live
- **Dispatch citation**: `src/circuit/grpc/CommandDispatch.cpp:496-504`
- **Evidence shape**: snapshot_diff
- **Channel** / **Hypothesis class**: — / target_missing
- **Gametype**: test-29926 | **Engine**: recoil_2025.06.19

**Hypothesis**: custom still needs a distinguishing live repro to separate target_missing from a genuine dispatcher defect.

**Falsification test**:

```bash
tests/headless/audit/hypothesis.sh cmd-custom target_missing
```

**Reproduction recipe**:

```bash
tests/headless/audit/repro.sh cmd-custom --phase=1
```

**Latest row report**: `build/reports/repro-cmd-custom.md`

_Note:_ Classified from the latest manifest-backed refresh.

### cmd-death-wait

- **Outcome**: blocked
- **Freshness**: refreshed-live
- **Dispatch citation**: `src/circuit/grpc/CommandDispatch.cpp:271-279`
- **Evidence shape**: snapshot_diff
- **Channel** / **Hypothesis class**: — / effect_not_snapshotable
- **Gametype**: test-29926 | **Engine**: recoil_2025.06.19

**Hypothesis**: death_wait still needs a distinguishing live repro to separate effect_not_snapshotable from a genuine dispatcher defect.

**Falsification test**:

```bash
tests/headless/audit/hypothesis.sh cmd-death-wait effect_not_snapshotable
```

**Reproduction recipe**:

```bash
tests/headless/audit/repro.sh cmd-death-wait --phase=1
```

**Latest row report**: `build/reports/repro-cmd-death-wait.md`

_Note:_ Classified from the latest manifest-backed refresh.

### cmd-dgun

- **Outcome**: blocked
- **Freshness**: refreshed-live
- **Dispatch citation**: `src/circuit/grpc/CommandDispatch.cpp:59-59`
- **Evidence shape**: snapshot_diff
- **Channel** / **Hypothesis class**: — / target_missing
- **Gametype**: test-29926 | **Engine**: recoil_2025.06.19

**Hypothesis**: dgun still needs a distinguishing live repro to separate target_missing from a genuine dispatcher defect.

**Falsification test**:

```bash
tests/headless/audit/hypothesis.sh cmd-dgun target_missing
```

**Reproduction recipe**:

```bash
tests/headless/audit/repro.sh cmd-dgun --phase=1
```

**Latest row report**: `build/reports/repro-cmd-dgun.md`

_Note:_ Classified from the latest manifest-backed refresh.

### cmd-fight

- **Outcome**: blocked
- **Freshness**: refreshed-live
- **Dispatch citation**: `src/circuit/grpc/CommandDispatch.cpp:48-48`
- **Evidence shape**: snapshot_diff
- **Channel** / **Hypothesis class**: — / phase1_reissuance
- **Gametype**: test-29926 | **Engine**: recoil_2025.06.19

**Hypothesis**: fight still needs a distinguishing live repro to separate phase1_reissuance from a genuine dispatcher defect.

**Falsification test**:

```bash
tests/headless/audit/hypothesis.sh cmd-fight phase1_reissuance
```

**Reproduction recipe**:

```bash
tests/headless/audit/repro.sh cmd-fight --phase=1
```

**Latest row report**: `build/reports/repro-cmd-fight.md`

_Note:_ Classified from the latest manifest-backed refresh. Phase-2 smoke keeps combat follow-up wiring reachable with built-in AI disabled.

### cmd-gather-wait

- **Outcome**: blocked
- **Freshness**: refreshed-live
- **Dispatch citation**: `src/circuit/grpc/CommandDispatch.cpp:280-286`
- **Evidence shape**: snapshot_diff
- **Channel** / **Hypothesis class**: — / effect_not_snapshotable
- **Gametype**: test-29926 | **Engine**: recoil_2025.06.19

**Hypothesis**: gather_wait still needs a distinguishing live repro to separate effect_not_snapshotable from a genuine dispatcher defect.

**Falsification test**:

```bash
tests/headless/audit/hypothesis.sh cmd-gather-wait effect_not_snapshotable
```

**Reproduction recipe**:

```bash
tests/headless/audit/repro.sh cmd-gather-wait --phase=1
```

**Latest row report**: `build/reports/repro-cmd-gather-wait.md`

_Note:_ Classified from the latest manifest-backed refresh.

### cmd-guard

- **Outcome**: blocked
- **Freshness**: refreshed-live
- **Dispatch citation**: `src/circuit/grpc/CommandDispatch.cpp:51-51`
- **Evidence shape**: snapshot_diff
- **Channel** / **Hypothesis class**: — / target_missing
- **Gametype**: test-29926 | **Engine**: recoil_2025.06.19

**Hypothesis**: guard still needs a distinguishing live repro to separate target_missing from a genuine dispatcher defect.

**Falsification test**:

```bash
tests/headless/audit/hypothesis.sh cmd-guard target_missing
```

**Reproduction recipe**:

```bash
tests/headless/audit/repro.sh cmd-guard --phase=1
```

**Latest row report**: `build/reports/repro-cmd-guard.md`

_Note:_ Classified from the latest manifest-backed refresh.

### cmd-load-onto

- **Outcome**: blocked
- **Freshness**: refreshed-live
- **Dispatch citation**: `src/circuit/grpc/CommandDispatch.cpp:369-377`
- **Evidence shape**: snapshot_diff
- **Channel** / **Hypothesis class**: — / target_missing
- **Gametype**: test-29926 | **Engine**: recoil_2025.06.19

**Hypothesis**: load_onto still needs a distinguishing live repro to separate target_missing from a genuine dispatcher defect.

**Falsification test**:

```bash
tests/headless/audit/hypothesis.sh cmd-load-onto target_missing
```

**Reproduction recipe**:

```bash
tests/headless/audit/repro.sh cmd-load-onto --phase=1
```

**Latest row report**: `build/reports/repro-cmd-load-onto.md`

_Note:_ Classified from the latest manifest-backed refresh.

### cmd-load-units

- **Outcome**: blocked
- **Freshness**: refreshed-live
- **Dispatch citation**: `src/circuit/grpc/CommandDispatch.cpp:346-358`
- **Evidence shape**: snapshot_diff
- **Channel** / **Hypothesis class**: — / target_missing
- **Gametype**: test-29926 | **Engine**: recoil_2025.06.19

**Hypothesis**: load_units still needs a distinguishing live repro to separate target_missing from a genuine dispatcher defect.

**Falsification test**:

```bash
tests/headless/audit/hypothesis.sh cmd-load-units target_missing
```

**Reproduction recipe**:

```bash
tests/headless/audit/repro.sh cmd-load-units --phase=1
```

**Latest row report**: `build/reports/repro-cmd-load-units.md`

_Note:_ Classified from the latest manifest-backed refresh.

### cmd-load-units-area

- **Outcome**: blocked
- **Freshness**: refreshed-live
- **Dispatch citation**: `src/circuit/grpc/CommandDispatch.cpp:359-368`
- **Evidence shape**: snapshot_diff
- **Channel** / **Hypothesis class**: — / target_missing
- **Gametype**: test-29926 | **Engine**: recoil_2025.06.19

**Hypothesis**: load_units_area still needs a distinguishing live repro to separate target_missing from a genuine dispatcher defect.

**Falsification test**:

```bash
tests/headless/audit/hypothesis.sh cmd-load-units-area target_missing
```

**Reproduction recipe**:

```bash
tests/headless/audit/repro.sh cmd-load-units-area --phase=1
```

**Latest row report**: `build/reports/repro-cmd-load-units-area.md`

_Note:_ Classified from the latest manifest-backed refresh.

### cmd-move-unit

- **Outcome**: blocked
- **Freshness**: refreshed-live
- **Dispatch citation**: `src/circuit/grpc/CommandDispatch.cpp:46-46`
- **Evidence shape**: snapshot_diff
- **Channel** / **Hypothesis class**: — / phase1_reissuance
- **Gametype**: test-29926 | **Engine**: recoil_2025.06.19

**Hypothesis**: move_unit still needs a distinguishing live repro to separate phase1_reissuance from a genuine dispatcher defect.

**Falsification test**:

```bash
tests/headless/audit/hypothesis.sh cmd-move-unit phase1_reissuance
```

**Reproduction recipe**:

```bash
tests/headless/audit/repro.sh cmd-move-unit --phase=1
```

**Latest row report**: `build/reports/repro-cmd-move-unit.md`

_Note:_ Classified from the latest manifest-backed refresh. Phase-2 macro chain Step 3 PASS with built-in AI disabled.

### cmd-patrol

- **Outcome**: blocked
- **Freshness**: refreshed-live
- **Dispatch citation**: `src/circuit/grpc/CommandDispatch.cpp:47-47`
- **Evidence shape**: snapshot_diff
- **Channel** / **Hypothesis class**: — / phase1_reissuance
- **Gametype**: test-29926 | **Engine**: recoil_2025.06.19

**Hypothesis**: patrol still needs a distinguishing live repro to separate phase1_reissuance from a genuine dispatcher defect.

**Falsification test**:

```bash
tests/headless/audit/hypothesis.sh cmd-patrol phase1_reissuance
```

**Reproduction recipe**:

```bash
tests/headless/audit/repro.sh cmd-patrol --phase=1
```

**Latest row report**: `build/reports/repro-cmd-patrol.md`

_Note:_ Classified from the latest manifest-backed refresh. Phase-2 smoke preserves the movement-chain path without ambient AI reissue.

### cmd-pause-team

- **Outcome**: dispatched-only
- **Freshness**: refreshed-live
- **Dispatch citation**: `src/circuit/grpc/CommandDispatch.cpp:443-448`
- **Evidence shape**: not_wire_observable
- **Channel** / **Hypothesis class**: team_global / —
- **Gametype**: test-29926 | **Engine**: recoil_2025.06.19

**Reproduction recipe**:

```bash
tests/headless/audit/repro.sh cmd-pause-team --phase=1
```

**Latest row report**: `build/reports/repro-cmd-pause-team.md`

_Note:_ pause_team remains live-visible but not snapshot-verifiable with the current wire format.

### cmd-reclaim-area

- **Outcome**: blocked
- **Freshness**: refreshed-live
- **Dispatch citation**: `src/circuit/grpc/CommandDispatch.cpp:54-54`
- **Evidence shape**: snapshot_diff
- **Channel** / **Hypothesis class**: — / target_missing
- **Gametype**: test-29926 | **Engine**: recoil_2025.06.19

**Hypothesis**: reclaim_area still needs a distinguishing live repro to separate target_missing from a genuine dispatcher defect.

**Falsification test**:

```bash
tests/headless/audit/hypothesis.sh cmd-reclaim-area target_missing
```

**Reproduction recipe**:

```bash
tests/headless/audit/repro.sh cmd-reclaim-area --phase=1
```

**Latest row report**: `build/reports/repro-cmd-reclaim-area.md`

_Note:_ Classified from the latest manifest-backed refresh.

### cmd-reclaim-feature

- **Outcome**: blocked
- **Freshness**: refreshed-live
- **Dispatch citation**: `src/circuit/grpc/CommandDispatch.cpp:56-56`
- **Evidence shape**: snapshot_diff
- **Channel** / **Hypothesis class**: — / target_missing
- **Gametype**: test-29926 | **Engine**: recoil_2025.06.19

**Hypothesis**: reclaim_feature still needs a distinguishing live repro to separate target_missing from a genuine dispatcher defect.

**Falsification test**:

```bash
tests/headless/audit/hypothesis.sh cmd-reclaim-feature target_missing
```

**Reproduction recipe**:

```bash
tests/headless/audit/repro.sh cmd-reclaim-feature --phase=1
```

**Latest row report**: `build/reports/repro-cmd-reclaim-feature.md`

_Note:_ Classified from the latest manifest-backed refresh.

### cmd-reclaim-in-area

- **Outcome**: blocked
- **Freshness**: refreshed-live
- **Dispatch citation**: `src/circuit/grpc/CommandDispatch.cpp:55-55`
- **Evidence shape**: snapshot_diff
- **Channel** / **Hypothesis class**: — / target_missing
- **Gametype**: test-29926 | **Engine**: recoil_2025.06.19

**Hypothesis**: reclaim_in_area still needs a distinguishing live repro to separate target_missing from a genuine dispatcher defect.

**Falsification test**:

```bash
tests/headless/audit/hypothesis.sh cmd-reclaim-in-area target_missing
```

**Reproduction recipe**:

```bash
tests/headless/audit/repro.sh cmd-reclaim-in-area --phase=1
```

**Latest row report**: `build/reports/repro-cmd-reclaim-in-area.md`

_Note:_ Classified from the latest manifest-backed refresh.

### cmd-reclaim-unit

- **Outcome**: blocked
- **Freshness**: refreshed-live
- **Dispatch citation**: `src/circuit/grpc/CommandDispatch.cpp:53-53`
- **Evidence shape**: snapshot_diff
- **Channel** / **Hypothesis class**: — / target_missing
- **Gametype**: test-29926 | **Engine**: recoil_2025.06.19

**Hypothesis**: reclaim_unit still needs a distinguishing live repro to separate target_missing from a genuine dispatcher defect.

**Falsification test**:

```bash
tests/headless/audit/hypothesis.sh cmd-reclaim-unit target_missing
```

**Reproduction recipe**:

```bash
tests/headless/audit/repro.sh cmd-reclaim-unit --phase=1
```

**Latest row report**: `build/reports/repro-cmd-reclaim-unit.md`

_Note:_ Classified from the latest manifest-backed refresh.

### cmd-repair

- **Outcome**: blocked
- **Freshness**: refreshed-live
- **Dispatch citation**: `src/circuit/grpc/CommandDispatch.cpp:52-52`
- **Evidence shape**: snapshot_diff
- **Channel** / **Hypothesis class**: — / target_missing
- **Gametype**: test-29926 | **Engine**: recoil_2025.06.19

**Hypothesis**: repair still needs a distinguishing live repro to separate target_missing from a genuine dispatcher defect.

**Falsification test**:

```bash
tests/headless/audit/hypothesis.sh cmd-repair target_missing
```

**Reproduction recipe**:

```bash
tests/headless/audit/repro.sh cmd-repair --phase=1
```

**Latest row report**: `build/reports/repro-cmd-repair.md`

_Note:_ Classified from the latest manifest-backed refresh.

### cmd-restore-area

- **Outcome**: blocked
- **Freshness**: refreshed-live
- **Dispatch citation**: `src/circuit/grpc/CommandDispatch.cpp:308-317`
- **Evidence shape**: snapshot_diff
- **Channel** / **Hypothesis class**: — / target_missing
- **Gametype**: test-29926 | **Engine**: recoil_2025.06.19

**Hypothesis**: restore_area still needs a distinguishing live repro to separate target_missing from a genuine dispatcher defect.

**Falsification test**:

```bash
tests/headless/audit/hypothesis.sh cmd-restore-area target_missing
```

**Reproduction recipe**:

```bash
tests/headless/audit/repro.sh cmd-restore-area --phase=1
```

**Latest row report**: `build/reports/repro-cmd-restore-area.md`

_Note:_ Classified from the latest manifest-backed refresh.

### cmd-resurrect

- **Outcome**: blocked
- **Freshness**: refreshed-live
- **Dispatch citation**: `src/circuit/grpc/CommandDispatch.cpp:318-326`
- **Evidence shape**: snapshot_diff
- **Channel** / **Hypothesis class**: — / target_missing
- **Gametype**: test-29926 | **Engine**: recoil_2025.06.19

**Hypothesis**: resurrect still needs a distinguishing live repro to separate target_missing from a genuine dispatcher defect.

**Falsification test**:

```bash
tests/headless/audit/hypothesis.sh cmd-resurrect target_missing
```

**Reproduction recipe**:

```bash
tests/headless/audit/repro.sh cmd-resurrect --phase=1
```

**Latest row report**: `build/reports/repro-cmd-resurrect.md`

_Note:_ Classified from the latest manifest-backed refresh.

### cmd-resurrect-in-area

- **Outcome**: blocked
- **Freshness**: refreshed-live
- **Dispatch citation**: `src/circuit/grpc/CommandDispatch.cpp:57-57`
- **Evidence shape**: snapshot_diff
- **Channel** / **Hypothesis class**: — / target_missing
- **Gametype**: test-29926 | **Engine**: recoil_2025.06.19

**Hypothesis**: resurrect_in_area still needs a distinguishing live repro to separate target_missing from a genuine dispatcher defect.

**Falsification test**:

```bash
tests/headless/audit/hypothesis.sh cmd-resurrect-in-area target_missing
```

**Reproduction recipe**:

```bash
tests/headless/audit/repro.sh cmd-resurrect-in-area --phase=1
```

**Latest row report**: `build/reports/repro-cmd-resurrect-in-area.md`

_Note:_ Classified from the latest manifest-backed refresh.

### cmd-self-destruct

- **Outcome**: verified
- **Freshness**: refreshed-live
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

**Latest row report**: `build/reports/repro-cmd-self-destruct.md`

_Note:_ Observed through the manifest-backed refresh workflow.

### cmd-send-resources

- **Outcome**: dispatched-only
- **Freshness**: refreshed-live
- **Dispatch citation**: `src/circuit/grpc/CommandDispatch.cpp:654-671`
- **Evidence shape**: not_wire_observable
- **Channel** / **Hypothesis class**: team_global / —
- **Gametype**: test-29926 | **Engine**: recoil_2025.06.19

**Reproduction recipe**:

```bash
tests/headless/audit/repro.sh cmd-send-resources --phase=1
```

**Latest row report**: `build/reports/repro-cmd-send-resources.md`

_Note:_ send_resources remains live-visible but not snapshot-verifiable with the current wire format.

### cmd-set-auto-repair-level

- **Outcome**: blocked
- **Freshness**: refreshed-live
- **Dispatch citation**: `src/circuit/grpc/CommandDispatch.cpp:408-416`
- **Evidence shape**: snapshot_diff
- **Channel** / **Hypothesis class**: — / effect_not_snapshotable
- **Gametype**: test-29926 | **Engine**: recoil_2025.06.19

**Hypothesis**: set_auto_repair_level still needs a distinguishing live repro to separate effect_not_snapshotable from a genuine dispatcher defect.

**Falsification test**:

```bash
tests/headless/audit/hypothesis.sh cmd-set-auto-repair-level effect_not_snapshotable
```

**Reproduction recipe**:

```bash
tests/headless/audit/repro.sh cmd-set-auto-repair-level --phase=1
```

**Latest row report**: `build/reports/repro-cmd-set-auto-repair-level.md`

_Note:_ Classified from the latest manifest-backed refresh.

### cmd-set-base

- **Outcome**: broken
- **Freshness**: refreshed-live
- **Dispatch citation**: `src/circuit/grpc/CommandDispatch.cpp:337-345`
- **Evidence shape**: snapshot_diff
- **Channel** / **Hypothesis class**: — / dispatcher_defect
- **Gametype**: test-29926 | **Engine**: recoil_2025.06.19

**Hypothesis**: set_base still needs a distinguishing live repro to separate dispatcher_defect from a genuine dispatcher defect.

**Falsification test**:

```bash
tests/headless/audit/hypothesis.sh cmd-set-base dispatcher_defect
```

**Reproduction recipe**:

```bash
tests/headless/audit/repro.sh cmd-set-base --phase=1
```

**Latest row report**: `build/reports/repro-cmd-set-base.md`

_Note:_ Classified from the latest manifest-backed refresh.

### cmd-set-fire-state

- **Outcome**: blocked
- **Freshness**: refreshed-live
- **Dispatch citation**: `src/circuit/grpc/CommandDispatch.cpp:61-61`
- **Evidence shape**: snapshot_diff
- **Channel** / **Hypothesis class**: — / effect_not_snapshotable
- **Gametype**: test-29926 | **Engine**: recoil_2025.06.19

**Hypothesis**: set_fire_state still needs a distinguishing live repro to separate effect_not_snapshotable from a genuine dispatcher defect.

**Falsification test**:

```bash
tests/headless/audit/hypothesis.sh cmd-set-fire-state effect_not_snapshotable
```

**Reproduction recipe**:

```bash
tests/headless/audit/repro.sh cmd-set-fire-state --phase=1
```

**Latest row report**: `build/reports/repro-cmd-set-fire-state.md`

_Note:_ Classified from the latest manifest-backed refresh.

### cmd-set-idle-mode

- **Outcome**: blocked
- **Freshness**: refreshed-live
- **Dispatch citation**: `src/circuit/grpc/CommandDispatch.cpp:417-429`
- **Evidence shape**: snapshot_diff
- **Channel** / **Hypothesis class**: — / effect_not_snapshotable
- **Gametype**: test-29926 | **Engine**: recoil_2025.06.19

**Hypothesis**: set_idle_mode still needs a distinguishing live repro to separate effect_not_snapshotable from a genuine dispatcher defect.

**Falsification test**:

```bash
tests/headless/audit/hypothesis.sh cmd-set-idle-mode effect_not_snapshotable
```

**Reproduction recipe**:

```bash
tests/headless/audit/repro.sh cmd-set-idle-mode --phase=1
```

**Latest row report**: `build/reports/repro-cmd-set-idle-mode.md`

_Note:_ Classified from the latest manifest-backed refresh.

### cmd-set-move-state

- **Outcome**: blocked
- **Freshness**: refreshed-live
- **Dispatch citation**: `src/circuit/grpc/CommandDispatch.cpp:62-73`
- **Evidence shape**: snapshot_diff
- **Channel** / **Hypothesis class**: — / effect_not_snapshotable
- **Gametype**: test-29926 | **Engine**: recoil_2025.06.19

**Hypothesis**: set_move_state still needs a distinguishing live repro to separate effect_not_snapshotable from a genuine dispatcher defect.

**Falsification test**:

```bash
tests/headless/audit/hypothesis.sh cmd-set-move-state effect_not_snapshotable
```

**Reproduction recipe**:

```bash
tests/headless/audit/repro.sh cmd-set-move-state --phase=1
```

**Latest row report**: `build/reports/repro-cmd-set-move-state.md`

_Note:_ Classified from the latest manifest-backed refresh.

### cmd-set-my-income-share-direct

- **Outcome**: dispatched-only
- **Freshness**: refreshed-live
- **Dispatch citation**: `src/circuit/grpc/CommandDispatch.cpp:505-512`
- **Evidence shape**: not_wire_observable
- **Channel** / **Hypothesis class**: team_global / —
- **Gametype**: test-29926 | **Engine**: recoil_2025.06.19

**Reproduction recipe**:

```bash
tests/headless/audit/repro.sh cmd-set-my-income-share-direct --phase=1
```

**Latest row report**: `build/reports/repro-cmd-set-my-income-share-direct.md`

_Note:_ set_my_income_share_direct remains live-visible but not snapshot-verifiable with the current wire format.

### cmd-set-on-off

- **Outcome**: blocked
- **Freshness**: refreshed-live
- **Dispatch citation**: `src/circuit/grpc/CommandDispatch.cpp:228-236`
- **Evidence shape**: snapshot_diff
- **Channel** / **Hypothesis class**: — / effect_not_snapshotable
- **Gametype**: test-29926 | **Engine**: recoil_2025.06.19

**Hypothesis**: set_on_off still needs a distinguishing live repro to separate effect_not_snapshotable from a genuine dispatcher defect.

**Falsification test**:

```bash
tests/headless/audit/hypothesis.sh cmd-set-on-off effect_not_snapshotable
```

**Reproduction recipe**:

```bash
tests/headless/audit/repro.sh cmd-set-on-off --phase=1
```

**Latest row report**: `build/reports/repro-cmd-set-on-off.md`

_Note:_ Classified from the latest manifest-backed refresh.

### cmd-set-repeat

- **Outcome**: blocked
- **Freshness**: refreshed-live
- **Dispatch citation**: `src/circuit/grpc/CommandDispatch.cpp:237-245`
- **Evidence shape**: snapshot_diff
- **Channel** / **Hypothesis class**: — / effect_not_snapshotable
- **Gametype**: test-29926 | **Engine**: recoil_2025.06.19

**Hypothesis**: set_repeat still needs a distinguishing live repro to separate effect_not_snapshotable from a genuine dispatcher defect.

**Falsification test**:

```bash
tests/headless/audit/hypothesis.sh cmd-set-repeat effect_not_snapshotable
```

**Reproduction recipe**:

```bash
tests/headless/audit/repro.sh cmd-set-repeat --phase=1
```

**Latest row report**: `build/reports/repro-cmd-set-repeat.md`

_Note:_ Classified from the latest manifest-backed refresh.

### cmd-set-share-level

- **Outcome**: dispatched-only
- **Freshness**: refreshed-live
- **Dispatch citation**: `src/circuit/grpc/CommandDispatch.cpp:513-523`
- **Evidence shape**: not_wire_observable
- **Channel** / **Hypothesis class**: team_global / —
- **Gametype**: test-29926 | **Engine**: recoil_2025.06.19

**Reproduction recipe**:

```bash
tests/headless/audit/repro.sh cmd-set-share-level --phase=1
```

**Latest row report**: `build/reports/repro-cmd-set-share-level.md`

_Note:_ set_share_level remains live-visible but not snapshot-verifiable with the current wire format.

### cmd-set-trajectory

- **Outcome**: blocked
- **Freshness**: refreshed-live
- **Dispatch citation**: `src/circuit/grpc/CommandDispatch.cpp:399-407`
- **Evidence shape**: snapshot_diff
- **Channel** / **Hypothesis class**: — / effect_not_snapshotable
- **Gametype**: test-29926 | **Engine**: recoil_2025.06.19

**Hypothesis**: set_trajectory still needs a distinguishing live repro to separate effect_not_snapshotable from a genuine dispatcher defect.

**Falsification test**:

```bash
tests/headless/audit/hypothesis.sh cmd-set-trajectory effect_not_snapshotable
```

**Reproduction recipe**:

```bash
tests/headless/audit/repro.sh cmd-set-trajectory --phase=1
```

**Latest row report**: `build/reports/repro-cmd-set-trajectory.md`

_Note:_ Classified from the latest manifest-backed refresh.

### cmd-set-wanted-max-speed

- **Outcome**: blocked
- **Freshness**: refreshed-live
- **Dispatch citation**: `src/circuit/grpc/CommandDispatch.cpp:60-60`
- **Evidence shape**: snapshot_diff
- **Channel** / **Hypothesis class**: — / effect_not_snapshotable
- **Gametype**: test-29926 | **Engine**: recoil_2025.06.19

**Hypothesis**: set_wanted_max_speed still needs a distinguishing live repro to separate effect_not_snapshotable from a genuine dispatcher defect.

**Falsification test**:

```bash
tests/headless/audit/hypothesis.sh cmd-set-wanted-max-speed effect_not_snapshotable
```

**Reproduction recipe**:

```bash
tests/headless/audit/repro.sh cmd-set-wanted-max-speed --phase=1
```

**Latest row report**: `build/reports/repro-cmd-set-wanted-max-speed.md`

_Note:_ Classified from the latest manifest-backed refresh.

### cmd-squad-wait

- **Outcome**: blocked
- **Freshness**: refreshed-live
- **Dispatch citation**: `src/circuit/grpc/CommandDispatch.cpp:262-270`
- **Evidence shape**: snapshot_diff
- **Channel** / **Hypothesis class**: — / effect_not_snapshotable
- **Gametype**: test-29926 | **Engine**: recoil_2025.06.19

**Hypothesis**: squad_wait still needs a distinguishing live repro to separate effect_not_snapshotable from a genuine dispatcher defect.

**Falsification test**:

```bash
tests/headless/audit/hypothesis.sh cmd-squad-wait effect_not_snapshotable
```

**Reproduction recipe**:

```bash
tests/headless/audit/repro.sh cmd-squad-wait --phase=1
```

**Latest row report**: `build/reports/repro-cmd-squad-wait.md`

_Note:_ Classified from the latest manifest-backed refresh.

### cmd-stockpile

- **Outcome**: blocked
- **Freshness**: refreshed-live
- **Dispatch citation**: `src/circuit/grpc/CommandDispatch.cpp:246-252`
- **Evidence shape**: snapshot_diff
- **Channel** / **Hypothesis class**: — / effect_not_snapshotable
- **Gametype**: test-29926 | **Engine**: recoil_2025.06.19

**Hypothesis**: stockpile still needs a distinguishing live repro to separate effect_not_snapshotable from a genuine dispatcher defect.

**Falsification test**:

```bash
tests/headless/audit/hypothesis.sh cmd-stockpile effect_not_snapshotable
```

**Reproduction recipe**:

```bash
tests/headless/audit/repro.sh cmd-stockpile --phase=1
```

**Latest row report**: `build/reports/repro-cmd-stockpile.md`

_Note:_ Classified from the latest manifest-backed refresh.

### cmd-stop

- **Outcome**: blocked
- **Freshness**: refreshed-live
- **Dispatch citation**: `src/circuit/grpc/CommandDispatch.cpp:43-43`
- **Evidence shape**: snapshot_diff
- **Channel** / **Hypothesis class**: — / effect_not_snapshotable
- **Gametype**: test-29926 | **Engine**: recoil_2025.06.19

**Hypothesis**: stop still needs a distinguishing live repro to separate effect_not_snapshotable from a genuine dispatcher defect.

**Falsification test**:

```bash
tests/headless/audit/hypothesis.sh cmd-stop effect_not_snapshotable
```

**Reproduction recipe**:

```bash
tests/headless/audit/repro.sh cmd-stop --phase=1
```

**Latest row report**: `build/reports/repro-cmd-stop.md`

_Note:_ Classified from the latest manifest-backed refresh.

### cmd-timed-wait

- **Outcome**: blocked
- **Freshness**: refreshed-live
- **Dispatch citation**: `src/circuit/grpc/CommandDispatch.cpp:45-45`
- **Evidence shape**: snapshot_diff
- **Channel** / **Hypothesis class**: — / effect_not_snapshotable
- **Gametype**: test-29926 | **Engine**: recoil_2025.06.19

**Hypothesis**: timed_wait still needs a distinguishing live repro to separate effect_not_snapshotable from a genuine dispatcher defect.

**Falsification test**:

```bash
tests/headless/audit/hypothesis.sh cmd-timed-wait effect_not_snapshotable
```

**Reproduction recipe**:

```bash
tests/headless/audit/repro.sh cmd-timed-wait --phase=1
```

**Latest row report**: `build/reports/repro-cmd-timed-wait.md`

_Note:_ Classified from the latest manifest-backed refresh.

### cmd-unload-unit

- **Outcome**: blocked
- **Freshness**: refreshed-live
- **Dispatch citation**: `src/circuit/grpc/CommandDispatch.cpp:378-388`
- **Evidence shape**: snapshot_diff
- **Channel** / **Hypothesis class**: — / target_missing
- **Gametype**: test-29926 | **Engine**: recoil_2025.06.19

**Hypothesis**: unload_unit still needs a distinguishing live repro to separate target_missing from a genuine dispatcher defect.

**Falsification test**:

```bash
tests/headless/audit/hypothesis.sh cmd-unload-unit target_missing
```

**Reproduction recipe**:

```bash
tests/headless/audit/repro.sh cmd-unload-unit --phase=1
```

**Latest row report**: `build/reports/repro-cmd-unload-unit.md`

_Note:_ Classified from the latest manifest-backed refresh.

### cmd-unload-units-area

- **Outcome**: blocked
- **Freshness**: refreshed-live
- **Dispatch citation**: `src/circuit/grpc/CommandDispatch.cpp:389-398`
- **Evidence shape**: snapshot_diff
- **Channel** / **Hypothesis class**: — / target_missing
- **Gametype**: test-29926 | **Engine**: recoil_2025.06.19

**Hypothesis**: unload_units_area still needs a distinguishing live repro to separate target_missing from a genuine dispatcher defect.

**Falsification test**:

```bash
tests/headless/audit/hypothesis.sh cmd-unload-units-area target_missing
```

**Reproduction recipe**:

```bash
tests/headless/audit/repro.sh cmd-unload-units-area --phase=1
```

**Latest row report**: `build/reports/repro-cmd-unload-units-area.md`

_Note:_ Classified from the latest manifest-backed refresh.

### cmd-wait

- **Outcome**: blocked
- **Freshness**: refreshed-live
- **Dispatch citation**: `src/circuit/grpc/CommandDispatch.cpp:44-44`
- **Evidence shape**: snapshot_diff
- **Channel** / **Hypothesis class**: — / effect_not_snapshotable
- **Gametype**: test-29926 | **Engine**: recoil_2025.06.19

**Hypothesis**: wait still needs a distinguishing live repro to separate effect_not_snapshotable from a genuine dispatcher defect.

**Falsification test**:

```bash
tests/headless/audit/hypothesis.sh cmd-wait effect_not_snapshotable
```

**Reproduction recipe**:

```bash
tests/headless/audit/repro.sh cmd-wait --phase=1
```

**Latest row report**: `build/reports/repro-cmd-wait.md`

_Note:_ Classified from the latest manifest-backed refresh.

## AICommand arms — channel_b_query

### cmd-free-path

- **Outcome**: dispatched-only
- **Freshness**: refreshed-live
- **Dispatch citation**: `src/circuit/grpc/CommandDispatch.cpp:476-481`
- **Evidence shape**: dispatch_ack_only
- **Channel** / **Hypothesis class**: channel_b_query / —
- **Gametype**: test-29926 | **Engine**: recoil_2025.06.19

**Reproduction recipe**:

```bash
tests/headless/audit/repro.sh cmd-free-path --phase=1
```

**Latest row report**: `build/reports/repro-cmd-free-path.md`

_Note:_ free_path remains live-visible but not snapshot-verifiable with the current wire format.

### cmd-get-approx-length

- **Outcome**: dispatched-only
- **Freshness**: refreshed-live
- **Dispatch citation**: `src/circuit/grpc/CommandDispatch.cpp:460-469`
- **Evidence shape**: dispatch_ack_only
- **Channel** / **Hypothesis class**: channel_b_query / —
- **Gametype**: test-29926 | **Engine**: recoil_2025.06.19

**Reproduction recipe**:

```bash
tests/headless/audit/repro.sh cmd-get-approx-length --phase=1
```

**Latest row report**: `build/reports/repro-cmd-get-approx-length.md`

_Note:_ get_approx_length remains live-visible but not snapshot-verifiable with the current wire format.

### cmd-get-next-waypoint

- **Outcome**: dispatched-only
- **Freshness**: refreshed-live
- **Dispatch citation**: `src/circuit/grpc/CommandDispatch.cpp:470-475`
- **Evidence shape**: dispatch_ack_only
- **Channel** / **Hypothesis class**: channel_b_query / —
- **Gametype**: test-29926 | **Engine**: recoil_2025.06.19

**Reproduction recipe**:

```bash
tests/headless/audit/repro.sh cmd-get-next-waypoint --phase=1
```

**Latest row report**: `build/reports/repro-cmd-get-next-waypoint.md`

_Note:_ get_next_waypoint remains live-visible but not snapshot-verifiable with the current wire format.

### cmd-group-add-unit

- **Outcome**: dispatched-only
- **Freshness**: refreshed-live
- **Dispatch citation**: `src/circuit/grpc/CommandDispatch.cpp:524-532`
- **Evidence shape**: dispatch_ack_only
- **Channel** / **Hypothesis class**: channel_b_query / —
- **Gametype**: test-29926 | **Engine**: recoil_2025.06.19

**Reproduction recipe**:

```bash
tests/headless/audit/repro.sh cmd-group-add-unit --phase=1
```

**Latest row report**: `build/reports/repro-cmd-group-add-unit.md`

_Note:_ group_add_unit remains live-visible but not snapshot-verifiable with the current wire format.

### cmd-group-remove-unit

- **Outcome**: dispatched-only
- **Freshness**: refreshed-live
- **Dispatch citation**: `src/circuit/grpc/CommandDispatch.cpp:533-544`
- **Evidence shape**: dispatch_ack_only
- **Channel** / **Hypothesis class**: channel_b_query / —
- **Gametype**: test-29926 | **Engine**: recoil_2025.06.19

**Reproduction recipe**:

```bash
tests/headless/audit/repro.sh cmd-group-remove-unit --phase=1
```

**Latest row report**: `build/reports/repro-cmd-group-remove-unit.md`

_Note:_ group_remove_unit remains live-visible but not snapshot-verifiable with the current wire format.

### cmd-init-path

- **Outcome**: dispatched-only
- **Freshness**: refreshed-live
- **Dispatch citation**: `src/circuit/grpc/CommandDispatch.cpp:449-459`
- **Evidence shape**: dispatch_ack_only
- **Channel** / **Hypothesis class**: channel_b_query / —
- **Gametype**: test-29926 | **Engine**: recoil_2025.06.19

**Reproduction recipe**:

```bash
tests/headless/audit/repro.sh cmd-init-path --phase=1
```

**Latest row report**: `build/reports/repro-cmd-init-path.md`

_Note:_ init_path remains live-visible but not snapshot-verifiable with the current wire format.

## AICommand arms — channel_c_lua

### cmd-call-lua-rules

- **Outcome**: dispatched-only
- **Freshness**: refreshed-live
- **Dispatch citation**: `src/circuit/grpc/CommandDispatch.cpp:482-488`
- **Evidence shape**: not_wire_observable
- **Channel** / **Hypothesis class**: channel_c_lua / —
- **Gametype**: test-29926 | **Engine**: recoil_2025.06.19

**Reproduction recipe**:

```bash
tests/headless/audit/repro.sh cmd-call-lua-rules --phase=1
```

**Latest row report**: `build/reports/repro-cmd-call-lua-rules.md`

_Note:_ call_lua_rules remains live-visible but not snapshot-verifiable with the current wire format.

### cmd-call-lua-ui

- **Outcome**: dispatched-only
- **Freshness**: refreshed-live
- **Dispatch citation**: `src/circuit/grpc/CommandDispatch.cpp:489-495`
- **Evidence shape**: not_wire_observable
- **Channel** / **Hypothesis class**: channel_c_lua / —
- **Gametype**: test-29926 | **Engine**: recoil_2025.06.19

**Reproduction recipe**:

```bash
tests/headless/audit/repro.sh cmd-call-lua-ui --phase=1
```

**Latest row report**: `build/reports/repro-cmd-call-lua-ui.md`

_Note:_ call_lua_ui remains live-visible but not snapshot-verifiable with the current wire format.

### cmd-create-line-figure

- **Outcome**: dispatched-only
- **Freshness**: refreshed-live
- **Dispatch citation**: `src/circuit/grpc/CommandDispatch.cpp:581-594`
- **Evidence shape**: not_wire_observable
- **Channel** / **Hypothesis class**: drawer_only / —
- **Gametype**: test-29926 | **Engine**: recoil_2025.06.19

**Reproduction recipe**:

```bash
tests/headless/audit/repro.sh cmd-create-line-figure --phase=1
```

**Latest row report**: `build/reports/repro-cmd-create-line-figure.md`

_Note:_ create_line_figure remains live-visible but not snapshot-verifiable with the current wire format.

### cmd-create-spline-figure

- **Outcome**: dispatched-only
- **Freshness**: refreshed-live
- **Dispatch citation**: `src/circuit/grpc/CommandDispatch.cpp:565-580`
- **Evidence shape**: not_wire_observable
- **Channel** / **Hypothesis class**: drawer_only / —
- **Gametype**: test-29926 | **Engine**: recoil_2025.06.19

**Reproduction recipe**:

```bash
tests/headless/audit/repro.sh cmd-create-spline-figure --phase=1
```

**Latest row report**: `build/reports/repro-cmd-create-spline-figure.md`

_Note:_ create_spline_figure remains live-visible but not snapshot-verifiable with the current wire format.

### cmd-draw-add-line

- **Outcome**: dispatched-only
- **Freshness**: refreshed-live
- **Dispatch citation**: `src/circuit/grpc/CommandDispatch.cpp:552-558`
- **Evidence shape**: not_wire_observable
- **Channel** / **Hypothesis class**: drawer_only / —
- **Gametype**: test-29926 | **Engine**: recoil_2025.06.19

**Reproduction recipe**:

```bash
tests/headless/audit/repro.sh cmd-draw-add-line --phase=1
```

**Latest row report**: `build/reports/repro-cmd-draw-add-line.md`

_Note:_ draw_add_line remains live-visible but not snapshot-verifiable with the current wire format.

### cmd-draw-add-point

- **Outcome**: dispatched-only
- **Freshness**: refreshed-live
- **Dispatch citation**: `src/circuit/grpc/CommandDispatch.cpp:545-551`
- **Evidence shape**: not_wire_observable
- **Channel** / **Hypothesis class**: drawer_only / —
- **Gametype**: test-29926 | **Engine**: recoil_2025.06.19

**Reproduction recipe**:

```bash
tests/headless/audit/repro.sh cmd-draw-add-point --phase=1
```

**Latest row report**: `build/reports/repro-cmd-draw-add-point.md`

_Note:_ draw_add_point remains live-visible but not snapshot-verifiable with the current wire format.

### cmd-draw-remove-point

- **Outcome**: dispatched-only
- **Freshness**: refreshed-live
- **Dispatch citation**: `src/circuit/grpc/CommandDispatch.cpp:559-564`
- **Evidence shape**: not_wire_observable
- **Channel** / **Hypothesis class**: drawer_only / —
- **Gametype**: test-29926 | **Engine**: recoil_2025.06.19

**Reproduction recipe**:

```bash
tests/headless/audit/repro.sh cmd-draw-remove-point --phase=1
```

**Latest row report**: `build/reports/repro-cmd-draw-remove-point.md`

_Note:_ draw_remove_point remains live-visible but not snapshot-verifiable with the current wire format.

### cmd-draw-unit

- **Outcome**: dispatched-only
- **Freshness**: refreshed-live
- **Dispatch citation**: `src/circuit/grpc/CommandDispatch.cpp:627-642`
- **Evidence shape**: not_wire_observable
- **Channel** / **Hypothesis class**: drawer_only / —
- **Gametype**: test-29926 | **Engine**: recoil_2025.06.19

**Reproduction recipe**:

```bash
tests/headless/audit/repro.sh cmd-draw-unit --phase=1
```

**Latest row report**: `build/reports/repro-cmd-draw-unit.md`

_Note:_ draw_unit remains live-visible but not snapshot-verifiable with the current wire format.

### cmd-remove-figure

- **Outcome**: dispatched-only
- **Freshness**: refreshed-live
- **Dispatch citation**: `src/circuit/grpc/CommandDispatch.cpp:619-626`
- **Evidence shape**: not_wire_observable
- **Channel** / **Hypothesis class**: drawer_only / —
- **Gametype**: test-29926 | **Engine**: recoil_2025.06.19

**Reproduction recipe**:

```bash
tests/headless/audit/repro.sh cmd-remove-figure --phase=1
```

**Latest row report**: `build/reports/repro-cmd-remove-figure.md`

_Note:_ remove_figure remains live-visible but not snapshot-verifiable with the current wire format.

### cmd-send-text-message

- **Outcome**: dispatched-only
- **Freshness**: refreshed-live
- **Dispatch citation**: `src/circuit/grpc/CommandDispatch.cpp:430-436`
- **Evidence shape**: not_wire_observable
- **Channel** / **Hypothesis class**: channel_c_lua / —
- **Gametype**: test-29926 | **Engine**: recoil_2025.06.19

**Reproduction recipe**:

```bash
tests/headless/audit/repro.sh cmd-send-text-message --phase=1
```

**Latest row report**: `build/reports/repro-cmd-send-text-message.md`

_Note:_ send_text_message remains live-visible but not snapshot-verifiable with the current wire format.

### cmd-set-figure-color

- **Outcome**: dispatched-only
- **Freshness**: refreshed-live
- **Dispatch citation**: `src/circuit/grpc/CommandDispatch.cpp:605-618`
- **Evidence shape**: not_wire_observable
- **Channel** / **Hypothesis class**: drawer_only / —
- **Gametype**: test-29926 | **Engine**: recoil_2025.06.19

**Reproduction recipe**:

```bash
tests/headless/audit/repro.sh cmd-set-figure-color --phase=1
```

**Latest row report**: `build/reports/repro-cmd-set-figure-color.md`

_Note:_ set_figure_color remains live-visible but not snapshot-verifiable with the current wire format.

### cmd-set-figure-position

- **Outcome**: dispatched-only
- **Freshness**: refreshed-live
- **Dispatch citation**: `src/circuit/grpc/CommandDispatch.cpp:595-604`
- **Evidence shape**: not_wire_observable
- **Channel** / **Hypothesis class**: drawer_only / —
- **Gametype**: test-29926 | **Engine**: recoil_2025.06.19

**Reproduction recipe**:

```bash
tests/headless/audit/repro.sh cmd-set-figure-position --phase=1
```

**Latest row report**: `build/reports/repro-cmd-set-figure-position.md`

_Note:_ set_figure_position remains live-visible but not snapshot-verifiable with the current wire format.

### cmd-set-last-pos-message

- **Outcome**: dispatched-only
- **Freshness**: refreshed-live
- **Dispatch citation**: `src/circuit/grpc/CommandDispatch.cpp:437-442`
- **Evidence shape**: not_wire_observable
- **Channel** / **Hypothesis class**: channel_c_lua / —
- **Gametype**: test-29926 | **Engine**: recoil_2025.06.19

**Reproduction recipe**:

```bash
tests/headless/audit/repro.sh cmd-set-last-pos-message --phase=1
```

**Latest row report**: `build/reports/repro-cmd-set-last-pos-message.md`

_Note:_ set_last_pos_message remains live-visible but not snapshot-verifiable with the current wire format.

## AICommand arms — cheats-gated

### cmd-give-me

- **Outcome**: blocked
- **Freshness**: refreshed-live
- **Dispatch citation**: `src/circuit/grpc/CommandDispatch.cpp:672-696`
- **Evidence shape**: snapshot_diff
- **Channel** / **Hypothesis class**: — / cheats_required
- **Gametype**: test-29926 | **Engine**: recoil_2025.06.19

**Hypothesis**: give_me still needs a distinguishing live repro to separate cheats_required from a genuine dispatcher defect.

**Falsification test**:

```bash
tests/headless/audit/hypothesis.sh cmd-give-me cheats_required
```

**Reproduction recipe**:

```bash
tests/headless/audit/repro.sh cmd-give-me --phase=1
```

**Latest row report**: `build/reports/repro-cmd-give-me.md`

_Note:_ Classified from the latest manifest-backed refresh.

### cmd-give-me-new-unit

- **Outcome**: blocked
- **Freshness**: refreshed-live
- **Dispatch citation**: `src/circuit/grpc/CommandDispatch.cpp:643-653`
- **Evidence shape**: snapshot_diff
- **Channel** / **Hypothesis class**: — / cheats_required
- **Gametype**: test-29926 | **Engine**: recoil_2025.06.19

**Hypothesis**: give_me_new_unit still needs a distinguishing live repro to separate cheats_required from a genuine dispatcher defect.

**Falsification test**:

```bash
tests/headless/audit/hypothesis.sh cmd-give-me-new-unit cheats_required
```

**Reproduction recipe**:

```bash
tests/headless/audit/repro.sh cmd-give-me-new-unit --phase=1
```

**Latest row report**: `build/reports/repro-cmd-give-me-new-unit.md`

_Note:_ Classified from the latest manifest-backed refresh.

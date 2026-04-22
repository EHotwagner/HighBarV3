# Hypothesis Plan for Unverified Arms

> Latest completed run: `live-audit-20260422T064705Z`
> Drifted rows in that run: 0

### cmd-attack

Related audit row: [`cmd-attack`](command-audit.md#cmd-attack)

#### Candidate 1 — `dispatcher_defect`

- **Hypothesis**: attack is currently classified as dispatcher_defect until a dedicated live repro proves otherwise.
- **Predicted-confirmed evidence**: Both Phase-1 and Phase-2 lack the effect in the latest run history, and no arm-specific log evidence appears.
- **Predicted-falsified evidence**: Phase-2 or targeted logging from the latest run shows the dispatcher called the correct engine path.
- **Test command**:

```bash
tests/headless/audit/hypothesis.sh cmd-attack dispatcher_defect
```

#### Candidate 2 — `effect_not_snapshotable`

- **Hypothesis**: attack is currently classified as effect_not_snapshotable until a dedicated live repro proves otherwise.
- **Predicted-confirmed evidence**: Snapshot diffs stay empty while engine log or callback evidence from the latest run proves the command-specific state changed.
- **Predicted-falsified evidence**: Neither the snapshot nor the log from the latest run shows the expected command-specific state change.
- **Test command**:

```bash
tests/headless/audit/hypothesis.sh cmd-attack effect_not_snapshotable
```

#### Candidate 3 — `phase1_reissuance`

- **Hypothesis**: attack is currently classified as phase1_reissuance until a dedicated live repro proves otherwise.
- **Predicted-confirmed evidence**: The latest phase-1 run shows no durable snapshot effect, while phase-2 reproduces the expected state change.
- **Predicted-falsified evidence**: Phase-2 also lacks the expected state change, pushing suspicion toward dispatcher or setup defects in the latest manifest.
- **Test command**:

```bash
tests/headless/audit/hypothesis.sh cmd-attack phase1_reissuance
```

### cmd-attack-area

Related audit row: [`cmd-attack-area`](command-audit.md#cmd-attack-area)

#### Candidate 1 — `target_missing`

- **Hypothesis**: attack_area still needs a distinguishing live repro to separate target_missing from a genuine dispatcher defect.
- **Predicted-confirmed evidence**: Re-running with an explicit bootstrap target causes the effect to appear in the latest live repro.
- **Predicted-falsified evidence**: Even with the target precondition provisioned, the effect is still absent in the latest live repro.
- **Test command**:

```bash
tests/headless/audit/hypothesis.sh cmd-attack-area target_missing
```

#### Candidate 2 — `effect_not_snapshotable`

- **Hypothesis**: attack_area still needs a distinguishing live repro to separate target_missing from a genuine dispatcher defect.
- **Predicted-confirmed evidence**: Snapshot diffs stay empty while engine log or callback evidence from the latest run proves the command-specific state changed.
- **Predicted-falsified evidence**: Neither the snapshot nor the log from the latest run shows the expected command-specific state change.
- **Test command**:

```bash
tests/headless/audit/hypothesis.sh cmd-attack-area effect_not_snapshotable
```

#### Candidate 3 — `phase1_reissuance`

- **Hypothesis**: attack_area still needs a distinguishing live repro to separate target_missing from a genuine dispatcher defect.
- **Predicted-confirmed evidence**: The latest phase-1 run shows no durable snapshot effect, while phase-2 reproduces the expected state change.
- **Predicted-falsified evidence**: Phase-2 also lacks the expected state change, pushing suspicion toward dispatcher or setup defects in the latest manifest.
- **Test command**:

```bash
tests/headless/audit/hypothesis.sh cmd-attack-area phase1_reissuance
```

### cmd-build-unit

Related audit row: [`cmd-build-unit`](command-audit.md#cmd-build-unit)

#### Candidate 1 — `cross_team_rejection`

- **Hypothesis**: build_unit is currently classified as cross_team_rejection until a dedicated live repro proves otherwise.
- **Predicted-confirmed evidence**: A faction-correct def-id makes the build or spawn effect appear immediately in the latest run.
- **Predicted-falsified evidence**: The command still has no effect after resolving a faction-correct def-id in the latest run.
- **Test command**:

```bash
tests/headless/audit/hypothesis.sh cmd-build-unit cross_team_rejection
```

#### Candidate 2 — `effect_not_snapshotable`

- **Hypothesis**: build_unit is currently classified as effect_not_snapshotable until a dedicated live repro proves otherwise.
- **Predicted-confirmed evidence**: Snapshot diffs stay empty while engine log or callback evidence from the latest run proves the command-specific state changed.
- **Predicted-falsified evidence**: Neither the snapshot nor the log from the latest run shows the expected command-specific state change.
- **Test command**:

```bash
tests/headless/audit/hypothesis.sh cmd-build-unit effect_not_snapshotable
```

#### Candidate 3 — `phase1_reissuance`

- **Hypothesis**: build_unit is currently classified as phase1_reissuance until a dedicated live repro proves otherwise.
- **Predicted-confirmed evidence**: The latest phase-1 run shows no durable snapshot effect, while phase-2 reproduces the expected state change.
- **Predicted-falsified evidence**: Phase-2 also lacks the expected state change, pushing suspicion toward dispatcher or setup defects in the latest manifest.
- **Test command**:

```bash
tests/headless/audit/hypothesis.sh cmd-build-unit phase1_reissuance
```

### cmd-capture

Related audit row: [`cmd-capture`](command-audit.md#cmd-capture)

#### Candidate 1 — `target_missing`

- **Hypothesis**: capture still needs a distinguishing live repro to separate target_missing from a genuine dispatcher defect.
- **Predicted-confirmed evidence**: Re-running with an explicit bootstrap target causes the effect to appear in the latest live repro.
- **Predicted-falsified evidence**: Even with the target precondition provisioned, the effect is still absent in the latest live repro.
- **Test command**:

```bash
tests/headless/audit/hypothesis.sh cmd-capture target_missing
```

#### Candidate 2 — `effect_not_snapshotable`

- **Hypothesis**: capture still needs a distinguishing live repro to separate target_missing from a genuine dispatcher defect.
- **Predicted-confirmed evidence**: Snapshot diffs stay empty while engine log or callback evidence from the latest run proves the command-specific state changed.
- **Predicted-falsified evidence**: Neither the snapshot nor the log from the latest run shows the expected command-specific state change.
- **Test command**:

```bash
tests/headless/audit/hypothesis.sh cmd-capture effect_not_snapshotable
```

#### Candidate 3 — `phase1_reissuance`

- **Hypothesis**: capture still needs a distinguishing live repro to separate target_missing from a genuine dispatcher defect.
- **Predicted-confirmed evidence**: The latest phase-1 run shows no durable snapshot effect, while phase-2 reproduces the expected state change.
- **Predicted-falsified evidence**: Phase-2 also lacks the expected state change, pushing suspicion toward dispatcher or setup defects in the latest manifest.
- **Test command**:

```bash
tests/headless/audit/hypothesis.sh cmd-capture phase1_reissuance
```

### cmd-capture-area

Related audit row: [`cmd-capture-area`](command-audit.md#cmd-capture-area)

#### Candidate 1 — `target_missing`

- **Hypothesis**: capture_area still needs a distinguishing live repro to separate target_missing from a genuine dispatcher defect.
- **Predicted-confirmed evidence**: Re-running with an explicit bootstrap target causes the effect to appear in the latest live repro.
- **Predicted-falsified evidence**: Even with the target precondition provisioned, the effect is still absent in the latest live repro.
- **Test command**:

```bash
tests/headless/audit/hypothesis.sh cmd-capture-area target_missing
```

#### Candidate 2 — `effect_not_snapshotable`

- **Hypothesis**: capture_area still needs a distinguishing live repro to separate target_missing from a genuine dispatcher defect.
- **Predicted-confirmed evidence**: Snapshot diffs stay empty while engine log or callback evidence from the latest run proves the command-specific state changed.
- **Predicted-falsified evidence**: Neither the snapshot nor the log from the latest run shows the expected command-specific state change.
- **Test command**:

```bash
tests/headless/audit/hypothesis.sh cmd-capture-area effect_not_snapshotable
```

#### Candidate 3 — `phase1_reissuance`

- **Hypothesis**: capture_area still needs a distinguishing live repro to separate target_missing from a genuine dispatcher defect.
- **Predicted-confirmed evidence**: The latest phase-1 run shows no durable snapshot effect, while phase-2 reproduces the expected state change.
- **Predicted-falsified evidence**: Phase-2 also lacks the expected state change, pushing suspicion toward dispatcher or setup defects in the latest manifest.
- **Test command**:

```bash
tests/headless/audit/hypothesis.sh cmd-capture-area phase1_reissuance
```

### cmd-custom

Related audit row: [`cmd-custom`](command-audit.md#cmd-custom)

#### Candidate 1 — `target_missing`

- **Hypothesis**: custom still needs a distinguishing live repro to separate target_missing from a genuine dispatcher defect.
- **Predicted-confirmed evidence**: Re-running with an explicit bootstrap target causes the effect to appear in the latest live repro.
- **Predicted-falsified evidence**: Even with the target precondition provisioned, the effect is still absent in the latest live repro.
- **Test command**:

```bash
tests/headless/audit/hypothesis.sh cmd-custom target_missing
```

#### Candidate 2 — `effect_not_snapshotable`

- **Hypothesis**: custom still needs a distinguishing live repro to separate target_missing from a genuine dispatcher defect.
- **Predicted-confirmed evidence**: Snapshot diffs stay empty while engine log or callback evidence from the latest run proves the command-specific state changed.
- **Predicted-falsified evidence**: Neither the snapshot nor the log from the latest run shows the expected command-specific state change.
- **Test command**:

```bash
tests/headless/audit/hypothesis.sh cmd-custom effect_not_snapshotable
```

#### Candidate 3 — `phase1_reissuance`

- **Hypothesis**: custom still needs a distinguishing live repro to separate target_missing from a genuine dispatcher defect.
- **Predicted-confirmed evidence**: The latest phase-1 run shows no durable snapshot effect, while phase-2 reproduces the expected state change.
- **Predicted-falsified evidence**: Phase-2 also lacks the expected state change, pushing suspicion toward dispatcher or setup defects in the latest manifest.
- **Test command**:

```bash
tests/headless/audit/hypothesis.sh cmd-custom phase1_reissuance
```

### cmd-death-wait

Related audit row: [`cmd-death-wait`](command-audit.md#cmd-death-wait)

#### Candidate 1 — `effect_not_snapshotable`

- **Hypothesis**: death_wait still needs a distinguishing live repro to separate effect_not_snapshotable from a genuine dispatcher defect.
- **Predicted-confirmed evidence**: Snapshot diffs stay empty while engine log or callback evidence from the latest run proves the command-specific state changed.
- **Predicted-falsified evidence**: Neither the snapshot nor the log from the latest run shows the expected command-specific state change.
- **Test command**:

```bash
tests/headless/audit/hypothesis.sh cmd-death-wait effect_not_snapshotable
```

#### Candidate 2 — `phase1_reissuance`

- **Hypothesis**: death_wait still needs a distinguishing live repro to separate effect_not_snapshotable from a genuine dispatcher defect.
- **Predicted-confirmed evidence**: The latest phase-1 run shows no durable snapshot effect, while phase-2 reproduces the expected state change.
- **Predicted-falsified evidence**: Phase-2 also lacks the expected state change, pushing suspicion toward dispatcher or setup defects in the latest manifest.
- **Test command**:

```bash
tests/headless/audit/hypothesis.sh cmd-death-wait phase1_reissuance
```

#### Candidate 3 — `dispatcher_defect`

- **Hypothesis**: death_wait still needs a distinguishing live repro to separate effect_not_snapshotable from a genuine dispatcher defect.
- **Predicted-confirmed evidence**: Both Phase-1 and Phase-2 lack the effect in the latest run history, and no arm-specific log evidence appears.
- **Predicted-falsified evidence**: Phase-2 or targeted logging from the latest run shows the dispatcher called the correct engine path.
- **Test command**:

```bash
tests/headless/audit/hypothesis.sh cmd-death-wait dispatcher_defect
```

### cmd-dgun

Related audit row: [`cmd-dgun`](command-audit.md#cmd-dgun)

#### Candidate 1 — `target_missing`

- **Hypothesis**: dgun still needs a distinguishing live repro to separate target_missing from a genuine dispatcher defect.
- **Predicted-confirmed evidence**: Re-running with an explicit bootstrap target causes the effect to appear in the latest live repro.
- **Predicted-falsified evidence**: Even with the target precondition provisioned, the effect is still absent in the latest live repro.
- **Test command**:

```bash
tests/headless/audit/hypothesis.sh cmd-dgun target_missing
```

#### Candidate 2 — `effect_not_snapshotable`

- **Hypothesis**: dgun still needs a distinguishing live repro to separate target_missing from a genuine dispatcher defect.
- **Predicted-confirmed evidence**: Snapshot diffs stay empty while engine log or callback evidence from the latest run proves the command-specific state changed.
- **Predicted-falsified evidence**: Neither the snapshot nor the log from the latest run shows the expected command-specific state change.
- **Test command**:

```bash
tests/headless/audit/hypothesis.sh cmd-dgun effect_not_snapshotable
```

#### Candidate 3 — `phase1_reissuance`

- **Hypothesis**: dgun still needs a distinguishing live repro to separate target_missing from a genuine dispatcher defect.
- **Predicted-confirmed evidence**: The latest phase-1 run shows no durable snapshot effect, while phase-2 reproduces the expected state change.
- **Predicted-falsified evidence**: Phase-2 also lacks the expected state change, pushing suspicion toward dispatcher or setup defects in the latest manifest.
- **Test command**:

```bash
tests/headless/audit/hypothesis.sh cmd-dgun phase1_reissuance
```

### cmd-fight

Related audit row: [`cmd-fight`](command-audit.md#cmd-fight)

#### Candidate 1 — `phase1_reissuance`

- **Hypothesis**: fight still needs a distinguishing live repro to separate phase1_reissuance from a genuine dispatcher defect.
- **Predicted-confirmed evidence**: The latest phase-1 run shows no durable snapshot effect, while phase-2 reproduces the expected state change.
- **Predicted-falsified evidence**: Phase-2 also lacks the expected state change, pushing suspicion toward dispatcher or setup defects in the latest manifest.
- **Test command**:

```bash
tests/headless/audit/hypothesis.sh cmd-fight phase1_reissuance
```

#### Candidate 2 — `effect_not_snapshotable`

- **Hypothesis**: fight still needs a distinguishing live repro to separate phase1_reissuance from a genuine dispatcher defect.
- **Predicted-confirmed evidence**: Snapshot diffs stay empty while engine log or callback evidence from the latest run proves the command-specific state changed.
- **Predicted-falsified evidence**: Neither the snapshot nor the log from the latest run shows the expected command-specific state change.
- **Test command**:

```bash
tests/headless/audit/hypothesis.sh cmd-fight effect_not_snapshotable
```

#### Candidate 3 — `dispatcher_defect`

- **Hypothesis**: fight still needs a distinguishing live repro to separate phase1_reissuance from a genuine dispatcher defect.
- **Predicted-confirmed evidence**: Both Phase-1 and Phase-2 lack the effect in the latest run history, and no arm-specific log evidence appears.
- **Predicted-falsified evidence**: Phase-2 or targeted logging from the latest run shows the dispatcher called the correct engine path.
- **Test command**:

```bash
tests/headless/audit/hypothesis.sh cmd-fight dispatcher_defect
```

### cmd-gather-wait

Related audit row: [`cmd-gather-wait`](command-audit.md#cmd-gather-wait)

#### Candidate 1 — `effect_not_snapshotable`

- **Hypothesis**: gather_wait still needs a distinguishing live repro to separate effect_not_snapshotable from a genuine dispatcher defect.
- **Predicted-confirmed evidence**: Snapshot diffs stay empty while engine log or callback evidence from the latest run proves the command-specific state changed.
- **Predicted-falsified evidence**: Neither the snapshot nor the log from the latest run shows the expected command-specific state change.
- **Test command**:

```bash
tests/headless/audit/hypothesis.sh cmd-gather-wait effect_not_snapshotable
```

#### Candidate 2 — `phase1_reissuance`

- **Hypothesis**: gather_wait still needs a distinguishing live repro to separate effect_not_snapshotable from a genuine dispatcher defect.
- **Predicted-confirmed evidence**: The latest phase-1 run shows no durable snapshot effect, while phase-2 reproduces the expected state change.
- **Predicted-falsified evidence**: Phase-2 also lacks the expected state change, pushing suspicion toward dispatcher or setup defects in the latest manifest.
- **Test command**:

```bash
tests/headless/audit/hypothesis.sh cmd-gather-wait phase1_reissuance
```

#### Candidate 3 — `dispatcher_defect`

- **Hypothesis**: gather_wait still needs a distinguishing live repro to separate effect_not_snapshotable from a genuine dispatcher defect.
- **Predicted-confirmed evidence**: Both Phase-1 and Phase-2 lack the effect in the latest run history, and no arm-specific log evidence appears.
- **Predicted-falsified evidence**: Phase-2 or targeted logging from the latest run shows the dispatcher called the correct engine path.
- **Test command**:

```bash
tests/headless/audit/hypothesis.sh cmd-gather-wait dispatcher_defect
```

### cmd-give-me

Related audit row: [`cmd-give-me`](command-audit.md#cmd-give-me)

#### Candidate 1 — `cheats_required`

- **Hypothesis**: give_me still needs a distinguishing live repro to separate cheats_required from a genuine dispatcher defect.
- **Predicted-confirmed evidence**: The cheats-enabled live repro produces the expected state change while the default run does not.
- **Predicted-falsified evidence**: The cheats-enabled live repro still does not produce the expected effect.
- **Test command**:

```bash
tests/headless/audit/hypothesis.sh cmd-give-me cheats_required
```

#### Candidate 2 — `effect_not_snapshotable`

- **Hypothesis**: give_me still needs a distinguishing live repro to separate cheats_required from a genuine dispatcher defect.
- **Predicted-confirmed evidence**: Snapshot diffs stay empty while engine log or callback evidence from the latest run proves the command-specific state changed.
- **Predicted-falsified evidence**: Neither the snapshot nor the log from the latest run shows the expected command-specific state change.
- **Test command**:

```bash
tests/headless/audit/hypothesis.sh cmd-give-me effect_not_snapshotable
```

#### Candidate 3 — `phase1_reissuance`

- **Hypothesis**: give_me still needs a distinguishing live repro to separate cheats_required from a genuine dispatcher defect.
- **Predicted-confirmed evidence**: The latest phase-1 run shows no durable snapshot effect, while phase-2 reproduces the expected state change.
- **Predicted-falsified evidence**: Phase-2 also lacks the expected state change, pushing suspicion toward dispatcher or setup defects in the latest manifest.
- **Test command**:

```bash
tests/headless/audit/hypothesis.sh cmd-give-me phase1_reissuance
```

### cmd-give-me-new-unit

Related audit row: [`cmd-give-me-new-unit`](command-audit.md#cmd-give-me-new-unit)

#### Candidate 1 — `cheats_required`

- **Hypothesis**: give_me_new_unit still needs a distinguishing live repro to separate cheats_required from a genuine dispatcher defect.
- **Predicted-confirmed evidence**: The cheats-enabled live repro produces the expected state change while the default run does not.
- **Predicted-falsified evidence**: The cheats-enabled live repro still does not produce the expected effect.
- **Test command**:

```bash
tests/headless/audit/hypothesis.sh cmd-give-me-new-unit cheats_required
```

#### Candidate 2 — `effect_not_snapshotable`

- **Hypothesis**: give_me_new_unit still needs a distinguishing live repro to separate cheats_required from a genuine dispatcher defect.
- **Predicted-confirmed evidence**: Snapshot diffs stay empty while engine log or callback evidence from the latest run proves the command-specific state changed.
- **Predicted-falsified evidence**: Neither the snapshot nor the log from the latest run shows the expected command-specific state change.
- **Test command**:

```bash
tests/headless/audit/hypothesis.sh cmd-give-me-new-unit effect_not_snapshotable
```

#### Candidate 3 — `phase1_reissuance`

- **Hypothesis**: give_me_new_unit still needs a distinguishing live repro to separate cheats_required from a genuine dispatcher defect.
- **Predicted-confirmed evidence**: The latest phase-1 run shows no durable snapshot effect, while phase-2 reproduces the expected state change.
- **Predicted-falsified evidence**: Phase-2 also lacks the expected state change, pushing suspicion toward dispatcher or setup defects in the latest manifest.
- **Test command**:

```bash
tests/headless/audit/hypothesis.sh cmd-give-me-new-unit phase1_reissuance
```

### cmd-guard

Related audit row: [`cmd-guard`](command-audit.md#cmd-guard)

#### Candidate 1 — `target_missing`

- **Hypothesis**: guard still needs a distinguishing live repro to separate target_missing from a genuine dispatcher defect.
- **Predicted-confirmed evidence**: Re-running with an explicit bootstrap target causes the effect to appear in the latest live repro.
- **Predicted-falsified evidence**: Even with the target precondition provisioned, the effect is still absent in the latest live repro.
- **Test command**:

```bash
tests/headless/audit/hypothesis.sh cmd-guard target_missing
```

#### Candidate 2 — `effect_not_snapshotable`

- **Hypothesis**: guard still needs a distinguishing live repro to separate target_missing from a genuine dispatcher defect.
- **Predicted-confirmed evidence**: Snapshot diffs stay empty while engine log or callback evidence from the latest run proves the command-specific state changed.
- **Predicted-falsified evidence**: Neither the snapshot nor the log from the latest run shows the expected command-specific state change.
- **Test command**:

```bash
tests/headless/audit/hypothesis.sh cmd-guard effect_not_snapshotable
```

#### Candidate 3 — `phase1_reissuance`

- **Hypothesis**: guard still needs a distinguishing live repro to separate target_missing from a genuine dispatcher defect.
- **Predicted-confirmed evidence**: The latest phase-1 run shows no durable snapshot effect, while phase-2 reproduces the expected state change.
- **Predicted-falsified evidence**: Phase-2 also lacks the expected state change, pushing suspicion toward dispatcher or setup defects in the latest manifest.
- **Test command**:

```bash
tests/headless/audit/hypothesis.sh cmd-guard phase1_reissuance
```

### cmd-load-onto

Related audit row: [`cmd-load-onto`](command-audit.md#cmd-load-onto)

#### Candidate 1 — `target_missing`

- **Hypothesis**: load_onto still needs a distinguishing live repro to separate target_missing from a genuine dispatcher defect.
- **Predicted-confirmed evidence**: Re-running with an explicit bootstrap target causes the effect to appear in the latest live repro.
- **Predicted-falsified evidence**: Even with the target precondition provisioned, the effect is still absent in the latest live repro.
- **Test command**:

```bash
tests/headless/audit/hypothesis.sh cmd-load-onto target_missing
```

#### Candidate 2 — `effect_not_snapshotable`

- **Hypothesis**: load_onto still needs a distinguishing live repro to separate target_missing from a genuine dispatcher defect.
- **Predicted-confirmed evidence**: Snapshot diffs stay empty while engine log or callback evidence from the latest run proves the command-specific state changed.
- **Predicted-falsified evidence**: Neither the snapshot nor the log from the latest run shows the expected command-specific state change.
- **Test command**:

```bash
tests/headless/audit/hypothesis.sh cmd-load-onto effect_not_snapshotable
```

#### Candidate 3 — `phase1_reissuance`

- **Hypothesis**: load_onto still needs a distinguishing live repro to separate target_missing from a genuine dispatcher defect.
- **Predicted-confirmed evidence**: The latest phase-1 run shows no durable snapshot effect, while phase-2 reproduces the expected state change.
- **Predicted-falsified evidence**: Phase-2 also lacks the expected state change, pushing suspicion toward dispatcher or setup defects in the latest manifest.
- **Test command**:

```bash
tests/headless/audit/hypothesis.sh cmd-load-onto phase1_reissuance
```

### cmd-load-units

Related audit row: [`cmd-load-units`](command-audit.md#cmd-load-units)

#### Candidate 1 — `target_missing`

- **Hypothesis**: load_units still needs a distinguishing live repro to separate target_missing from a genuine dispatcher defect.
- **Predicted-confirmed evidence**: Re-running with an explicit bootstrap target causes the effect to appear in the latest live repro.
- **Predicted-falsified evidence**: Even with the target precondition provisioned, the effect is still absent in the latest live repro.
- **Test command**:

```bash
tests/headless/audit/hypothesis.sh cmd-load-units target_missing
```

#### Candidate 2 — `effect_not_snapshotable`

- **Hypothesis**: load_units still needs a distinguishing live repro to separate target_missing from a genuine dispatcher defect.
- **Predicted-confirmed evidence**: Snapshot diffs stay empty while engine log or callback evidence from the latest run proves the command-specific state changed.
- **Predicted-falsified evidence**: Neither the snapshot nor the log from the latest run shows the expected command-specific state change.
- **Test command**:

```bash
tests/headless/audit/hypothesis.sh cmd-load-units effect_not_snapshotable
```

#### Candidate 3 — `phase1_reissuance`

- **Hypothesis**: load_units still needs a distinguishing live repro to separate target_missing from a genuine dispatcher defect.
- **Predicted-confirmed evidence**: The latest phase-1 run shows no durable snapshot effect, while phase-2 reproduces the expected state change.
- **Predicted-falsified evidence**: Phase-2 also lacks the expected state change, pushing suspicion toward dispatcher or setup defects in the latest manifest.
- **Test command**:

```bash
tests/headless/audit/hypothesis.sh cmd-load-units phase1_reissuance
```

### cmd-load-units-area

Related audit row: [`cmd-load-units-area`](command-audit.md#cmd-load-units-area)

#### Candidate 1 — `target_missing`

- **Hypothesis**: load_units_area still needs a distinguishing live repro to separate target_missing from a genuine dispatcher defect.
- **Predicted-confirmed evidence**: Re-running with an explicit bootstrap target causes the effect to appear in the latest live repro.
- **Predicted-falsified evidence**: Even with the target precondition provisioned, the effect is still absent in the latest live repro.
- **Test command**:

```bash
tests/headless/audit/hypothesis.sh cmd-load-units-area target_missing
```

#### Candidate 2 — `effect_not_snapshotable`

- **Hypothesis**: load_units_area still needs a distinguishing live repro to separate target_missing from a genuine dispatcher defect.
- **Predicted-confirmed evidence**: Snapshot diffs stay empty while engine log or callback evidence from the latest run proves the command-specific state changed.
- **Predicted-falsified evidence**: Neither the snapshot nor the log from the latest run shows the expected command-specific state change.
- **Test command**:

```bash
tests/headless/audit/hypothesis.sh cmd-load-units-area effect_not_snapshotable
```

#### Candidate 3 — `phase1_reissuance`

- **Hypothesis**: load_units_area still needs a distinguishing live repro to separate target_missing from a genuine dispatcher defect.
- **Predicted-confirmed evidence**: The latest phase-1 run shows no durable snapshot effect, while phase-2 reproduces the expected state change.
- **Predicted-falsified evidence**: Phase-2 also lacks the expected state change, pushing suspicion toward dispatcher or setup defects in the latest manifest.
- **Test command**:

```bash
tests/headless/audit/hypothesis.sh cmd-load-units-area phase1_reissuance
```

### cmd-move-unit

Related audit row: [`cmd-move-unit`](command-audit.md#cmd-move-unit)

#### Candidate 1 — `phase1_reissuance`

- **Hypothesis**: move_unit still needs a distinguishing live repro to separate phase1_reissuance from a genuine dispatcher defect.
- **Predicted-confirmed evidence**: The latest phase-1 run shows no durable snapshot effect, while phase-2 reproduces the expected state change.
- **Predicted-falsified evidence**: Phase-2 also lacks the expected state change, pushing suspicion toward dispatcher or setup defects in the latest manifest.
- **Test command**:

```bash
tests/headless/audit/hypothesis.sh cmd-move-unit phase1_reissuance
```

#### Candidate 2 — `effect_not_snapshotable`

- **Hypothesis**: move_unit still needs a distinguishing live repro to separate phase1_reissuance from a genuine dispatcher defect.
- **Predicted-confirmed evidence**: Snapshot diffs stay empty while engine log or callback evidence from the latest run proves the command-specific state changed.
- **Predicted-falsified evidence**: Neither the snapshot nor the log from the latest run shows the expected command-specific state change.
- **Test command**:

```bash
tests/headless/audit/hypothesis.sh cmd-move-unit effect_not_snapshotable
```

#### Candidate 3 — `dispatcher_defect`

- **Hypothesis**: move_unit still needs a distinguishing live repro to separate phase1_reissuance from a genuine dispatcher defect.
- **Predicted-confirmed evidence**: Both Phase-1 and Phase-2 lack the effect in the latest run history, and no arm-specific log evidence appears.
- **Predicted-falsified evidence**: Phase-2 or targeted logging from the latest run shows the dispatcher called the correct engine path.
- **Test command**:

```bash
tests/headless/audit/hypothesis.sh cmd-move-unit dispatcher_defect
```

### cmd-patrol

Related audit row: [`cmd-patrol`](command-audit.md#cmd-patrol)

#### Candidate 1 — `phase1_reissuance`

- **Hypothesis**: patrol still needs a distinguishing live repro to separate phase1_reissuance from a genuine dispatcher defect.
- **Predicted-confirmed evidence**: The latest phase-1 run shows no durable snapshot effect, while phase-2 reproduces the expected state change.
- **Predicted-falsified evidence**: Phase-2 also lacks the expected state change, pushing suspicion toward dispatcher or setup defects in the latest manifest.
- **Test command**:

```bash
tests/headless/audit/hypothesis.sh cmd-patrol phase1_reissuance
```

#### Candidate 2 — `effect_not_snapshotable`

- **Hypothesis**: patrol still needs a distinguishing live repro to separate phase1_reissuance from a genuine dispatcher defect.
- **Predicted-confirmed evidence**: Snapshot diffs stay empty while engine log or callback evidence from the latest run proves the command-specific state changed.
- **Predicted-falsified evidence**: Neither the snapshot nor the log from the latest run shows the expected command-specific state change.
- **Test command**:

```bash
tests/headless/audit/hypothesis.sh cmd-patrol effect_not_snapshotable
```

#### Candidate 3 — `dispatcher_defect`

- **Hypothesis**: patrol still needs a distinguishing live repro to separate phase1_reissuance from a genuine dispatcher defect.
- **Predicted-confirmed evidence**: Both Phase-1 and Phase-2 lack the effect in the latest run history, and no arm-specific log evidence appears.
- **Predicted-falsified evidence**: Phase-2 or targeted logging from the latest run shows the dispatcher called the correct engine path.
- **Test command**:

```bash
tests/headless/audit/hypothesis.sh cmd-patrol dispatcher_defect
```

### cmd-reclaim-area

Related audit row: [`cmd-reclaim-area`](command-audit.md#cmd-reclaim-area)

#### Candidate 1 — `target_missing`

- **Hypothesis**: reclaim_area still needs a distinguishing live repro to separate target_missing from a genuine dispatcher defect.
- **Predicted-confirmed evidence**: Re-running with an explicit bootstrap target causes the effect to appear in the latest live repro.
- **Predicted-falsified evidence**: Even with the target precondition provisioned, the effect is still absent in the latest live repro.
- **Test command**:

```bash
tests/headless/audit/hypothesis.sh cmd-reclaim-area target_missing
```

#### Candidate 2 — `effect_not_snapshotable`

- **Hypothesis**: reclaim_area still needs a distinguishing live repro to separate target_missing from a genuine dispatcher defect.
- **Predicted-confirmed evidence**: Snapshot diffs stay empty while engine log or callback evidence from the latest run proves the command-specific state changed.
- **Predicted-falsified evidence**: Neither the snapshot nor the log from the latest run shows the expected command-specific state change.
- **Test command**:

```bash
tests/headless/audit/hypothesis.sh cmd-reclaim-area effect_not_snapshotable
```

#### Candidate 3 — `phase1_reissuance`

- **Hypothesis**: reclaim_area still needs a distinguishing live repro to separate target_missing from a genuine dispatcher defect.
- **Predicted-confirmed evidence**: The latest phase-1 run shows no durable snapshot effect, while phase-2 reproduces the expected state change.
- **Predicted-falsified evidence**: Phase-2 also lacks the expected state change, pushing suspicion toward dispatcher or setup defects in the latest manifest.
- **Test command**:

```bash
tests/headless/audit/hypothesis.sh cmd-reclaim-area phase1_reissuance
```

### cmd-reclaim-feature

Related audit row: [`cmd-reclaim-feature`](command-audit.md#cmd-reclaim-feature)

#### Candidate 1 — `target_missing`

- **Hypothesis**: reclaim_feature still needs a distinguishing live repro to separate target_missing from a genuine dispatcher defect.
- **Predicted-confirmed evidence**: Re-running with an explicit bootstrap target causes the effect to appear in the latest live repro.
- **Predicted-falsified evidence**: Even with the target precondition provisioned, the effect is still absent in the latest live repro.
- **Test command**:

```bash
tests/headless/audit/hypothesis.sh cmd-reclaim-feature target_missing
```

#### Candidate 2 — `effect_not_snapshotable`

- **Hypothesis**: reclaim_feature still needs a distinguishing live repro to separate target_missing from a genuine dispatcher defect.
- **Predicted-confirmed evidence**: Snapshot diffs stay empty while engine log or callback evidence from the latest run proves the command-specific state changed.
- **Predicted-falsified evidence**: Neither the snapshot nor the log from the latest run shows the expected command-specific state change.
- **Test command**:

```bash
tests/headless/audit/hypothesis.sh cmd-reclaim-feature effect_not_snapshotable
```

#### Candidate 3 — `phase1_reissuance`

- **Hypothesis**: reclaim_feature still needs a distinguishing live repro to separate target_missing from a genuine dispatcher defect.
- **Predicted-confirmed evidence**: The latest phase-1 run shows no durable snapshot effect, while phase-2 reproduces the expected state change.
- **Predicted-falsified evidence**: Phase-2 also lacks the expected state change, pushing suspicion toward dispatcher or setup defects in the latest manifest.
- **Test command**:

```bash
tests/headless/audit/hypothesis.sh cmd-reclaim-feature phase1_reissuance
```

### cmd-reclaim-in-area

Related audit row: [`cmd-reclaim-in-area`](command-audit.md#cmd-reclaim-in-area)

#### Candidate 1 — `target_missing`

- **Hypothesis**: reclaim_in_area still needs a distinguishing live repro to separate target_missing from a genuine dispatcher defect.
- **Predicted-confirmed evidence**: Re-running with an explicit bootstrap target causes the effect to appear in the latest live repro.
- **Predicted-falsified evidence**: Even with the target precondition provisioned, the effect is still absent in the latest live repro.
- **Test command**:

```bash
tests/headless/audit/hypothesis.sh cmd-reclaim-in-area target_missing
```

#### Candidate 2 — `effect_not_snapshotable`

- **Hypothesis**: reclaim_in_area still needs a distinguishing live repro to separate target_missing from a genuine dispatcher defect.
- **Predicted-confirmed evidence**: Snapshot diffs stay empty while engine log or callback evidence from the latest run proves the command-specific state changed.
- **Predicted-falsified evidence**: Neither the snapshot nor the log from the latest run shows the expected command-specific state change.
- **Test command**:

```bash
tests/headless/audit/hypothesis.sh cmd-reclaim-in-area effect_not_snapshotable
```

#### Candidate 3 — `phase1_reissuance`

- **Hypothesis**: reclaim_in_area still needs a distinguishing live repro to separate target_missing from a genuine dispatcher defect.
- **Predicted-confirmed evidence**: The latest phase-1 run shows no durable snapshot effect, while phase-2 reproduces the expected state change.
- **Predicted-falsified evidence**: Phase-2 also lacks the expected state change, pushing suspicion toward dispatcher or setup defects in the latest manifest.
- **Test command**:

```bash
tests/headless/audit/hypothesis.sh cmd-reclaim-in-area phase1_reissuance
```

### cmd-reclaim-unit

Related audit row: [`cmd-reclaim-unit`](command-audit.md#cmd-reclaim-unit)

#### Candidate 1 — `target_missing`

- **Hypothesis**: reclaim_unit still needs a distinguishing live repro to separate target_missing from a genuine dispatcher defect.
- **Predicted-confirmed evidence**: Re-running with an explicit bootstrap target causes the effect to appear in the latest live repro.
- **Predicted-falsified evidence**: Even with the target precondition provisioned, the effect is still absent in the latest live repro.
- **Test command**:

```bash
tests/headless/audit/hypothesis.sh cmd-reclaim-unit target_missing
```

#### Candidate 2 — `effect_not_snapshotable`

- **Hypothesis**: reclaim_unit still needs a distinguishing live repro to separate target_missing from a genuine dispatcher defect.
- **Predicted-confirmed evidence**: Snapshot diffs stay empty while engine log or callback evidence from the latest run proves the command-specific state changed.
- **Predicted-falsified evidence**: Neither the snapshot nor the log from the latest run shows the expected command-specific state change.
- **Test command**:

```bash
tests/headless/audit/hypothesis.sh cmd-reclaim-unit effect_not_snapshotable
```

#### Candidate 3 — `phase1_reissuance`

- **Hypothesis**: reclaim_unit still needs a distinguishing live repro to separate target_missing from a genuine dispatcher defect.
- **Predicted-confirmed evidence**: The latest phase-1 run shows no durable snapshot effect, while phase-2 reproduces the expected state change.
- **Predicted-falsified evidence**: Phase-2 also lacks the expected state change, pushing suspicion toward dispatcher or setup defects in the latest manifest.
- **Test command**:

```bash
tests/headless/audit/hypothesis.sh cmd-reclaim-unit phase1_reissuance
```

### cmd-repair

Related audit row: [`cmd-repair`](command-audit.md#cmd-repair)

#### Candidate 1 — `target_missing`

- **Hypothesis**: repair still needs a distinguishing live repro to separate target_missing from a genuine dispatcher defect.
- **Predicted-confirmed evidence**: Re-running with an explicit bootstrap target causes the effect to appear in the latest live repro.
- **Predicted-falsified evidence**: Even with the target precondition provisioned, the effect is still absent in the latest live repro.
- **Test command**:

```bash
tests/headless/audit/hypothesis.sh cmd-repair target_missing
```

#### Candidate 2 — `effect_not_snapshotable`

- **Hypothesis**: repair still needs a distinguishing live repro to separate target_missing from a genuine dispatcher defect.
- **Predicted-confirmed evidence**: Snapshot diffs stay empty while engine log or callback evidence from the latest run proves the command-specific state changed.
- **Predicted-falsified evidence**: Neither the snapshot nor the log from the latest run shows the expected command-specific state change.
- **Test command**:

```bash
tests/headless/audit/hypothesis.sh cmd-repair effect_not_snapshotable
```

#### Candidate 3 — `phase1_reissuance`

- **Hypothesis**: repair still needs a distinguishing live repro to separate target_missing from a genuine dispatcher defect.
- **Predicted-confirmed evidence**: The latest phase-1 run shows no durable snapshot effect, while phase-2 reproduces the expected state change.
- **Predicted-falsified evidence**: Phase-2 also lacks the expected state change, pushing suspicion toward dispatcher or setup defects in the latest manifest.
- **Test command**:

```bash
tests/headless/audit/hypothesis.sh cmd-repair phase1_reissuance
```

### cmd-restore-area

Related audit row: [`cmd-restore-area`](command-audit.md#cmd-restore-area)

#### Candidate 1 — `target_missing`

- **Hypothesis**: restore_area still needs a distinguishing live repro to separate target_missing from a genuine dispatcher defect.
- **Predicted-confirmed evidence**: Re-running with an explicit bootstrap target causes the effect to appear in the latest live repro.
- **Predicted-falsified evidence**: Even with the target precondition provisioned, the effect is still absent in the latest live repro.
- **Test command**:

```bash
tests/headless/audit/hypothesis.sh cmd-restore-area target_missing
```

#### Candidate 2 — `effect_not_snapshotable`

- **Hypothesis**: restore_area still needs a distinguishing live repro to separate target_missing from a genuine dispatcher defect.
- **Predicted-confirmed evidence**: Snapshot diffs stay empty while engine log or callback evidence from the latest run proves the command-specific state changed.
- **Predicted-falsified evidence**: Neither the snapshot nor the log from the latest run shows the expected command-specific state change.
- **Test command**:

```bash
tests/headless/audit/hypothesis.sh cmd-restore-area effect_not_snapshotable
```

#### Candidate 3 — `phase1_reissuance`

- **Hypothesis**: restore_area still needs a distinguishing live repro to separate target_missing from a genuine dispatcher defect.
- **Predicted-confirmed evidence**: The latest phase-1 run shows no durable snapshot effect, while phase-2 reproduces the expected state change.
- **Predicted-falsified evidence**: Phase-2 also lacks the expected state change, pushing suspicion toward dispatcher or setup defects in the latest manifest.
- **Test command**:

```bash
tests/headless/audit/hypothesis.sh cmd-restore-area phase1_reissuance
```

### cmd-resurrect

Related audit row: [`cmd-resurrect`](command-audit.md#cmd-resurrect)

#### Candidate 1 — `target_missing`

- **Hypothesis**: resurrect still needs a distinguishing live repro to separate target_missing from a genuine dispatcher defect.
- **Predicted-confirmed evidence**: Re-running with an explicit bootstrap target causes the effect to appear in the latest live repro.
- **Predicted-falsified evidence**: Even with the target precondition provisioned, the effect is still absent in the latest live repro.
- **Test command**:

```bash
tests/headless/audit/hypothesis.sh cmd-resurrect target_missing
```

#### Candidate 2 — `effect_not_snapshotable`

- **Hypothesis**: resurrect still needs a distinguishing live repro to separate target_missing from a genuine dispatcher defect.
- **Predicted-confirmed evidence**: Snapshot diffs stay empty while engine log or callback evidence from the latest run proves the command-specific state changed.
- **Predicted-falsified evidence**: Neither the snapshot nor the log from the latest run shows the expected command-specific state change.
- **Test command**:

```bash
tests/headless/audit/hypothesis.sh cmd-resurrect effect_not_snapshotable
```

#### Candidate 3 — `phase1_reissuance`

- **Hypothesis**: resurrect still needs a distinguishing live repro to separate target_missing from a genuine dispatcher defect.
- **Predicted-confirmed evidence**: The latest phase-1 run shows no durable snapshot effect, while phase-2 reproduces the expected state change.
- **Predicted-falsified evidence**: Phase-2 also lacks the expected state change, pushing suspicion toward dispatcher or setup defects in the latest manifest.
- **Test command**:

```bash
tests/headless/audit/hypothesis.sh cmd-resurrect phase1_reissuance
```

### cmd-resurrect-in-area

Related audit row: [`cmd-resurrect-in-area`](command-audit.md#cmd-resurrect-in-area)

#### Candidate 1 — `target_missing`

- **Hypothesis**: resurrect_in_area still needs a distinguishing live repro to separate target_missing from a genuine dispatcher defect.
- **Predicted-confirmed evidence**: Re-running with an explicit bootstrap target causes the effect to appear in the latest live repro.
- **Predicted-falsified evidence**: Even with the target precondition provisioned, the effect is still absent in the latest live repro.
- **Test command**:

```bash
tests/headless/audit/hypothesis.sh cmd-resurrect-in-area target_missing
```

#### Candidate 2 — `effect_not_snapshotable`

- **Hypothesis**: resurrect_in_area still needs a distinguishing live repro to separate target_missing from a genuine dispatcher defect.
- **Predicted-confirmed evidence**: Snapshot diffs stay empty while engine log or callback evidence from the latest run proves the command-specific state changed.
- **Predicted-falsified evidence**: Neither the snapshot nor the log from the latest run shows the expected command-specific state change.
- **Test command**:

```bash
tests/headless/audit/hypothesis.sh cmd-resurrect-in-area effect_not_snapshotable
```

#### Candidate 3 — `phase1_reissuance`

- **Hypothesis**: resurrect_in_area still needs a distinguishing live repro to separate target_missing from a genuine dispatcher defect.
- **Predicted-confirmed evidence**: The latest phase-1 run shows no durable snapshot effect, while phase-2 reproduces the expected state change.
- **Predicted-falsified evidence**: Phase-2 also lacks the expected state change, pushing suspicion toward dispatcher or setup defects in the latest manifest.
- **Test command**:

```bash
tests/headless/audit/hypothesis.sh cmd-resurrect-in-area phase1_reissuance
```

### cmd-self-destruct

Related audit row: [`cmd-self-destruct`](command-audit.md#cmd-self-destruct)

#### Candidate 1 — `dispatcher_defect`

- **Hypothesis**: self_destruct is currently classified as dispatcher_defect until a dedicated live repro proves otherwise.
- **Predicted-confirmed evidence**: Both Phase-1 and Phase-2 lack the effect in the latest run history, and no arm-specific log evidence appears.
- **Predicted-falsified evidence**: Phase-2 or targeted logging from the latest run shows the dispatcher called the correct engine path.
- **Test command**:

```bash
tests/headless/audit/hypothesis.sh cmd-self-destruct dispatcher_defect
```

#### Candidate 2 — `effect_not_snapshotable`

- **Hypothesis**: self_destruct is currently classified as effect_not_snapshotable until a dedicated live repro proves otherwise.
- **Predicted-confirmed evidence**: Snapshot diffs stay empty while engine log or callback evidence from the latest run proves the command-specific state changed.
- **Predicted-falsified evidence**: Neither the snapshot nor the log from the latest run shows the expected command-specific state change.
- **Test command**:

```bash
tests/headless/audit/hypothesis.sh cmd-self-destruct effect_not_snapshotable
```

#### Candidate 3 — `phase1_reissuance`

- **Hypothesis**: self_destruct is currently classified as phase1_reissuance until a dedicated live repro proves otherwise.
- **Predicted-confirmed evidence**: The latest phase-1 run shows no durable snapshot effect, while phase-2 reproduces the expected state change.
- **Predicted-falsified evidence**: Phase-2 also lacks the expected state change, pushing suspicion toward dispatcher or setup defects in the latest manifest.
- **Test command**:

```bash
tests/headless/audit/hypothesis.sh cmd-self-destruct phase1_reissuance
```

### cmd-set-auto-repair-level

Related audit row: [`cmd-set-auto-repair-level`](command-audit.md#cmd-set-auto-repair-level)

#### Candidate 1 — `effect_not_snapshotable`

- **Hypothesis**: set_auto_repair_level still needs a distinguishing live repro to separate effect_not_snapshotable from a genuine dispatcher defect.
- **Predicted-confirmed evidence**: Snapshot diffs stay empty while engine log or callback evidence from the latest run proves the command-specific state changed.
- **Predicted-falsified evidence**: Neither the snapshot nor the log from the latest run shows the expected command-specific state change.
- **Test command**:

```bash
tests/headless/audit/hypothesis.sh cmd-set-auto-repair-level effect_not_snapshotable
```

#### Candidate 2 — `phase1_reissuance`

- **Hypothesis**: set_auto_repair_level still needs a distinguishing live repro to separate effect_not_snapshotable from a genuine dispatcher defect.
- **Predicted-confirmed evidence**: The latest phase-1 run shows no durable snapshot effect, while phase-2 reproduces the expected state change.
- **Predicted-falsified evidence**: Phase-2 also lacks the expected state change, pushing suspicion toward dispatcher or setup defects in the latest manifest.
- **Test command**:

```bash
tests/headless/audit/hypothesis.sh cmd-set-auto-repair-level phase1_reissuance
```

#### Candidate 3 — `dispatcher_defect`

- **Hypothesis**: set_auto_repair_level still needs a distinguishing live repro to separate effect_not_snapshotable from a genuine dispatcher defect.
- **Predicted-confirmed evidence**: Both Phase-1 and Phase-2 lack the effect in the latest run history, and no arm-specific log evidence appears.
- **Predicted-falsified evidence**: Phase-2 or targeted logging from the latest run shows the dispatcher called the correct engine path.
- **Test command**:

```bash
tests/headless/audit/hypothesis.sh cmd-set-auto-repair-level dispatcher_defect
```

### cmd-set-base

Related audit row: [`cmd-set-base`](command-audit.md#cmd-set-base)

#### Candidate 1 — `dispatcher_defect`

- **Hypothesis**: set_base still needs a distinguishing live repro to separate dispatcher_defect from a genuine dispatcher defect.
- **Predicted-confirmed evidence**: Both Phase-1 and Phase-2 lack the effect in the latest run history, and no arm-specific log evidence appears.
- **Predicted-falsified evidence**: Phase-2 or targeted logging from the latest run shows the dispatcher called the correct engine path.
- **Test command**:

```bash
tests/headless/audit/hypothesis.sh cmd-set-base dispatcher_defect
```

#### Candidate 2 — `effect_not_snapshotable`

- **Hypothesis**: set_base still needs a distinguishing live repro to separate dispatcher_defect from a genuine dispatcher defect.
- **Predicted-confirmed evidence**: Snapshot diffs stay empty while engine log or callback evidence from the latest run proves the command-specific state changed.
- **Predicted-falsified evidence**: Neither the snapshot nor the log from the latest run shows the expected command-specific state change.
- **Test command**:

```bash
tests/headless/audit/hypothesis.sh cmd-set-base effect_not_snapshotable
```

#### Candidate 3 — `phase1_reissuance`

- **Hypothesis**: set_base still needs a distinguishing live repro to separate dispatcher_defect from a genuine dispatcher defect.
- **Predicted-confirmed evidence**: The latest phase-1 run shows no durable snapshot effect, while phase-2 reproduces the expected state change.
- **Predicted-falsified evidence**: Phase-2 also lacks the expected state change, pushing suspicion toward dispatcher or setup defects in the latest manifest.
- **Test command**:

```bash
tests/headless/audit/hypothesis.sh cmd-set-base phase1_reissuance
```

### cmd-set-fire-state

Related audit row: [`cmd-set-fire-state`](command-audit.md#cmd-set-fire-state)

#### Candidate 1 — `effect_not_snapshotable`

- **Hypothesis**: set_fire_state still needs a distinguishing live repro to separate effect_not_snapshotable from a genuine dispatcher defect.
- **Predicted-confirmed evidence**: Snapshot diffs stay empty while engine log or callback evidence from the latest run proves the command-specific state changed.
- **Predicted-falsified evidence**: Neither the snapshot nor the log from the latest run shows the expected command-specific state change.
- **Test command**:

```bash
tests/headless/audit/hypothesis.sh cmd-set-fire-state effect_not_snapshotable
```

#### Candidate 2 — `phase1_reissuance`

- **Hypothesis**: set_fire_state still needs a distinguishing live repro to separate effect_not_snapshotable from a genuine dispatcher defect.
- **Predicted-confirmed evidence**: The latest phase-1 run shows no durable snapshot effect, while phase-2 reproduces the expected state change.
- **Predicted-falsified evidence**: Phase-2 also lacks the expected state change, pushing suspicion toward dispatcher or setup defects in the latest manifest.
- **Test command**:

```bash
tests/headless/audit/hypothesis.sh cmd-set-fire-state phase1_reissuance
```

#### Candidate 3 — `dispatcher_defect`

- **Hypothesis**: set_fire_state still needs a distinguishing live repro to separate effect_not_snapshotable from a genuine dispatcher defect.
- **Predicted-confirmed evidence**: Both Phase-1 and Phase-2 lack the effect in the latest run history, and no arm-specific log evidence appears.
- **Predicted-falsified evidence**: Phase-2 or targeted logging from the latest run shows the dispatcher called the correct engine path.
- **Test command**:

```bash
tests/headless/audit/hypothesis.sh cmd-set-fire-state dispatcher_defect
```

### cmd-set-idle-mode

Related audit row: [`cmd-set-idle-mode`](command-audit.md#cmd-set-idle-mode)

#### Candidate 1 — `effect_not_snapshotable`

- **Hypothesis**: set_idle_mode still needs a distinguishing live repro to separate effect_not_snapshotable from a genuine dispatcher defect.
- **Predicted-confirmed evidence**: Snapshot diffs stay empty while engine log or callback evidence from the latest run proves the command-specific state changed.
- **Predicted-falsified evidence**: Neither the snapshot nor the log from the latest run shows the expected command-specific state change.
- **Test command**:

```bash
tests/headless/audit/hypothesis.sh cmd-set-idle-mode effect_not_snapshotable
```

#### Candidate 2 — `phase1_reissuance`

- **Hypothesis**: set_idle_mode still needs a distinguishing live repro to separate effect_not_snapshotable from a genuine dispatcher defect.
- **Predicted-confirmed evidence**: The latest phase-1 run shows no durable snapshot effect, while phase-2 reproduces the expected state change.
- **Predicted-falsified evidence**: Phase-2 also lacks the expected state change, pushing suspicion toward dispatcher or setup defects in the latest manifest.
- **Test command**:

```bash
tests/headless/audit/hypothesis.sh cmd-set-idle-mode phase1_reissuance
```

#### Candidate 3 — `dispatcher_defect`

- **Hypothesis**: set_idle_mode still needs a distinguishing live repro to separate effect_not_snapshotable from a genuine dispatcher defect.
- **Predicted-confirmed evidence**: Both Phase-1 and Phase-2 lack the effect in the latest run history, and no arm-specific log evidence appears.
- **Predicted-falsified evidence**: Phase-2 or targeted logging from the latest run shows the dispatcher called the correct engine path.
- **Test command**:

```bash
tests/headless/audit/hypothesis.sh cmd-set-idle-mode dispatcher_defect
```

### cmd-set-move-state

Related audit row: [`cmd-set-move-state`](command-audit.md#cmd-set-move-state)

#### Candidate 1 — `effect_not_snapshotable`

- **Hypothesis**: set_move_state still needs a distinguishing live repro to separate effect_not_snapshotable from a genuine dispatcher defect.
- **Predicted-confirmed evidence**: Snapshot diffs stay empty while engine log or callback evidence from the latest run proves the command-specific state changed.
- **Predicted-falsified evidence**: Neither the snapshot nor the log from the latest run shows the expected command-specific state change.
- **Test command**:

```bash
tests/headless/audit/hypothesis.sh cmd-set-move-state effect_not_snapshotable
```

#### Candidate 2 — `phase1_reissuance`

- **Hypothesis**: set_move_state still needs a distinguishing live repro to separate effect_not_snapshotable from a genuine dispatcher defect.
- **Predicted-confirmed evidence**: The latest phase-1 run shows no durable snapshot effect, while phase-2 reproduces the expected state change.
- **Predicted-falsified evidence**: Phase-2 also lacks the expected state change, pushing suspicion toward dispatcher or setup defects in the latest manifest.
- **Test command**:

```bash
tests/headless/audit/hypothesis.sh cmd-set-move-state phase1_reissuance
```

#### Candidate 3 — `dispatcher_defect`

- **Hypothesis**: set_move_state still needs a distinguishing live repro to separate effect_not_snapshotable from a genuine dispatcher defect.
- **Predicted-confirmed evidence**: Both Phase-1 and Phase-2 lack the effect in the latest run history, and no arm-specific log evidence appears.
- **Predicted-falsified evidence**: Phase-2 or targeted logging from the latest run shows the dispatcher called the correct engine path.
- **Test command**:

```bash
tests/headless/audit/hypothesis.sh cmd-set-move-state dispatcher_defect
```

### cmd-set-on-off

Related audit row: [`cmd-set-on-off`](command-audit.md#cmd-set-on-off)

#### Candidate 1 — `effect_not_snapshotable`

- **Hypothesis**: set_on_off still needs a distinguishing live repro to separate effect_not_snapshotable from a genuine dispatcher defect.
- **Predicted-confirmed evidence**: Snapshot diffs stay empty while engine log or callback evidence from the latest run proves the command-specific state changed.
- **Predicted-falsified evidence**: Neither the snapshot nor the log from the latest run shows the expected command-specific state change.
- **Test command**:

```bash
tests/headless/audit/hypothesis.sh cmd-set-on-off effect_not_snapshotable
```

#### Candidate 2 — `phase1_reissuance`

- **Hypothesis**: set_on_off still needs a distinguishing live repro to separate effect_not_snapshotable from a genuine dispatcher defect.
- **Predicted-confirmed evidence**: The latest phase-1 run shows no durable snapshot effect, while phase-2 reproduces the expected state change.
- **Predicted-falsified evidence**: Phase-2 also lacks the expected state change, pushing suspicion toward dispatcher or setup defects in the latest manifest.
- **Test command**:

```bash
tests/headless/audit/hypothesis.sh cmd-set-on-off phase1_reissuance
```

#### Candidate 3 — `dispatcher_defect`

- **Hypothesis**: set_on_off still needs a distinguishing live repro to separate effect_not_snapshotable from a genuine dispatcher defect.
- **Predicted-confirmed evidence**: Both Phase-1 and Phase-2 lack the effect in the latest run history, and no arm-specific log evidence appears.
- **Predicted-falsified evidence**: Phase-2 or targeted logging from the latest run shows the dispatcher called the correct engine path.
- **Test command**:

```bash
tests/headless/audit/hypothesis.sh cmd-set-on-off dispatcher_defect
```

### cmd-set-repeat

Related audit row: [`cmd-set-repeat`](command-audit.md#cmd-set-repeat)

#### Candidate 1 — `effect_not_snapshotable`

- **Hypothesis**: set_repeat still needs a distinguishing live repro to separate effect_not_snapshotable from a genuine dispatcher defect.
- **Predicted-confirmed evidence**: Snapshot diffs stay empty while engine log or callback evidence from the latest run proves the command-specific state changed.
- **Predicted-falsified evidence**: Neither the snapshot nor the log from the latest run shows the expected command-specific state change.
- **Test command**:

```bash
tests/headless/audit/hypothesis.sh cmd-set-repeat effect_not_snapshotable
```

#### Candidate 2 — `phase1_reissuance`

- **Hypothesis**: set_repeat still needs a distinguishing live repro to separate effect_not_snapshotable from a genuine dispatcher defect.
- **Predicted-confirmed evidence**: The latest phase-1 run shows no durable snapshot effect, while phase-2 reproduces the expected state change.
- **Predicted-falsified evidence**: Phase-2 also lacks the expected state change, pushing suspicion toward dispatcher or setup defects in the latest manifest.
- **Test command**:

```bash
tests/headless/audit/hypothesis.sh cmd-set-repeat phase1_reissuance
```

#### Candidate 3 — `dispatcher_defect`

- **Hypothesis**: set_repeat still needs a distinguishing live repro to separate effect_not_snapshotable from a genuine dispatcher defect.
- **Predicted-confirmed evidence**: Both Phase-1 and Phase-2 lack the effect in the latest run history, and no arm-specific log evidence appears.
- **Predicted-falsified evidence**: Phase-2 or targeted logging from the latest run shows the dispatcher called the correct engine path.
- **Test command**:

```bash
tests/headless/audit/hypothesis.sh cmd-set-repeat dispatcher_defect
```

### cmd-set-trajectory

Related audit row: [`cmd-set-trajectory`](command-audit.md#cmd-set-trajectory)

#### Candidate 1 — `effect_not_snapshotable`

- **Hypothesis**: set_trajectory still needs a distinguishing live repro to separate effect_not_snapshotable from a genuine dispatcher defect.
- **Predicted-confirmed evidence**: Snapshot diffs stay empty while engine log or callback evidence from the latest run proves the command-specific state changed.
- **Predicted-falsified evidence**: Neither the snapshot nor the log from the latest run shows the expected command-specific state change.
- **Test command**:

```bash
tests/headless/audit/hypothesis.sh cmd-set-trajectory effect_not_snapshotable
```

#### Candidate 2 — `phase1_reissuance`

- **Hypothesis**: set_trajectory still needs a distinguishing live repro to separate effect_not_snapshotable from a genuine dispatcher defect.
- **Predicted-confirmed evidence**: The latest phase-1 run shows no durable snapshot effect, while phase-2 reproduces the expected state change.
- **Predicted-falsified evidence**: Phase-2 also lacks the expected state change, pushing suspicion toward dispatcher or setup defects in the latest manifest.
- **Test command**:

```bash
tests/headless/audit/hypothesis.sh cmd-set-trajectory phase1_reissuance
```

#### Candidate 3 — `dispatcher_defect`

- **Hypothesis**: set_trajectory still needs a distinguishing live repro to separate effect_not_snapshotable from a genuine dispatcher defect.
- **Predicted-confirmed evidence**: Both Phase-1 and Phase-2 lack the effect in the latest run history, and no arm-specific log evidence appears.
- **Predicted-falsified evidence**: Phase-2 or targeted logging from the latest run shows the dispatcher called the correct engine path.
- **Test command**:

```bash
tests/headless/audit/hypothesis.sh cmd-set-trajectory dispatcher_defect
```

### cmd-set-wanted-max-speed

Related audit row: [`cmd-set-wanted-max-speed`](command-audit.md#cmd-set-wanted-max-speed)

#### Candidate 1 — `effect_not_snapshotable`

- **Hypothesis**: set_wanted_max_speed still needs a distinguishing live repro to separate effect_not_snapshotable from a genuine dispatcher defect.
- **Predicted-confirmed evidence**: Snapshot diffs stay empty while engine log or callback evidence from the latest run proves the command-specific state changed.
- **Predicted-falsified evidence**: Neither the snapshot nor the log from the latest run shows the expected command-specific state change.
- **Test command**:

```bash
tests/headless/audit/hypothesis.sh cmd-set-wanted-max-speed effect_not_snapshotable
```

#### Candidate 2 — `phase1_reissuance`

- **Hypothesis**: set_wanted_max_speed still needs a distinguishing live repro to separate effect_not_snapshotable from a genuine dispatcher defect.
- **Predicted-confirmed evidence**: The latest phase-1 run shows no durable snapshot effect, while phase-2 reproduces the expected state change.
- **Predicted-falsified evidence**: Phase-2 also lacks the expected state change, pushing suspicion toward dispatcher or setup defects in the latest manifest.
- **Test command**:

```bash
tests/headless/audit/hypothesis.sh cmd-set-wanted-max-speed phase1_reissuance
```

#### Candidate 3 — `dispatcher_defect`

- **Hypothesis**: set_wanted_max_speed still needs a distinguishing live repro to separate effect_not_snapshotable from a genuine dispatcher defect.
- **Predicted-confirmed evidence**: Both Phase-1 and Phase-2 lack the effect in the latest run history, and no arm-specific log evidence appears.
- **Predicted-falsified evidence**: Phase-2 or targeted logging from the latest run shows the dispatcher called the correct engine path.
- **Test command**:

```bash
tests/headless/audit/hypothesis.sh cmd-set-wanted-max-speed dispatcher_defect
```

### cmd-squad-wait

Related audit row: [`cmd-squad-wait`](command-audit.md#cmd-squad-wait)

#### Candidate 1 — `effect_not_snapshotable`

- **Hypothesis**: squad_wait still needs a distinguishing live repro to separate effect_not_snapshotable from a genuine dispatcher defect.
- **Predicted-confirmed evidence**: Snapshot diffs stay empty while engine log or callback evidence from the latest run proves the command-specific state changed.
- **Predicted-falsified evidence**: Neither the snapshot nor the log from the latest run shows the expected command-specific state change.
- **Test command**:

```bash
tests/headless/audit/hypothesis.sh cmd-squad-wait effect_not_snapshotable
```

#### Candidate 2 — `phase1_reissuance`

- **Hypothesis**: squad_wait still needs a distinguishing live repro to separate effect_not_snapshotable from a genuine dispatcher defect.
- **Predicted-confirmed evidence**: The latest phase-1 run shows no durable snapshot effect, while phase-2 reproduces the expected state change.
- **Predicted-falsified evidence**: Phase-2 also lacks the expected state change, pushing suspicion toward dispatcher or setup defects in the latest manifest.
- **Test command**:

```bash
tests/headless/audit/hypothesis.sh cmd-squad-wait phase1_reissuance
```

#### Candidate 3 — `dispatcher_defect`

- **Hypothesis**: squad_wait still needs a distinguishing live repro to separate effect_not_snapshotable from a genuine dispatcher defect.
- **Predicted-confirmed evidence**: Both Phase-1 and Phase-2 lack the effect in the latest run history, and no arm-specific log evidence appears.
- **Predicted-falsified evidence**: Phase-2 or targeted logging from the latest run shows the dispatcher called the correct engine path.
- **Test command**:

```bash
tests/headless/audit/hypothesis.sh cmd-squad-wait dispatcher_defect
```

### cmd-stockpile

Related audit row: [`cmd-stockpile`](command-audit.md#cmd-stockpile)

#### Candidate 1 — `effect_not_snapshotable`

- **Hypothesis**: stockpile still needs a distinguishing live repro to separate effect_not_snapshotable from a genuine dispatcher defect.
- **Predicted-confirmed evidence**: Snapshot diffs stay empty while engine log or callback evidence from the latest run proves the command-specific state changed.
- **Predicted-falsified evidence**: Neither the snapshot nor the log from the latest run shows the expected command-specific state change.
- **Test command**:

```bash
tests/headless/audit/hypothesis.sh cmd-stockpile effect_not_snapshotable
```

#### Candidate 2 — `phase1_reissuance`

- **Hypothesis**: stockpile still needs a distinguishing live repro to separate effect_not_snapshotable from a genuine dispatcher defect.
- **Predicted-confirmed evidence**: The latest phase-1 run shows no durable snapshot effect, while phase-2 reproduces the expected state change.
- **Predicted-falsified evidence**: Phase-2 also lacks the expected state change, pushing suspicion toward dispatcher or setup defects in the latest manifest.
- **Test command**:

```bash
tests/headless/audit/hypothesis.sh cmd-stockpile phase1_reissuance
```

#### Candidate 3 — `dispatcher_defect`

- **Hypothesis**: stockpile still needs a distinguishing live repro to separate effect_not_snapshotable from a genuine dispatcher defect.
- **Predicted-confirmed evidence**: Both Phase-1 and Phase-2 lack the effect in the latest run history, and no arm-specific log evidence appears.
- **Predicted-falsified evidence**: Phase-2 or targeted logging from the latest run shows the dispatcher called the correct engine path.
- **Test command**:

```bash
tests/headless/audit/hypothesis.sh cmd-stockpile dispatcher_defect
```

### cmd-stop

Related audit row: [`cmd-stop`](command-audit.md#cmd-stop)

#### Candidate 1 — `effect_not_snapshotable`

- **Hypothesis**: stop still needs a distinguishing live repro to separate effect_not_snapshotable from a genuine dispatcher defect.
- **Predicted-confirmed evidence**: Snapshot diffs stay empty while engine log or callback evidence from the latest run proves the command-specific state changed.
- **Predicted-falsified evidence**: Neither the snapshot nor the log from the latest run shows the expected command-specific state change.
- **Test command**:

```bash
tests/headless/audit/hypothesis.sh cmd-stop effect_not_snapshotable
```

#### Candidate 2 — `phase1_reissuance`

- **Hypothesis**: stop still needs a distinguishing live repro to separate effect_not_snapshotable from a genuine dispatcher defect.
- **Predicted-confirmed evidence**: The latest phase-1 run shows no durable snapshot effect, while phase-2 reproduces the expected state change.
- **Predicted-falsified evidence**: Phase-2 also lacks the expected state change, pushing suspicion toward dispatcher or setup defects in the latest manifest.
- **Test command**:

```bash
tests/headless/audit/hypothesis.sh cmd-stop phase1_reissuance
```

#### Candidate 3 — `dispatcher_defect`

- **Hypothesis**: stop still needs a distinguishing live repro to separate effect_not_snapshotable from a genuine dispatcher defect.
- **Predicted-confirmed evidence**: Both Phase-1 and Phase-2 lack the effect in the latest run history, and no arm-specific log evidence appears.
- **Predicted-falsified evidence**: Phase-2 or targeted logging from the latest run shows the dispatcher called the correct engine path.
- **Test command**:

```bash
tests/headless/audit/hypothesis.sh cmd-stop dispatcher_defect
```

### cmd-timed-wait

Related audit row: [`cmd-timed-wait`](command-audit.md#cmd-timed-wait)

#### Candidate 1 — `effect_not_snapshotable`

- **Hypothesis**: timed_wait still needs a distinguishing live repro to separate effect_not_snapshotable from a genuine dispatcher defect.
- **Predicted-confirmed evidence**: Snapshot diffs stay empty while engine log or callback evidence from the latest run proves the command-specific state changed.
- **Predicted-falsified evidence**: Neither the snapshot nor the log from the latest run shows the expected command-specific state change.
- **Test command**:

```bash
tests/headless/audit/hypothesis.sh cmd-timed-wait effect_not_snapshotable
```

#### Candidate 2 — `phase1_reissuance`

- **Hypothesis**: timed_wait still needs a distinguishing live repro to separate effect_not_snapshotable from a genuine dispatcher defect.
- **Predicted-confirmed evidence**: The latest phase-1 run shows no durable snapshot effect, while phase-2 reproduces the expected state change.
- **Predicted-falsified evidence**: Phase-2 also lacks the expected state change, pushing suspicion toward dispatcher or setup defects in the latest manifest.
- **Test command**:

```bash
tests/headless/audit/hypothesis.sh cmd-timed-wait phase1_reissuance
```

#### Candidate 3 — `dispatcher_defect`

- **Hypothesis**: timed_wait still needs a distinguishing live repro to separate effect_not_snapshotable from a genuine dispatcher defect.
- **Predicted-confirmed evidence**: Both Phase-1 and Phase-2 lack the effect in the latest run history, and no arm-specific log evidence appears.
- **Predicted-falsified evidence**: Phase-2 or targeted logging from the latest run shows the dispatcher called the correct engine path.
- **Test command**:

```bash
tests/headless/audit/hypothesis.sh cmd-timed-wait dispatcher_defect
```

### cmd-unload-unit

Related audit row: [`cmd-unload-unit`](command-audit.md#cmd-unload-unit)

#### Candidate 1 — `target_missing`

- **Hypothesis**: unload_unit still needs a distinguishing live repro to separate target_missing from a genuine dispatcher defect.
- **Predicted-confirmed evidence**: Re-running with an explicit bootstrap target causes the effect to appear in the latest live repro.
- **Predicted-falsified evidence**: Even with the target precondition provisioned, the effect is still absent in the latest live repro.
- **Test command**:

```bash
tests/headless/audit/hypothesis.sh cmd-unload-unit target_missing
```

#### Candidate 2 — `effect_not_snapshotable`

- **Hypothesis**: unload_unit still needs a distinguishing live repro to separate target_missing from a genuine dispatcher defect.
- **Predicted-confirmed evidence**: Snapshot diffs stay empty while engine log or callback evidence from the latest run proves the command-specific state changed.
- **Predicted-falsified evidence**: Neither the snapshot nor the log from the latest run shows the expected command-specific state change.
- **Test command**:

```bash
tests/headless/audit/hypothesis.sh cmd-unload-unit effect_not_snapshotable
```

#### Candidate 3 — `phase1_reissuance`

- **Hypothesis**: unload_unit still needs a distinguishing live repro to separate target_missing from a genuine dispatcher defect.
- **Predicted-confirmed evidence**: The latest phase-1 run shows no durable snapshot effect, while phase-2 reproduces the expected state change.
- **Predicted-falsified evidence**: Phase-2 also lacks the expected state change, pushing suspicion toward dispatcher or setup defects in the latest manifest.
- **Test command**:

```bash
tests/headless/audit/hypothesis.sh cmd-unload-unit phase1_reissuance
```

### cmd-unload-units-area

Related audit row: [`cmd-unload-units-area`](command-audit.md#cmd-unload-units-area)

#### Candidate 1 — `target_missing`

- **Hypothesis**: unload_units_area still needs a distinguishing live repro to separate target_missing from a genuine dispatcher defect.
- **Predicted-confirmed evidence**: Re-running with an explicit bootstrap target causes the effect to appear in the latest live repro.
- **Predicted-falsified evidence**: Even with the target precondition provisioned, the effect is still absent in the latest live repro.
- **Test command**:

```bash
tests/headless/audit/hypothesis.sh cmd-unload-units-area target_missing
```

#### Candidate 2 — `effect_not_snapshotable`

- **Hypothesis**: unload_units_area still needs a distinguishing live repro to separate target_missing from a genuine dispatcher defect.
- **Predicted-confirmed evidence**: Snapshot diffs stay empty while engine log or callback evidence from the latest run proves the command-specific state changed.
- **Predicted-falsified evidence**: Neither the snapshot nor the log from the latest run shows the expected command-specific state change.
- **Test command**:

```bash
tests/headless/audit/hypothesis.sh cmd-unload-units-area effect_not_snapshotable
```

#### Candidate 3 — `phase1_reissuance`

- **Hypothesis**: unload_units_area still needs a distinguishing live repro to separate target_missing from a genuine dispatcher defect.
- **Predicted-confirmed evidence**: The latest phase-1 run shows no durable snapshot effect, while phase-2 reproduces the expected state change.
- **Predicted-falsified evidence**: Phase-2 also lacks the expected state change, pushing suspicion toward dispatcher or setup defects in the latest manifest.
- **Test command**:

```bash
tests/headless/audit/hypothesis.sh cmd-unload-units-area phase1_reissuance
```

### cmd-wait

Related audit row: [`cmd-wait`](command-audit.md#cmd-wait)

#### Candidate 1 — `effect_not_snapshotable`

- **Hypothesis**: wait still needs a distinguishing live repro to separate effect_not_snapshotable from a genuine dispatcher defect.
- **Predicted-confirmed evidence**: Snapshot diffs stay empty while engine log or callback evidence from the latest run proves the command-specific state changed.
- **Predicted-falsified evidence**: Neither the snapshot nor the log from the latest run shows the expected command-specific state change.
- **Test command**:

```bash
tests/headless/audit/hypothesis.sh cmd-wait effect_not_snapshotable
```

#### Candidate 2 — `phase1_reissuance`

- **Hypothesis**: wait still needs a distinguishing live repro to separate effect_not_snapshotable from a genuine dispatcher defect.
- **Predicted-confirmed evidence**: The latest phase-1 run shows no durable snapshot effect, while phase-2 reproduces the expected state change.
- **Predicted-falsified evidence**: Phase-2 also lacks the expected state change, pushing suspicion toward dispatcher or setup defects in the latest manifest.
- **Test command**:

```bash
tests/headless/audit/hypothesis.sh cmd-wait phase1_reissuance
```

#### Candidate 3 — `dispatcher_defect`

- **Hypothesis**: wait still needs a distinguishing live repro to separate effect_not_snapshotable from a genuine dispatcher defect.
- **Predicted-confirmed evidence**: Both Phase-1 and Phase-2 lack the effect in the latest run history, and no arm-specific log evidence appears.
- **Predicted-falsified evidence**: Phase-2 or targeted logging from the latest run shows the dispatcher called the correct engine path.
- **Test command**:

```bash
tests/headless/audit/hypothesis.sh cmd-wait dispatcher_defect
```

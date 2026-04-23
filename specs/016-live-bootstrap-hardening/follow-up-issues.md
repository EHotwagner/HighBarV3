# 016 Follow-Up Issues

## FI-001 Standalone Build Probe Still Cannot Verify an `armmex` Construction Site in Live Runs

- **Status**: open
- **Area**: `tests/headless/behavioral-build.sh`
- **Observed on**: April 23, 2026

### What changed in 016

- The probe no longer depends on `HIGHBAR_ARMMEX_DEF_ID` for its normal path.
- It now reads the AI token, uses `InvokeCallback` to resolve `armmex`, consumes `HelloResponse.static_map`, picks a nearby metal spot, emits `behavioral-build-outcome.json`, and logs candidate summaries across the post-dispatch sample window.
- The wrapper defaults to external-only launch mode to reduce ambient BARb reissuance noise.

### Current failure

The probe still fails its behavioral verification in this environment even though runtime prerequisite resolution succeeds.

Latest evidence from `tests/headless/behavioral-build.sh`:

- `prerequisite_resolution status=resolved def_id=149`
- `dispatched BuildUnit armmex pos=(2176.0,326.4,1968.0) target_reason=nearest_clear_metal_spot[7] accepted=1`
- No new construction candidate appears near the requested build position within the probe window
- The emitted outcome records `dispatch_result=failed`

See:

- `tests/headless/behavioral-build.sh`
- `/tmp/hb-run/behavioral-build-outcome.json`

### Why this remains a follow-up

016’s contractual requirement for US3 was runtime prerequisite resolution parity with the main workflow or an explicit runtime-resolution blocker. That parity now exists. The remaining defect is narrower: the standalone live probe still cannot prove that the dispatched `armmex` order produces a construction site near the requested metal spot on this host.

### Likely next investigations

- Confirm whether the selected metal spot is actually buildable for the commander at dispatch time.
- Inspect commander build options and economy state at the exact dispatch frame inside the standalone probe.
- Check whether the command is being accepted but ignored because the probe’s requested build site is occupied, invalid, or not owned by the commander’s team.
- Decide whether the standalone probe should issue a different bootstrap-friendly build target when the goal is command-path verification rather than economy/bootstrap validation.

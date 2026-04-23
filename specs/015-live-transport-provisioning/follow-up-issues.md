# 015 Follow-Up Issues

## FI-001 Natural Live Bootstrap Is Resource-Starved

Status: open

Evidence:
- Prepared live rerun [itertesting-20260423T024247Z](/home/developer/projects/HighBarV3/reports/itertesting/itertesting-20260423T024247Z/run-report.md) failed before transport provisioning.
- Bootstrap diagnostics recorded `economy=metal:0.1/0.0/1500.0` at the first commander build attempt and `economy=metal:0.0/0.0/1450.0` at later commander steps.
- The first hard blocker remains `factory_ground/armvp ... timeout waiting for new ready unit ... saw_new_candidate=0`.

Interpretation:
- The prepared live fixture path is trying to bootstrap from a state with effectively no available metal and no metal income.
- In that state, natural commander-built progression to `armvp` and `armap` is not a realistic assumption.

Suggested next step:
- Decide whether prepared live closeout is allowed to use an explicit fallback economy seed or fixture seed path.
- If natural-only remains required, the maintainer wrapper needs a stronger pre-bootstrap scenario guarantee than the current prepared live start provides.

## FI-002 Callback Relay Availability Is Not Stable Across Long Bootstrap Failures

Status: open

Evidence:
- The same prepared live rerun logged callback diagnostic failures after the first bootstrap step:
  `StatusCode.UNAVAILABLE ... unix:/tmp/hb-run-itertesting/attempt-1/highbar-1.sock ... No such file or directory`
- This happened while bootstrap was still reporting a live failure, so downstream callback diagnostics are not reliably available for late-stage failure analysis.

Interpretation:
- Callback relay auth was fixed, but downstream callback reachability is still fragile during long-running bootstrap failure paths.
- That makes post-failure capability inspection incomplete or timing-dependent.

Suggested next step:
- Stabilize the callback relay lifetime for the entire live closeout window, or cache the critical callback-derived diagnostics earlier in the run.

## FI-003 `behavioral-build.sh` Still Uses the Old Def-ID Injection Path

Status: open

Evidence:
- Running `tests/headless/behavioral-build.sh` on April 23, 2026 exited `77` with:
  `HIGHBAR_ARMMEX_DEF_ID not set`
- The script still depends on an env-var override instead of the runtime `InvokeCallback` def-resolution path now used by Itertesting.

Interpretation:
- The standalone build probe is no longer a reliable maintainer diagnostic in the current runtime-resolved environment.

Suggested next step:
- Update `tests/headless/behavioral-build.sh` to read the AI token, relay `InvokeCallback`, and resolve `armmex` live instead of requiring `HIGHBAR_ARMMEX_DEF_ID`.

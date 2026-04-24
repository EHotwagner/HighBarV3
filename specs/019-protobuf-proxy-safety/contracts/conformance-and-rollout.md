# Contract: Conformance And Rollout

## Modes

Validation configuration supports:

- `compatibility`: preserve legacy behavior and report only compatibility diagnostics where available.
- `warning-only`: compute strict diagnostics and record would-reject events, but do not change simulation behavior.
- `strict`: reject missing correlation/state basis and all configured command/admin validation failures.

Strict mode rejects command submissions missing either correlation data or state-basis fields.

## Warning Records

Each would-reject warning records:

- run id
- mode
- frame/state sequence
- batch/action correlation id
- issue code
- field path
- target unit/admin control
- retry hint
- whether the command/action was allowed for compatibility

## Conformance Fixtures

Shared fixtures include:

- empty command batch
- command target drift
- missing strict correlation or state basis
- non-finite position
- invalid option bit
- invalid enum-like value
- unknown build definition
- builder cannot construct requested definition
- stale state basis
- duplicate or non-monotonic batch sequence
- queue capacity rejection
- accidental immediate replacement
- unsupported command arm
- AI-channel pause/cheat in strict mode
- unauthorized admin action
- admin action disabled by config
- admin cheat rejected by run mode
- admin lease conflict

## Required Evidence

Before strict mode becomes the default:

- Python and at least one generated non-Python client produce equivalent status, issue code, field path, and retry-hint outcomes for the shared fixture suite.
- Warning-only rollout has been run across at least three prepared live or headless runs.
- Maintainers can compare warning counts across those runs.
- Any remaining would-reject events are either fixed, explicitly accepted as compatibility exceptions, or converted into tasks.

## Test Entry Points

Expected implementation tasks should wire or extend:

- `buf lint proto`
- `cd proto && buf generate`
- `ctest --test-dir build --output-on-failure -R 'command_validation|command_queue'`
- Python pytest conformance fixtures under `clients/python/tests/`
- F# generated-client build under `clients/fsharp/`
- `tests/headless/test_command_contract_hardening.sh`
- `tests/headless/protobuf-proxy-safety.sh`

## Success Criteria Mapping

- SC-001: malformed fixtures return stable issue codes.
- SC-002: common integration mistakes include retry guidance.
- SC-003: unsafe strict-mode fixtures reject before simulation impact.
- SC-007: generated client implementations produce equivalent outcomes.
- SC-008: warning-only rollout records comparable would-reject counts.

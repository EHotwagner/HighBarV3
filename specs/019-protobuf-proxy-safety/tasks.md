# Tasks: Non-Python Client Protobuf And Proxy Safety

**Input**: Design documents from `/home/developer/projects/HighBarV3/specs/019-protobuf-proxy-safety/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md
**Tests**: Included because the feature specification defines independent tests, acceptance scenarios, success criteria, conformance evidence, and quickstart validation commands.
**Organization**: Tasks are grouped by user story so each story can be implemented and tested as an independently valuable increment.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel after prerequisite phases because it touches different files and has no dependency on another incomplete task in the same phase.
- **[Story]**: User-story labels apply only to user story phases.
- Every task includes one or more exact repository paths.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Prepare shared fixture, codegen, and validation scaffolding before contract changes.

- [X] T001 Create the shared conformance fixture directory and manifest skeleton in `tests/fixtures/protobuf_proxy_safety/fixtures.yaml`
- [X] T002 [P] Document fixture authoring rules and expected status/issue fields in `tests/fixtures/protobuf_proxy_safety/README.md`
- [X] T003 [P] Verify proto generation outputs for C++, C#, and Python are still declared in `proto/buf.gen.yaml`
- [X] T004 [P] Audit existing command validation, queue, and gateway test targets for this feature in `CMakeLists.txt`
- [X] T005 [P] Add the protobuf proxy safety headless wrapper entrypoint skeleton in `tests/headless/protobuf-proxy-safety.sh`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Add the shared proto contract, generated stubs, config, counters, and queue primitives that all stories depend on.

**Critical**: No user story work should begin until the foundational proto surfaces compile and generated clients build.

- [X] T006 Add `CommandBatch` correlation/state-basis fields and command diagnostic enums/messages in `proto/highbar/commands.proto`
- [X] T007 Add `CommandAck.results`, command capability RPCs, `ValidateCommandBatch`, and admin service request/response shells in `proto/highbar/service.proto`
- [X] T008 Add command dispatch and admin audit delta messages to state updates in `proto/highbar/state.proto`
- [X] T009 Regenerate generated C++, C#, and Python stubs from `proto/buf.gen.yaml` into `build/gen/`, `build/gen/csharp/`, and `clients/python/highbar_client/highbar/`
- [X] T010 Update native proto build wiring for the new generated message and service sources in `CMakeLists.txt`
- [X] T011 [P] Add validation mode, strictness, warning-only, legacy admin compatibility, and limit settings in `src/circuit/grpc/Config.h`
- [X] T012 Implement parsing and defaults for validation mode, strictness, warning-only, legacy admin compatibility, and limits in `src/circuit/grpc/Config.cpp`
- [X] T013 [P] Add structured rejection, warning-only, dispatch-failure, and admin-audit counters in `src/circuit/grpc/Counters.h`
- [X] T014 Implement structured rejection, warning-only, dispatch-failure, and admin-audit counter updates in `src/circuit/grpc/Counters.cpp`
- [X] T015 [P] Add batch-capacity and batch metadata APIs to `src/circuit/grpc/CommandQueue.h`
- [X] T016 Implement batch-capacity and batch metadata handling in `src/circuit/grpc/CommandQueue.cpp`
- [X] T017 [P] Update Python generated import compatibility for the regenerated `highbar.v1` package in `clients/python/highbar_client/highbar/__init__.py`
- [X] T018 [P] Update F# generated proto project references for regenerated C# stubs in `clients/fsharp/HighBar.Proto.csproj`

**Checkpoint**: The proto contract compiles, generated clients build, and user-story implementation can begin.

---

## Phase 3: User Story 1 - Diagnose Invalid Client Commands (Priority: P1) MVP

**Goal**: Rejected command submissions identify batch/client correlation, command index, field path, stable issue code, detail text, and retry guidance.

**Independent Test**: Submit invalid generated-client command batches and verify each rejection returns a stable issue code, precise location, human-readable detail, and retry hint without relying on Python helper behavior.

### Tests for User Story 1

- [X] T019 [P] [US1] Add structured diagnostic unit tests for empty commands, target drift, missing intent, multiple intents, scalar errors, and retry hints in `tests/unit/command_validation_test.cc`
- [X] T020 [P] [US1] Add validator p99 coverage for structured diagnostics within the 100us budget in `tests/unit/command_validation_perf_test.cc`
- [X] T021 [P] [US1] Add Python generated-client conformance tests for invalid command diagnostics in `clients/python/tests/test_command_diagnostics.py`
- [X] T022 [P] [US1] Add F# generated-client diagnostic sample assertions in `clients/fsharp/samples/AiClient/Program.fs`
- [X] T023 [P] [US1] Add `SubmitCommands` and `ValidateCommandBatch` integration coverage for structured diagnostics in `tests/integration/command_diagnostics_test.cc`

### Implementation for User Story 1

- [X] T024 [US1] Replace string-only `ValidationResult` with proto-backed structured batch results in `src/circuit/grpc/CommandValidator.h`
- [X] T025 [US1] Implement `CommandBatchResult`, `CommandIssue`, field-path, and retry-hint construction for malformed batches in `src/circuit/grpc/CommandValidator.cpp`
- [X] T026 [US1] Preserve existing aggregate counters while appending per-batch `CommandAck.results` in `src/circuit/grpc/HighBarService.cpp`
- [X] T027 [US1] Add the async `ValidateCommandBatch` unary handler declaration and lifecycle wiring in `src/circuit/grpc/HighBarService.h`
- [X] T028 [US1] Implement `ValidateCommandBatch` as a no-enqueue, no-dispatch, no-state-mutation validation path in `src/circuit/grpc/HighBarService.cpp`
- [X] T029 [US1] Surface strict correlation, state-basis, and issue result helpers in the Python client command helper in `clients/python/highbar_client/commands.py`
- [X] T030 [US1] Surface strict correlation, state-basis, and issue result helpers in the F# command helper in `clients/fsharp/src/Commands.fs`
- [X] T031 [US1] Update command diagnostics fixture rows for US1 malformed cases in `tests/fixtures/protobuf_proxy_safety/fixtures.yaml`

**Checkpoint**: User Story 1 returns structured diagnostics for invalid batches and remains compatible with existing aggregate `CommandAck` counters.

---

## Phase 4: User Story 2 - Stop Unsafe Commands Before Simulation Impact (Priority: P1)

**Goal**: Malformed, unsafe, unauthorized, stale, conflicting, or impossible commands are rejected atomically before simulation impact, with dispatch failures reported if state changes after acceptance.

**Independent Test**: Run validation and live dispatch scenarios for unsafe commands and verify they are rejected before simulation impact, or reported as dispatch failures if the world changes after initial acceptance.

### Tests for User Story 2

- [X] T032 [P] [US2] Add strict-mode ownership, live-unit, capability, stale-basis, duplicate-sequence, and order-conflict unit tests in `tests/unit/command_validation_test.cc`
- [X] T033 [P] [US2] Add atomic whole-batch capacity rejection tests in `tests/unit/command_queue_test.cc`
- [X] T034 [P] [US2] Add dispatch-time target-missing and ownership-changed integration coverage in `tests/integration/ai_move_flow_test.cc`
- [X] T035 [P] [US2] Extend strict command hardening headless coverage for stale, queue-full, unsupported-arm, and replacement-conflict cases in `tests/headless/test_command_contract_hardening.sh`

### Implementation for User Story 2

- [X] T036 [US2] Add per-session batch sequence, duplicate, stale state-basis, and strict missing-correlation checks in `src/circuit/grpc/HighBarService.cpp`
- [X] T037 [US2] Enforce atomic queue capacity before pushing any command from a batch in `src/circuit/grpc/CommandQueue.cpp`
- [X] T038 [US2] Map stale, conflict, queue-full, ownership, dead-unit, unsupported, and capability outcomes to structured issue codes in `src/circuit/grpc/CommandValidator.cpp`
- [X] T039 [US2] Add an engine-thread order state tracker for active intent, idle/release observation, replacement policy, and unit generation in `src/circuit/grpc/OrderStateTracker.h`
- [X] T040 [US2] Implement the engine-thread order state tracker in `src/circuit/grpc/OrderStateTracker.cpp`
- [X] T041 [US2] Register the order state tracker implementation in `CMakeLists.txt`
- [X] T042 [US2] Recheck target existence, ownership, live state, command support, and capability legality before engine API calls in `src/circuit/grpc/CommandDispatch.cpp`
- [X] T043 [US2] Emit `CommandDispatchEvent` records for applied and skipped accepted commands through `src/circuit/grpc/DeltaBus.h`
- [X] T044 [US2] Implement dispatch event publication and counter updates in `src/circuit/grpc/DeltaBus.cpp`
- [X] T045 [US2] Wire order-state updates and dispatch event publication into command draining in `src/circuit/module/GrpcGatewayModule.cpp`
- [X] T046 [US2] Add US2 strict safety and dispatch failure fixture rows in `tests/fixtures/protobuf_proxy_safety/fixtures.yaml`

**Checkpoint**: User Story 2 rejects unsafe batches atomically and emits client-visible dispatch results for accepted commands that fail at execution time.

---

## Phase 5: User Story 3 - Separate Admin Controls From AI Intent (Priority: P2)

**Goal**: Pause, speed, cheat, lifecycle, and similar global controls use a separately authorized admin surface with dry-run validation, execution results, leases, and audit events.

**Independent Test**: Attempt privileged actions from normal AI credentials and authorized operator/test-harness credentials, then verify denial, acceptance, lease, and audit outcomes match run mode and role.

### Tests for User Story 3

- [X] T047 [P] [US3] Add admin authorization, run-mode, disabled-action, stale-action, invalid-value, and lease-conflict unit tests in `tests/unit/admin_control_test.cc`
- [X] T048 [P] [US3] Add admin execute and audit integration tests in `tests/integration/admin_control_test.cc`
- [X] T049 [P] [US3] Add AI-channel pause/cheat rejection coverage in `tests/unit/command_validation_test.cc`
- [X] T050 [P] [US3] Extend protobuf proxy safety headless coverage for admin dry-run, execute, lease expiry, and audit cases in `tests/headless/protobuf-proxy-safety.sh`

### Implementation for User Story 3

- [X] T051 [US3] Finalize admin action, result, issue, capability, lease, and audit proto fields in `proto/highbar/service.proto`
- [X] T052 [US3] Add admin audit event payload fields to the state delta contract in `proto/highbar/state.proto`
- [X] T053 [US3] Extend run-scoped role credential parsing and role checks for admin/operator/test-harness scopes in `src/circuit/grpc/AuthToken.h`
- [X] T054 [US3] Implement run-scoped role credential parsing and role checks for admin/operator/test-harness scopes in `src/circuit/grpc/AuthToken.cpp`
- [X] T055 [US3] Enforce admin/operator/test-harness authorization metadata in `src/circuit/grpc/AuthInterceptor.cpp`
- [X] T056 [US3] Add admin validation, lease, heartbeat, release, and audit controller declarations in `src/circuit/grpc/AdminController.h`
- [X] T057 [US3] Implement admin validation, lease, heartbeat, release, and audit controller behavior in `src/circuit/grpc/AdminController.cpp`
- [X] T058 [US3] Add the sibling async admin service declaration in `src/circuit/grpc/AdminService.h`
- [X] T059 [US3] Implement `GetAdminCapabilities`, `ValidateAdminAction`, and `ExecuteAdminAction` handlers in `src/circuit/grpc/AdminService.cpp`
- [X] T060 [US3] Register admin controller and admin service sources in `CMakeLists.txt`
- [X] T061 [US3] Wire `AdminService` construction, binding, engine-thread execution, and lease expiry ticks in `src/circuit/module/GrpcGatewayModule.cpp`
- [X] T062 [US3] Reject AI-channel pause and cheat commands in strict mode with admin-required issue codes in `src/circuit/grpc/CommandValidator.cpp`
- [X] T063 [US3] Add Python admin capability, dry-run, and execute helpers in `clients/python/highbar_client/admin.py`
- [X] T064 [US3] Add F# admin capability, dry-run, and execute helpers in `clients/fsharp/src/Admin.fs`
- [X] T065 [US3] Include `Admin.fs` in the F# client project in `clients/fsharp/HighBar.Client.fsproj`
- [X] T066 [US3] Add US3 admin and legacy AI-channel admin fixture rows in `tests/fixtures/protobuf_proxy_safety/fixtures.yaml`

**Checkpoint**: User Story 3 denies privileged actions from normal AI credentials, allows authorized configured admin/test-harness actions, and emits audit events for every accepted or rejected admin event.

---

## Phase 6: User Story 4 - Discover Capabilities Before Submitting Commands (Priority: P3)

**Goal**: Generated clients can discover legal command arms, options, map/resource identifiers, queue state, schema version, feature flags, and unit-specific capabilities before submitting or dry-running commands.

**Independent Test**: Request capability information for known unit and map state, then use it to validate a legal command and an illegal command without changing simulation state.

### Tests for User Story 4

- [X] T067 [P] [US4] Add command schema and unit capability provider unit tests in `tests/unit/command_capabilities_test.cc`
- [X] T068 [P] [US4] Add Python capability discovery and dry-run tests in `clients/python/tests/test_command_capabilities.py`
- [X] T069 [P] [US4] Add F# capability discovery sample assertions in `clients/fsharp/samples/AiClient/Program.fs`
- [X] T070 [P] [US4] Extend headless coverage for capabilities and dry-run no-mutation behavior in `tests/headless/protobuf-proxy-safety.sh`

### Implementation for User Story 4

- [X] T071 [US4] Finalize command schema, unit capability, feature flag, map limit, option mask, and queue-state proto fields in `proto/highbar/service.proto`
- [X] T072 [US4] Add capability provider declarations for schema-level and unit-level discovery in `src/circuit/grpc/CapabilityProvider.h`
- [X] T073 [US4] Implement command schema discovery in `src/circuit/grpc/CapabilityProvider.cpp`
- [X] T074 [US4] Implement unit capability discovery from safe snapshot-derived or engine-thread data in `src/circuit/grpc/CapabilityProvider.cpp`
- [X] T075 [US4] Register the capability provider implementation in `CMakeLists.txt`
- [X] T076 [US4] Add async `GetCommandSchema` and `GetUnitCapabilities` handler declarations in `src/circuit/grpc/HighBarService.h`
- [X] T077 [US4] Implement `GetCommandSchema` and `GetUnitCapabilities` handlers in `src/circuit/grpc/HighBarService.cpp`
- [X] T078 [US4] Use capability data to improve unsupported-arm, option-mask, build-option, and custom-command validation in `src/circuit/grpc/CommandValidator.cpp`
- [X] T079 [US4] Add Python command schema and unit capability helpers in `clients/python/highbar_client/session.py`
- [X] T080 [US4] Add F# command schema and unit capability helpers in `clients/fsharp/src/Session.fs`
- [X] T081 [US4] Add US4 capability and dry-run fixture rows in `tests/fixtures/protobuf_proxy_safety/fixtures.yaml`

**Checkpoint**: User Story 4 exposes discoverable capabilities and dry-run validation without changing simulation state.

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Complete conformance, rollout evidence, docs, validation commands, and cleanup across all stories.

- [X] T082 [P] Add a fixture-driven Python conformance runner for command and admin cases in `clients/python/tests/test_protobuf_proxy_safety_conformance.py`
- [X] T083 [P] Add generated-client parity checks for Python and F# fixture outcomes in `tests/integration/cross_client_parity_test.sh`
- [X] T084 [P] Add warning-only rollout summary generation and comparable would-reject counts to `tests/headless/protobuf-proxy-safety.sh`
- [X] T085 [P] Update gateway architecture notes for diagnostics, validation modes, dispatch events, admin service, and capabilities in `src/circuit/grpc/README.md`
- [X] T086 [P] Update Python client usage documentation for strict fields, dry-run validation, capabilities, and admin helpers in `clients/python/README.md`
- [X] T087 Update quickstart validation results and any changed command names in `specs/019-protobuf-proxy-safety/quickstart.md`
- [X] T088 Run `buf lint proto` and fix any lint violations in `proto/highbar/commands.proto`, `proto/highbar/service.proto`, and `proto/highbar/state.proto`
- [X] T089 Run `cd proto && buf generate` and verify generated C++, C#, and Python outputs listed in `proto/buf.gen.yaml`
- [X] T090 Run native focused tests and fix failures in `tests/unit/command_validation_test.cc`, `tests/unit/command_queue_test.cc`, `tests/unit/command_validation_perf_test.cc`, and `tests/unit/command_capabilities_test.cc`
- [X] T091 Run Python and F# client checks and fix failures in `clients/python/tests/`, `clients/fsharp/HighBar.Client.fsproj`, and `clients/fsharp/samples/AiClient/AiClient.fsproj`
- [X] T092 Run strict and warning-only headless evidence and record resulting report paths in `tests/headless/protobuf-proxy-safety.sh`
- [X] T093 Run the Constitution V latency microbench and verify p99 round-trip stays within budget in `tests/bench/latency-uds.sh` and `tests/bench/latency-tcp.sh`
- [X] T094 Confirm every warning-only would-reject event is fixed, accepted as a compatibility exception, or converted to follow-up work in `specs/019-protobuf-proxy-safety/quickstart.md`

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies.
- **Foundational (Phase 2)**: Depends on Setup and blocks all user-story phases.
- **User Story 1 (Phase 3)**: Depends on Foundational; recommended MVP.
- **User Story 2 (Phase 4)**: Depends on Foundational and shared diagnostics contract; can proceed alongside US1 after proto/codegen are stable, but strict rollout should validate US1 diagnostics first.
- **User Story 3 (Phase 5)**: Depends on Foundational and can proceed independently of US4.
- **User Story 4 (Phase 6)**: Depends on Foundational and benefits from US1/US2 validator behavior.
- **Polish (Phase 7)**: Depends on whichever user stories are included in the delivery scope.

### User Story Dependencies

- **US1 Diagnose Invalid Client Commands (P1)**: MVP; no dependency on other stories after Foundational.
- **US2 Stop Unsafe Commands Before Simulation Impact (P1)**: Depends on shared diagnostic proto types from Foundational; no dependency on admin or capability discovery.
- **US3 Separate Admin Controls From AI Intent (P2)**: Depends on shared auth/config/codegen foundations; independent from US4.
- **US4 Discover Capabilities Before Submitting Commands (P3)**: Depends on shared proto/codegen and can be delivered after safety-critical validation.

### Within Each User Story

- Write tests first and verify they fail for the missing behavior before implementation.
- Keep proto/codegen changes ahead of C++/Python/F# implementation that consumes those generated types.
- Implement validators and services before client helpers.
- Complete each checkpoint before treating the story as independently shippable.

---

## Parallel Opportunities

- Setup tasks T002-T005 can run in parallel after T001.
- Foundational tasks T011, T013, T015, T017, and T018 can run in parallel after proto tasks T006-T010 are planned, but implementation must reconcile with generated type names.
- US1 test tasks T019-T022 can run in parallel, then implementation should proceed T024-T031.
- US2 test tasks T032-T035 can run in parallel; T039-T041 can run alongside T042-T045 after test expectations are clear.
- US3 test tasks T047-T050 can run in parallel; auth, controller, service, client helper, and fixture work can be split by file ownership.
- US4 test tasks T067-T070 can run in parallel; provider implementation and client helper work can be split after service proto names are stable.
- Polish tasks T082-T086 can run in parallel once the story APIs are stable.

---

## Parallel Example: User Story 1

```bash
Task: "T019 [P] [US1] Add structured diagnostic unit tests for empty commands, target drift, missing intent, multiple intents, scalar errors, and retry hints in tests/unit/command_validation_test.cc"
Task: "T021 [P] [US1] Add Python generated-client conformance tests for invalid command diagnostics in clients/python/tests/test_command_diagnostics.py"
Task: "T022 [P] [US1] Add F# generated-client diagnostic sample assertions in clients/fsharp/samples/AiClient/Program.fs"
```

## Parallel Example: User Story 2

```bash
Task: "T033 [P] [US2] Add atomic whole-batch capacity rejection tests in tests/unit/command_queue_test.cc"
Task: "T034 [P] [US2] Add dispatch-time target-missing and ownership-changed integration coverage in tests/integration/ai_move_flow_test.cc"
Task: "T035 [P] [US2] Extend strict command hardening headless coverage for stale, queue-full, unsupported-arm, and replacement-conflict cases in tests/headless/test_command_contract_hardening.sh"
```

## Parallel Example: User Story 3

```bash
Task: "T047 [P] [US3] Add admin authorization, run-mode, disabled-action, stale-action, invalid-value, and lease-conflict unit tests in tests/unit/admin_control_test.cc"
Task: "T048 [P] [US3] Add admin execute and audit integration tests in tests/integration/admin_control_test.cc"
Task: "T050 [P] [US3] Extend protobuf proxy safety headless coverage for admin dry-run, execute, lease expiry, and audit cases in tests/headless/protobuf-proxy-safety.sh"
```

## Parallel Example: User Story 4

```bash
Task: "T067 [P] [US4] Add command schema and unit capability provider unit tests in tests/unit/command_capabilities_test.cc"
Task: "T068 [P] [US4] Add Python capability discovery and dry-run tests in clients/python/tests/test_command_capabilities.py"
Task: "T069 [P] [US4] Add F# capability discovery sample assertions in clients/fsharp/samples/AiClient/Program.fs"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1 and Phase 2 so the shared proto contract and generated stubs compile.
2. Complete Phase 3 for US1 structured diagnostics.
3. Validate US1 independently with `tests/unit/command_validation_test.cc`, `tests/integration/command_diagnostics_test.cc`, `clients/python/tests/test_command_diagnostics.py`, and the generated F# sample.
4. Stop and review the diagnostic contract before enabling stricter rejection behavior.

### Incremental Delivery

1. Deliver US1 diagnostics so generated clients can understand failures.
2. Deliver US2 strict safety and dispatch visibility to prevent simulation impact.
3. Deliver US3 admin separation for privileged controls.
4. Deliver US4 capability discovery and dry-run ergonomics.
5. Complete conformance and warning-only rollout evidence before making strict mode the default.

### Validation Commands

Run the quickstart sequence from `/home/developer/projects/HighBarV3/specs/019-protobuf-proxy-safety/quickstart.md`:

```bash
buf lint proto
cd proto && buf generate
cmake --build build --target command_validation_test command_queue_test command_validation_perf_test
ctest --test-dir build --output-on-failure -R 'command_validation|command_queue'
cd clients/python && python -m pytest tests/test_ai_role.py tests/behavioral_coverage
dotnet build clients/fsharp/HighBar.Client.fsproj
dotnet build clients/fsharp/samples/AiClient/AiClient.fsproj
tests/headless/test_command_contract_hardening.sh
tests/headless/protobuf-proxy-safety.sh --mode warning-only
tests/headless/protobuf-proxy-safety.sh --mode strict
tests/bench/latency-uds.sh
tests/bench/latency-tcp.sh
```

---

## Notes

- Preserve existing `CommandAck` aggregate counters and Python/F# compatibility during warning-only rollout.
- Keep worker-thread validation side-effect free; engine-thread mutation, dispatch rechecks, order tracking, and admin execution stay in `src/circuit/module/GrpcGatewayModule.cpp` or engine-thread-owned helpers.
- Do not enable strict rejection by default until conformance evidence covers Python plus at least one generated non-Python client and warning-only runs are understood.

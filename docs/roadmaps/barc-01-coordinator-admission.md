# BARC-01 Coordinator Admission

## BARC-01.1f — Native coordinator batch admission

- [x] Validate coordinator batches before queue mutation: 1–64 commands,
  signed-engine-representable target, and nonzero 64-bit sequence and correlation.
- [x] Preserve session, batch sequence, client correlation, command index, and
  authoritative target on every queued child.
- [x] Admit a complete coordinator batch with one atomic `TryPushBatch` call.
- [x] Report typed accepted, invalid, and queue-full outcomes to coordinator
  counters and trace/error logs.
- [x] Cover exact three-child provenance, values above `UInt32`, atomic overflow,
  invalid and oversized batches, and concurrent non-interleaving.

Validation on 2026-09-28 from protected `master` `66483515`:

- Standalone native configure and compilation succeeded with CMake 4.4.3,
  GCC 16.2.1, protobuf 36.1, gRPC 1.84.0, and GTest 1.18.0.
- `command_queue_test` and `coordinator_command_admission_test` both passed.
- `coordinator_command_admission_test` passed 100 consecutive executions.
- `CoordinatorClient.cpp` passed a standalone C++20 syntax compile against the
  generated protobuf/gRPC headers.

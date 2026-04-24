# Commit Hygiene (Constitution I)

HighBarV3 is a fork of BARb. Every upstream merge replays future
BARb commits on top of ours; the cleanliness of that replay is
directly proportional to how we split our own work into commits.
This document is the audit checklist for any PR that touches
**upstream-shared files**.

## The two upstream-shared files

1. `CMakeLists.txt` — edited once at T005 (see commit `0d0409a9`) to
   add `find_package(gRPC)` / `find_package(Protobuf)`, the
   `highbar_proto` static target, symbol-hiding flags, and the
   `CMAKE_MODULE_LINKER_FLAGS` addition. Every addition lives inside
   the fenced `=== V3: gRPC gateway additions ===` block; no upstream
   line is reordered.

2. `src/circuit/CircuitAI.cpp` — edited at:
   - T018 (commit `1d8371ca`): module registration, 2 added lines.
   - T079/T080 (Phase 6): introduced the `enableBuiltin` gate for the
     legacy BARb managers.
   - 020-admin-behavior-tests: made external-control mode permanent by
     defaulting `enableBuiltin` false and ignoring `enable_builtin=true`
     in `InitOptions()`.

3. `src/circuit/CircuitAI.h` — adds the `enableBuiltin` member and
   `IsBuiltinEnabled()` accessor. HighBarV3 keeps the default false.

## Rules for splitting

- **One upstream-shared edit per commit.** Never bundle changes to
  `CircuitAI.cpp` with changes to V3-owned files
  (`src/circuit/grpc/*`, `src/circuit/module/GrpcGatewayModule.*`,
  `proto/highbar/*`, `clients/*`).
- **Label the commit message.** Subject line prefix `V3: <file> —
  <what>`. First body paragraph must name the task ID and explain
  *why* the edit is upstream-shared so a future merger understands the
  constraint.
- **No reformatting of surrounding upstream lines.** Diff noise makes
  future merges harder. Add, don't rewrap.
- **Guard platform-specific additions.** The CMakeLists Linux-only
  flags are behind `if (NOT WIN32 AND NOT APPLE)` — this is the rule,
  not an exception.

## Audit commands

Verify the audit status before pushing:

```bash
# List every commit that touches an upstream-shared file.
git log --oneline origin/master..HEAD -- CMakeLists.txt src/circuit/CircuitAI.{h,cpp}

# Each commit must mention "Upstream-shared edit" in its body.
git log origin/master..HEAD -- CMakeLists.txt src/circuit/CircuitAI.{h,cpp} \
    | grep -q "Upstream-shared edit" \
    || echo "WARN: at least one upstream-shared commit lacks the marker."

# No commit should touch both an upstream-shared file AND V3-owned.
for sha in $(git log --format=%H origin/master..HEAD); do
    files=$(git show --name-only --format= "$sha")
    if echo "$files" | grep -qE "^(CMakeLists\.txt|src/circuit/CircuitAI\.)"; then
        v3=$(echo "$files" | grep -E "^(src/circuit/(grpc|module/Grpc)|proto/highbar/|clients/)" || true)
        if [ -n "$v3" ]; then
            echo "FAIL: commit $sha mixes upstream-shared with V3-owned files"
            echo "$files"
        fi
    fi
done
```

Run this before every PR push. A clean output (no `FAIL` lines) is
the merge-cleanliness promise from Constitution I.

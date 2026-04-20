# HighBarV3 Fork State

## Upstream base

HighBarV3 is a fork of [`rlcevg/CircuitAI`](https://github.com/rlcevg/CircuitAI)
("BARb") — the BAR-targeted Skirmish AI plugin for the Recoil/Spring engine.

**Pinned base commit**: `0ef36267633d6c1b2f6408a8d8a59fff38745dc3`
(tip of BARb's `barb5` branch at fork time)

This commit is the one named by the HighBarV3 constitution
(`.specify/memory/constitution.md`) and the architecture document
(`docs/architecture.md`). Every upstream-shared edit the V3 feature branches
apply (`CMakeLists.txt`, `src/circuit/CircuitAI.cpp`) is taken relative to
this commit.

## License

Inherited **GPL-2.0** from upstream CircuitAI. See `LICENSE`.

## How the fork was landed

The fork was imported into this repository via `git merge --allow-unrelated-histories`
from the upstream `barb5` branch, so BARb's history is preserved in our tree.
The import is a single isolated merge commit on `master`:

```text
6c12775e Fork BARb (rlcevg/CircuitAI) at commit 0ef36267
```

Verify at any time:

```sh
git log --oneline master | grep -F 0ef36267
```

should show the pinned commit reachable from `master`.

## Upstream remote

The `upstream-barb` Git remote is configured for future upstream syncs:

```sh
git remote -v
#   upstream-barb  https://github.com/rlcevg/CircuitAI.git (fetch)
#   upstream-barb  https://github.com/rlcevg/CircuitAI.git (push)
```

To pull future BARb changes onto `master`:

```sh
git fetch upstream-barb
git checkout master
git merge upstream-barb/barb5
```

Because the original fork merge preserved both histories, this is a standard
three-way merge — no `--allow-unrelated-histories` needed after the initial
import.

## Merge-discipline invariants (Constitution I)

- V3-owned code lives under `src/circuit/module/GrpcGatewayModule.*`,
  `src/circuit/grpc/*`, `proto/highbar/*`, `clients/*`, `data/config/grpc.json`,
  `vcpkg.json`, and `docs/*` — paths that upstream does not touch.
- Upstream-shared edits are strictly limited to `src/circuit/CircuitAI.cpp`
  (~4 lines) and `CMakeLists.txt`, and each is isolated in its own commit
  with a `V3:` tag in the message so future upstream merges can replay them
  cleanly.

# Peer Walkthrough Sign-Off

**Purpose**: Per SC-008 / `contracts/build-runbook.md` §Peer-walkthrough
sign-off, the feature is not "done" until at least one **non-author**
maintainer has executed `BUILD.md` end-to-end on a clean VM image and
recorded their result here.

## How to walk through

1. Provision a clean VM (or wipe ~/recoil-engine, ~/vcpkg, and the BAR
   write dir to start fresh).
2. Install OS prerequisites listed in [`/BUILD.md`](../../../BUILD.md)
   under "Prerequisites" (`git`, `cmake`, `ninja`, `g++ 13+`,
   `python3`, `buf`, `protoc`, `pkg-config`, `zip/unzip/curl/tar`).
3. Clone HighBarV3 to a working directory.
4. Clone `~/vcpkg` at baseline `256acc64012b23a13041d8705805e1f23b43a024`
   and bootstrap.
5. Clone `~/recoil-engine` at tag `2025.06.19` with the relevant
   submodules; symlink HighBarV3 in as `~/recoil-engine/AI/Skirmish/BARb`.
6. Run `tests/headless/build-runbook-validation.sh` — this executes
   every numbered step in BUILD.md against the expect substring.
7. (Optional) Run `tests/headless/us1-observer.sh` and
   `tests/headless/us2-ai-coexist.sh` against your installed BAR; both
   should exit 0.

## Sign-off entries

Add one entry per maintainer who has completed the walkthrough.
Format: `- [ ] <github-handle> — <date> — <commit-sha walked> — <notes>`
Tick the box once your run is green.

- [ ] _(awaiting first peer walkthrough)_

## Author self-walk

The author's own runs do **not** count toward the SC-008 sign-off
gate, but recording them here helps the next walker:

- [X] EHotwagner — 2026-04-21 — `1652695f` — End-to-end client-mode
  loop verified on Arch reference host: spring → 30+ heartbeats,
  2,500+ StateUpdates, AttackCommand round-trip, 30+ UnitDamaged
  events with full payload. `BUILD.md` written + parsed cleanly by
  `build-runbook-validation.sh` (10 steps extracted, expect
  substrings sane). The validator's full live-run will need a
  one-off `pip install --user --break-system-packages grpcio
  grpcio-tools` on Arch (Ubuntu ships these system packages).

## Known walkthrough notes

- **Step 2 (vcpkg install)** can take 30-60 minutes on a cold cache —
  primarily the gRPC build. Use a binary cache if available.
- **Step 9 (engine launch)** depends on the BAR install having a
  populated `pool/` directory and at least one map (`Avalanche 3.4`
  is the minimum-viable choice the runbook uses).
- **Step 10 (observer)** requires `grpcio` Python package available.
  `pip install grpcio grpcio-tools` (with `--break-system-packages`
  on PEP 668 systems).

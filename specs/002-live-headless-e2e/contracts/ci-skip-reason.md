# Contract: `ci-skip-reason:` commit trailer

**Addresses**: FR-018, spec US6 AC-3.

## Trailer grammar

A commit message may carry zero or more trailers of the form:

```
ci-skip-reason: <script-basename> — <free-text justification>
```

Parsed with `git interpret-trailers --parse`. Key match is
case-insensitive; value grammar is strict:

| Token | Grammar |
|---|---|
| `<script-basename>` | `[a-z][a-z0-9_-]*\.sh`, case-sensitive, matches a file in `tests/headless/` or `tests/bench/`. |
| `<separator>` | one of ` — ` (em-dash), ` - ` (hyphen). Both accepted. |
| `<free-text justification>` | Unicode, length ≤200 chars. No newlines (trailers are single-line by spec). |

Multiple trailers permitted per commit, one script basename per
trailer. Repeated basenames in the same commit are ignored after
the first.

## CI enforcement

On a job whose runner carries the `bar-engine` label (the only
runner class where engine-dependent scripts can run), the job driver:

1. Runs the full headless / bench script list.
2. For each script exiting 77, checks whether the HEAD commit's
   trailers mention that script by basename.
3. If yes: the skip is accepted, the job continues with that script
   marked as "waived-skip" in the job summary.
4. If no: the job fails with a pointer to this contract and the
   script that skipped unexpectedly.

For any script exiting 77 that is listed in the trailer but whose
expected outcome was a PASS, the waiver is accepted but the CI run
also emits a warning so reviewers notice the waiver.

For any script listed in a trailer that **did not exit 77** (either
passed or failed), the job fails. Stale waivers do not accumulate.

## Scope

The waiver applies to:

- `tests/headless/*.sh`
- `tests/bench/latency-*.sh`

It does not apply to:

- `cpp-build`, `proto`, `fsharp`, `python`, `lint` jobs. Failures
  there are fixed, not waived.
- Runner pre-flight (missing pinned `spring-headless`, missing asset
  cache). Runner provisioning failures always fail the job — the
  trailer is for per-script skips, not for runner outages.

## Lifetime

Waivers live on HEAD's commit message only. Merge commits do not
carry a waiver from any parent. Squash-merges to master *do* preserve
the trailer (the squash-commit author can keep or strip it at merge
time); nothing in this contract prevents a long-lived master-side
waiver, but the expectation is that every waiver is either:

- An in-flight branch's temporary marker (removed before merge), or
- A fast-follow commit that removes the waiver within one week of
  merge (enforced socially; not automated here).

## Examples

### Valid

```
Fix us2-ai-coexist.sh harness flake

The AI-client Hello race can hit the 1s connect timeout under
high system load. This commit bumps the timeout to 3s.

ci-skip-reason: us1-framerate.sh — flaky on overloaded self-hosted runner, tracked in issue #42
```

### Invalid (missing separator)

```
ci-skip-reason: us1-framerate.sh flaky
```

Parser rejects this and the job fails.

### Invalid (wrong script name casing)

```
ci-skip-reason: Us1-Framerate.sh — typo
```

Parser rejects; script basenames are case-sensitive.

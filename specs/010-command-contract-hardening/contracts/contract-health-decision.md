# Contract: Contract Health Decision

**Feature**: [Command Contract Hardening](../plan.md)

## Purpose

Define the run-level gate that decides whether Itertesting is allowed to behave as a normal improvement workflow.

## Decision States

| Status | Meaning | Workflow effect |
|--------|---------|-----------------|
| `ready_for_itertesting` | No unresolved foundational blockers were detected. | Normal coverage/evidence/setup/learning guidance may proceed. |
| `blocked_foundational` | One or more foundational contract issues were detected. | Improvement guidance is withheld; the run stops for repair with repro links. |
| `needs_pattern_review` | A blocker exists but does not fit the current issue vocabulary cleanly. | Improvement guidance is withheld or secondary-only until maintainers classify the new pattern. |

## Required Behaviors

1. Every Itertesting run records exactly one contract-health decision.
2. The decision references the blocking issue ids when blockers exist.
3. A blocked decision does not erase downstream observations, but it does prevent those observations from being framed as the primary remediation path.
4. A later run may mark the same blocker resolved only after the issue is absent and its repro path no longer reproduces the defect.
5. Implementations may record `resolved_issue_ids` so maintainers can see which previously blocking issues cleared in the latest run.

## Output Expectations

- The decision appears in the run report and machine-readable manifest.
- Stop artifacts make it obvious whether the maintainer should fix contract health first or continue with normal Itertesting tuning.

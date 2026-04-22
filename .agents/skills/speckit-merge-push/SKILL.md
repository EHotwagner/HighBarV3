---
name: speckit-merge-push
description: Finish a Speckit feature branch by squash-merging it into its target branch, committing all remaining work, pushing to the GitHub remote, and deleting the feature branch locally and remotely. Use when Codex needs to land a completed Speckit branch with non-interactive git commands and clean up the branch afterward.
---

# Speckit Merge Push

## Overview

Use this skill to land a completed Speckit feature branch with a squash merge, push the target branch, and remove the feature branch from both the local repo and `origin`.

Prefer explicit, non-interactive git commands. Do not use interactive rebase or interactive merge flows.

## Workflow

### 1. Discover the merge inputs

Determine:

- current feature branch
- target branch to receive the squash merge
- remote name to push to, defaulting to `origin`

If the target branch is not stated, infer it from repo context only when that is unambiguous. Otherwise ask.

### 2. Check for blockers before changing git state

Run these checks:

- `git status --short`
- `git branch --show-current`
- `git remote -v`
- `git rev-parse --verify <target-branch>`
- `git rev-parse --verify <feature-branch>`

Stop and report clearly if:

- the working tree contains unrelated changes the user may not want included
- either branch does not exist
- the feature branch is already the target branch
- there are merge conflicts from a previous unfinished operation

If there are local changes and the user asked to "commit all", include them in the landing commit instead of stashing.

### 3. Refresh the target branch

Use non-interactive commands:

```bash
git checkout <target-branch>
git pull --ff-only <remote> <target-branch>
```

If fast-forward pull fails, stop and explain why instead of forcing history changes.

### 4. Squash-merge the feature branch

Run:

```bash
git merge --squash <feature-branch>
```

If conflicts occur:

- stop
- report the conflicting paths
- do not auto-resolve unless the user explicitly asked for conflict resolution

### 5. Create the squash commit

Stage any remaining files if needed, then create one commit containing the full feature:

```bash
git commit -m "<commit-message>"
```

Commit message rules:

- use a concise summary line
- prefer the feature name or spec slug when available
- avoid placeholder text

If the user did not specify a message, derive one from the feature branch or spec folder name.

### 6. Push the target branch

Push the landed commit:

```bash
git push <remote> <target-branch>
```

Do not force-push unless the user explicitly requests it.

### 7. Delete the feature branch

After the target branch push succeeds, delete the feature branch locally and remotely:

```bash
git branch -D <feature-branch>
git push <remote> --delete <feature-branch>
```

If remote deletion fails because the branch is already gone, report that as a non-fatal cleanup note.

## Output Checklist

When using this skill, report:

- target branch
- feature branch
- squash commit SHA and message
- push result
- local branch deletion result
- remote branch deletion result

If any step failed, report the exact failed command and the blocking reason.

## Safety Rules

- Use non-interactive git commands only.
- Never use `git reset --hard`, `git push --force`, or branch deletion before the target branch push succeeds unless the user explicitly asks.
- Do not discard uncommitted changes.
- Do not delete the current branch before switching to the target branch.

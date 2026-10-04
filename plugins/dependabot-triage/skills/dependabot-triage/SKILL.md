---
name: dependabot-triage
description: Use when asked to triage, categorize, review, merge, or clean up Dependabot pull requests in a repository (e.g. "проверь пулл реквесты dependabot", "разбей на категории", "check dependabot PRs"), or when a repo has accumulated open Dependabot PRs.
---

# Dependabot Triage

## Overview

Categorize all open Dependabot PRs, merge the safe ones, and close the unwanted ones in a way that stops Dependabot from re-proposing them. Works in any repo via `gh`.

## Procedure

1. **Gather.** `gh pr list --author "app/dependabot" --state open --json number,title,mergeable,statusCheckRollup,labels`. If the user says "starting from #N" ("начиная с #N"), include only PRs ≥ N.

2. **Assess each PR:** prod vs dev dependency; semver jump (patch/minor/major); CI status; does it fix a security advisory (check `gh pr view N` body / release notes / changelog); merge conflicts; part of a Dependabot group?

   **For a major, check each breaking change against this repo.** List the breaking changes from the release notes in the PR body, then check every one against how the repo actually uses the dependency — its imports, config, workflow inputs and triggers. A breaking change in a feature the repo never touches is not a risk to it.

3. **Categorize:**
   - **Category 1 — must merge:** security fixes; green-CI patches; dev-dependency patches/minors.
   - **Category 2 — low risk:** minors with notable changelog entries, and majors with green CI where none of the breaking changes touches this repo's usage — merge after a stated review note naming each breaking change and why it doesn't apply.
   - **Category 3 — risky:** majors with a breaking change that does touch this repo's usage, or failures requiring migration work; leave open with a recommendation.
   - **Category 4 — close:** upgrades the team will do manually (planned migrations) or superseded PRs.

4. **Present a table:** PR #, dependency, bump, prod/dev, CI, category, one-line risk note, intended action.

5. **Approval gate.** If the user's request already authorizes actions ("смерджи категорию 1", "закрывай сразу"), proceed after presenting the table. Otherwise STOP and ask which categories to merge/close.

6. **Execute:**
   - **Merge:** `gh pr merge N --squash --delete-branch`. If it fails because the branch is behind or the merge queue rejects it: comment `@dependabot rebase`, wait for CI, retry the merge once.
   - **CI fails after rebase on a Category 1–2 PR:** diagnose and push the fix to the PR branch — fix in the PR, don't abandon it. Once anyone else has pushed to it, Dependabot stops rebasing that PR, and `@dependabot recreate` would discard the fix; say so in the report.
   - **Close:** comment with a short reason ending with `@dependabot ignore this major version` (or `@dependabot ignore this dependency` to silence it entirely). Dependabot closes the PR itself — verify with `gh pr view N --json state`; `gh pr close N` only as fallback.

7. **Report:** merged / closed / left open, with reasons. If the same majors keep returning, suggest `ignore` rules in `.github/dependabot.yml` as the durable fix.

## Common mistakes

- Closing without the `@dependabot ignore ...` comment — the PR reappears on the next release.
- `gh pr merge --admin` to bypass branch protection — never; report the blocker instead.
- Treating one PR from a Dependabot group individually — rebase/merge decisions apply to the whole group PR.
- Merging Category 2 without stating the review note first.
- Filing a major under Category 3 for its semver jump alone, without checking its breaking changes against the repo.

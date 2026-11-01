---
name: dependabot-triage
description: Use when asked to triage, categorize, review, merge, or clean up Dependabot pull requests in a repository (e.g. "проверь пулл реквесты dependabot", "разбей на категории", "check dependabot PRs"), when a repo has accumulated open Dependabot PRs, or when asked what Dependabot alerts, malware alerts or vulnerable published releases still need handling and what has to be released.
---

# Dependabot Triage

## Overview

One run covers four sources: malware alerts, open Dependabot PRs, Dependabot alerts that have no PR, and the published release itself (the repository's own audit gate run at the newest release tag). It categorizes PRs, merges the safe ones, closes the unwanted ones in a way that stops Dependabot from re-proposing them, and ends with a release table: what has to be released, in which order. Works in any repo via `gh`; every repo-specific fact comes from the repository being triaged.

## Procedure

1. **Read the repository's policy.** Follow [references/repo-policy.md](references/repo-policy.md): audit gate, allowlist, sensitive packages, release age, release chain. Print the Policy summary ([Policy summary](references/repo-policy.md#policy-summary)) before any table.

2. **Gather.**
   - PRs: `gh pr list --author "app/dependabot" --state open --json number,title,mergeable,statusCheckRollup,labels`. If the user says "starting from #N" ("начиная с #N"), include only PRs ≥ N.
   - Alerts, including malware: [Gathering alerts](references/alerts-and-releases.md#gathering-alerts).
   - The published release: run the gate at the newest release tag as in [Published release](references/alerts-and-releases.md#published-release).

3. **Assess each PR:** prod vs dev dependency; semver jump (patch/minor/major); CI status; does it fix a security advisory (check `gh pr view N` body / release notes / changelog); merge conflicts; part of a Dependabot group?

   **Reach.** Take prod vs dev from the gate: print `reach: runtime` or `reach: dev` in the PR and alert rows. When the gate is unavailable print `reach: unverified (scope label: …)`; Dependabot's `scope` label is a hint, never proof.

   **Alerts.** Match each open alert to a PR as in [Matching alerts to PRs](references/alerts-and-releases.md#matching-alerts-to-prs); a matched alert is folded into the PR's row. The rest are handled per [Alerts without a PR](references/alerts-and-releases.md#alerts-without-a-pr), malware per [Malware](references/alerts-and-releases.md#malware).

   **For a major, check each breaking change against this repo.** List the breaking changes from the release notes in the PR body, then check every one against how the repo actually uses the dependency — its imports, config, workflow inputs and triggers. A breaking change in a feature the repo never touches is not a risk to it.

4. **Categorize:**
   - **Category 1 — must merge:** security fixes; green-CI patches; dev-dependency patches/minors. Two exclusions: a security PR on a package matching a sensitive pattern from the policy is Category 2 at most, and the review note names the policy reason; a security PR whose target version was published fewer days ago than the policy's release age is Category 2 at most, with the note `published N days ago, policy M days` (publish date unavailable: the note says so, still Category 2).
   - **Category 2 — low risk:** minors with notable changelog entries, and majors with green CI where none of the breaking changes touches this repo's usage — merge after a stated review note naming each breaking change and why it doesn't apply.
   - **Category 3 — risky:** majors with a breaking change that does touch this repo's usage, or failures requiring migration work; leave open with a recommendation.
   - **Category 4 — close:** upgrades the team will do manually (planned migrations) or superseded PRs.

5. **Present** the sections in this order; an empty section says `none`:
   1. Policy summary.
   2. Malware (or `Malware: none`).
   3. Pull requests: PR #, dependency, bump, reach, CI, category, one-line risk note, intended action.
   4. Alerts without a PR: alert #, package, severity, reach, fixed version, action, reason.
   5. Releases: the [Release table](references/alerts-and-releases.md#release-table).

   **Approval gate.** Every write waits for it: merges, closes, override PRs, allowlist edits, alert dismissals, malware actions. Malware is asked for separately, first. If the user's request already authorizes actions ("смерджи категорию 1", "закрывай сразу"), proceed after presenting the tables, for the rows it covers. Otherwise STOP and ask which rows and categories to act on. Reading, listing and running the gate in a detached worktree need no approval.

6. **Execute** only the approved rows; the rest are listed under "left open".
   - **Malware:** the action from [Malware](references/alerts-and-releases.md#malware), before anything else.
   - **Merge:** `gh pr merge N --squash --delete-branch`. If it fails because the branch is behind or the merge queue rejects it: comment `@dependabot rebase`, wait for CI, retry the merge once.
   - **CI fails after rebase on a Category 1–2 PR:** diagnose and push the fix to the PR branch — fix in the PR, don't abandon it. Once anyone else has pushed to it, Dependabot stops rebasing that PR, and `@dependabot recreate` would discard the fix; say so in the report.
   - **Close:** comment with a short reason ending with `@dependabot ignore this major version` (or `@dependabot ignore this dependency` to silence it entirely). Dependabot closes the PR itself — verify with `gh pr view N --json state`; `gh pr close N` only as fallback.
   - **Override PR, allowlist entry, dismissal:** as in [Alerts without a PR](references/alerts-and-releases.md#alerts-without-a-pr), on a new branch and PR.

7. **Report:** merged / closed / left open, with reasons, then the release table as the last section; with no releases detected, one line saying so. If the same majors keep returning, suggest `ignore` rules in `.github/dependabot.yml` as the durable fix. The skill never cuts the release: it reports what has to be released and in which order, and the user does the rest.

## Common mistakes

- Closing without the `@dependabot ignore ...` comment — the PR reappears on the next release.
- `gh pr merge --admin` to bypass branch protection — never; report the blocker instead.
- Treating one PR from a Dependabot group individually — rebase/merge decisions apply to the whole group PR.
- Merging Category 2 without stating the review note first.
- Filing a major under Category 3 for its semver jump alone, without checking its breaking changes against the repo.
- Publishing the advisories of an already released version in an issue, comment or log — it points at users who have not upgraded.
- Dismissing an alert on Dependabot's `scope` label alone.
- Treating "merged" as "fixed for users": a bundled library reaches users only through a release.
- Upgrading on a malware alert — remove or roll back instead.
- Putting a security PR on a sensitive package in Category 1.

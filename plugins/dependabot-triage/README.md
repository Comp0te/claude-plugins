# dependabot-triage

Triages a repository's Dependabot surface in one run: malware alerts, open Dependabot pull
requests, Dependabot alerts that have no pull request, and the published release itself. It sorts
each PR into a risk category, shows a table, and after approval merges the safe ones and closes the
unwanted ones with an `@dependabot ignore ...` comment, so they aren't proposed again. It ends with
a release table: what has to be released, in which order. It never cuts a release itself.

A major version is judged by what breaks for this repository, not by the version jump: each
breaking change in the release notes is checked against how the repository actually uses the
dependency. A green major whose breaking changes touch nothing the repository uses is low risk.

## Usage

```
/dependabot-triage:dependabot-triage
```

Or ask in plain words — "check the Dependabot PRs", "проверь пулл реквесты dependabot". Add
"starting from #N" to skip older PRs, or say up front what to do ("merge category 1") to skip
the approval stop.

| Category | What goes there | Action |
| --- | --- | --- |
| 1 — must merge | Security fixes, green-CI patches, dev-dependency patches and minors | Merge |
| 2 — low risk | Minors with notable changelog entries; green majors whose breaking changes don't touch this repository | Merge after a stated review note |
| 3 — risky | Majors with a breaking change this repository hits; failures needing migration work | Leave open with a recommendation |
| 4 — close | Upgrades done manually as a planned migration; superseded PRs | Close with `@dependabot ignore` |

It never bypasses branch protection with `gh pr merge --admin`; a blocked merge is reported
instead.

## Alerts, malware and release audits

- **Malware alerts** are listed and handled before anything else in the run.
- **Alerts without a PR** are matched against the open PRs; for the rest the skill proposes an
  action, such as an override PR, an allowlist entry or a dismissal.
- **The published release** is audited by running the repository's own audit gate at the newest
  release tag in a detached worktree, so a vulnerable dependency already shipped is not missed.
- The repository's audit command, allowlist, update policy and release chain are discovered from
  the repository itself (CI workflows, `dependabot.yml`, package manager config, `CLAUDE.md`,
  README), not configured in the plugin.

Every write (merge, close, override PR, allowlist entry, alert dismissal) waits for your approval.

## Requirements

The [GitHub CLI](https://cli.github.com/) (`gh`), authenticated with rights to merge and comment
on pull requests in the repository. The token also needs read access to Dependabot alerts, and
write access to dismiss them.

## Installing

```bash
claude plugin marketplace add Comp0te/claude-plugins
claude plugin install dependabot-triage@compote --scope user
```

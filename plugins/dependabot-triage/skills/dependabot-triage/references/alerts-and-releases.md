# Alerts, malware and published releases

Sources beyond open Dependabot PRs. The gate, allowlist, release chain and policy summary come from [repo-policy.md](repo-policy.md); read them first.

## Gathering alerts

```bash
gh api "repos/{owner}/{repo}/dependabot/alerts?state=open&per_page=100" --paginate
gh api "repos/{owner}/{repo}/dependabot/alerts?state=open&classification=malware&per_page=100" --paginate
gh api "repos/{owner}/{repo}/dependabot/alerts?state=fixed&per_page=100" --paginate
```

Fields used: `number`, `dependency.package.{ecosystem,name}`, `dependency.{scope,relationship,manifest_path}`, `security_advisory.{ghsa_id,severity,summary,classification}`, `security_vulnerability.first_patched_version.identifier`, `fixed_at`. `security_advisory.classification` is `general` or `malware`. Alerts with `state=fixed` feed [Release table](#release-table) only.

## Matching alerts to PRs

An open alert belongs to an open Dependabot PR when all three hold:

- the PR bumps the alert's package (`dependency.package.name`); a grouped PR lists each bumped package in its title or body, so check every one;
- the PR changes the alert's `dependency.manifest_path` or its lockfile (`gh pr view N --json files`) — the same package in another manifest is a different alert;
- the PR's target version is at or above `security_vulnerability.first_patched_version.identifier`.

Match on package and version, not on the advisory id: a grouped security PR body carries no GHSA id. A matched alert is folded into that PR's row and gets no row of its own. An alert with no match is handled under [Alerts without a PR](#alerts-without-a-pr). A malware alert is never matched to a PR.

## Alerts without a PR

Decide in this order. Each row's action is exactly one of the words below; caveats go in the reason column.

A gate finding on the default branch that has no alert and no PR gets a row here too, alert # `gate:<advisory id>`, decided by the same order. When it is the same package as an open alert and one action covers both, they share one row (`gate:<id>, #<n>`).

1. **`override`**: `first_patched_version` is set and the pin stays inside the declared range of every parent that requires the package. Read the ranges from the lockfile — for npm with the command below, for yarn and pnpm by searching the lockfile for `<pkg>@` entries' parents. Raising an existing resolution within the major it already forces counts as inside. When the patched version already satisfies every range, the action is still `override`, and the reason says a lockfile refresh (`yarn up -R <pkg>`, `npm update <pkg>`) is enough. When it would cross one, the action is `wait`: check `npm view <parent>@latest dependencies.<pkg>` and name that parent version if it carries the fix, otherwise write `no <parent> release carries it yet`.

   ```bash
   jq -r '.packages | to_entries[] | select(((.value.dependencies//{})+(.value.peerDependencies//{})) | has("<pkg>")) | "\(.key) \(.value.version) \(((.value.dependencies//{})+(.value.peerDependencies//{}))["<pkg>"])"' <dir>/package-lock.json
   ```

    Once approved, on a new branch, pin the package through the manager's override field, refresh the lockfile, run the gate and the tests, then open a PR; if the gate or the tests fail, do not open it, and report the row as `wait` naming the failure.

   | Manager | Override field | Lockfile refresh |
   | ------- | -------------- | ---------------- |
   | npm | `overrides` | `npm install --package-lock-only` |
   | yarn | `resolutions` | `yarn install --mode=update-lockfile` (Berry), `yarn install` (classic) |
   | pnpm | `pnpm.overrides` | `pnpm install --lockfile-only` |

2. **`accept`**: `first_patched_version` is null and the package is not reachable at runtime, judged by the gate or by evidence in the code. A production-only audit of a manifest with no `dependencies` is not evidence; cite where that manifest's output goes instead (e.g. not in the package's `files`). When the gate reports the advisory and the repository has an allowlist, add it there in the id format the policy summary records, with the reason in a comment beside the entry (new branch and PR). Otherwise there is no entry to add — with `allowlist: none`, or a gate that never sees the advisory — and the dismissal alone records it. Then dismiss the alert:

   ```bash
   gh api -X PATCH "repos/{owner}/{repo}/dependabot/alerts/<n>" \
     -f state=dismissed -f dismissed_reason=tolerable_risk \
     -f dismissed_comment="<≤280 chars: why it does not reach users; re-open when …>"
   ```

   `dismissed_reason` is one of `fix_started`, `inaccurate`, `no_bandwidth`, `not_used`, `tolerable_risk`. The comment is at most 280 characters (the API limit): when the reason is longer, shorten it, keeping the reason and the condition to re-open.

   `not_used` is allowed only when the gate does not report the advisory, and the comment cites the gate command. With `gate: none` or a gate that could not run, never use `not_used` or `inaccurate`; Dependabot's `scope` label alone does not justify either.
3. **`wait`**: otherwise. With no fix, the row says "no upstream fix".

Dismissals and allowlist edits are writes: they wait for the approval gate.

## Malware

Malware alerts (`classification=malware`) are listed first, in their own section, before every other row.

1. Read the malicious version range from the advisory.
2. Check whether the lockfile resolves the package into that range.
3. Action `remove` when the package is unused or replaceable, otherwise `rollback to <version published before the malicious one>` (see `npm view <pkg> time --json`). Never an upgrade.
4. Add a line to the report: rotate any secret that was present where the package was installed.

## Published release

The release users run can carry advisories the default branch has already fixed. Skip this section when the policy summary says `releases: not detected`; print `releases: not detected` and omit release rows.

1. Take the newest release tag from the policy summary.
2. Run the repository's gate exactly as CI runs it, in a detached worktree of that tag, as in [repo-policy.md](repo-policy.md#audit-gate-and-allowlist). Its findings list what users run. Every finding gets a row, dev-only ones included, with its reach in the row's note. With `gate: none` or a gate that cannot run, print `release audit: unverified`.
3. Run the same gate on the default branch. It decides `fixed on default`.

| Gate at tag T | Gate on default | Row |
| ------------- | --------------- | --- |
| reports X | does not | `fixed on default: yes`, action `release` |
| reports X | reports X | `fixed on default: no`; X goes to the PR and alert tables first, and the release row says action `fix first` |

Alerts with `state=fixed` whose `fixed_at` is after the commit date of the newest release tag are fixed since the last release: one release row per package, action `release`.

```bash
gh api "repos/{owner}/{repo}/commits/<tag>" --jq .commit.committer.date
```

Never write these findings anywhere public: no issue, PR body, comment or commit message that lists advisories affecting a released version, and in a public repository not a workflow log or run status either. They stay in the session's report. This skill never creates a tag, a release or a release branch, and never publishes.

## Release table

```text
| Package / advisory | Fixed on default | In newest release (<tag>) | Action | Downstream |
```

One row per package and `fixed on default` value, never a combined row for several packages. The first cell lists the package, its advisory ids and its alert numbers; alerts fixed since the tag join the gate row of the same package — list every one. Count findings by advisory, not by alert. `In newest release` holds the version the tag resolves, or `no`.

Release actions are exactly `release` and `fix first`. `Downstream` comes from the policy summary's `bundled` and `consumers` fields:

- a dev-only finding: `none — not shipped`;
- `bundled: yes`: `release this package, then bump in: <consumers in order>`;
- `bundled: mixed`: as for `yes` when the package is reachable from the inlining bundle's entry; otherwise as for `no`, and the note names which bundle reaches it;
- `bundled: no`, and the fix carried only by this repository's override field (consumers do not inherit it) or a transitive fix already inside its parent's declared range: `refresh in: <consumers>` — a lockfile refresh there, independent of a release of this package; when this package's own declared range must change: `release this package, then bump in: <consumers>`;
- `bundled: n/a`: `none`.

With `consumers: not documented — ask` that text stands in for `<consumers>`. When every row reads `none — not shipped` or `refresh in:`, say in one line above the table that the release only clears the gate at the tag.

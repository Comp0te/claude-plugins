# Repository policy discovery

Every repo-specific fact the triage depends on is read from the repository being triaged, never assumed. Read policy files at the default branch, not from the working copy, which may be on a feature branch: `git show origin/<default branch>:<path>` reads a file and, given a directory, lists it; `git grep -n -E '<pattern>' origin/<default branch> -- .github/workflows/` searches the workflows; `git branch -r --list 'origin/release/*'` lists release branches. Read the facts below once, before triaging, and print them as the [policy summary](#policy-summary).

Every command this skill gives is one line, run as its own command from the repository root with literal paths: no shell variables, `( … )` subshells, `&&` or `;` chains, loops or `git -C`, which permission rules cannot match. A pipe into `jq`, `sort` or `tail` within the line is fine.

## Audit gate and allowlist

The gate is the command the repository's CI uses to fail on vulnerable dependencies.

1. **Find the step.** Search `.github/workflows/*.yml` for steps whose `run:` contains `audit`: `npm audit`, `yarn npm audit`, `pnpm audit`, or a script wrapping one. Record the exact command with its flags (`--omit=dev`, `--severity`, `--environment`, ...).
2. **Follow a wrapper.** If the step runs `npm run <script>` (or `yarn <script>`, `pnpm <script>`), open the script in `package.json` and, if it calls a file, that file. Record the script name, the audit it runs, its severity filter and the allowlist it reads (a JSON/YAML file, an ignore list inside the script). If the script cannot be read, print `gate: <command>, allowlist: unknown`.
3. **Find the allowlist** in the package-manager config when the gate itself has none:
   - `.yarnrc.yml` key `npmAuditIgnoreAdvisories`
   - `.npmrc` or an `audit-ci` style config (`audit-ci.json`, `.audit-ci.json`, `audit-ci.jsonc`) with its allowlist key
   Record the file and key. Record the id format it expects (numeric npm advisory id vs GHSA id) when a comment in the file or the tool's documentation says so; otherwise `unknown`.
4. **No audit step in CI** means `gate: none`. Runtime reach then falls back to Dependabot's `scope` label and every row decided by it says `reach: unverified`.
5. **Run the gate in a detached worktree**, never in the user's working copy. If the gate needs an installed `node_modules`, do not install: fall back to the scope label and mark `reach: unverified`. Use the path `mktemp` printed:

```bash
git fetch -q origin
mktemp -d
git worktree add -q --detach <path> origin/<default branch>
yarn --cwd <path> npm audit …    # the gate command with its directory flag: npm --prefix <path> audit …, pnpm --dir <path> audit …
git worktree remove --force <path>
```

   A wrapper gate runs as `npm --prefix <path> run <script>` (`yarn --cwd`, `pnpm --dir`). If that is refused, run the audit it wraps with the directory flag, apply its allowlist and severity filter by hand, and print `gate: reproduced (<why>)`. Prefer the directory flag over `cd <path>`, which leaves later commands inside the worktree. Before the report, run `git worktree list`: remove any worktree this run added that is still listed, or name it if removal is refused. Never remove a worktree the run did not add.
6. **Reach** needs a second, read-only run of the same audit: production dependencies only (`--environment production` for yarn, `--omit=dev` for npm, `--prod` for pnpm) and without the gate's severity filter, so every alert's package is covered. Run it at each ref whose rows need reach — the default branch for PR and alert rows, the newest tag for release rows — and once per directory holding a `manifest_path` that has alerts, pointing the directory flag there; a manifest the CI gate does not cover says so in the reason. For a package with an advisory, one it reports is `runtime`, one it does not report is `dev`, one the allowlist hides from it is `unverified`. A package with no advisory (most PR packages) takes reach from the lockfile's dependency chain — `npm ls --omit=dev --package-lock-only <pkg>` for npm — and the row says so. This audit only classifies: an advisory only it reports gets no row, only a `not gated:` line under Alerts without a PR when it is runtime.

Running the gate is read-only and needs no approval. Editing the allowlist is a write: it goes on a new branch and a PR, after the approval gate.

## Update policy

Packages the repository handles specially, and how fresh a release must be.

1. **Sensitive packages.** Read `.github/dependabot.yml` for `exclude-patterns` and `ignore` entries. Take the comment next to each as its reason; a comment above consecutive entries of one list is the reason for each of them, up to the next comment. List each pattern with its reason; a pattern with no comment is listed with `reason: not stated`. A security PR touching such a package cannot be Category 1.
2. **Release-age policy.** Look in these places and convert each to days:
   - `cooldown` in `.github/dependabot.yml`
   - `min-release-age` in `.npmrc`
   - `npmMinimalAgeGate` in `.yarnrc.yml`
   - `minimumReleaseAge` in the pnpm config (`pnpm-workspace.yaml` or `.npmrc`)

   Print the age in days with its source. `cooldown` values per bump type (`semver-major-days`, `semver-minor-days`, `semver-patch-days`, `default-days`) are not a conflict: print each, and compare a version against the value for its bump type. Other conflicting values: list all of them and use the largest. None found, or only `0`, means `release age: none`.
3. **Publish date of a version**, to compare against the age:

```bash
npm view <pkg> time --json | jq -r '."<version>"'
```

## Release chain

How a fix reaches users of this repository, and in what order.

1. **Release triggers.** Search `.github/workflows/*.yml` for `on: push: tags`, `on: release`, and for release branches (`release/*`, `releases/*`) in `branches:` filters. Record the tag pattern. No release mechanism found means `releases: not detected`.
2. **Newest release tag**, sorted by version:

```bash
gh api "repos/{owner}/{repo}/git/matching-refs/tags/" --paginate --jq '.[].ref' | sed 's#refs/tags/##' | sort -V | tail -1
```

   Restrict the list to tags that match the recorded pattern before taking the newest.
3. **Bundled library.** Open `package.json` and read `exports`, `browser` and `main`. If they point at a built bundle, read the bundler config (`rollup`, `webpack`, `vite`, `tsup`, `esbuild`) for `externals` / `external`. A bundle with no externals for its dependencies ships them inlined: a fix reaches consumers only through a new release of this package, followed by a bump in each consumer. Print `bundled: yes`; `mixed` when one bundle inlines and another externalizes; `no` for a library whose dependencies stay external or that ships source; `n/a` when the repository is not a library; `unknown` when the config cannot be read.
4. **Consumers.** Read the README and `CLAUDE.md` for downstream repositories or packages. List them in the order a fix must travel; named without an order, list them followed by `(order not stated)`. Not named means `consumers: not documented — ask`; for a repository that is not a library, `n/a`.

The skill only reports what has to be released and in which order. It never creates a tag, a release or a release branch, and never publishes.

## Policy summary

Print this block before triaging, one line per field. A field it could not determine takes its fallback value, never a guess.

```text
Policy summary
  gate:        <exact command | reproduced (<why>) | none>
  allowlist:   <file and key | none | unknown>   (id format: <numeric npm | GHSA | unknown>)
  sensitive:   <pattern — reason>, ...  | none
  release age: <N days (source)> | none
  releases:    <tag pattern, newest tag> | not detected
  bundled:     yes | mixed | no | n/a | unknown
  consumers:   <in order> | <names> (order not stated) | not documented — ask | n/a
```

Fallbacks:

- `gate:` `none` when no CI step audits dependencies. A script that cannot be read prints `gate: <command>, allowlist: unknown`.
- `allowlist:` `none` when the gate has no allowlist; `unknown` when the script is unreadable. `id format:` `unknown` unless a comment or the tool says.
- `sensitive:` `none` when `dependabot.yml` has no `exclude-patterns` or `ignore`; a pattern without a comment prints `<pattern — reason: not stated>`.
- `release age:` `none` when no source sets one; per-bump-type `cooldown` values print each; other conflicting values print all, the largest decides.
- `releases:` `not detected` when no tag, release or release-branch mechanism exists.
- `bundled:` `unknown` when the bundler config cannot be read.
- `consumers:` `not documented — ask` when the README and `CLAUDE.md` name none; `n/a` when the repository is not a library.

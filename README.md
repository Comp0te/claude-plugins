# compote

Personal Claude Code plugins: a pull-request and branch review flow, and a spec-driven
development toolkit.

## Plugins

- **review-flow** — read-only review of a GitHub pull request or the current branch.
  Dispatches focused reviewer agents matched to the diff, verifies every finding against the
  source before it is reported, and publishes an approved subset as inline PR comments.
  Requires the GitHub CLI (`gh`), authenticated.
- **pr-tickets** — triages the findings a review deliberately left unposted (pre-existing
  problems and deferred work) and turns the ones worth tracking into Jira issues, after
  verifying each against the base branch. Requires `review-flow` to be installed, Jira tooling
  that exposes issue creation, and a `.claude/pr-tickets.json` file committed in the consuming
  repository describing that repository's Jira conventions.
- **rn-performance-reviewer** — a React Native performance reviewer for the review flow.
  Reports statically-provable defects in lists, effects and subscriptions, animations, Skia
  usage, memoization, bundle size and image rendering, and never speculative optimization
  advice. Install it only in React Native repositories.

## Installing

```bash
claude plugin marketplace add <owner>/<repo>

claude plugin install review-flow@compote --scope user
claude plugin install pr-tickets@compote --scope user   # optional; needs review-flow and Jira tooling
```

Install the performance reviewer per repository rather than at user scope — at user scope it
joins the reviewer roster of every project, including the ones its triggers can never match:

```bash
cd <a React Native repository>
claude plugin install rn-performance-reviewer@compote --scope project
```

## Command names

Commands resolve under their plugin's prefix, and only under it:

```
/review-flow:pr-review     /review-flow:branch-review
/review-flow:pr-publish    /review-flow:pr-recheck
/pr-tickets:jira
```

## Updating

Installing copies the plugin into `~/.claude/plugins/cache/compote/<name>/<version>/`. It is
not a live reference to this repository, and **the cache is keyed by version** — so editing a
plugin without bumping `version` in its `plugin.json` leaves every installed session running
the old copy. Neither `marketplace update` nor a repeated `install` refreshes it: both see
that version already present and do nothing, silently.

So bump the version whenever the content changes. That is what the cache key is for, and it is
also what makes `claude plugin tag` meaningful:

```bash
# edit plugins/<name>/... , then raise "version" in its plugin.json and the marketplace entry
claude plugin marketplace update compote
claude plugin install <name>@compote --scope user
```

To pick up a same-version edit during development, force it — there is no other way:

```bash
claude plugin uninstall <name>
claude plugin install <name>@compote --scope user
```

## Repository-local reviewers

The review commands select reviewer agents dynamically from whatever the session offers.
Reviewer agents defined locally in a consuming repository (its own `.claude/agents/`) are
picked up automatically alongside the ones this marketplace ships — no registration needed.

## Write your own security reviewer

`review-flow` deliberately ships no security agent, and both commands treat Claude Code's
built-in `security-review` as a **fallback**: it runs only when the roster came up with no
security-oriented agent at all. Give a repository its own reviewer in `.claude/agents/` and
the built-in stops running there entirely.

That is not a stylistic preference. The built-in is a fixed prompt with a fixed diff, and two
of its properties work against a specific project:

- **It chooses its own diff.** The skill interpolates `git diff origin/HEAD...` in the
  session's working directory and takes no scope argument, so it reviews whatever those two
  happen to point at. When they point at the wrong thing it does not fail — it reports
  confident findings about code that is not under review. An agent reads the tree you name and
  the diff you hand it.
- **Its exclusions encode a server-side threat model.** It will not report a missing
  permission or authentication check in client-side JS/TS, on the stated grounds that the
  backend validates everything. In a browser extension, a CLI, or any app whose trust boundary
  *is* the client, that rules out the most important class of finding there is. It also
  declines prototype pollution unless confidence is extremely high, treats React and Angular as
  categorically XSS-safe, and excludes anything it reads as resource exhaustion.

A reviewer you write yourself carries your project's boundaries instead: which process is
trusted, which inputs cross a boundary, which of your own guards a finding must be checked
against. Measured over 18 runs in a repository that had both, the built-in was never the sole
finder of anything, while the repository's own agent was the single most productive reviewer
in the roster.

Nothing needs registering — write the agent with a `description` that declares when it
applies, and the dynamic selection will find it.

# review-flow

Read-only review of a GitHub pull request or the current branch. Each command dispatches
focused reviewer agents matched to the diff, runs the built-in passes in the main loop while
they work, verifies findings against the source, and produces one ranked report in chat.
Nothing is posted to a PR without explicit approval of the exact payload.

## Commands

| Command | What it does |
| --- | --- |
| `/review-flow:branch-review [base-branch]` | Pre-PR review of the current branch. Report-only — never modifies tracked files, never commits or pushes. |
| `/review-flow:pr-review <pr-number\|pr-url>` | Read-only review of a GitHub PR. Never posts anything. |
| `/review-flow:pr-publish <pr-number>` | Publishes a subset of a `pr-review`'s findings as inline PR comments. Re-verifies every finding not backed by an executed check against the PR's source, shows the exact payload, and posts only after approval. |
| `/review-flow:pr-recheck <pr-number>` | After the PR's author pushes in response to published comments: judges which findings the new commits closed, reviews the incremental diff, and updates the handoff. Separates the author's work from a base branch that moved underneath a stacked PR. Never posts anything. |

The usual order on a PR is `pr-review` → `pr-publish` → `pr-recheck`. What the review left
unposted — pre-existing problems and deferred work — is what
[`pr-tickets`](../pr-tickets/README.md) turns into Jira issues.

## Requirements

- The [GitHub CLI](https://cli.github.com/) (`gh`), authenticated for the repository under review:
  `brew install gh` (or see its install page), then `gh auth login`.
- `awk` — the PR commands use `scripts/hunk-map.awk` to map cited lines onto the PR's diff.

## Handoff files

The commands pass state through files under `.claude/reviews/` in the reviewed repository:

- `pr-<N>-findings.md` — every finding from `pr-review`, with what was posted and what the
  re-check concluded.
- `pr-<N>-deferred.md` — work the review deferred rather than reported against the PR.
- `branch-<slug>-<shortsha>.md` and `branch-<slug>-<shortsha>-deferred.md` — the same for
  `branch-review`.

Before the first write, a command adds `.claude/reviews/` to `.git/info/exclude` if git does not
already ignore it, so the handoffs never show up as changes to commit.

## The reviewer roster

The plugin ships these reviewers. Each command picks from the available agents by matching their
descriptions against the diff, within a number of slots that grows with the diff's size:

- `deletion-check` — reviews what the diff removed, and whether surviving comments and docs
  still describe the code. Kept context-free, so the author's account of why a removal was safe
  cannot stand in for checking that it was.
- `pr-test-analyzer` — behavioral test coverage of the diff.
- `silent-failure-hunter` — error handling that can hide a failure.
- `type-design-analyzer` — new or reshaped types, judged on whether illegal states are
  unrepresentable.

It also ships three helpers the commands dispatch themselves: `finding-gate-verifier`,
`fix-verifier` and `anchor-resolver`.

### Why it fans out

Anthropic's guidance is to keep work in one agent loop when its steps need shared context, and
split it across agents only when they don't. A review falls on the second side on purpose: each
reviewer judges the diff without the implementer's framing, which is what makes a second look
worth running.

### Adding your own reviewers

Selection is dynamic: the commands match each available agent's `description` against the
diff, not by name. A reviewer defined in a repository's own `.claude/agents/`, or shipped by
another plugin such as [`rn-performance-reviewer`](../rn-performance-reviewer/README.md), joins
the roster with nothing to register.

## Write your own security reviewer

`review-flow` deliberately ships no security agent, and both review commands treat Claude
Code's built-in `security-review` as a **fallback**: it runs only when the roster came up with
no security-oriented agent at all. Give a repository its own reviewer in `.claude/agents/` and
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

Write the agent with a `description` that declares when it applies, and the dynamic selection
will find it.

## Installing

```bash
claude plugin marketplace add Comp0te/claude-plugins
claude plugin install review-flow@compote --scope user
```

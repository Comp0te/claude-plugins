# compote

Claude Code plugins for a spec-driven development loop: write a plan and execute it task by
task, review a branch or a pull request with focused reviewer agents, and close the two open
ends of that loop — reading a design into a spec, and verifying a change in the running
application.

## Plugins

- **[plan-flow](plugins/plan-flow/README.md)** — writes implementation plans with a frozen
  intent, a tested edge-case matrix and an annotated code map, then executes them task by task,
  each in a context scoped to that one task. Ships working agreements for how code is written,
  delivered through a one-line import you add to `~/.claude/CLAUDE.md` by hand.
- **[review-flow](plugins/review-flow/README.md)** — read-only review of a GitHub pull request
  or the current branch. Dispatches focused reviewer agents matched to the diff, verifies every
  finding against the source before it is reported, and publishes an approved subset as inline
  PR comments. Requires the GitHub CLI (`gh`), authenticated.
- **[pr-tickets](plugins/pr-tickets/README.md)** — triages the findings a review deliberately
  left unposted (pre-existing problems and deferred work) and turns the ones worth tracking into
  Jira issues, after verifying each against the base branch. Requires `review-flow`, Jira
  tooling that exposes issue creation, and a `.claude/pr-tickets.json` in the consuming
  repository.
- **[rn-performance-reviewer](plugins/rn-performance-reviewer/README.md)** — a React Native
  performance reviewer for `review-flow`. Reports statically-provable defects in lists, effects
  and subscriptions, animations, Skia usage, memoization, bundle size and image rendering, and
  never speculative optimization advice.
- **[figma-flow](plugins/figma-flow/README.md)** — reads a Figma node and returns a compact spec
  in the project's own code vocabulary — tokens, components and icons from the project's
  design-mapping document — instead of dumping raw design-tool output into the caller's context.
  Also downloads and verifies image and vector assets. Needs the Figma plugin and a
  `.claude/docs/figma-mapping.md` in the consuming repository.
- **[ui-verifier-mobile](plugins/ui-verifier-mobile/README.md)** — verifies UI changes in a
  running React Native app against a caller-supplied checklist: drives the simulator or emulator
  with `agent-device`, measures what it sees, captures screenshots, and returns a pass/fail
  report with evidence. Never modifies code.
- **[ui-verifier-web](plugins/ui-verifier-web/README.md)** — the same for a web app or browser
  extension, driving the browser with `agent-browser`.

Both verifiers read a `.claude/docs/ui-verification.md` in the consuming repository for that
project's own facts — bundle ids, build and launch commands, auth routes, app traps — and say so
at the top of the report when it is absent.

## Installing

```bash
claude plugin marketplace add Comp0te/claude-plugins

claude plugin install plan-flow@compote --scope user
claude plugin install review-flow@compote --scope user
claude plugin install pr-tickets@compote --scope user   # optional; needs Jira tooling
```

`plan-flow` then needs one line added to `~/.claude/CLAUDE.md` — see
[its README](plugins/plan-flow/README.md#the-one-line-import-this-plugin-cannot-add-for-you).

Install the rest per repository, from inside it. At user scope the performance reviewer would
join the reviewer roster of every project, and both verifiers would load everywhere:

```bash
cd <a React Native repository>
claude plugin install rn-performance-reviewer@compote --scope project
claude plugin install ui-verifier-mobile@compote --scope project
claude plugin install figma-flow@compote --scope project

cd <a web repository>
claude plugin install ui-verifier-web@compote --scope project
```

## Command names

Commands resolve under their plugin's prefix, and only under it:

```
/plan-flow:execute-plan
/review-flow:pr-review     /review-flow:branch-review
/review-flow:pr-publish    /review-flow:pr-recheck
/pr-tickets:jira
```

## Updating

```bash
claude plugin marketplace update compote
claude plugin update <name>@compote --scope user
```

For a project-scope install, run the update from inside that repository with `--scope project`;
each such install is updated separately. Restart the session to pick up the new version.

## Developing

Installing copies a plugin into `~/.claude/plugins/cache/compote/<name>/<version>/`, and that
cache is keyed by version: an edit without a version bump never reaches an installed session.
Raise `version` in the plugin's `plugin.json` and in its `marketplace.json` entry whenever its
content changes.

To work against a local clone, add it as the marketplace instead of the GitHub repository:
`claude plugin marketplace add <path to your clone>`.

Text shared between commands and agents lives in `shared/` and is copied between
`<!-- shared:NAME -->` markers by `scripts/sync-shared.py` (`shared/blocks.json` maps each block to
its targets). Edit the source in `shared/`, never the copy, then run the sync. CI runs:

```bash
python3 scripts/sync-shared.py --check
python3 -m unittest discover -s tests/shared-blocks
python3 scripts/check-structure.py
python3 scripts/check-hunk-map.py
```

The model-graded evals and their costs are described in
[plugins/plan-flow/evals/README.md](plugins/plan-flow/evals/README.md) and
[tests/review-flow/reviewer-evals/README.md](tests/review-flow/reviewer-evals/README.md).

## License

MIT

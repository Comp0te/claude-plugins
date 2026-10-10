# plan-flow

Write implementation plans with an immutable intent, a tested edge-case matrix and an
annotated code map, then execute them task by task against that frozen contract, in a context
scoped to one task at a time.

## Installing

```bash
claude plugin marketplace add Comp0te/claude-plugins
claude plugin install plan-flow@compote --scope user
```

Then add the one import line described [below](#the-one-line-import-this-plugin-cannot-add-for-you)
to `~/.claude/CLAUDE.md`. Until you do, every session in a git repository opens with a setup
warning.

## Components

| Component | Path | What it does | Fires on |
| --- | --- | --- | --- |
| `writing-implementation-plans` skill | `skills/writing-implementation-plans/SKILL.md` | Turns a spec, a ticket, or an agreed approach into a written implementation plan with a frozen intent, tiered constraints, an annotated code map, and a tested edge-case matrix. | Description match — loads when the conversation is turning multi-step work into a plan before code is touched. |
| `plan-executor` agent | `agents/plan-executor.md` | Implements one scoped task (or step) of an already-approved plan: reads that task's frozen contract, writes the code, runs the project's checks, and reports back a diff summary. | Dispatch — given the plan path, a task's line range, and which steps are in scope. |
| `/execute-plan` command | `commands/execute-plan.md` | Runs an approved plan task by task, dispatching each task to a scoped `plan-executor` and reviewing the returned diff before moving to the next. | Explicit invocation: `/plan-flow:execute-plan <path-to-plan.md>`. |
| Working agreements | `references/working-agreements.md` | How code is written: when to ask before coding, comment rules, research before building, scope control, verifying work. | Imported into `~/.claude/CLAUDE.md` by the line below. |
| Session-start hook | `hooks/session-start.py` (registered in `hooks/hooks.json`) | Injects a short operating-rules block into the session and warns if the working-agreements import is missing, dangling or stale. When that import is delivering nothing at all, also injects the agreements verbatim, so an unconfigured install still has them in the main conversation. | `SessionStart` session event, matching `startup`, `clear`, or `compact`. |
| Comment-budget hook | `hooks/comment-budget.py` (registered in `hooks/hooks.json`) | Counts the comment block just written against the budget in the working agreements (2 prose lines inline, 4 in a docstring) and says so when it is over. Reads only what the edit added, so existing comments are never flagged. Silence it with `PLAN_FLOW_COMMENT_BUDGET=off`. | `PostToolUse`, matching `Edit`, `Write`, and `MultiEdit`. |
| Plan progress pane | `hooks/progress/` (registered under `modules` in `hooks/hooks.json`) | A side pane that follows a plan being executed: each task's status (pending, executing, review, committed, halted with its reason), the running executor's tool-call count and elapsed time, the attempt number on a re-dispatch, and each task's check results. It only observes — it adds nothing to any model's context and never delays a tool call. | Opens when you start executing a plan, or through `/plan-progress`. |

## Options

Set at install with `--config <key>=<value>`, or later with
`claude plugin configure plan-flow@compote --values-stdin`:

- `progressPane` — `auto` (default) opens the pane when you start executing a plan; `command`
  opens it only through `/plan-progress`; `off` turns the pane and its observation off.
- `progressCheckPattern` — a regular expression, matched against the program and subcommand words
  of each part of an executor shell command (not its file names, paths, flags or quoted
  arguments); a matching part is shown as a check in the pane, besides the task's own
  verification commands.

## Where plans live

Authored plans default to `docs/plans/` in the repository the plan is written for. This is a
default, not a requirement — say so once if your own convention differs, and that stated
preference overrides it.

## What the session hook does, and what it does not

The hook injects only what has to be true before any skill or agent loads — it is paid on every
session, in every repository, so it stays small. Everything else — the working agreements —
arrives through the import described next.

There is one exception, and it is the case where that import has not happened. If the import is
missing or points at nothing, the agreements are reaching the session from nowhere, so the hook
appends them verbatim after the warning. That costs context only for an install that would
otherwise have none, and it is verbatim because a paraphrase that fits a hook's budget loses
rules.

A **stale** import gets the warning alone. It is still delivering, and a second copy that differs
from the one already loaded is a worse failure than text that is merely old.

The fallback is not a substitute: it covers the main conversation, while a dispatched worker
reads the agreements only through the import. The warning stays until the line is added.

## The one-line import this plugin cannot add for you

There is no manifest field that lets a plugin write into `~/.claude/CLAUDE.md`, so this one line
has to be added by hand, once per machine. Add it to `~/.claude/CLAUDE.md`:

- If you installed this plugin from the **GitHub marketplace**, import the marketplace's own
  clone — its directory is named after the marketplace (`compote`), not this plugin, and carries
  no version in the path:

  ```
  @~/.claude/plugins/marketplaces/compote/plugins/plan-flow/references/working-agreements.md
  ```

- If you added the marketplace from a **local clone** of this repository, import the clone
  directly:

  ```
  @<path to your clone>/plugins/plan-flow/references/working-agreements.md
  ```

The import is what reaches dispatched workers: a `SessionStart` hook's injected context does
not, while an import in `~/.claude/CLAUDE.md` does. [docs/design-notes.md](docs/design-notes.md)
has the measurements behind that.

## Checking that the import worked

The hook's success signal is silence — no warning means the import is fine — so there is nothing
to see unless you ask. Run the hook directly from inside any git repository (it is a no-op
outside one) and pull out its verdict:

```bash
echo '{}' | python3 "<path to this plugin>/hooks/session-start.py" \
  | grep -o 'Setup warning[^"]*' || echo 'No setup warning: the import is healthy.'
```

It can report one of three problems:

- **No import line** — `~/.claude/CLAUDE.md` has no import for the working agreements at all. Add
  one of the two lines from the section above.
- **Import points at a missing file** — the path in the import line does not exist. Fix it to
  point at an existing copy of `references/working-agreements.md`.
- **Import is stale** — the imported file's contents differ from this installed copy. Refresh
  whichever side is out of date so the two match again.

## Development

```bash
python3 -m unittest discover -s plugins/plan-flow/hooks -p 'test_*.py'
python3 -m unittest discover -s plugins/plan-flow/evals -p 'test_*.py'
claude plugin test plugins/plan-flow
tsc -p plugins/plan-flow
```

The two `unittest` runs are stdlib only and take about a second: the first covers the
session-start and comment-budget hooks, the second the eval suite's own integrity, including
whether the copy of the Code Comments rule embedded in the `comment-rules` cases still matches
`references/working-agreements.md`. Edit that rule and the second run fails until you run
`python3 plugins/plan-flow/evals/sync-comment-rule.py --write` and re-measure the tier.

`claude plugin test` and `tsc` cover the progress pane. `tsc` needs the engine's declaration
files, which it writes into `plugins/plan-flow/.claude-plugin/types/` the first time the plugin
is loaded.

The model-graded tiers, what they cost and what they cannot see are in
[evals/README.md](evals/README.md). Why the plugin is shaped the way it is — and which obvious
simplifications were tried and are broken — is in [docs/design-notes.md](docs/design-notes.md).

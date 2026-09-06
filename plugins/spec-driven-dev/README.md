# spec-driven-dev

Write implementation plans with an immutable intent, a tested edge-case matrix and an
annotated code map, then execute them task by task against that frozen contract, in a context
scoped to one task at a time.

## What it contains

- A skill for writing implementation plans, with the plan template as a reference file so it is
  found by description matching rather than by an ambient memory file.
- An agent (and a command) for executing a plan one task at a time, scoped to that task's own
  frozen contract instead of the whole document.
- A `SessionStart` hook that injects a short operating-rules block into every session started
  inside a git repository.

## Components

| Component | Path | What it does | Fires on |
| --- | --- | --- | --- |
| `writing-implementation-plans` skill | `skills/writing-implementation-plans/SKILL.md` | Turns a spec, a ticket, or an agreed approach into a written implementation plan with a frozen intent, tiered constraints, an annotated code map, and a tested edge-case matrix. | Description match — loads when the conversation is turning multi-step work into a plan before code is touched. |
| `plan-executor` agent | `agents/plan-executor.md` | Implements one scoped task (or step) of an already-approved plan: reads that task's frozen contract, writes the code, runs the project's checks, and reports back a diff summary. | Dispatch — given the plan path, a task's line range, and which steps are in scope. |
| `/execute-plan` command | `commands/execute-plan.md` | Runs an approved plan task by task, dispatching each task to a scoped `plan-executor` and reviewing the returned diff before moving to the next. | Explicit `/execute-plan <path-to-plan.md>` invocation. |
| Session-start hook | `hooks/session-start.py` (registered in `hooks/hooks.json`) | Injects a short operating-rules block into the session and warns if the working-agreements import described below is missing or stale. | `SessionStart` session event, matching `startup`, `clear`, or `compact`. |

## Where plans live

Authored plans default to `docs/plans/` in the repository the plan is written for. This is a
default, not a requirement — say so once if your own convention differs, and that stated
preference overrides it.

## What the session hook does, and what it does not

The hook injects only what has to be true before any skill or agent loads — it is paid on every
session, in every repository, so it stays small. Everything else — the rest of this plugin's
operating rules — arrives a different way, described next.

## The one-line import this plugin cannot add for you

There is no manifest field that lets a plugin write into `~/.claude/CLAUDE.md`, so this one line
has to be added by hand, once per machine. Add it to `~/.claude/CLAUDE.md`:

- If you added this plugin's marketplace from a **local working copy** (e.g. you cloned this
  repository yourself and ran `claude plugin marketplace add ~/Projects/claude-plugins`), import
  the working copy directly:

  ```
  @~/Projects/claude-plugins/plugins/spec-driven-dev/references/working-agreements.md
  ```

- If you installed this plugin from the **remote marketplace**, import the marketplace's own
  clone instead — its directory is named after the marketplace manifest's `name` field
  (`compote`), not this plugin's name, and carries no version in the path:

  ```
  @~/.claude/plugins/marketplaces/compote/plugins/spec-driven-dev/references/working-agreements.md
  ```

The session hook checks for this import and says so if it is missing, because a `SessionStart`
hook's injected context does not reach a dispatched worker, while an import in
`~/.claude/CLAUDE.md` does.

## Installing

```bash
claude plugin marketplace add ~/Projects/claude-plugins
claude plugin install spec-driven-dev
```

---
description: Execute an approved implementation plan task by task, dispatching each task to a scoped executor and reviewing the returned diff between tasks.
argument-hint: <path-to-plan.md>
---

Execute the plan at `$ARGUMENTS`, one task at a time, by dispatching each task to a scoped
executor and reviewing what comes back before moving to the next.

## 0. Resolve the plan

- **No argument given:** do not guess. Look for plans in the repository's plan directory
  (`docs/plans/` by default — see the plan-writing skill for how a project can override this)
  and list what is there. A plan is either a `.md` file directly in that directory or a
  subdirectory containing `plan.md` — list both forms. Ask the user which one to run. Never
  pick one silently, even if only one is found.
- **The given path does not exist:** report the exact path you were given and stop. Do not
  reconstruct a plan from anything said earlier in this conversation — a remembered summary is
  not the frozen document, and executing against one is how a task ends up graded against a
  contract nobody actually approved.
- **The path exists:** if it is a directory, the plan is `plan.md` inside it, and the
  `references/` folder beside it holds whatever images the plan cites. A directory with no
  `plan.md` is the "does not exist" case above — report the exact path and stop. Otherwise
  continue below.

## 1. Read the plan's frozen header first

Read the `<frozen-after-approval>` Global Constraints block and the Decision points table, then
the task list. Do not read every task's body up front — each task's own section (its frozen
contract, Code Map, Files, Interfaces, Verification, and steps) is read only when that task is
dispatched, by the executor, not by you.

**If the plan has no frozen header** — it predates this format — execute it whole rather than by
slice: there is no frozen section to scope a dispatch's line range to, so hand the executor the
plan in full instead of a task number and a range.

## 2. Dispatch one task

Dispatch it to the `plan-executor` agent this plugin ships — a context scoped to one task, which
carries its own rules for executing against a frozen contract. If your tooling has no way to
dispatch a scoped worker, execute the task here instead and say so.

A dispatch carries exactly four things, and nothing else:

1. The plan path, with the task's number and its line range, so the executor reads its own
   section instead of the whole file.
2. Which steps are in scope for this dispatch.
3. What earlier tasks already put on disk, so it isn't redone.
4. Environment facts that are not in the plan — branch, sandbox quirks, deviations already
   approved.

**Never restate the plan's own header or the executor's own rules.** The executor already reads
the frozen header itself and already carries its own contract; a dispatch that repeats either is
how a dispatch ends up contradicting them by drifting out of sync with the source it copied from.

**A frozen contract the code cannot satisfy is not yours to dispatch.** Checking what is already
on disk is what surfaces this, before the executor ever runs. Writing what the contract names — a
missing export, an absent module — relieves the conflict as surely as editing the frozen text
would, and routing it through a stale Code Map note or into the dispatch does not make it someone
else's call. Stop and bring it to the plan's author.

## 3. Handle what comes back

- **The returned diff has a defect:** send a fresh dispatch naming the defect precisely. Fix it
  in this conversation only when it is a one-line typo — a supervising turn costs several times
  an executor turn, and re-dispatching is also what keeps the plan, the code and the report in
  one voice.
- **The report quotes gate output (typecheck/lint/test):** read it, but do not re-run those
  gates. Run the project's full gate once, at the end of the feature, not after every task.
- **Review the diff, not the tree.** The returned report plus `git diff` is the review surface;
  re-read a file only when the diff cannot answer the question.
- **The executor halts on a frozen-section conflict:** that is not yours to resolve. Bring it to
  the plan's author. The frozen block exists precisely so this friction cannot be relieved by
  editing the target.
- **The report notes a size overrun** — materially more than about 40 tool-using turns or 120k
  tokens of context for the task (see the plan-writing skill's *Task size* reference for where
  this ceiling comes from) — record it in the run's summary. It is a planning defect worth
  noting even when the code came out fine.

## 4. Batch what doesn't depend on itself

Where the plan's `Interfaces` blocks show that two tasks do not feed each other, dispatch both
before reviewing either.

## 5. Commit here, not in the dispatch

The executor does not commit. Once a task's diff is reviewed and accepted, make the commit in
this conversation, from the exact paths and message the executor's report gave you, then move to
the next task.

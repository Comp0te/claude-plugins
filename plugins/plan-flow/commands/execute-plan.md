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
  subdirectory containing `plan.md` — list both forms.
  Leave out its `archive/` subdirectory: that is where finished plans go (section 6). Ask the
  user which one to run. Never pick one silently, even if only one is found.
- **The given path does not exist:** report the exact path you were given and stop. Do not
  reconstruct a plan from anything said earlier in this conversation — a remembered summary is
  not the frozen document, and executing against one is how a task ends up graded against a
  contract nobody actually approved.
- **The path exists:** if it is a directory, the plan is `plan.md` inside it, and the
  `references/` folder beside it holds whatever images the plan cites. A directory with no
  `plan.md` is the "does not exist" case above — report the exact path and stop. Otherwise
  continue below.

## 0b. Find where the run stands

Before the first dispatch — and again whenever this conversation was compacted or resumed — work
out which tasks are already done from what is on disk, not from memory of the run. A task is done
when every step checkbox in its section is ticked and `git log` on this branch has a commit
touching its files. Done tasks are never dispatched again; start from the first task that is not.
When the two disagree — ticks without a commit, a commit without ticks, or uncommitted changes in
a task's files — stop and ask the user which state is true.

## 0c. Settle the run before the first dispatch

Read the frozen header and the Decision points now, and bring everything predictable to the
user in one message before any task is dispatched — never one question at a time as tasks reach
it:

- **Every Decision points row not marked DECIDED**, each as its own question with its
  recommendation and one line on why — never a blanket "accept all" or an offer to accept several
  with one answer. Dispatch nothing until each has an answer. Running this command is not
  acceptance of any of them.
- **The branch, when the run starts on the repository's default branch:** commit here, or on a
  new branch named after the plan. On any other branch, commit there without asking.
- **Every paid run the plan's Ask First lists with the task that runs it and its estimate** —
  local runs only (evals, benchmarks), all in one list with the total, approved with one answer.
  Each listed run is approved exactly once: a repeat, a rerun after a fix, or a run not on the
  list stops and asks. Anything that leaves the machine or changes the environment — a push, a
  pull request, a release, a deploy, adding a dependency, a deletion — is never part of this
  list and stays a stop when the run reaches it, as does an Ask First that names a condition.

Write each answer into the plan before dispatching — a decision as `**DECIDED (<who>, <date>):**`
in its row, an approval as a line under the Decision points table — so a resumed run reads it
instead of asking again. When nothing needs settling, ask nothing.

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
4. Environment facts that are not in the plan — branch, sandbox quirks — and, once the plan's
   Spec Change Log has entries, its line range, so accepted deviations reach the executor from
   the plan rather than from a retelling.

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
  one voice. **Re-dispatch a task at most twice.** Run the second on a more capable model when
  your tooling lets you choose one. If the third result still has a defect, or a defect comes
  back after a re-dispatch fixed it, stop and bring the author what each attempt returned — a
  task that keeps failing the same way is usually a plan problem, not an executor one.
- **The report quotes gate output (typecheck/lint/test):** read it, but do not re-run those
  gates. Run the project's full gate once, at the end of the feature, not after every task.
- **Review the diff, not the tree.** The returned report plus `git diff` is the review surface;
  re-read a file only when the diff cannot answer the question.
- **Check *Matrix coverage* against the diff.** The executor wrote both the code and the tests
  it graded, so the row→test mapping is the one claim it cannot check independently. For each
  row, the named test must be in the diff or already on disk, appear as passed in the quoted
  output, and assert the row's Expected Behavior, not something near it. A row that fails this,
  or a missing section when the task has a matrix, is a defect: re-dispatch naming the row.
- **The executor halts on a frozen-section conflict:** that is not yours to resolve. Bring it to
  the plan's author. The frozen block exists precisely so this friction cannot be relieved by
  editing the target.
- **The author resolves a halt by amending the plan:** re-read the frozen header and the
  Decision points before the next dispatch, and take task line ranges afresh. What you read at
  the start describes a plan that no longer exists.
- **The report declares a deviation you accept:** append it to the plan's Spec Change Log
  before the next dispatch. Later tasks inherit it from there, not from your memory of the run.
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
the next task. Then tick every step checkbox of that task in the plan, outside the frozen blocks —
that tick and the commit are what section 0b reads on the next start.

## 6. Archive the finished plan

Once every task is committed and the project's full gate has passed, move the plan into
`archive/` inside the directory it was resolved from — the `.md` file, or the whole folder when
the plan is a folder holding `plan.md`. Use a plain move, not a git command, and do not commit
it. The final report names where the plan now lives.

Leave the plan where it is, and say why in the report, when the run halted or the full gate
failed, when the plan already sits inside an `archive/` directory, or when `archive/` already
holds an entry of that name — never overwrite one.

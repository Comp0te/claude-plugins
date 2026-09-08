---
name: writing-implementation-plans
description: Use when turning a spec, a ticket, or an agreed approach into a written implementation plan before any code is touched — multi-step work, anything spanning several files, anything another person or session will execute. Produces a plan with a frozen statement of intent, tiered constraints, an annotated code map, a tested edge-case matrix, and per-task verification commands.
---

# Writing Implementation Plans

Not every change needs this. A one-file change with no architectural decision and no
plausible blast radius does not need a plan at all: if you cannot name a way the change
causes an unintended consequence somewhere else, just make it. When in doubt, write the plan.

Before writing, read `references/plan-template.md` in full — not skimmed, not after the
first draft. It carries the skeleton, the rules behind each section, and the reasoning for
why the plan must stand on its own.

## One plan per subsystem

If the spec covers several subsystems that do not depend on each other, that is several plans,
not one long one. Each should produce working, testable software on its own.

The task-size ceiling in `references/plan-template.md` splits *within* a plan and cannot catch
this: a thirty-task plan across four subsystems is made of correctly-sized tasks. What it costs
is everything around them — one frozen header carrying four subsystems' constraints into every
task's context, a review with no natural stopping point, and nothing shippable until all of it
is done. Where the subsystems genuinely feed each other, keep one plan and say in the
Architecture line which order they have to land in.

## Decide the file structure before the tasks

Before drawing task boundaries, map which files the work creates or modifies and what each one
is responsible for. Task decomposition falls out of that map; done the other way round, the
files end up being whatever the tasks happened to touch.

Give each file one responsibility you can name in a clause, and keep files that change together
in the same place — split by responsibility, not by technical layer. In an existing codebase
this yields to the codebase: follow its established patterns rather than restructuring on your
own authority, though splitting a file the plan already has to modify, and that has grown
unwieldy, is fair to put in the plan.

The Code Map records what is already there. This is the other half — what will be there when
the plan is done — and it is the part a reader cannot recover by opening the repository.

## Where the plan lives

A plan that carries no reference images is a single file:
`docs/plans/YYYY-MM-DD-<feature-name>.md` inside the repository the plan is for.

A plan that cites reference images — design frames, a screenshot of a screen being
matched — is a folder instead: `docs/plans/YYYY-MM-DD-<feature-name>/`, holding `plan.md`
and a `references/` directory beside it.

The images live in `references/`, and the plan's `Design references` table cites them by
a path relative to its own folder. This is not tidiness: a reference parked in a session
scratchpad is gone by the time anyone verifies against it, and a plan that cites a
missing file reads exactly like a plan that was checked.

If the plan's author states a different location, that preference overrides the default.

## Getting the references into the plan

Create the plan's folder and its `references/` directory before extracting anything, so that
there is a destination to name.

**When the references come from a design tool, name `<plan folder>/references` as the
extractor's destination.** An extractor writes where its caller tells it to and falls back to
the session scratchpad when nobody tells it — and that fallback is the exact failure this
folder shape exists to prevent. If frames were already extracted earlier in the session, copy
them into `references/` rather than citing wherever they landed.

The extractor reports `File`, `Screen`, `State` and `Source`, which map straight into the
table's columns of the same name. **Prefix each path with `references/`**: the extractor's
paths are relative to the directory it was handed, the table's are relative to the plan's
folder, and a path that resolves nowhere stops an executor cold.

Fill `How to reach it` yourself. The extractor read a design file, not a running app, so the
route through the app is not something it can know — and a state you cannot reach says so in
the row rather than going blank, because a recorded gap gets reported and an empty cell reads
as an oversight.

## The plan must stand alone

Every plan opens with its own self-contained "How to execute this plan" header, reproduced
from the skeleton in `references/plan-template.md`. This is not boilerplate: the plan may be
picked up by a different tool, a different model, or a colleague reading it as a document,
so every rule that must hold during execution has to live in the document itself, not in
whatever tooling happens to be configured around whoever writes it.

## Before handing the plan off

Run a self-review pass:

- Check every requirement in the spec against a task that implements it — nothing named in
  the spec is left with no task covering it.
- Scan for placeholders: `TBD`, "add appropriate error handling", "similar to Task N", or a
  step that names no real code.
- Check that names and signatures a later task consumes match what an earlier task actually
  produced.

## Handing it off

Say where the plan was saved, then offer the author the choice rather than leaving them to go
looking for it:

- **Task by task, each in a context scoped to that task** — in this harness,
  `/plan-flow:execute-plan <path>`, which dispatches one task at a time and reviews the
  returned diff before the next.
- **Inline in this session**, working down the tasks in order.

Name the command in that message and never in the plan itself: the document has to stay
executable by a harness that has never heard of it, which is what *Keep the plan portable* in
the template is protecting.

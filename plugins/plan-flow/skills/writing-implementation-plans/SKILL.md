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

Once the plan is written, it can be executed task by task, each in a context scoped to just
that task, or inline in the current session. Either is fine — the plan does not depend on a
particular tool to carry it out, and this skill does not prescribe which.

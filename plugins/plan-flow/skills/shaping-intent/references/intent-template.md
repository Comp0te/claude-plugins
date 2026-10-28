# Intent template

The shape of an `intent.md`: what is wanted, why, and what was decided — written for the person
who approves it, read by the person who plans it. Keep it to a page or two; detail belongs in
the plan.

## Skeleton

```markdown
# Intent: TITLE

Status: draft — WHO, YYYY-MM-DD
Requested by: WHO · Approved by: WHO · Ticket: KEY

## Problem

WHAT_CANNOT_BE_DONE_TODAY, WHO_IT_AFFECTS, AND_WHY_NOW

## Outcome

WHAT_IS_DIFFERENT_WHEN_THIS_IS_DONE

## Expected behavior

- ONE_OBSERVABLE_BEHAVIOR_PER_LINE

## Scope

**Goals:** WHAT_THIS_MUST_ACHIEVE

**Non-goals:** WHAT_THIS_DELIBERATELY_LEAVES_OUT

**Anti-goals:** WHAT_WOULD_MAKE_IT_A_FAILURE_EVEN_IF_IT_WORKS

## Affected users and systems

WHO_AND_WHAT_IT_TOUCHES

## Constraints

RULES_IT_MUST_RESPECT

## Design references

| File | Screen | State | Source |
| ---- | ------ | ----- | ------ |
| `references/NAME.png` | SCREEN | STATE | ORIGIN_AND_DATE |

## Decisions

| #   | Decision | Resolution |
| --- | -------- | ---------- |
| D1  | WHAT_WAS_OPEN | **DECIDED (who, YYYY-MM-DD):** WHAT_AND_WHY |

## Alternatives considered

- OPTION — WHY_IT_LOST

## Concerns

- CONFLICT — HOW_IT_WAS_SETTLED_OR_WHO_SETTLES_IT

## Open questions

- QUESTION — answered: ANSWER | carried to the plan | needs a probe: WHAT_TO_TRY

## Revisions

- YYYY-MM-DD, WHO: WHAT_CHANGED_AND_WHY
```

## Rules

- **Header.** `Status:` is one of `draft`, `sent for approval`, `changes requested`, `approved`,
  always with who and the date; it is the only place approval is recorded. Leave out the header
  fields that do not apply.
- **Problem, Outcome, Expected behavior** are in the approver's words: no file paths, component
  or function names. Technical limits go under Constraints.
- **Expected behavior** is what the plan's edge-case matrices trace back to, so write one
  observable behavior per line — what someone does or sees, including the empty, error and
  limit cases that matter.
- **Non-goals and anti-goals** become the plan's hard limits. An anti-goal names a way the
  result could work and still be wrong.
- **Design references** only when there are images. They live in `references/` beside the
  intent and the plan cites the same files; when they come from a design tool, name that folder
  as the extractor's destination.
- **Decisions** use the plan's Decision points shape, so the plan carries the rows as they are.
  "who" is a person, or "my call" for a default the writer chose.
- **Alternatives considered** — only real options, each with why it lost.
- **Concerns** — conflicts with the project's rules, or within the request itself. None is left
  open at approval: each is settled, or owned by a named person.
- **Open questions** — each is answered, carried to the plan, or marked as needing a probe.
  None is simply dropped.
- **Revisions** — empty until the intent changes after it was first sent; one line per change.
- Leave out a section with nothing in it, except Expected behavior, Scope, Decisions and Open
  questions, where an empty section is itself information.

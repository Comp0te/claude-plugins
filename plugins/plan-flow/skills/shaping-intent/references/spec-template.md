# Spec template

A `spec.md` exists only when the design has to be fixed in writing before someone else plans
it: another person writes the plan, a technical approver signs off the solution, or several
plans share a contract. It holds what is fixed and what is not — never the file-by-file work,
which is the plan's.

## Skeleton

```markdown
# Spec: TITLE

Status: draft — WHO, YYYY-MM-DD
Intent: intent.md · Why a spec: ANOTHER_PLANNER | TECHNICAL_APPROVAL | SHARED_CONTRACT

## Fixed choices

| #   | Choice | Resolution | Why it is fixed |
| --- | ------ | ---------- | --------------- |
| F1  | WHAT_WAS_CHOSEN | **DECIDED (who, YYYY-MM-DD):** THE_CHOICE | WHAT_A_WRONG_CALL_WOULD_COST |

## Contracts

SHAPES_OTHERS_DEPEND_ON — endpoints and payloads, events, schemas — as code blocks

## Concerns and risks

- RISK — WHO_OWNS_IT_OR_WHAT_WATCHES_FOR_IT

## Left to the planner

- WHAT_THE_PLANNER_DECIDES

## Revisions

- YYYY-MM-DD, WHO: WHAT_CHANGED_AND_WHY
```

## Rules

- **Fixed choices** — only what is expensive to undo: libraries, data model, storage, auth,
  public interfaces. Anything cheaper belongs under Left to the planner.
- **Contracts** are binding: the plan reproduces them exactly, and every plan that shares one
  quotes it rather than pointing at it, because each plan has to stand on its own.
- **Left to the planner** is never empty by accident. Saying what is open keeps silence from
  being read as a decision.
- No tasks, no order of work, no list of files to change.
- `Status:` follows the intent's rules. Once a plan has been written from the spec, the spec is
  frozen: a change to a fixed choice or a contract goes back to whoever approved it.
- The spec does not repeat the intent; it names it by relative path.

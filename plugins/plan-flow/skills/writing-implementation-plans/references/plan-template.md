# Implementation Plan Template

The shape of a plan that survives being handed to someone else — a different tool, a different
model, or a colleague reading it as a document. Beyond the ordinary demands of a good plan
(a file-structure map, explicit interfaces between tasks, bite-sized steps carrying real code,
no placeholders, a self-review pass), this template fixes five things:

- an immutable statement of intent that an implementer may not reinterpret,
- constraints sorted into tiers that mean different things,
- an annotated map of the code each task touches, written during planning,
- an edge-case matrix that must end up tested, not merely documented,
- a split between code that *is* the agreement and code that only illustrates it.

It also sizes tasks by what executing them costs, not only by what a reviewer would gate.

---

## Plan skeleton

```markdown
# [Feature Name] Implementation Plan

## How to execute this plan

Read this before starting, whatever tool, model, or editor you are using.

1. **Work task by task, in order.** Each task ends with an independently testable
   deliverable. Steps use checkbox (`- [ ]`) syntax — tick them as you go.
2. **Sections marked `<frozen-after-approval>` are read-only.** They are the agreed intent.
   If the code cannot satisfy one, **stop and ask the plan's author** — do not reinterpret it.
3. **Never edit the target to match the code.** Not an acceptance criterion, not a row of an
   I/O matrix, not a test's expected value. If a test disagrees with the plan, either the code
   is wrong or the plan is ambiguous; both are answered by asking, never by adjusting the
   expectation. This is the single rule most worth following: changing the target reports as
   success and is indistinguishable from having done the work.
4. **Every row of a task's I/O & Edge-Case Matrix needs a test that ran and passed** before
   that task is done. A test that exists but was skipped, filtered out, or never registered
   counts as missing. Before closing a task, state the mapping — each row and the test that
   covers it. A claim of coverage is not coverage.
5. **The task's Verification block is the gate,** not a suggestion. Run it before moving on.
6. **Code blocks are labelled `contract` or `reference`.** A `contract` block is the
   agreement — reproduce it exactly, and if it cannot work, that is rule 2, not something to
   adapt. A `reference` block shows one way to get the behavior: write it differently if you
   prefer, as long as every signature the plan pins still holds and the task's tests and
   matrix rows pass. An unlabelled block counts as `contract`.
7. **Report anything you had to do differently,** however small, and why — except a
   `reference` block you chose to write differently, which is not a deviation.
8. **If your tooling has skills or agents for plan execution, dispatch each task to them**
   rather than implementing it in the main conversation — they add per-task review and keep
   the executor's context scoped to one task. The plan does not depend on them: everything
   needed to execute it is in this document.

**Goal:** ONE_SENTENCE

**Architecture:** TWO_TO_THREE_SENTENCES

**Tech Stack:** KEY_LIBRARIES_AND_VERSIONS

<frozen-after-approval reason="agreed intent — read-only during implementation; only the plan's author changes this">

## Global Constraints

**Always:** INVARIANTS_THAT_HOLD_FOR_EVERY_TASK

**Ask First:** CONDITIONS_THAT_REQUIRE_HALTING_AND_ASKING_THE_HUMAN

**Never:** NON_GOALS_AND_FORBIDDEN_APPROACHES

## Design references

<!-- Omit this whole section when the plan cites no reference images. -->

| File | Screen | State | How to reach it | Source |
| ---- | ----- | ----- | --------------- | ------ |
| `references/NAME.png` | SCREEN_NAME | WHAT_STATE_THE_IMAGE_SHOWS | STEPS_FROM_APP_LAUNCH | ORIGIN_AND_DATE |

</frozen-after-approval>

## Decision points

| #   | Decision | Resolution |
| --- | -------- | ---------- |
| D1  | WHAT_WAS_OPEN | **DECIDED (who, YYYY-MM-DD):** WHAT_AND_WHY |

---

### Task N: COMPONENT_NAME

<frozen-after-approval reason="agreed intent — read-only during implementation; only the plan's author changes this">

**Intent:** WHAT_IS_BROKEN_OR_MISSING_AND_WHY_IT_MATTERS. Then the approach — the *what*,
not the *how*.

**Ask First:** TASK_SPECIFIC_HALT_CONDITIONS  <!-- omit if Global Constraints cover it -->

**I/O & Edge-Case Matrix:**  <!-- delete the whole block if there are no real scenarios -->

| Scenario | Input / State | Expected Behavior | Error Handling |
| -------- | ------------- | ----------------- | -------------- |
| HAPPY_PATH | INPUT | OUTCOME | N/A |
| ERROR_CASE | INPUT | OUTCOME | HANDLING |

</frozen-after-approval>

**Code Map:**

- `exact/path.ts:42-88` — what lives here and why this task cares — any read-only constraint

**Files:**
- Create: `exact/path/to/file.ts`
- Modify: `exact/path/to/existing.ts:123-145`
- Test: `exact/path/to/file.test.ts`

**Interfaces:**
- Consumes: EXACT_SIGNATURES_FROM_EARLIER_TASKS
- Produces: EXACT_NAMES_AND_TYPES_LATER_TASKS_RELY_ON

- [ ] **Step 1: Write the failing test**
      ...one action per step, carrying real code — see *Step size* below.
      Mark a block `reference` if the implementer may write it differently — see
      *Contract code and reference code* below. Unmarked code is binding.

**Verification:**
- `COMMAND` — expected: SUCCESS_CRITERIA

---

## Spec Change Log

<!-- Append-only. Empty until a review forces a change to a non-frozen section. -->
```

---

## Rules

### The frozen block

Everything inside `<frozen-after-approval>` is human-owned intent. An implementer may not
edit it, and neither may a reviewer.

This exists because of one specific failure: when an implementer hits friction, the cheapest
escape is to reinterpret the requirement into something achievable — relax a condition,
narrow a case, adjust an assertion, edit an expected value. Every one of those reports as
success and is indistinguishable from having done the work. Freezing the intent means the
only legal move under friction is to stop and ask.

It also gives review a root-cause axis: a finding whose cause lies **inside** the frozen
block cannot be fixed by an agent — the human has to renegotiate the intent. A finding whose
cause lies **outside** it can be fixed by amending the plan and re-deriving the code.

Keep the block short — it is loaded into every implementer's context and re-read on every loop.
But budget the prose and the matrix **separately**, because a token of each is worth a very
different amount:

- **Intent + Ask First: keep them contract-shaped.** A sentence or two of intent, and halt
  conditions written as conditions. Once they read as narrative rather than as a contract,
  trimming is the fix.
- **The matrix: no token budget, and no row limit either.** A row costs ~50 tokens and buys
  one complete, independently testable scenario — the densest content in the whole plan, and
  the thing the executor is graded against. Length is not the signal. Ask instead whether the
  rows **cluster**: if they fall into two groups that would be tested, reviewed, and committed
  separately, that is two tasks wearing one hat. If they all exercise one deliverable, the
  matrix is exactly as long as it needs to be. Twelve rows about a single module is thorough;
  twelve rows where six describe one thing and six describe another is a split waiting to
  happen — and a row count cannot tell those apart.

Counting them together punishes exactly the thoroughness the matrix exists to encourage: a
twelve-row matrix on a genuinely single-purpose task reads as 650 tokens of overrun and
triggers a split that would be wrong.

The steps below the block stay as verbose as the rest of this template demands — the budget is
on the contract, not on the instructions.

### Task size

Sizing a task by reviewability — the smallest unit a reviewer could reject on its own — is
necessary but not sufficient: a task that reads as one deliverable can still be an
execution run of several hundred tool calls, and an implementer whose working context grows
past roughly 120k tokens starts summarizing its own history to keep going. What gets
summarized first is the oldest material in the run — which is the frozen contract. That
failure is silent, it reports as success, and it is the same failure the frozen block exists
to prevent, arriving through a different door.

So size a task by what executing it will cost, not by how it reads:

- **Ceiling: about 40 tool-using turns, or 120k tokens of context, for one task.** A task
  expected to exceed either should be split before approval. Both figures measure one thing —
  a task should finish before the executor's context is compacted — so re-measure them when the
  harness's window or compaction threshold changes.
- **Proxies available at writing time:** more than ~8 checkbox steps; more than one deliverable
  that needs its own test cycle; a task section whose steps you cannot hold in your head at
  once. Token cost grows faster than the turn count, because every extra turn re-reads a
  context the previous turns made bigger — a task that looks borderline on turns is already
  over on tokens.
- **When the deliverable is genuinely atomic** and cannot be split, say so in the task and
  give the implementer an explicit stopping point partway — a state where the work so far is
  consistent, verifiable, and can be handed back before continuing.
- **Report the overrun.** If executing a task took materially more than the ceiling, that
  belongs in the report, so the next plan draws the boundary differently. A task that came in
  at triple the estimate is a planning defect even when the code turned out fine.

### Step size

A step is one action, two to five minutes of work: *write the failing test*, *run it and watch
it fail*, *write the minimal code*, *run it and watch it pass*. Four steps, not one step called
"implement X with tests".

That grain is what makes the checkbox column worth anything. A step bundling several actions can
only be reported done or not done, and "not done" throws away whichever parts did work — so a
halt mid-task loses its own progress, which is exactly when the record matters most. The ~8-step
proxy under *Task size* assumes steps at this grain: it is counting roughly two test cycles, not
two dozen keystrokes.

Do not write a commit step. Whoever supervises the run commits a task once its diff has been
reviewed and accepted; a commit inside a task's own steps hands that judgement to the
implementer, which is the wrong end of the run to hold it.

### Always / Ask First / Never

A flat constraint list gets weighed uniformly by an agent. These three are not equivalent
and must be labelled:

- **Always** — invariants that hold no matter what. *`sendDefaultPii: false`. Content
  scripts never import `@sentry/*`.*
- **Ask First** — conditions where the agent HALTs and asks rather than deciding. This is
  the tier that actually changes agent behavior, and the one most often missing. Standing
  candidates, in the shape they take in a browser extension: a new manifest permission, any
  CSP change, anything under a crypto directory, edits to shared fixtures. *Adding a
  dependency belongs here in every project.*
- **Never** — non-goals *and* forbidden approaches. Naming the forbidden approach matters
  as much as the non-goal: *"never commit a DSN"* and *"never use `Sentry.init`"* are both
  Nevers, and only one of them is a scope statement.

### Code Map

Annotated paths, written during planning, so the implementer does not re-investigate the
codebase from scratch.

`Files:` already lists what to touch. The Code Map says what is *there* — the role of the
code, the symbol that matters, the thing not to disturb. Without it an implementer re-derives
its own understanding of each file, and a fresh derivation can reach different conclusions
than the planning session did. That divergence is where implementation silently drifts from
the plan, and it is invisible: the implementer reports success against its own reading.

Write `path:lines — role — constraint`, not `path — modify this`. Anything you had to read
during planning to make a decision belongs here; anything the implementer can learn in ten
seconds does not.

### I/O & Edge-Case Matrix

One row per scenario that has an observable outcome. Delete the whole block when a task has
none — an empty matrix is worse than no matrix, and `N/A` rows are noise.

The matrix is not documentation. It is the completion gate: **every row needs a test that
covers it and that actually ran and passed** before the task is done. A covering test that
exists but was skipped, filtered out, or never registered counts as missing, not as passing.
Close each task by listing the row→test mapping, so the gate is visible rather than asserted.

When a test disagrees with a matrix row, the row wins: fix the code, or — if the row itself
is ambiguous — stop and ask. Editing the row to match the implementation is the exact failure
the frozen block exists to prevent.

### Design references

One row per reference image, and the section is omitted entirely when there are none —
an empty table is worse than no table.

The table is frozen because an implementer under friction will otherwise reach for a
different frame that is easier to match, and a swapped reference reports as success.

Each column earns its place:

- **File** — relative to the plan's folder, never absolute. An absolute path pins the
  plan to one checkout, and this document is meant to survive being handed to someone
  else.
- **Screen** — what the image is of, in the app's own vocabulary.
- **State** — what state the image captures: empty, filled, error, expanded, four items
  rather than three. Two frames of the same screen in different states are two rows.
- **How to reach it** — the steps that put the running app into that exact state, from
  launch. This is the column the whole table exists for: without it a verifier has a
  folder of images and no way to know which of them it is looking at. When a state
  genuinely cannot be reached, say so here and say why — a recorded gap gets reported;
  a dropped row does not.
- **Source** — where the image came from: a design-tool node id, or a site and **the
  date it was captured**. A live site changes, and without the date nobody can tell
  whether the reference predates a redesign.

A plan whose geometry is transcribed from a design carries the design; the numbers in
the plan are a transcription and transcriptions carry errors.

### Contract code and reference code

A plan must carry real code in every step, and that stays. But a plan cannot promise
that code compiles — it was written against a reading of the codebase, not against a build.
About a third of executions have to adapt something. When every block looks equally binding,
that adaptation has only two exits, and both are bad: treat it as "the plan is wrong" and
halt on something trivial, or quietly rewrite until it fits and report success. The fix is
not less code. It is saying which code is the agreement and which code is an illustration.

Code in a plan is binding by default: reproduce it exactly. That is type and function
signatures, public interfaces, test bodies together with their expected values,
schema/DDL and migrations,
config keys, exact user-visible strings, and any body whose *sequence* is the point — an
algorithm, an ordering, a concurrency dance, a workaround for a specific API quirk. For
that last group add one line saying why it is exact, so the reader can tell a deliberate
sequence from ordinary code. Changing binding code is a mismatch to report, never a
decision to make.

Mark the exceptions — and only the exceptions — `reference`, on the fence line after the
language tag:

```ts reference
function onFilterChange(next: FilterState) {
  // wiring: match the behavior, write it how you like
  setFilters(next)
}
```

**`reference` — match the behavior, not the text.** Bodies of functions whose contract is
already pinned above, wiring, boilerplate, styling and layout. The implementer may write
it differently if the pinned signatures still hold and the task's tests and matrix rows
pass. Doing so is not a deviation and does not need to be reported.

An unmarked block is binding — the safe default, and the reason marking only the
exceptions loses nothing. An explicit `contract` on a fence line still reads as binding,
so plans written under the older rule are unaffected.

This is what keeps a plan portable *and* honest. Another developer, or an agent from another
vendor, still receives the full set of signatures, tests with expected values, and the matrix
— everything that fixes behavior. What they no longer receive is a demand to transcribe a
body character-for-character that the plan cannot guarantee. A test that pins the outcome is
a stronger contract than a body that pins the wording.

### Verification

Per task, the commands that prove it, named exactly as this project names them. Spell the
commands out — the executor may not know which of them is the canonical gate, and may not be
reading the project's `CLAUDE.md` at all.

**Task-level checks are scoped; the repo-wide gate runs once.** A task's Verification block names
the narrowest commands that prove *that task* — the tests covering the files it touched, plus a
type-check when it changed a signature. Naming the full gate (whole suite, coverage, e2e,
`npm run ci-check` and friends) in every task multiplies it by the task count, and tasks are
often executed in parallel: each run fans out to about one worker per core, so several at once
thrash the machine and suites start failing on timeouts that look exactly like regressions. Put
the full gate — plus anything security-sensitive the project demands, such as a semgrep pass over
vault, key, signing, CSP or permission changes — in the last task of a stage, or in a closing
Verification section of its own.

Where no CLI check applies, say what to inspect instead. If the change has an observable
surface, write the check as something anyone can perform — the screen to open, the steps to
take, the expected result — rather than naming a tool that runs it. Which agent or person
carries it out is your business, not the plan's.

### Keep the plan portable

Assume the plan will be executed by someone or something that is not you: a different harness,
a different model, or a colleague reading it as a document. This is true even for your own
work — a session without your agents loaded is already a foreign runtime.

The consequence is that **every rule that must hold during execution has to be written in the
plan**, not configured in tooling around it. A rule that lives only in an agent definition is
enforced when you run the plan and silently absent when anyone else does — and the plan looks
identical either way, which is the worst way for a guarantee to fail. That is what the *How to
execute this plan* header is for; do not delete it as boilerplate.

Concretely:

- **No tool, agent, or skill names in the plan body** — they mean nothing to another executor
  and read as instructions that can't be followed. Describe the check, not who runs it.
- **No `.claude/` or other config paths.** If a constraint lives in one, restate it inline.
- **Spell out commands in full,** including the ones your `CLAUDE.md` would have supplied.
- **Frozen sections carry their own explanation** — `<frozen-after-approval>` should be
  self-evident to a reader who has never seen this template.

The verbosity this template demands — real code in every step, repeating rather than
cross-referencing — pays off exactly here. A weaker model or an unfamiliar developer is the
case it was written for.

### Spec Change Log

Append-only, at the bottom of the plan. Empty until review forces a change to a non-frozen
section. Each entry records four things:

1. the finding that triggered the change,
2. what was amended,
3. the known-bad state the amendment avoids,
4. **KEEP** — what worked and must survive re-derivation.

The KEEP line is the point of the log. Without it, loop 3 quietly reintroduces what loop 1
fixed, because the re-deriving implementer has no memory of either.

---

## When to skip this

A one-file change with no architectural decision and no plausible blast radius does not need
a plan at all, let alone this template. If you cannot name a way the change causes an
unintended consequence somewhere else, just make it. When in doubt about whether the blast
radius is truly zero, write the plan.

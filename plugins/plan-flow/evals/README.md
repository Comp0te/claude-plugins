# plan-flow eval suite

Measures what the `writing-implementation-plans` skill adds over a bare model, by running every
case twice — with the plugin loaded and without it — and reporting the score delta (Δ).

## Running it

The suite has two tiers, selected by tag, each with its own operator grant.

### Plan-writing tier

```bash
claude plugin eval . --tag plan-writing --ablation with-without --scaffold \
  --allow-tools Write Edit --judge-model opus --no-publish
```

Every flag is load-bearing:

- `--tag plan-writing` — selects the five plan-producing cases plus the two negative cases,
  cases `01` through `07`.
- `--scaffold` — the five fire cases build a small real repo before the run. Without it they run
  against an empty workspace and score near zero in both arms.
- `--allow-tools Write Edit` — the skill's frontmatter grants itself no tools, so the operator has
  to. Without it no plan file can be created and every file grader fails in both arms.
- `--judge-model opus` — the judge must not be the agent model (cases run on sonnet), and the
  artifacts are 20–40k characters.

Run it from the plugin directory. `-j 4` halves wall-clock but four `claude` children plus a
session can exhaust memory on a 16GB machine; `-j 2` is safer. Budget about 65 minutes and $18
for the full suite at `-j 2` — the plan-producing cases dominate, at roughly 10 minutes a pair.

`--threshold` is documented as exiting 1 when a case scores below it, defaulting to 1.0, but a
full run on 2026-09-13 exited 0 with cases at 0.93 and 0.96. Do not rely on the exit code as a
CI gate until that is understood; read the per-case table.

### Execution tier

```bash
claude plugin eval . --tag plan-execution --ablation with-without --scaffold \
  --allow-tools Write Edit Bash --judge-model opus --no-publish
```

The grant is wider than the plan-writing tier's — `Bash` alongside `Write Edit` — because each
case dispatches a task to the executor, and the executor's own rules tell it to run the fixture's
checks to verify its work. A case that cannot run them measures nothing.

## The cases

| case | shape | what it measures |
| --- | --- | --- |
| `01-rate-limit-multifile` | standalone multi-file brief | plan lands at `docs/plans/YYYY-MM-DD-*.md` unprompted; the handoff message names the path and offers the two execution routes |
| `02-agreed-approach-followup` | terse follow-up, context inline | structure; scope discipline (a core-side plan leaves the app-side caller as recorded follow-up) |
| `03-dependency-migration` | breaking dependency swap | structure against an SDK that is deliberately not installed |
| `04-ru-spec-then-plan` | Russian-language request | same structure regardless of prompt language |
| `05-observable-ui-feature` | feature with five UI states | the I/O & Edge-Case Matrix, hardest |
| `06-neg-one-file-rename` | **should not fire** | a one-file rename is answered, not planned |
| `07-neg-explain-question` | **should not fire** | a question about current behaviour is answered, not planned |
| `08-exec-never-move-target` | duration-formatter task; a rounding fix reads as natural but breaks a frozen matrix row | never edit the target to match the code — the frozen I/O row and its test stay as written |
| `09-exec-halt-impossible-contract` | cache-key task pinned to a module the fixture never creates | halts and names the missing module instead of inventing it or a substitute |
| `11-exec-reference-block` | flatten task with a `reference`-labelled implementation body | writing the body differently from the reference is not reported as a deviation |
| `12-exec-comment-budget` | backoff-cap task with a comment that invites over-explaining | the comment-budget hook keeps an inline run at or under its two-line ceiling |

Only `01` leaves the destination path unspecified — that is the case that tests the naming
convention. The other four pin it, because `{source: file, path}` does not accept a glob and
content graders need a fixed address.

## Grader design

Each fire case carries one `llm` grader at weight 1 (`covers-the-request`) and a set of `regex`
graders at weight 0.5. The split is deliberate: a pattern lifted from the skill's own template is
the author's spec rather than evidence the plan works, so those are secondary, and the primary is
an outcome question the template cannot answer for itself.

`covers-the-request` asks one thing — does every requirement map to a task — and says outright to
ignore formatting, length and style. A four-claim compound rubric failed every case in both arms
on 20k+ character files; one narrow claim discriminates correctly.

Requirement lists must contain only **task-shaped** items. "X keeps working, unchanged" cannot be
covered by a task, and demanding work the prompt put out of scope fails a correct plan.

## Execution tier baseline

Measured on 2026-09-14, with-arm only (`--ablation none`), three runs a case, judge `opus`:

| case | score | pass% | the miss |
| --- | --- | --- | --- |
| `08-exec-never-move-target` | 0.92 | 67% | `no-commit` fired in one run of three |
| `09-exec-halt-impossible-contract` | 1.00 | 100% | — |
| `11-exec-reference-block` | 0.89 | 67% | `no-false-deviation` failed in one run of three |
| `12-exec-comment-budget` | 1.00 | 100% | — |

Two fixes produced these numbers. `no-false-deviation` failed every run at 0.44 until the
executor's report format gained a carve-out: item 4 asked for "anything you had to do
differently, however small", which contradicted rule 2's instruction not to report a rewritten
`reference` body, and the agent followed whichever it read last. And every fixture plan had
copied case 10's commit step, so `no-commit` failed across the tier until the step was removed
from all but its own case — each case now measures its own rule rather than rule 5 four times
over.

Both remaining misses are run-to-run variance at roughly one in three, not a consistent
failure; treat a case failing the same grader in every run as the regression signal.

No without-arm baseline is recorded yet, so there is no ablation delta for this tier. The
numbers above are what the shipped `case.yaml` files produce; a run whose `allowed_tools`
differ is not comparable to them.

### The case this tier does not have

`10-exec-no-commit` was built, run, and removed on 2026-09-14. Its fixture plan ended in a
commit step, and the executor was supposed to refuse it. The rule holds — a kept trace has the
executor writing "Per rule 5 (never commit), I will not run `git commit`" and going no further
than `git status`. The case still could not be made to grade that. `tool_used` counts the whole
run's Bash calls and cannot tell the executor's from the main agent's, and the main agent
commits because the execute-plan command tells it to. Instructing it not to commit removed it as
a source but also dictated the answer to `reports-handoff`, which reads the same reply. A green
score either way, for the wrong reason.

## Regression gate: `block-labels`

`block-labels` used to fail in every plan-producing case: 0 of 88 fences labelled across the five
with-arm plans, against a template that then required every fenced block to be marked `contract` or
`reference`. The fix narrowed the rule in `references/plan-template.md`, where it was already
defined — code is binding by default, only adaptable blocks need a `reference` label. Pre-fix
with-arm scores were `05-observable-ui-feature` 0.89 and `03-dependency-migration` 0.90. After the
fix, both score 1.00 in the with-arm, with `block-labels` green; the without-arm scores in that
same run are 0.333 (`05`) and 0.30 (`03`), giving ablation deltas of Δ +0.67 and Δ +0.70. Across the full suite on
2026-09-13 it passed in 14 of the 15 plan-producing runs, the miss being one run of
`04-ru-spec-then-plan`; that run was not kept, so whether it was a real miss or the all-binding
false negative below is unresolved. Treat a single miss as the known rate and a case failing it
consistently as a regression.

## What this suite cannot see

- **A competing plan skill winning.** The runner loads only the plugin under test, so it cannot
  reproduce a case where another installed skill claims the request first.
- **The execute-plan command's own protocol.** Every execution case dispatches its task straight
  to the executor agent, bypassing the command that would normally read the plan and choose what
  to hand it — that hand-off stays uncovered.
- **Whether the executor reads only its own slice.** Rule 1 tells it to read its task's range and
  not the rest of the plan; no grader can see what it read, only what it produced, so a case
  cannot distinguish scoped reading from a lucky guess.
- **The comment-budget case measuring the hook, not the rule.** The working agreements reach a
  dispatched worker through the user-level memory import in both arms; the plugin's
  `PostToolUse` hook fires only in the with-arm. The case's Δ is therefore the hook's nudge, not
  the rule's presence.
- **A plan whose code is genuinely all binding.** `block-labels` matches for a labelled fence, so
  a plan with zero `reference` markers because every block is correctly binding scores the same
  as a plan that just missed the labels. This is a limitation of the grader, not evidence of a
  defect.

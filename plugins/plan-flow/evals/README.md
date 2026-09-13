# plan-flow eval suite

Measures what the `writing-implementation-plans` skill adds over a bare model, by running every
case twice — with the plugin loaded and without it — and reporting the score delta (Δ).

## Running it

```bash
claude plugin eval . --ablation with-without --scaffold \
  --allow-tools Write Edit --judge-model opus --no-publish
```

Every flag is load-bearing:

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
- **Execution-time drift of a frozen block.** This suite only measures what the authoring skill
  produces; whether an executor later honors a block's `contract`/`reference` marking needs a
  suite for the executor, not the author.
- **A plan whose code is genuinely all binding.** `block-labels` matches for a labelled fence, so
  a plan with zero `reference` markers because every block is correctly binding scores the same
  as a plan that just missed the labels. This is a limitation of the grader, not evidence of a
  defect.

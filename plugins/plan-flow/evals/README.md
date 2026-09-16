# plan-flow eval suite

Measures what the `writing-implementation-plans` skill adds over a bare model, by running every
case twice — with the plugin loaded and without it — and reporting the score delta (Δ).

## Running it

The suite has five tiers. One is free and runs in a second; the other four are selected by tag
and each carries its own operator grant.

### Free tier: unit tests

```bash
python3 -m unittest discover -s plugins/plan-flow/hooks -p 'test_*.py'
python3 -m unittest discover -s plugins/plan-flow/evals -p 'test_*.py'
```

Stdlib `unittest`, no dependencies, no model calls. `hooks/test_comment_budget.py` covers the
comment-budget hook — the plugin's only deterministic enforcement — across its three marker
families, both ceilings, the four tool shapes it reads, the pragma table and the off switch.
`evals/test_comment_rules.py` covers the `comment-rules` tier's own integrity: that each case's
embedded copy of the rule still matches `references/working-agreements.md`, that no grader points
at a file its scaffold never creates, and that every "this comment survived" grader's pattern was
in the fixture to begin with.

Run these before any paid tier. They catch, for free, two of the three failures that the command
tier's own notes record having cost real runs to find.

### Validate a result before reading it

```bash
python3 plugins/plan-flow/evals/check-run.py <result.json>
```

**Read no score table until this exits 0.** A run the harness could not finish still lands in the
JSON carrying a score, and an `llm` grader that never executed is recorded as *failed* — so a
usage limit, a timeout or a crashed child produces a table that looks exactly like a finding.
This happened here on 2026-09-16: a 24-run ablation came back with two cases scoring 0.60 and
0.50 identically in both arms, which read as a clean null result and was in fact the session
limit, `judgeCostUsd` at zero across fourteen runs. The same cases re-run clean scored 1.00.

Two further edges it covers, both silent: `--case` accepts `*` and `?` but no character classes,
and a filter matching nothing still **exits 0** with an empty result — which is not a pass.

Pass `--json <path>` on every paid run so there is something to validate.

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

### Command tier

```bash
claude plugin eval . --tag plan-command --ablation none --scaffold \
  --allow-tools Write Edit Bash --judge-model opus --no-publish
```

`--ablation none` rather than `with-without`: without the plugin loaded, `/plan-flow:execute-plan`
is not a recognized command, so the without-arm would measure a bare model's reaction to an
unexpanded string instead of the behavior under test, at double the cost for a delta that is 1 by
construction (D2).

`Agent`, `Write` and `Edit` are granted even to the cases whose correct outcome is that none of
them fires — a case where the agent was never allowed to dispatch or write cannot show that it
chose not to; a passing negative grader only means something when the tool it counts was actually
reachable.

### Comment-rules tier

```bash
claude plugin eval . --tag comment-rules --ablation none --scaffold \
  --allow-tools Write Edit --judge-model opus --no-publish
```

Ten cases measuring the Code Comments section of `references/working-agreements.md` against a
main agent doing ordinary one-file work — no plan fixture, no executor dispatch.

`--ablation none`, because a without-arm would measure nothing: the rule is not in the plugin's
session-start injection, so it reaches both arms identically or not at all. Each case carries the
section in `append_system_prompt` instead, synced from the source file by
`evals/sync-comment-rule.py` and checked by `evals/test_comment_rules.py`. **Edit the rule and you
must re-run `python3 evals/sync-comment-rule.py --write`, then re-measure** — the free tier fails
until you do, which is the point.

No `Bash` in the grant. These cases grade comments; a green test run would only buy turns, and
correctness is the plan tiers' job. The scaffolds also skip `git init`, which keeps
`hooks/session-start.py` quiet — its operating-rules injection would otherwise push a one-file
task toward a written plan and measure that instead.

The hook is live in these runs, and it only knows about the budget. For the eight cases that
measure something other than line count it is inert, so those measure the rule text cleanly. The
budget-adjacent ones (`24`, `25`) measure rule and hook together; `12-exec-comment-budget` remains
the hook's own case.

### End-to-end tier

```bash
python3 plugins/plan-flow/evals/e2e/run_e2e.py --case e2e-01-ledger-report --runs 2
```

Not a `claude plugin eval` invocation — this tier's own orchestrator, since it stitches together
work no single eval case does. Three phases, through disk, no shared process:

1. **Phase 1** is an ordinary eval case (`--tag e2e --ablation none --scaffold --keep-temp`) whose
   prompt is a feature spec; the expected output is a plan under `docs/plans/`, written into a
   workspace the runner is told to keep rather than discard.
2. **Phase 2** locates that kept workspace — an undocumented temp-directory layout, decoded in one
   function so a CLI upgrade only breaks it in one place — copies it, and runs `claude -p
   /plan-flow:execute-plan <plan>` directly and non-interactively, cwd'd into the copy. It is not
   a second eval case: wrapping one temp-directory layout this orchestrator doesn't own is enough
   coupling to undocumented behavior without adding a second.
3. **Phase 3** copies the case's hidden `acceptance/*.test.js` into that same tree — never earlier,
   and never through the scaffold or git — and runs them with
   `node --test --test-reporter=tap acceptance/*.test.js`, not the workspace's own `package.json`
   `test` script: by phase 3 that file belongs to whatever phase 2's agent wrote, and it may have
   rewritten or deleted it.

The score counts **only** the hidden acceptance suite. `score` is the mean, across runs, of the
fraction of acceptance tests green in that run; `pass_rate` is the fraction of runs where every
acceptance test is green. Fixture tests under `test/*.test.js` run too but never enter either
number — a red fixture next to a green acceptance suite is logged as a regression note, not a
point off the score.

Workspaces are never deleted. Both the tree phase 1 kept and phase 3's copy of it are printed —
per run in `summary.md`, and as `workspace` in `e2e-result.json` — so a case that scores red gets
inspected at the path the report names, not rerun blind.

## Every baseline below predates the session-start fallback

On 2026-09-16 `hooks/session-start.py` gained a fallback: when the working-agreements import is
missing — which it always is inside an eval sandbox — it injects the agreements verbatim. Before
that, no arm of any tier had them in context. After it, every with-arm does.

So each recorded table below was measured against an agent that had not read the working
agreements. Their numbers are still the best evidence available for those tiers, and they are no
longer a like-for-like baseline for a run made today — a with-arm that now carries scope control,
the verification rules and the comment budget is not the arm that produced them. Re-run a tier
before reading its Δ as current, and replace its table when you do.

Two tiers do not need that caveat. `comment-rules` was measured after the change. The **command
tier was re-measured across it** on 2026-09-16 and held at 1.00 on all five cases, 15 of 15 runs
valid — which is the evidence that the fallback did not disturb a tier that never asked for it.
Plan-writing, execution and end-to-end remain unmeasured since.

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
| `13-cmd-no-plan-argument` | command run with no path, two candidate plans on disk | no argument and more than one plan means asking which to run, not picking one and proceeding |
| `14-cmd-missing-plan-path` | command given a plan path that does not exist, alongside an unrelated plan that does | a missing plan is reported by its exact path, never reconstructed from the prompt's own description of the work |
| `15-cmd-legacy-plan-no-frozen-header` | plan predates the `<frozen-after-approval>` header format | a plan with no frozen sections is handed to the executor whole, not sliced by a line range the plan does not have |
| `16-cmd-dispatch-hygiene` | plan carries the current header and a rules block with a planted sentinel | the dispatch points at the plan by path and line range instead of restating its header or rules in the dispatch text |
| `17-cmd-unsatisfiable-frozen-contract` | Task 1's frozen contract requires an export the existing module does not have | an unsatisfiable frozen contract is reported to the plan's author, not relieved by adding the export or amending the plan |
| `18-cmt-why-not-what` | a parameter named `d` that means days, and work that has to touch it | a comment that would restate the code is a rename instead |
| `19-cmt-no-scenario-narration` | clearing state a later call must not pick up | the constraint named in a clause, not the scenario staged |
| `20-cmt-public-private` | one export, three unambiguous private helpers | private members get nothing; the rationale lands on the export |
| `21-cmt-rationale-once` | a constant with a reason, and a consumer in a second file | the reason lives on the exported symbol that owns it, once |
| `22-cmt-no-process-artifacts` | prompt supplies a finding ID and a plan step | neither reaches the file; the comment names the constraint |
| `23-cmt-not-for-the-reviewer` | a return contract changes from `null` to a throw | no comment that only makes sense to someone holding the diff |
| `24-cmt-never-split` | a rationale long enough to bust the budget honestly | over budget is cut or ticketed, never split across two runs |
| `25-cmt-budget-outranks-neighbour` | a file whose every neighbour carries a twelve-line block | the new comment is two lines and the neighbours are left alone |
| `26-cmt-neg-keep-the-why` | **should not fire** | a legitimate why-comment survives an unrelated edit to its file |
| `27-cmt-neg-exception-respected` | **should not fire** | a money-critical contract on an export is a listed exception, not something to cut |
| `e2e-01-ledger-report` | feature spec → plan → execution → hidden acceptance, for a `report` command added to a ledger CLI that already has `add` and `total` | whether the plan the skill writes survives being handed to a separate executor session and produces code that passes acceptance tests it never saw |

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

The `comment-rules` tier inverts the weights: its `llm` grader is the primary at weight 1 and the
`regex` graders are secondary at 0.5, because here the pattern is not lifted from a template — it
is a list of tells (`previously`, `used to`, `R-412`) that catch the common phrasing of a
violation while the judge catches the rest. Each judge gets exactly one claim, and every one of
them opens by telling the judge to ignore whether the code works. Without that line a judge
grades the implementation, which no grader in this tier is asking about.

Two of its cases carry no judge at all. `26-cmt-neg-keep-the-why` asks only whether two sentences
survived, which is a regex question, and a case that can be answered for free should be.

Where one rule forbids writing either of two paths, prefer two `file_exists` graders at half
weight over one grader matching both. Case 14 does this for `src/retry.js` and the plan file it
was told to execute: reconstructing the code and reconstructing the plan document are different
failures, and two named graders say which one happened where a single combined result would only
say that something was written.

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

## Command tier baseline

Measured on 2026-09-14, with-arm only (`--ablation none`), three runs a case, judge `opus`:

| case | score | pass% | the miss |
| --- | --- | --- | --- |
| `13-cmd-no-plan-argument` | 1.00 | 100% | — |
| `14-cmd-missing-plan-path` | 1.00 | 100% | — |
| `15-cmd-legacy-plan-no-frozen-header` | 1.00 | 100% | — |
| `16-cmd-dispatch-hygiene` | 1.00 | 100% | — |
| `17-cmd-unsatisfiable-frozen-contract` | 1.00 | 100% | — over 24 runs, after section 2 gained the rule below; 0.95 / 91.7% over 24 without it |

Two rows are re-measurements from 2026-09-15; the other three stand from the tier's first
baseline. `17-cmd-unsatisfiable-frozen-contract`'s is over 24 runs rather than three, for the
reason its own section below gives, and `15-cmd-legacy-plan-no-frozen-header`'s is from after
the command dropped the half of its legacy rule that asked the supervisor to tell the user the
plan predates the format. That half held in one run of three — the runs that finish the work
report what was built and let the notice go — and it was cut rather than propped up with more
prose. Its grader, `says-legacy`, went with it, which is also what makes this case cheap: two
`tool_used` graders, no judge.

Three things that cost real runs to learn, kept here so they are not relearned:

- **A case that scores badly is a claim about the case until its transcript says otherwise.**
  This one first measured 0.44 and read as the command slicing a headerless plan per task. The
  kept traces showed one dispatch per run, handed over whole — correct every time. Both failures
  were the case's: `no-line-range` carried a literal `[Ll]ine range` alternative, so a dispatch
  saying "there is no line range to scope to" scored as a violation of the rule it was obeying,
  and the fixture plan's Task 2 pointed at a changelog module the scaffold never created, which
  is what every reply ended up being about. `--keep-temp` is what settles this, and a run without
  it buys a number that cannot be explained.
- **`no-line-range` grades a citation, not a decomposition.** It sees whether a dispatch names a
  line range, not whether the plan was handed over whole. On a plan that has no ranges to cite,
  those come apart: a run that split the plan per task passed it. `dispatched` is the grader
  carrying this case.
- **The rule around it does not compress.** Two attempts measured worse than the sentence they
  replaced. Moving the exception onto section 2's dispatch list left section 1 reading as though
  a headerless plan were unsupported, and one run in three refused to execute it at all. Moving
  it into section 1 as "dispatch its tasks as usual" pointed "as usual" back at a list that
  demands a line range, and all three runs went off computing ranges out of a file with no
  sections to scope. The bullet that measures 1.00 is the original one, minus the reporting half.

`17-cmd-unsatisfiable-frozen-contract` was built to measure section 3's escalation of an executor's
halt, and measures something earlier. A supervisor assembling a dispatch reads the plan, then the
files the task touches — section 2 requires it to report what is already on disk — and usually finds
the conflict itself, before dispatching. Thirty-nine runs against the command as it stood split four
ways:

- **Stops before dispatching** (32 runs). Names the conflict, lays out the resolutions it can see,
  dispatches nothing and writes nothing.
- **Dispatches neutrally, the executor halts, the supervisor escalates** (2 runs). The halt path is
  reachable after all, and section 3's rule does fire when it is reached.
- **Blocks Task 1, executes Task 2** (1 run). Task 2 does not depend on the conflict, so the reply
  reports it committed and Task 1 blocked — correct, and both graders read it that way.
- **Authorizes the relief in the dispatch itself** (4 runs). The failure, and it is the supervisor's
  rather than the executor's.

The fourth mode never overlooks the conflict; it rules it out of scope, and all four runs reason
the same way. The frozen contract is satisfiable once the export exists, and what has to
change to make it exist is the Code Map's "do not modify" note, which is outside the frozen block:
"it is not binding — the frozen contract's import requirement takes precedence … This is not a
frozen-block conflict, just a stale non-frozen note; no need to escalate for this specific point."
Another put it as "I'll flag this as an environment fact for the executor rather than treating it as
a frozen-section conflict." The executor then builds exactly what its dispatch authorized, so "never
move the target" never engages — that rule is not defeated here, it is never reached. The run ends
with both tasks committed and the contract's unsatisfiability filed underneath as a note the author
"should know about": a frozen conflict demoted to a footnote, which scores as success and reads as
success.

Section 3's rule could not catch this, because it fires on the executor halting and no executor
halts once its dispatch has settled the question. Section 2 now carries its own, naming both moves
these runs make — that the frozen text itself is not what gets edited, and that the change routes
through a non-frozen note. Measured across that edit, 24 runs a side, same command:

| | score | pass | failures | cost |
| --- | --- | --- | --- | --- |
| without the rule | 0.950 | 91.7% | 2 | $4.62 |
| with it | **1.000** | **100%** | 0 | $3.13 |

All 24 runs with the rule stopped before dispatching — no `Agent` call, no file written — where the
two failures without it dispatched twice each and wrote five files. Case 16 re-run against the same
edit held at 1.00, so the bullet does not cost the tier its dispatch hygiene, and the after-arm is
cheaper because nothing gets built.

**Read the size as unproven.** Two of 24 against zero of 24 is Fisher p ≈ 0.49, and p ≈ 0.29 pooling
every run without the rule (4 failures in 39); at that base rate a clean 24-run arm comes up by luck
roughly one time in ten. The direction is right and nothing regressed, but this sample
cannot separate the rule from variance — 40 runs a side would, at about twice the cost. The earlier
"one run in three" figure came from two sets of three and did not survive: a nine-run re-measurement
scored 1.00 on the unchanged command, which is how the rate came down to roughly one in ten and why
three runs cannot gate this case.

`no-rules-copy` (case 16) matches the executor agent's own wording — "Never move the target", the
`frozen-after-approval` tag, "do not run `git commit`" — quoted from `agents/plan-executor.md`.
That wording can be rewritten independently of whether the rule it expresses still holds, so a
`no-rules-copy` failure is a cue to re-read the pattern against the current agent file before it
is read as a regression. The three alternatives are not equally durable, and the grader decays
rather than breaking: `frozen-after-approval` is a tag name the plan format itself depends on and
will outlive any edit to the agent's prose, while the two quoted sentences are ordinary wording
that a rewrite can retire silently. Losing them costs two ways of catching a restatement and
keeps the third; the grader cannot read `agents/plan-executor.md` to notice, because a grader's
file source resolves inside the run's scaffold, not the plugin.

## Comment-rules tier baseline

Measured 2026-09-16, `--ablation none`, three runs a case, judge `opus`, $2.52 for the tier:

| case | score | pass% | the miss |
| --- | --- | --- | --- |
| `18-cmt-why-not-what` | 0.75 | 0% | `renamed-not-annotated` failed 3 of 3 — see below |
| `19-cmt-no-scenario-narration` | 1.00 | 100% | — |
| `20-cmt-public-private` | 1.00 | 100% | — |
| `21-cmt-rationale-once` | 1.00 | 100% | — re-measured after the prompt fix below; 0.75 / 0% before it |
| `22-cmt-no-process-artifacts` | 1.00 | 100% | — |
| `23-cmt-not-for-the-reviewer` | 1.00 | 100% | — |
| `24-cmt-never-split` | 1.00 | 100% | — |
| `25-cmt-budget-outranks-neighbour` | 1.00 | 100% | — |
| `26-cmt-neg-keep-the-why` | 1.00 | 100% | — |
| `27-cmt-neg-exception-respected` | 1.00 | 100% | — |

**`18-cmt-why-not-what` is the tier's one real finding, and it is about the rule rather than the
case.** All three runs produced the same file: the parameter stayed named `d`, and no comment was
written anywhere. So `no-restating` passes on a file with no comments to restate anything, while
the clause's second half — "if a rename would say it, rename" — never fires. The rule suppresses
the comment and does not produce the name that was supposed to replace it, leaving
`if (promo && d < promo.windowDays)` in a file that is now less legible than one with a bad
comment would have been. That is the clause to reword first, and this row is the instrument for
telling whether a rewording helped. Do not chase it to green by weakening the grader.

**One rewording has already been tried against it and reverted.** Adding "deleting the comment
and leaving the name is not the fix" to the clause — naming the exact move the runs make — moved
`18` not at all: 0.75 again, `renamed-not-annotated` failing 3 of 3, on the full tier re-measured
across the edit at $7.57. `27-cmt-neg-exception-respected` came back 0.87 in the same run against
1.00 before it, which looked like a possible regression and was not: the ablation below scores
that case 0.87 in *both* arms, so the dip is the case's own variance. A clause that measures
neutral is words that have not earned their place, in a section whose own rule is that over
budget means cut — so the sentence went back to what it was. Whatever is retried here, do not
retry that.

`21-cmt-rationale-once` failed the same way for the opposite reason, and that one *was* the
case's fault. Its `rationale-on-the-owner` grader wanted the reason recorded on `MAX_BATCH`, but
the prompt only asked for `upload` to be batched — demanding work the prompt put out of scope,
which the grader-design note above already warns against. The prompt now asks for the reason to
survive in the code without saying where, which is the part under test; all three runs then put
two lines on the exported constant and nothing in the consumer.

Both diagnoses came from `--keep-temp` workspaces. A red row in this tier means read the file
before touching the grader — the two rows above needed opposite fixes and looked identical in
the score table.

## What the rule text is worth: the hook-delivery ablation

Generated with `evals/make-ablation.py`, measured 2026-09-16, all ten cases, three runs an arm,
judge `opus`. The variants carry no `append_system_prompt`, so the with-arm gets the rule through
the session-start fallback and the without-arm gets nothing:

| case | with | without | Δ |
| --- | --- | --- | --- |
| `18-cmt-why-not-what` | 0.75 | 0.75 | +0.00 |
| `19-cmt-no-scenario-narration` | 1.00 | 1.00 | +0.00 |
| `20-cmt-public-private` | 1.00 | 1.00 | +0.00 |
| `21-cmt-rationale-once` | 1.00 | 1.00 | +0.00 |
| `22-cmt-no-process-artifacts` | 1.00 | 1.00 | +0.00 |
| `23-cmt-not-for-the-reviewer` | 1.00 | 1.00 | +0.00 |
| `24-cmt-never-split` | 1.00 | 1.00 | +0.00 |
| `25-cmt-budget-outranks-neighbour` | 1.00 | 0.67 | **+0.33** |
| `26-cmt-neg-keep-the-why` | 1.00 | 1.00 | +0.00 |
| `27-cmt-neg-exception-respected` | 0.87 | 0.87 | +0.00 |

**One clause out of the section has a measurable effect. Mean Δ +0.033.** Untold, the model
already keeps finding IDs out of comments, already declines to narrate what the code used to do,
already does not split one thought across two blocks, already leaves a legitimate why-comment
alone, already puts a rationale on the symbol that owns it. Writing those down changed nothing a
grader can see. That is not an argument for deleting them — a rule that costs nothing and holds
the line on a worse day is cheap — but it is a strong argument against spending more words on
them, and against reading a green tier score as the rule doing work.

**The clause that earns its place is the one that contradicts the model's default.** In a file
whose every neighbour carries a twelve-line comment block, the without-arm matched the local
style in two runs of three; the with-arm wrote two lines every time. That is the sentence "the
budget outranks the file you are editing: a neighbour with a twelve-line block is not a
precedent" — the only clause telling the model to do something it would not otherwise do, and the
only one that moved a number. Style-matching is the default it has to beat; the rest of the
section is already the default.

**`18-cmt-why-not-what` fails identically in both arms.** Not a weak clause — an inert one. Its
0.75 is what the model does with or without being told, which is why the rewording recorded in
the tier baseline above moved it by exactly zero. Anything aimed at it has to beat a default, the
way the budget clause does.

**`27-cmt-neg-exception-respected` scores 0.87 in both arms**, so the 0.87 it showed during the
rewording run was its own variance and not the edit's doing. `exception-not-cut` failing one run
in three regardless of whether the rule is present is a property of the case; it wants a look
before its row is read as a finding either way.

**Read the size as unproven.** Two failures of three, on one case, n=3 an arm. The direction
matches the mechanism and nothing regressed, but this cannot separate the clause from variance;
the command tier's note on Fisher exact applies unchanged. What ten cases establish that four
could not is the *shape* — the section's value is concentrated in one sentence, not spread.

Two operational notes, both paid for. The first attempt reported four cases at
1.00/1.00/0.60/0.50 and was entirely the session limit, which is what `check-run.py` above exists
for. The second was killed by the OS for memory at `-j 2` — the concurrency this README calls the
safer one — after completing three cases; the remainder finished at `-j 1`. Run this tier
serially, and validate whatever comes back.

## End-to-end tier baseline

Measured 2026-09-15. Phase 1 ran once, for two runs; phases 2 and 3 were then replayed over
its recorded result with `--phase1-json`, so the plans below were written once and executed
three separate times:

| case | score | pass% | phase1 cost | phase2 cost | date | the miss |
| --- | --- | --- | --- | --- | --- | --- |
| `e2e-01-ledger-report` | 1.000 | 100% | $1.09 | $5.71 | 2026-09-15 | none in these two runs — read the caveats below before trusting the number |

A perfect score on a first recorded baseline is the least trustworthy number this table can
carry, and this one has a documented reason to distrust it. Phase 1 was not re-run to produce
it — the same two plans have now gone through phase 2 three separate times. The first time
scored 13/15 and a total failure; the second, 15/15 twice; this recorded run, the third, 15/15
twice again. The plan was identical in all three; only the executor session differed. Two clean
runs on top of one attempt that wasn't is not evidence the plan travels reliably, it's a second
coin landing the same way — and the runs that did land there disagree with each other on how:
23 turns against 5, and 19 fixture tests the executor wrote for itself against 37, neither
of which counts toward score.

Before any of those three attempts, the very first live run never reached phase 2 at all. It
ran against the spec before it was widened to cover the `--format` and `migrate` rows, and the
work read as small enough that phase 1 answered in prose and never called the planning skill —
no plan file, nothing for phase 2 to execute. Widening the spec fixed that, and also more than
doubled phase 2's cost per run, from roughly $1.49 to roughly $3.59; this baseline's two runs
cost $2.33 and $3.38.

A score above zero also starts higher than it looks. Three of the fifteen acceptance rows — the
malformed-line checks for `report` and `migrate`, and the unknown-`--format` check — only ask
for a non-zero exit and a stderr message, which an unrecognized command already produces before
anything is implemented. 3/15 is the floor this case starts at, not a fifth of the work done.

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
- **The execute-plan command's later sections.** The command tier covers plan resolution and the
  dispatch itself (sections 0–2), but not section 3's review loop, section 4's batching of
  independent tasks, or section 5's commit — the last is excluded on purpose (D4): `tool_used`
  counts a run's Bash calls without attributing them to the supervisor or the executor, so a
  green `git commit` grader cannot show *who* committed.
- **A dispatch that paraphrases the executor's rules.** `no-rules-copy` matches wording quoted
  from `agents/plan-executor.md`, so a dispatch that restates those rules in its own words passes
  it while still failing the rule it stands in for. `no-header-copy` is narrower than it looks
  only in the same direction: its three sentinels each name the thing their frozen line
  constrains, so conveying that constraint carries the token, and what escapes is a restatement
  vague enough to have dropped all three. Neither can be closed with a judge — an `llm` grader's
  `focus` accepts `last_message`, `files`, `mock_calls` and `{source: file, path}`, and none of
  them expose an `Agent` call's input.
- **Whether the executor reads only its own slice.** Rule 1 tells it to read its task's range and
  not the rest of the plan; no grader can see what it read, only what it produced, so a case
  cannot distinguish scoped reading from a lucky guess.
- **Which of two things `12-exec-comment-budget` is measuring.** Its with-arm now carries both
  the rule and the hook — the rule since `hooks/session-start.py` gained its fallback, the hook
  as before — and its without-arm carries neither, so the Δ is the pair and cannot be split. To
  separate them the case would need a third arm with `PLAN_FLOW_COMMENT_BUDGET=off`, and a case's
  `env` only accepts `EVAL_`-prefixed names, which that variable is not.
- **The rule arriving the way it really arrives.** The `comment-rules` tier delivers the section
  through `append_system_prompt`, and since the session-start fallback the same text also arrives
  as a `SessionStart` payload — so in this tier the rule is now present twice, in two positions,
  neither of which is the `@`-import a configured machine uses. A tier score is evidence about
  the wording, not about the delivery. Dropping `append_system_prompt` and letting the fallback
  carry it alone is the obvious simplification, and the measurement for it is in
  `evals-ablation/`; do not make that change on the strength of the wording alone.
- **A comment in a file no grader names.** `focus` and `target` take one fixed path and no glob,
  so every comment-rules grader is pinned to a file the scaffold created. A violation the agent
  writes into a file it invented is invisible.
- **Whether case 25's judge counted the right block.** `new-comment-in-budget` asks the judge to
  ignore two long pre-existing comment blocks and grade only the one on the new function. A judge
  that misidentifies which block is new fails the case for a reason that has nothing to do with
  the rule; read the file before reading the verdict.
- **A plan whose code is genuinely all binding.** `block-labels` matches for a labelled fence, so
  a plan with zero `reference` markers because every block is correctly binding scores the same
  as a plan that just missed the labels. This is a limitation of the grader, not evidence of a
  defect.
- **Whether the end-to-end tier's own executor reads only its own slice.** Same limit as above,
  applied to phase 2: nothing watches what `claude -p /plan-flow:execute-plan` read, only what it
  produced, so a plan handed over whole reads the same as one scoped correctly by luck.
- **No without-arm for this tier.** Phase 1 runs with `--ablation none`; without the skill loaded
  there is no plan for phase 2 to execute, so there is nothing to hand it in the without-arm's
  place.
- **Whether the plan's own I/O matrix is honest.** The same agent that writes the plan in phase 1
  also writes its I/O & Edge-Case Matrix, and only the hidden acceptance suite counts toward
  score — a matrix that quietly narrows the spec scores the same as one that covers it in full.
  The agent effectively sets its own bar.
- **A score above zero meaning anything got built.** Three of the fifteen acceptance rows — the
  malformed-line checks for `report` and `migrate`, and the unknown-`--format` check — also pass
  against a fixture where nothing was implemented: an unrecognized command already exits
  non-zero with a stderr message and empty stdout, which is exactly what those checks want.
  3/15 is the floor this case starts at, not a fifth of the work done.
- **How much of a score is plan quality versus execution luck.** Phase 1 is expensive enough that
  a baseline reuses its plans rather than regenerating them, so the tier's score also carries
  whatever phase 2 does with an identical plan on a given day. The two plans behind this
  baseline have now been handed to phase 2 three times: 13/15 and a total failure, then 15/15
  twice, then the 15/15 twice recorded above. A row that shows two clean runs cannot tell that
  apart from a plan that travels reliably.
- **Whether phase 2 actually halted.** Halt detection matches phrasing lifted from
  `agents/plan-executor.md` and `commands/execute-plan.md`; it has never been checked against a
  transcript of a real halt, so a `"halted"` status is a string match, not a confirmed one.

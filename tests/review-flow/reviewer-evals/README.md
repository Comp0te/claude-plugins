# review-flow reviewer evals

Measures, per review-flow reviewer agent, whether it catches a planted defect, whether it scopes
it correctly, and how many false positives it raises — on the defect diff and on a clean twin of
the same shape. Lives outside `plugins/` so it never ships to installs.

## Running it

Two tiers: a free offline one that never calls a model, and a paid one that does.

### Free tier: grader and fixture tests

```bash
python3 -m unittest discover -s tests/review-flow/reviewer-evals -p 'test_*.py' -v
```

Stdlib `unittest`, no network, no `claude` invocation — `test_run.py` drives `run.py` as a
subprocess against `fake_claude.py`, a stand-in that never leaves the machine. Run this before
any paid run and after any change to `grade.py`, a `case.json`, or a fixture tree.

### Paid tier: a live run

```bash
python3 tests/review-flow/reviewer-evals/run.py --runs 3 -j 2
```

Needs network access to `api.anthropic.com` and an authenticated `claude` CLI (OAuth — this
runner never passes `--bare`, which would drop it). Each of the 9 case/variant rows runs 3 times
against the real agent, an isolated two-commit git repo per job under the system temp directory.
Writes raw JSON and metadata under a fresh `results/<UTC timestamp>/`, then a graded
`results/<...>/summary.md`. A full 27-job run at `-j 2` costs about **$3.54** and takes
**~19 minutes** wall clock; a one-case, one-run smoke (`--case '01-*' --runs 1`) is a cheap way to
confirm login and network before a full run.

`--case` filters by glob over case directory names (e.g. `--case '01-*'`). `--out` overrides the
results directory. `--regrade <dir>` rewrites `summary.md` from files already on disk without
invoking the agent — use it after an approved change to a `case.json`'s `expected`/`allowed`
points, to see the effect on an existing run without spending anything.

## Local gate

From the repository root, in your own terminal (`claude plugin eval` and the reviewer's `claude -p`
children fail with EPERM inside a sandbox):

    python3 scripts/run-evals.py --plugin <name>      # diff against the plugin's last release tag
    python3 scripts/run-evals.py --since <ref>        # diff against any ref
    python3 scripts/run-evals.py --all                # every plan-flow tier and every reviewer case
    python3 scripts/run-evals.py --smoke              # one plan-flow case and one reviewer case
    python3 scripts/run-evals.py --plugin <name> --dry-run   # print the selection and estimate only

It prints the selection and an API-list estimate before any model call, asks for confirmation above
$10 (`--yes` skips the prompt; without a TTY it exits 3 instead of running), runs the plan-flow
tiers with `--ablation none` and `--max-cost-usd` set to 1.5 times the invocation's estimate
(minimum $2), then gates the results. Exit 0 ok, 1 regression, 2 harness failure or bad input,
3 needs confirmation. Runs use the `claude` CLI as logged in on the machine and draw on the
subscription's usage limits; no credential is read or passed.

This suite is selected by changes to the review-flow reviewer agents and `brief.md`. Baseline:
`tests/review-flow/reviewer-evals/baselines/baseline.json`.

Thresholds (`scripts/eval-gate.py`): a plan-flow case regresses when its mean score drops more
than 0.20 below baseline, or a grader the baseline passed fails every run (needs 2+ runs). A
reviewer row regresses when its caught, scope-ok or claim-ok rate drops by more than 0.34
(one run in three), or its false-positive mean rises by 1.0 or more. An invalid run is a harness
failure, never a score. Cases with no baseline entry are reported as unbaselined and do not fail.

Re-recording: a baseline is written only on the author's say-so. Run
`python3 scripts/run-evals.py --all --yes`, then
`python3 scripts/eval-gate.py --write-baseline --plan-flow <run dir>/pf-*.json --reviewer <dir>/summary.json`
on the result files, review the diff, and commit the baseline files. Case 30 is never selected by
the entry point; record it from its own `--tag working-agreements --runs 3` result.

Cost of a run (API-list equivalent; on a subscription it is usage, not money):

| Selection | Runs | Estimate |
| --------- | ---- | -------- |
| Smoke | 1 plan-flow + 1 reviewer | about $0.45 |
| One reviewer agent changed (2-3 cases) | 12-18 | about $5-7 |
| `execute-plan.md` changed (plan-command) | 15 | about $2 |
| Working agreements / session-start hook | comment-rules + plan-command, about 45 | about $5 |
| Plan-writing skill changed | 24 | about $11 |
| `--all` (four plan-flow tiers + ten reviewer cases) | about 180 | about $50; 1.5-2 h at `-j 2` |

Per-run figures behind the estimate: comment-rules $0.08, plan-command $0.13, plan-writing $0.45,
plan-execution $0.60 (unmeasured), reviewer $0.10 per row-run (measured 2026-10-27 at $0.03-0.09; the
earlier $0.38 overstated $3.55 / 27).

## Cases

Each case cites the incident it reproduces by handoff file and finding id (cases 11 and 12 are synthetic).
A case with `requirement.<variant>.md` gets that text as a `<requirement>` block in the brief; the same text sits in the variant's `docs/task.md`, so a finding may cite either. Fixtures carry no
customer data or verbatim text from those handoffs.

| Case | Reviewer | Source |
| --- | --- | --- |
| `06-unreachable-second-start` | `deletion-check` | a branch-review handoff, F22 (gate verdict false positive: no in-flight guard, but the control that could start a second flow is not rendered while one is live). Defect: the button still renders while a flow runs. Clean: the button is hidden while `status === 'running'`. |
| `07-removal-required-by-ac` | `deletion-check` | a branch-review handoff, F14 (dropped: a button was removed only for statuses the task's acceptance criteria exclude). Defect: also removed for `ACTIVE`, which `docs/task.md` keeps. Clean: removed for exactly the excluded statuses. |
| `08-vacuous-test-claim` | `pr-test-analyzer` | a branch-review handoff, F36 (the agent said a test could not detect removal of a `.catch(() => {})`; a probe showed the runner fails on the unhandled rejection). Defect: the failing-read test installs a rejecting reader but never calls `refresh()` and asserts only a value that holds either way. Clean: the same test also awaits `assert.doesNotReject(refresh())`. |
| `09-pre-existing-at-base` | `silent-failure-hunter` | audit round 5 §2.3, a PR review F2 (`scope: introduced` on a gap that existed equally at base). Defect: the diff reworks `syncOne` beside an empty `catch {}` in `syncAll` that is identical before the change, so a finding on it must say `pre-existing`. Clean: the same change also makes `syncAll` log and rethrow. |
| `10-count-claims` | `silent-failure-hunter` | audit round 5 §2.3, a PR review F3 ("five dispatch sites" where there were four; "every render" where only a render without a stored theme was affected) and F7 ("eight of nine" where it was seven). Defect: four `dispatch(...).catch(() => {})` sites across four files, one inside `if (!storedTheme)`; a finding on them must not miscount or universalise (`expected.forbidden`, reported as `claim ok`). Clean: all four route the error through `reportError`. |
| `11-requirement-harmful-retry` | `silent-failure-hunter` | a requirement that asks for retrying a failed card charge, with code that does exactly that. Defect: `requirement.defect.md` says "retry the charge up to 3 times" and `payOrder` calls `charge(order.total)` with no idempotency key, so a timed-out charge that went through is charged again; the catch must name the requirement (`expected.keywords` are attribution words only, so a finding about the code alone does not count). Clean: the requirement adds "with the same idempotency key" and the code passes one. |
| `12-requirement-undefined-boundary` | `pr-test-analyzer` | a requirement that leaves a case undefined, with code that decides it silently. Defect: `requirement.defect.md` says "over 100" gets the discount and "under 100" pays shipping, so an order of exactly 100 gets neither. Clean: the requirement says "100 or more" and the code matches. `allowed` absorbs a finding that no test prices an order of exactly 100, which holds in both variants. |

## Reading `summary.md`

One row per case/variant. Columns:

- **caught / scope ok** — only meaningful on `defect`: whether any finding matched one of the
  case's `any_of` points (by citation overlap and keyword), and whether one of those matches
  carried the expected `scope`. `-` on `clean` (there is nothing to catch).
- **claim ok** — only on a `defect` row whose case lists `expected.forbidden` (regexes, matched
  case-insensitively): runs whose caught findings match none of them, over runs caught. A caught
  finding that states a wrong count or quantifier ("five call sites") is caught but not claim ok.
  `-` when the case has no `forbidden` key.
- **fp mean / fp max** — findings that matched neither an `any_of` point nor an `allowed` point,
  averaged and maxed across the row's runs. `allowed` entries absorb real, expected-but-off-target
  issues (an incidental deletion, a pre-existing gap) so they don't count against the agent.
- **unparsed** — the run wrote finding records (a citation, a "why it matters"/`evidence` line)
  but the parser never found a `scope: introduced|pre-existing` it recognized. Never read as zero
  findings; see "Known parser limits" below.
- **invalid** — the run did not finish cleanly (non-success `subtype`, `is_error`, empty `result`,
  zero cost, or a timeout past `--timeout`). Never scored as zero findings either, and makes
  `run.py` exit non-zero.

**Case 05, directly below case 01 in the table, is the fence check.** It reuses case 01's fixture
trees verbatim (`fixture_from`) with the same `expected`/`allowed` points, but wraps the PR
description in `<pr-author-text>` containing an instruction telling the reviewer to stand down.
Its row should read the same as case 01's `defect` row; a divergence means the injected text
changed the agent's behavior, not the fixture.

## Known parser limits

The parser (`grade.py`) is deliberately tolerant rather than strict — this
baseline measures today's agent prompts against it as-is, not a parser tuned to them. Observed
limits, kept as measured rather than patched:

- **Case 02's clean twin is disputable by design**: moving the admin check into the route leaves
  the exported `deleteUsers` unguarded for any other caller, and agents fairly say so. It stays
  counted as an fp, so read case 02's clean fp column with that in mind. Example:
  `recorded/deletion-check-bracketed-findings-clean.txt`.
- **A `scope:` written inside a "not reported" / "cleared" note can still be picked up** as if it
  were a live finding — the tolerant parser has no notion of a negated context, only of where the
  word `scope` appears.
- **A "no findings" answer with a grounding citation trips the unparsed heuristic**: citing a known
  file as evidence for finding nothing is enough for `parse_findings` to treat the answer as
  unparsed rather than as zero findings, since it can't tell "grounded, found nothing" from "wrote
  records the parser couldn't score" without a `scope` to anchor on.
- **A bare filename with no directory prefix never resolves to a known file**, even when it names
  exactly one: case 03's clean-0 cites `runRequest.ts:11-13` (no `src/request/` prefix) in a
  pre-existing finding, and that finding is graded with no citation at all. Resolving by unique
  basename would also turn in-prose mentions like `` `consumer.ts:8` `` into citations of the
  wrong finding.

## `recorded/`

Real agent answers pulled from a live run, one raw `result` string per file, used by
`test_grade.py` to assert finding counts and citations a human read from the raw text. They exist
to guard segmentation behavior a synthetic answer didn't reproduce — each file's test says which
run it came from and what it guards. Not exhaustive: add one when a live run's layout breaks an
assumption a synthetic `SegmentationTests` case doesn't already cover.

## `baselines/`

`baselines/<run date>.md` is a copy of one full run's `summary.md`, kept for comparison against
future runs. Not regenerated automatically — copy it by hand after a run you intend to keep as a
reference point.

`baselines/2026-09-27-aligned-keys.md` is the current one, taken after the reviewers switched to
the six aligned output keys (`file:`/`scope:`/`issue:`/`why:`/`fix:`/`evidence:`).

## `brief.md`

Copies text verbatim from `plugins/review-flow/commands/pr-review.md` (the gate-status framing,
the "run nothing but targeted checks" paragraph, the executable-checks sentence) so agents are
graded against the same brief `/pr-review` would give them. **Update it whenever that source text
changes**, or the eval measures a brief no reviewer will ever actually see. `test_run.py`'s
`test_brief_and_git_log_carry_no_case_identifying_words` also asserts the rendered brief and the
workspace's git log carry no word that would tell the agent it is under test or which twin
(`defect`/`clean`) it holds — including `evaluation`, `eval`, `fixture`, `defect`, `clean`, and
`planted` — and that the workspace path itself (`repo-<hex>`, no case name or variant) doesn't
leak it either.

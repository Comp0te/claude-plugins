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
`results/<...>/summary.md`. The full 27-job baseline (2026-09-26, `-j 2`) cost **$3.54** and took
**~19 minutes** wall clock; a one-case, one-run smoke (`--case '01-*' --runs 1`) is a cheap way to
confirm login and network before a full run.

`--case` filters by glob over case directory names (e.g. `--case '01-*'`). `--out` overrides the
results directory. `--regrade <dir>` rewrites `summary.md` from files already on disk without
invoking the agent — use it after an approved change to a `case.json`'s `expected`/`allowed`
points, to see the effect on an existing run without spending anything.

## Reading `summary.md`

One row per case/variant. Columns:

- **caught / scope ok** — only meaningful on `defect`: whether any finding matched one of the
  case's `any_of` points (by citation overlap and keyword), and whether one of those matches
  carried the expected `scope`. `-` on `clean` (there is nothing to catch).
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

The parser (`grade.py`) is deliberately tolerant rather than strict-after-key-alignment (D3) — this
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
the six aligned output keys (`file:`/`scope:`/`issue:`/`why:`/`fix:`/`evidence:`); it supersedes
`baselines/2026-09-26.md` and lists the per-row changes against it.

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

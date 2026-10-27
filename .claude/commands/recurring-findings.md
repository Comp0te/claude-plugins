---
description: Triage recurring review findings across projects and propose where each recurring class should live (lint, hook, reviewer, skill, project, agreements)
---

Run one triage session over review findings from every project. The script counts and
applies thresholds; you classify and propose. Run from the root of this repository.

Nothing outside the ledger is written unless the human approves that specific proposal in this
session, and the ledger is written only through `scripts/recurring-findings.py`. If any script
call exits 2, stop, show its message, and make no further writes (except `assign`, below).

Do not classify plan-change records: they are carried in the records file and ignored here.
Do not compute counts, thresholds, or recurrence yourself. Do not re-propose a class the human
rejected unless the digest lists it again (the script reopens it after >=2 more subjects).

## Inputs

- Project roots: `$ARGUMENTS` if given, otherwise every checkout under `~/Projects` (`~/Projects/*/`);
  each root is one project checkout, not a parent directory.
- Ledger: `~/.claude/recurring-findings/ledger.json` (untracked, outside this repository; create
  the directory if missing). A different `--ledger` path may be passed for a dry run.
- Agreements file: `plugins/plan-flow/references/working-agreements.md`.
- Work directory: `$WORK`, default `$TMPDIR`; holds the records and assign files. A different
  directory may be given, like `--ledger`.

Below, `$LEDGER` is the ledger path, `$RECORDS` is `$WORK/rf-records.jsonl`, and the assign file
is `$WORK/rf-assign.json`.

## 1. Records

```bash
python3 scripts/sdlc-metrics.py --records "$RECORDS" <roots>
```

## 2. Classify

```bash
python3 scripts/recurring-findings.py unclassified --records "$RECORDS" --ledger "$LEDGER"
```

It prints JSON with the existing `classes` and the `findings` that have no class yet. If
`findings` is empty, skip to step 3 and do no classification.

Otherwise group those findings into classes. A class is a defect pattern, stated stack-neutrally
where the evidence allows. Reuse an existing class id whenever one fits. A one-off finding gets
its own class. Class ids match `^[a-z0-9][a-z0-9-]*$`.

Write `$WORK/rf-assign.json`:

```json
{
  "classes": { "<new-id>": { "name": "<short name>", "description": "<one sentence>" } },
  "assignments": { "<record key>": "<class id>" }
}
```

`classes` lists only new ids; `assignments` maps every finding key from the output to a class id.
Class breadth: a class is drawn so that one rule, checklist line or hook would stop every
finding in it; findings that would need different rules are different classes.

Then run:

```bash
python3 scripts/recurring-findings.py assign --records "$RECORDS" --ledger "$LEDGER" --input "$WORK/rf-assign.json"
```

If `assign` exits 2, its message names the invalid input: fix the assign file and rerun. This is
the one exit 2 that is retried rather than stopping the session.

## 3. Digest

```bash
python3 scripts/recurring-findings.py digest --records "$RECORDS" --ledger "$LEDGER"
```

It lists candidates (classes spanning >=2 distinct review subjects, each marked
`agreements-eligible` or not), demotions (`superseded`, `ineffective`, `quiet`), and the
agreements budget. Optional flags: `--agreements <path>`, `--budget <lines>` (default 60),
`--quiet-after <n>` (default 10).

## 4. Route

For each candidate, walk the rungs top to bottom and propose the **first** one whose test holds.
Cost is what the home spends on every future session: the first two spend nothing, the middle two
load only when relevant, the last two load every session.

1. **lint** — the defect is recognisable from code shape alone (a forbidden call, an empty
   catch, a missing wrapper), another contributor would write it too, and the affected
   project(s) run a linter or static analyser that does not already catch it (read the config;
   never assume). Home: that config, created when the project runs the tool without one.
   Proposal: the rule, and a positive and negative example drawn from the evidence.
2. **hook** — the behaviour must always hold and is checkable at edit or commit time from a path
   or a file's content, but not as a code-shape rule (an edit under a path the active plan marks
   Ask First; a generated file edited by hand). Home: a hook in the project, or in a plugin of
   this repository when it applies across projects. Proposal: the trigger, the check, and the
   message the hook prints.
3. **reviewer** — a defect class a reviewer agent owns or should own (test quality, error
   handling, type design, comment rot, a project's own domain reviewer), unless that agent is
   already in the class's `found by`: a reviewer that already catches it needs no new line, the
   recurrence is in authoring, so continue down the ladder. Home: that agent's checklist.
   Proposal: one checklist line plus a companion eval-case sketch.
4. **skill** — behaviour that belongs to a workflow step rather than to code review (how a plan
   is written, how a task is executed, how verification is reported). Home: that skill's
   reference file. Proposal: the line, the section it goes in, and a companion eval-case sketch.
5. **project** — all evidence is in one project and none of the above fits. Home: that project's
   own instructions file. Proposal: one line.
6. **agreements** — only when the script marks the class `agreements-eligible` **and** the
   behaviour does not depend on one stack **and** no rung above fits **and** `budget-check` on the
   proposed text reports that it fits — otherwise the proposal names the existing line it
   replaces or shortens, passed to `budget-check --replaces`. One or two lines in the file's own
   style, plus a companion eval-case sketch.
7. **none** — recurring by label only (unrelated bugs that share a shape), or not worth a home.
   Not presented one by one: listed together after the other proposals, one line each with the
   reason, and recorded with `decide --status rejected` once the human confirms the list.

**Class breadth:** a class is drawn so that one rule, checklist line or hook would stop every
finding in it; findings that would need different rules are different classes.

**Fit:** a rung fits when it stops most of the class's findings; the proposal names the rest,
which are routed on their own if they recur. When the home already holds text that covers the
class, the proposal quotes that line instead of adding one; on approval it is recorded as landed
with that line and no edit is made. When the homes are local to each affected project at the
same rung, one proposal names every target, and each gets its own `decide --status landed`.

**Generic text:** before presenting a proposal whose target is in this repository, its change
text and eval sketch go through `check-text`; a hit is reworded before presenting.

**Demotions** from the digest are proposals too: `superseded` → remove the text line now that
lint or a hook enforces it; `ineffective` → escalate to a lower-numbered rung or rework the text
with an eval, never add a second line saying the same thing louder; `quiet` → move the text to
the cheapest rung that still covers it (rung 3–5) instead of deleting it.

Mechanics:

- Rung 3 reads the `found by: a×n, ...` list at the end of the class's digest line.
- Rung 6: write the proposed text to a file in `$WORK`, then
  `python3 scripts/recurring-findings.py budget-check --add <file> [--replaces <start>-<end>]`
  (optional `--agreements <path>`, `--budget <lines>`). It prints JSON with `fits`.
- `check-text` takes the records and a file holding the change text and eval sketch:
  `python3 scripts/recurring-findings.py check-text --records "$RECORDS" --input <file>`.
  It prints `clean` (exit 0) or one hit per line (exit 1).
- Rung 1 uses the same bar as the rule-candidates section of
  `plugins/review-flow/commands/branch-review.md`: syntactically recognizable, repeatable by
  someone else, not already covered. Read that section; do not paraphrase it.
- Rung 3 targets are the agents under `plugins/review-flow/agents/` and any project-local
  reviewer. Rung 4 targets are skill references and agents under `plugins/plan-flow/`.
- Rung 6 text follows the Code Comments conventions of the agreements file: read them first.
  A rung 6 proposal that neither fits nor names a line to replace is not presented.
- Any proposal that deletes or rewords an existing agreements line (demotions included) is
  presented, never applied unasked.
- Text for any instruction file has no finding IDs, no review references, no process narration.
- A change to a project's own files lands in that project, not in this repository.
- Nothing committed to this repository names or identifies a project: proposals that land here,
  and their eval sketches, are stated generically (no project names, paths, branch or ticket
  names, or code). Evidence lines in the presented proposal may show record keys; the text to
  be written may not.

## 5. Present

One proposal at a time, in this format, then wait for approve / reject / defer:

```text
### <class id> — <name>
evidence: <n> findings · <n> subjects · projects: <a, b>
  - <record key> — <title or first clause of issue>      (at most 5 keys, then "+N more")
rung: <number>. <name> → <target file(s) or project(s)>
why not cheaper: <one sentence per skipped rung above this one>
change:
  <exact text, rule, or hook spec>
eval sketch: <input → expected behaviour>      (rungs 3, 4, 6 only)
```

The `rung:` line may name several targets. Rung 7 items are not presented this way: after the
last proposal, list them together, one line each with its reason, and ask for one confirmation.

Record the answer:

- **Approve** — apply the edit to the named file only (none when the home already holds the
  quoted line) and show the diff. Then record `landed` once per target:
  `decide --class <id> --status landed --rung <lint|hook|reviewer|skill|project|agreements> --target <file> --text "<the text>"`.
  There is no separate `accepted` step.
- **Reject** — `decide --status rejected`. The class is not proposed again until it gains >=2
  subjects.
- **Defer** — `decide --status deferred`. It is proposed again next run.

Every `decide` call takes the same base flags:

```bash
python3 scripts/recurring-findings.py decide --records "$RECORDS" --ledger "$LEDGER" --class <id> --status <rejected|deferred|landed>
```

For a `landed` home, `--rung` is one of `lint, hook, reviewer, skill, project, agreements, none`,
and `--target` and `--text` are required. Keep the stored `--text` as generic as the change itself.

## 6. Close

Run `digest` again, print it, and print the ledger path.

---
description: Triage recurring review findings across projects and propose where each recurring class should live (lint, hook, reviewer, skill, project, agreements)
---

Run one triage session over review findings from every project. The script counts and
applies thresholds; you classify and propose. Run from the root of this repository.

Nothing outside the ledger is written unless the human approves that specific proposal in this
session, and the ledger is written only through `scripts/recurring-findings.py`. If any script
call exits 2, stop, show its message, and make no further writes.

Do not classify plan-change records: they are carried in the records file and ignored here.
Do not compute counts, thresholds, or recurrence yourself. Do not re-propose a class the human
rejected unless the digest lists it again (the script reopens it after >=2 more subjects).

## Inputs

- Project roots: `$ARGUMENTS` if given, otherwise every checkout under `~/Projects` (`~/Projects/*/`);
  each root is one project checkout, not a parent directory.
- Ledger: `~/.claude/recurring-findings/ledger.json` (untracked, outside this repository; create
  the directory if missing). A different `--ledger` path may be passed for a dry run.
- Agreements file: `plugins/plan-flow/references/working-agreements.md`.

Below, `$LEDGER` is the ledger path and `$RECORDS` is `$TMPDIR/rf-records.jsonl`.

## 1. Records

```bash
python3 scripts/sdlc-metrics.py --records "$TMPDIR/rf-records.jsonl" <roots>
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

Write `$TMPDIR/rf-assign.json`:

```json
{
  "classes": { "<new-id>": { "name": "<short name>", "description": "<one sentence>" } },
  "assignments": { "<record key>": "<class id>" }
}
```

`classes` lists only new ids; `assignments` maps every finding key from the output to a class id.
Then run:

```bash
python3 scripts/recurring-findings.py assign --records "$RECORDS" --ledger "$LEDGER" --input "$TMPDIR/rf-assign.json"
```

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
   project(s) have a lint or static-analysis config that does not already catch it (read the
   config; never assume). Home: that config. Proposal: the rule, and a positive and negative
   example drawn from the evidence.
2. **hook** — the behaviour must always hold and is checkable at edit or commit time from a path
   or a file's content, but not as a code-shape rule (an edit under a path the active plan marks
   Ask First; a generated file edited by hand). Home: a hook in the project, or in a plugin of
   this repository when it applies across projects. Proposal: the trigger, the check, and the
   message the hook prints.
3. **reviewer** — a defect class a reviewer agent owns or should own (test quality, error
   handling, type design, comment rot, a project's own domain reviewer). Home: that agent's
   checklist. Proposal: one checklist line plus a companion eval-case sketch.
4. **skill** — behaviour that belongs to a workflow step rather than to code review (how a plan
   is written, how a task is executed, how verification is reported). Home: that skill's
   reference file. Proposal: the line, the section it goes in, and a companion eval-case sketch.
5. **project** — all evidence is in one project and none of the above fits. Home: that project's
   own instructions file. Proposal: one line.
6. **agreements** — only when the script marks the class `agreements-eligible` **and** the
   behaviour does not depend on one stack **and** no rung above fits **and** the digest shows the
   budget holds after adding it — otherwise the proposal names the existing line it replaces or
   shortens. One or two lines in the file's own style, plus a companion eval-case sketch.
7. **none** — recurring by label only (unrelated bugs that share a shape), or not worth a home.
   Recorded with `decide --status rejected` and a one-line reason given to the human.

**Demotions** from the digest are proposals too: `superseded` → remove the text line now that
lint or a hook enforces it; `ineffective` → escalate to a lower-numbered rung or rework the text
with an eval, never add a second line saying the same thing louder; `quiet` → move the text to
the cheapest rung that still covers it (rung 3–5) instead of deleting it.

Reference points when routing:

- Rung 1 uses the same bar as the rule-candidates section of
  `plugins/review-flow/commands/branch-review.md`: syntactically recognizable, repeatable by
  someone else, not already covered. Read that section; do not paraphrase it.
- Rung 3 targets are the agents under `plugins/review-flow/agents/` and any project-local
  reviewer.
- Rung 4 targets are skill references and agents under `plugins/plan-flow/`.
- Rung 6 text follows the Code Comments conventions of the agreements file: read them first.
  The file stays within its line budget, or the proposal names the existing line it replaces or
  shortens. A rung 6 proposal without that is not presented.
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
  - <record key> — <title or first clause of issue>
rung: <number>. <name> → <target file or project>
why not cheaper: <one sentence per skipped rung above this one>
change:
  <exact text, rule, or hook spec>
eval sketch: <input → expected behaviour>      (rungs 3, 4, 6 only)
```

Record the answer:

- **Approve** — apply the edit to the named file only and show the diff. Then
  `decide --status accepted`. Record `landed` only once the human confirms the edit is kept (or
  it was committed):
  `decide --class <id> --status landed --rung <lint|hook|reviewer|skill|project|agreements> --target <file> --text "<the text>"`.
- **Reject** — `decide --status rejected`. The class is not proposed again until it gains >=2
  subjects.
- **Defer** — `decide --status deferred`. It is proposed again next run.

Every `decide` call takes the same base flags:

```bash
python3 scripts/recurring-findings.py decide --records "$RECORDS" --ledger "$LEDGER" --class <id> --status <accepted|rejected|deferred|landed>
```

For a `landed` home, `--rung` is one of `lint, hook, reviewer, skill, project, agreements, none`,
and `--target` and `--text` are required. Keep the stored `--text` as generic as the change itself.

## 6. Close

Run `digest` again, print it, and print the ledger path.

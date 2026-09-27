
```
rounds:
  - round 1 @ <head-sha> — reviewed YYYY-MM-DD — dispatch→agents <N>m, agents→anchors <N>m, anchors→report <N>m — low-dropped <N> — mb <merge-base-sha>
published-log: (none)
```

`rounds:` — one line per round, ascending. A review round writes `reviewed <date>`; publication appends `, published <date>` to its own line; a re-check appends a new line, `- round <k> @ <sha> — rechecked YYYY-MM-DD`.

**`mb <merge-base-sha>` closes the round line, and every round writes its own.** The commit the head was compared against for that round — `git merge-base <head-sha> origin/<base>` at the time. It goes last, past everything `/pr-publish` matches on, so it is inert to that command's freshness test.

It exists for one case, and nothing else in the file can answer it: **the base branch moves between rounds.** That happens whenever this pull request sits in a stacked chain — the parent PR lands a commit, or is restacked, and this branch is rebased onto the new base. The head SHA then changes without the author having written anything, and a two-dot diff `<old-head>..<new-head>` is a mixture of their work and the base's advance with no seam in it. With both rounds' merge bases recorded, the seam is exact: `<old-mb>..<new-mb>` is the base's advance and belongs to whoever wrote it, and a `git range-diff <old-mb>..<old-head> <new-mb>..<new-head>` is what the author actually did. Without the field the earlier merge base has to be reconstructed, which only works while the base advanced by fast-forward — the one condition a restack breaks.

**Every round line carries its own three timings, and the round that produced them writes them.** Wall clock in whole minutes, measured from that round's own start: `dispatch→agents` is the first agent dispatched to the last one reported, `agents→anchors` is that moment to anchors resolved, `anchors→report` is anchors to the report footer printed. Write `—` for a stage this round did not run. Keep them on the round's own line and after the date: `/pr-publish` locates a re-check by matching the marker and the SHA on one `rounds:` line, so anything appended past them is inert to it. Without these the pipeline has no duration data at all — every claim it has made about its own cost was derived from the order of its stages rather than measured, and nothing distinguishes a change that helped from one that did not.

**`low-dropped <N>` is the last field before `mb`, and the round that dropped them writes it.** The count of findings this round rated Low and discarded at classification — `low-dropped 0` when there were none, never omitted. It goes here because the Low drop is the one irreversible decision in the flow: a Low is not authored, not anchored, not written to this file and not written to the deferred log, so unless the number is recorded at the moment it is taken, nothing downstream can ever recover it. The disclosure the report already makes is not enough — the report is not archived, so the count survives only in a chat transcript nobody re-reads. The question it exists to answer is whether the bar is discarding real work: across the reviews measured so far Low fell from half the corpus to none of it while the mass moved *into* Medium rather than out of the review, and that migration is invisible without this field.

**A publication also records what the gate cost, appended to its own round line as `gate <N>m over <K> findings, <C> rationale-wrong`.** Wall clock in whole minutes from the gate's dispatch to its verdicts returned; `<K>` is how many findings entered it; `<C>` is how many came back `CONFIRMED, RATIONALE WRONG`. Write `gate 0m over 0 findings` when nothing needed gating, and `— gate skipped: <why>` when the gate could not run at all. The gate is the most expensive single block in the pipeline and the only one still costed from two figures somebody typed in by hand — the round timings measure everything up to the report and stop just short of it. `<C>` is there so the obvious question becomes answerable: whether a wrong rationale costs more agent time to settle than a sound one, which decides whether the gate can ever be made cheaper rather than merely shorter.

`published-log:` — `(none)` until something has been sent. After the first send, one entry per finding that reached the pull request:

```
published-log:
  - F<n> @ <file>:<line> — <comment-url> — "<first line of the comment body>"
```


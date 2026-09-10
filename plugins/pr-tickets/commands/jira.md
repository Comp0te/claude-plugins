---
description: Triage what a PR review deliberately left unposted — pre-existing findings, the deferred-work log, and work the PR's author agreed to defer. Cheap filters and a Jira dedupe first, then you pick the shortlist, then the picked rows are verified against the base branch before any ticket is created.
argument-hint: <pr-number>
---

Triage the unposted remainder of the review of pull request `$ARGUMENTS` and turn what deserves it into Jira tickets.

## Preflight — stop here if either is missing

Check both before reading any findings file, and report what is missing rather than working
around it:

1. **Issue-tracker tooling that can create an issue.** If this session has no tool for
   creating a Jira issue, stop and say so plainly, naming what would need to be connected.
   Write nothing, and never present an approved payload as though it had been filed.
2. **A verification agent for review findings.** This command files tickets for problems the
   review classified as pre-existing, and every one of them is confirmed against the base
   branch before a ticket exists. If no such agent is available in this session, stop and say
   that the review flow this command depends on is not installed. Filing an unverified
   finding creates a ticket nobody can act on and that nobody will close.

**Bind the PR number once as `<N>` and use `<N>` everywhere below.** Never re-expand the raw argument text into a later command line: the argument routinely carries a long instruction block alongside the number, and re-expanding it at each mention copies that whole block into context several times over, for nothing.

This command writes to **Jira** and to nothing else external. You MUST NOT post comments, reviews, replies, thread resolutions, or approvals to GitHub, and MUST NOT modify any file tracked by git. The only files you may write are `.claude/reviews/pr-<N>-findings.md` and `.claude/reviews/pr-<N>-deferred.md` in the main repository root, plus scratch directories outside the repository. Nothing reaches Jira until the user has approved the final ticket list in this session, with the full payload of every ticket written to a file they can open.

**Head-SHA freshness is deliberately not a gate here.** `/pr-publish` stops when the PR has moved because its comments anchor to diff lines. Nothing in this command anchors to a diff: a pre-existing problem is true whatever the author pushed since, and the line numbers that matter are the base branch's, resolved in step 3. Do not refuse to run because the head moved, and do not send the user to `/pr-recheck` for that reason.

**The order of this command is deliberate: cheapest decisions first, the user's selection second, the expensive verification last, on the survivors only.** Most rows are settled by a rule that needs nothing but the findings file and a Jira search, and verifying a row that a one-line rule was about to drop is wasted work. Do not reorder it, and in particular do not reach for the base tree in step 2 to decide something step 2 can decide without it.

## 1. Collect the three inputs

- `$ARGUMENTS` empty: ask for a PR number and stop.
- Read `.claude/reviews/pr-<N>-findings.md` from the repository root. Missing: stop and tell the user to run `/review-flow:pr-review <N>` first — the plugin-qualified form, with the number substituted, so it can be pasted as-is. **Never reconstruct findings here** — this command triages, it does not review. A row invented in this step becomes a ticket nobody verified.

Rows come from three places. Collect all three before recommending anything: the sets overlap, and a row seen from two directions carries more than either alone.

### A. Held pre-existing findings

Every finding with `verdict: hold` **and** `scope: pre-existing`, **excluding any that already carries `ticketed <KEY>`**.

`dropped` is never included — the review or the gate settled it. `posted`, `replied` and `resolved` are not included either; they reached the author and are that thread's business, except where they come back through source C below.

**The `ticketed` exclusion is the one that is easy to miss, and it is the one that files a duplicate.** Step 6 records a promoted finding as `verdict: ticketed <KEY>` *alongside* its existing verdict and deliberately leaves the verdict at `hold` — so on a second run the finding still matches `hold` + `pre-existing` and comes back through this source unless it is filtered here. Source B's own filter (`promoted:` / `skipped:`) does not cover it: the dedupe below keeps the row from the findings file, which is authoritative, so a log entry marked `promoted:` drops out while the finding it came from survives. Filter on `ticketed` here, at collection, before anything is classified and before anything is composed.

**If no verdict has been resolved yet** — every finding still `pending`, because `/pr-publish` has not run for this round — fall back to `scope: pre-existing` regardless of verdict, and say in the report that the hold set is provisional: publication may yet move some of these. Do not run `/pr-publish` yourself to settle it.

**Do not skip the verification in step 3 on the grounds that `/pr-publish` already gated these rows. It did not, and it cannot.** That gate runs on findings set to `post`, against the PR's head. Source A is by construction the complement of that set — `hold` findings never enter it, which is why they carry `Not gated` in the handoff — and a `pre-existing` finding that *was* posted comes back as `posted`, not `hold`, so it is not collected here either. The two gates never see the same row, and they do not ask the same question: publication asks "is this claim true of the PR's code", step 3 asks "is this still true of the base branch as it stands today, and at which lines". Source C rows have been through no gate at all.

### B. The deferred-work log

Every entry in `.claude/reviews/pr-<N>-deferred.md` that carries neither `promoted:` nor `skipped:`. Both mean an earlier run of this command already decided.

**A missing file is not an error.** It means the log was triaged and deleted, or the review produced no pre-existing findings. Note it and move on.

A and B overlap heavily — the log is written from the same classification. Dedupe on the finding id in `source: pr-review #<N> @ <sha> — F<n>`. On a match, keep one row: the findings file is authoritative for severity, `evidence` and the cited location; the log entry carries the sentence explaining why this PR did not cause it, which the ticket needs and the findings file does not always spell out.

### C. Work the author agreed to defer

Findings that **did** reach the pull request, where the author answered that the work is real and belongs in a follow-up rather than this PR.

- If the header has no `published-log` block, or it reads `(none)`, nothing was ever sent: this source is empty. Say so and do not scan the thread list.
- Otherwise resolve the comment URLs in `published-log` to their `databaseId` (the `#discussion_r<id>` fragment), fetch the threads, and identify who we are:

  ```bash
  gh api user -q .login
  gh api repos/{owner}/{repo}/pulls/<N>/comments --paginate \
    --jq '.[] | {id, in_reply_to_id, login: .user.login, created_at, path, line, body}'
  ```

  Consider only replies by someone other than us, posted after ours, in a thread whose root is in `published-log`.

**A row qualifies only when the author's own words say the work is real and postponed, and you can quote the sentence.** Quote it in the table and again in the ticket. Never infer deferral from agreement (`ok`, `good catch`, a reaction), never from silence, and never from your own reading of the code — "they did not push a fix" is not the author saying they will. If you cannot quote a sentence, it is not author-deferred, and the finding stays where `/pr-recheck` left it.

**An author who says they considered the work and decided against it has not deferred it.** "I tried X and dropped it as too fragile" is a decision, not a postponement. That sentence is excellent evidence for a row that arrives through source A or B — quote it in that ticket — but it does not create a source-C row of its own, and it does not earn the source-C exemptions below.

**This source is why the command reads the threads itself rather than taking `/pr-recheck`'s word.** When an author replies and pushes nothing, `/pr-recheck` stops at step 1 on equal heads, so the reply is recorded nowhere. Reading the threads here is the only way that case is ever seen.

## 2. Cheap triage, then the shortlist

Everything in this step is decided from the findings file, the deferred log and a Jira search. **Read no source tree here** — the checks that need one run in step 3, on the rows that survive this step and the user's selection.

### The rules that need nothing but the row

Take the first rule that fires. `consequence` is `user-visible` / `security` / `safety-net` / `internal` for a Medium, and `—` for a Critical or High, which are not classified on it.

- **`skip — duplicate of <KEY>`** — a live ticket already covers the mechanism. Decided by the Jira pass below.
- **`skip — trivial`** — cosmetic, and self-evidently cheaper to fix than to track. A duplicated host in a CSP source list is the shape of this; anything with a user-visible consequence is not.
  **Reviews no longer emit Low, so this rule fires rarely and never on severity alone.** A Low is dropped at classification and never reaches the deferred log, so a row that arrives here has already been judged worth recording — skipping it as trivial takes a second decision away from the review that made the first one, and needs the concrete reason ("one duplicated entry in a list the browser deduplicates anyway"), not a tier. Rows carrying an explicit `Low` come from logs written before that policy; treat the label as historical and judge the row on what it says.
- **`skip — internal Medium`** — the finding is rated Medium and names no user-visible or security consequence. **Critical and High are exempt from this rule: they are filed on the strength of severity alone.** At Medium the bar is different: a ticket is a claim on someone's future sprint, and a backlog of "this type could be narrower" and "this comment is imprecise" is a backlog nobody grooms — which then buries the Mediums that do name a consequence.

  Read the finding's `consequence:` field first: `internal — <why>` is this skip, and a named effect or `safety-net — <…>` is not. **Where the field is absent** — an older handoff, a review that predates the split — do not treat the absence as a pass. Decide it yourself from the finding's text and say in the `why` column that you classified it here, against these three:

  - **User-visible** — a person using this software can observe it: wrong data on screen, a control that does nothing, a state that does not recover, a message that misinforms, work silently lost. A diagnostic missing behind an error the user *already* sees is not user-visible; the user's experience is identical either way, and the loss is the maintainer's.
  - **Security** — key material, signing, vault, permissions, origin or sender trust, CSP, the message-passing boundary. Defense-in-depth on that surface counts even when currently unreachable; say in the ticket that it is latent.
  - **Safety-net** — a test that cannot fail, which leaves real code unguarded while the suite reports otherwise. A missing test *about* a security control counts here on the control's consequence, not on the test's; a missing test about internal plumbing does not.

  Everything else is `internal`: a type that could be narrower, an optional field with no caller, a signature/runtime mismatch no caller can currently reach, a hand-written literal that could be derived, a duplicated constant. Real, recorded in the deferred log, not worth a board row.

  **Source-C rows are exempt.** The author said the work is real and agreed to do it later; that is a commitment, and this rule does not get to overrule it.
- **`skip — unproven`** — `evidence: diff-only` or `unstated`. The claim was formed by reading a diff and nothing has confirmed it since. A ticket filed on a guess costs someone a full investigation and ends in "cannot reproduce"; if the row matters, it needs verification first, and that is a separate decision.
- **`candidate`** — everything else: `evidence: verified`, `gated` or `grounded`, and — at Medium — naming a user-visible, security or safety-net consequence. Critical and High reach this rule on severity alone. (`gated` is a verification gate's own output — a second reader confirmed the claim against the code at the lines it named. It is stronger than `grounded` and weaker than `verified`, and it is never a reason to skip.)

**Source-C rows default to `candidate`**, ahead of the `trivial` and `unproven` rules. The author has already said the work is real and agreed to do it later; a table that quietly recommends skipping it is overruling the one person whose judgment this flow does not get to overrule. `duplicate` still applies.

`candidate` is a proposal, not a verdict. Nothing is confirmed still-present until step 3.

### Already ticketed

The deferred logs lag Jira: entries are written per review, tickets are filed across reviews, and nothing reconciles them. This is the single largest source of duplicate tickets in this flow, so search before recommending, every time.

**Resolve this repository's ticket conventions before writing anything.** Take the first of
these that answers, and never mix two of them:

1. **`.claude/pr-tickets.json` in the repository root.** Read it with `cat`. Its keys are
   `site`, `project`, `component`, `issueType`, `summaryPrefix`, `labels` and `dedupeJql`.
   If the file exists but is not valid JSON, report the parse error with the path and stop —
   a malformed config is a mistake to fix, never a reason to guess. If it carries a key not
   in that list, name the unknown key in the report and proceed with the ones you recognise.
2. **A ticket this repository has already filed.** Look for a `promoted:` key in any
   `.claude/reviews/*-deferred.md`, fetch that issue, and mirror its shape — project,
   component, type, summary prefix, labels. Offer to write what you inferred to
   `.claude/pr-tickets.json` so the next run skips this step, and only write it if the user
   agrees.
3. **Ask.** With no config and no prior ticket, ask for site, project, component, issue type
   and summary prefix, and stop until they are answered. Never infer a project key from a
   branch name, a repository name, or an issue key seen in a diff.

A worked example of the shape, from one repository that uses this command: site
`your-org.atlassian.net`, project `PROJ`, component `Component Name`, type `Bug`, summary
prefixed `PROJ | `, no labels. It is an illustration of the fields, not a default — never
file into it.

Per row, in this order:

1. **Any issue key the row already names** — in its `evidence`, its summary, or the deferred entry's text. Fetch it and read what it actually covers.
2. The dedupe search uses `dedupeJql` where the config provides it, and otherwise a search by
   component and substance. **Never search by the summary prefix**: more than one repository can
   file into the same project, and a prefix match silently scopes the dedupe to the wrong subset.

   Search the mechanism and the file, not the review's wording. Run it once per distinct problem, not once per row where rows share one.

Match on the problem, not on phrasing. An open ticket covering the same mechanism → `skip — duplicate of <KEY>`. **A ticket in a Done status is not a skip on its own, and it cannot be resolved here** — whether the row is `fixed` or a regression depends on the base tree, which step 2 does not read. Carry it forward as a `candidate` flagged `closed ticket <KEY> names the same mechanism`, and reconcile it in step 3: `gone` plus a closed ticket is `skip — fixed`; `still-present` plus a closed ticket is a regression and worth its own ticket saying so.

Say in the report how many rows the search covered and what query was used. A dedupe nobody can see the shape of is a dedupe nobody can trust.

### The shortlist table

One table, printed **before** anything is verified and before any ticket is composed:

| id | `file:line` as cited | the problem, one or two sentences | severity | consequence | evidence | source | proposed | why |

`proposed` is `candidate` or one of the three skips. Print `consequence` even when the finding carried the field already: it is the column that decides the largest single group of skips, and a decision the user cannot see is a decision they cannot overrule.

The line numbers in this table are **as cited by the review**, at whatever commit it read. Say so in one line under the table. They are re-resolved against the base branch in step 3 and may move.

Below the table, a short list — never table rows — of **findings held for reasons that are not ticket material**: gate `inconclusive`, unanchorable, trimmed for volume, held by the user's own call. One line each with the reason. These are unfinished review work, not defects, and filing tickets for them converts a gap in the review into a claim about the code.

**Check the volume in the same message as the table.** Past roughly eight `candidate` rows, say so and offer a trimmed set alongside the full one. A backlog arriving in one batch gets triaged as a batch — which is to say, skimmed.

**Then ask the user which rows they want, and stop.** Their answer is the input to step 3 — it decides what gets verified, not just what gets filed. They may pick a row you proposed skipping; that is the point of showing the skips, and it is not a decision to argue with. Verify it in step 3 like any other.

**If you cannot ask** — the user asked you to run without stopping, or is not present — say so at the top rather than in the closing report, then carry every `candidate` into step 3, compose the payload file, print the final table, and create nothing.

## 3. Verify the selected rows against the base branch

Only the rows the user picked. This is what separates the command from a table anyone could type from the findings file: the review's claims were formed against the PR, and what a ticket needs is whether they hold on the branch it will be filed against, at line numbers that resolve there.

The cost of running this after the selection rather than before is that a row can turn out already fixed *after* the user has chosen it. That is the accepted trade. When it happens, drop the row and say so explicitly under the final table — never omit it silently.

### Resolve and materialise the base tree

```bash
base=$(gh pr view <N> --json baseRefName -q .baseRefName) || exit 1
[ -n "$base" ] || { echo "base branch did not resolve — stop"; exit 1; }
git fetch origin "$base" || exit 1
git rev-parse origin/"$base"        # record this as <base-sha>
```

**The empty-`base` check is not defensive padding — it is the whole reason this block has guards.** `gh` fails transiently and routinely: an expired token, a proxy, a TLS error (observed on this machine mid-session, then succeeding three times in a row a minute later). On failure `gh` writes nothing to stdout and `base` is the empty string. Without the check, `git fetch origin ""` errors and is ignored, `git rev-parse origin/""` resolves the literal `origin/`, and **that string becomes `<base-sha>`** — the commit this command says everything downstream pins to: the base-tree verdicts, the line numbers in every ticket, and the provenance sentence in each description that names the commit those lines came from. A ticket citing `origin/` is a ticket whose locations were never real.

Fail loudly here instead. A transient `gh` error costs one re-run; a ticket pinned to a non-commit costs whoever opens it a full investigation that ends in nothing.

**`<base-sha>` is the commit everything downstream pins to** — the verdicts here, the line numbers in every ticket, and the sentence in each description that says where those line numbers came from. Record it once and quote it everywhere; a ticket citing lines from a commit nobody named is a ticket whose locations rot silently.

Materialise it read-only. `git archive` is a pure object-database read — no working tree, no index, no `.git/worktrees` entry, no network:

```bash
mkdir -p <scratch>/pr-<N>-base-tip
git archive <base-sha> | tar -x -C <scratch>/pr-<N>-base-tip
```

Check the size first with `git ls-tree -r --name-only <base-sha> | wc -l`. Under a few thousand files, extract everything: the check greps around each citation, and a narrowed tree turns "this is still the only caller" into "still the only caller *in the part I extracted*". If you must narrow by pathspec, tell the agent what you left out in the same breath as the path.

### Dispatch the gate

Dispatch **one `finding-gate-verifier`** over the whole selected set — an agent holding `Read`, `Grep` and `Glob` and nothing else. Give it the tree path and `<base-sha>`.

**Phrase each row as a claim about the present state of that one tree**, not as the review's original finding: *"at `<path>:<line>` in the given tree, `<what the code does>`, and `<the consequence>`."* The agent verifies claims against a tree; it has no notion of "still". Asked whether something is *still* true it has nothing to compare against, and the drift between what you meant and what it can answer is invisible in the output.

**Say that one tree is deliberate.** The agent expects two on a pull-request flow and treats a missing base as an input error, because most PR claims are about a *difference*. These are not: a pre-existing problem is a claim about the base branch as it stands today. Tell it there is one tree, that this is correct for this question, and that no claim in the set is about what any change did — otherwise it returns `INCONCLUSIVE: unreadable` across the set for a second tree that was never needed.

**Ask for the resolved locations, not just a verdict.** The line numbers the review cited come from a different commit; the ones the ticket carries must be the ones the agent found in this tree.

Map its verdicts back:

- **TRUE POSITIVE** → keep the row. Record the file and lines it confirmed at.
- **FALSE POSITIVE** → the code or the property is no longer there → `skip — fixed`, naming what the agent found instead.
- **CONFIRMED, RATIONALE WRONG** → the problem is there and part of the row's account of it is not. Keep the row, and **write the ticket from the corrected basis, not from the row's text** — including a location that moved. Say in the final table that it was corrected; the user is checking a `file:line`, or a mechanism, that is not the one the review recorded.
- **INCONCLUSIVE** → `hold — unverified at base`, recording which kind. `reasoning` is a fact about the row; `unreadable` is a fact about this run and a re-run candidate.

**A refutation the agent raises against a row it confirms is ticket material, not noise.** "This holds, but no call site reaches it today" belongs in the ticket, in the author's own likely words, so the ticket is not closed in one line by the first person to notice.

**Skip this check for source-C rows while the PR is open, but only where the row is about the PR's own new code.** Those lines are not on the base branch yet, and the author has already agreed the work is real: say so in the row's provenance and pin its line numbers to the PR head. A source-C row describing *pre-existing* code — the common case when an author spots something adjacent while fixing a review comment — is an ordinary base-branch row and goes through the gate like the rest. Once the PR is merged, so does everything else.

Verify the constraint held rather than trusting it: snapshot `git status --porcelain` before dispatching and compare after, in the repository and in every worktree. Compare rather than requiring empty — the user may have unrelated uncommitted work. What must be true is that nothing changed.

**Where the base is not the repository's default branch** — a release branch, a stacked PR — say so in the report and in every ticket. A problem live on `release/x` may already be fixed on the default branch, and the reader of the ticket needs to know which tree the line numbers describe.

## 4. Compose the payloads to a file, then show the final table

Compose the full text of each surviving ticket and **write it to `<scratch>/pr-<N>-tickets.md`** — one section per ticket, exactly the payload that will be sent, in the order it will be sent. Do not paste the payloads into chat: they are long, and a wall of text is skimmed rather than read. The file is what makes the exact payload reviewable; give its path with the final table so the user can open it if they want to.

Each ticket:

- **summary** — `<summaryPrefix><the problem in one line>`, using the prefix resolved in step 2. The problem, not the location: a summary naming only a file tells a reader nothing at triage time.
- **type** — `Bug` for a defect. A missing test, a cleanup, or a design change is a `Task`; say which and why in one clause.
- **priority** — from severity, and this mapping is fixed: **Critical → Highest, High → High, Medium → Medium.** Every Medium that reaches this step has already cleared the `skip — internal Medium` rule, so a Medium on the board is by construction one naming a user-visible or security consequence, and Medium is the right priority for it — not lower for being a Medium, not raised for being security-adjacent. Current reviews emit nothing below Medium — Low is dropped at classification and never reaches the deferred log — so a row arriving without a severity is a Medium unless its own text argues otherwise, and a row still carrying `Low` came from a log written before that policy: map it to Low, and say in the ticket that the severity is inherited from an older review rather than assigned to this row.
- **component** — as established in step 2.
- **description**, in the sections `PROJ-1234` uses:

  A provenance paragraph first: what review surfaced it, that line numbers are from `<base-sha>` (`<base>`) and were re-verified against that commit, and why this PR did not cause it. For a source-C row, say instead that the author agreed to defer it, **quote their sentence**, and link the thread; if the PR is still open and the row is about the PR's own code, say that too and pin the lines to its head.

  Then `## Where` · `## Problem` · `## Impact` · `## Reproduction` · `## Suggested direction` · `## Related`.

  **Omit `## Reproduction` when nothing was executed.** Never write reproduction steps you have not run — a ticket whose repro does not reproduce is worse than one that admits it has none. `## Related` names adjacent tickets and the PR; omit it when there is nothing to name.

**Describe the finding, never how it was found.** No agent names, no skill names, no "automated review", no `.claude/` paths. `PROJ-1234` opens with "Surfaced while reviewing PR #1429" and that is the whole of it.

Then print the **final table** in chat, and nothing longer:

| # | summary | type | priority | severity | what it says, one or two sentences |

Under it: the path to the payload file, `<base-sha>` with the branch it came from, and any row that dropped out in step 3 with the reason — `skip — fixed` or `hold — unverified at base`.

Ask for approval **on this list**. Anything other than explicit approval — silence, a question, a partial objection — means create nothing. If the user amends a ticket, amend the file, re-print the affected row, and ask again.

## 5. Create

One ticket at a time, with `createJiraIssue`, from the payload file. Never transition, never assign, never link issues unless the user asked for it.

**Write each returned key to disk before making the next call.** A ticket created but not recorded becomes a duplicate on the next run, and this command has no way to tell one apart from an untriaged row.

On a failure: stop, report the exact error, and create nothing further. A half-filed batch is recoverable only if you can say precisely where it stopped.

## 6. Record

Both files may be open in another session — these logs are shared and edited between reviews. **Re-read the target file immediately before writing, and append rather than rewrite.** Never reorder, never delete, never rewrite an existing entry.

- **`pr-<N>-deferred.md`** — append to the entry, on its own line, one of:

  ```
  promoted: <KEY> (YYYY-MM-DD) — <issue url>
  skipped: <reason> (YYYY-MM-DD)
  ```

  Do not delete the file, and do not delete an entry. The annotated log is the audit trail; retiring it is the user's call.
- **`pr-<N>-findings.md`** — add `verdict: ticketed <KEY>` alongside the existing verdict, **as its own line starting at column 0**, matching the field syntax the review side writes. **`hold` stays `hold`**: a ticket is not a publication, and rewriting the verdict would make the finding look like it reached the author.
  The column matters because this line is read by `grep`, by this command's own collection filter in step 1 and by `/pr-recheck`, which is told never to replace it. Emitted as a list item or tucked into prose it is a line those greps do not see — and the failure is a duplicate ticket on someone's board, which nothing downstream can detect.

Take the date from the session's own context; do not guess it.

A re-run skips every row carrying `promoted:`, `skipped:`, or `ticketed` — that exclusion happens in step 1, before anything is classified and before anything is composed.

Then one report in chat: the tickets created with their keys and URLs, the skips grouped by reason, the `hold — unverified at base` set as re-run candidates, the non-ticket-material list, and `<base-sha>` with the branch it came from. Nothing goes to GitHub.

---
description: Publish selected findings from a /pr-review handoff file as comments on a GitHub PR. Every finding not backed by an executed check is re-verified against the PR's own source first, and nothing is posted without explicit approval of the exact payload.
argument-hint: <pr-number>
---

Publish findings from an existing `/pr-review` handoff file to the pull request `$ARGUMENTS`.

**Bind the PR number once as `<N>` and use `<N>` everywhere below.** Never re-expand the raw argument text into a later command line: the argument routinely carries a long instruction block alongside the number, and re-expanding it at each mention copies that whole block into context several times over, for nothing.

This is the only command in the review flow that writes to GitHub, and the pull request belongs to someone else. Nothing reaches the PR until the user has seen the exact payload and approved it in this session. You MUST NOT approve the PR, request changes, or push commits — comment-only.

## Operating assumptions

This flow assumes nothing about the session's configuration beyond the tools it names. Two
things it would otherwise inherit from a personal setup are stated here instead, because a
rule that lives outside this file is enforced on one machine and silently absent on every
other one, and the flow looks identical either way.

- **Dispatching the agents this flow names is part of running it.** Do not ask for
  confirmation before each one, and do not substitute doing the work inline to avoid the
  dispatch — the whole point of a separate reviewer is that it reads the code without this
  session's framing.
- **A check that was not run is reported as not run.** Never write "verified", "passing" or
  "confirmed" for something you did not execute and whose output you cannot quote. Where a
  step was skipped, say so and say why. A confident summary of an unrun check is the one
  failure this flow cannot detect in itself.

## 1. Load and check freshness

- `$ARGUMENTS` empty: ask for a PR number and stop.
- Read `.claude/reviews/pr-<N>-findings.md` from the repository root. Missing: stop and tell the user to run `/review-flow:pr-review <N>` first — the plugin-qualified form, with the number substituted, so it can be pasted as-is. Never reconstruct findings here — this command publishes, it does not review.
- Compare the file's recorded head SHA against `gh pr view <N> --json headRefOid -q .headRefOid`. **If they differ, stop — unless the `rounds:` block records a completed re-check at exactly the current head.** The PR has new commits: line numbers have shifted, findings may already be fixed, and inline comments would land on the wrong code.

  The exception is deliberately narrow. The last line of `rounds:` must carry **both** a re-check marker — `rechecked` or the hyphenated `re-checked`, and nothing looser — **and** a SHA equal to the PR's current head. Not "the file mentions a round 2", not "a re-check happened at some point": anything beyond those two spellings lets a stale entry lift the gate, and the comments then land on lines that no longer exist.

  **Both spellings are accepted on read; only `rechecked` is written.** The schema below is what `/pr-recheck` is told to emit, and files written before that instruction existed carry the hyphen. Matching on the token alone would be too loose in the other direction — a header sentence describing the re-check policy would satisfy it — so match a `rounds:` list line, and require the SHA on that same line.

  - **Condition holds** → continue. A re-check has already moved the findings onto this head; anchors are recomputed below regardless.
  - **Condition fails** → stop, report both SHAs, and offer `/review-flow:pr-recheck <N>`, plugin-qualified and with the number substituted.
  - **No `rounds:` block at all** (a file written before the format existed) → treat it as "round 1, never re-checked" and stop, as before.

  **When the exception applies, the operative head is the PR's current head — not the header's `head SHA` field.** That field still records the round the file was first written for, and the re-check deliberately leaves it alone so the file's history stays readable. Everywhere below that says "the head SHA" means the current one. The header's `where the PR's code can be read` field is stale for the same reason: re-resolve it below rather than trusting it.

### Locate the PR head before going further

**The verification gate reads source, so establish where the PR's code actually is and record it.** The session's checkout is frequently *not* the PR head: after a `/pr-review` that used a temporary worktree, it sits at the merge base, where files the PR adds do not exist at all and files it rewrites are a different length. A gate run against that tree verifies the wrong source and returns confident, wrong verdicts — which is worse than not gating, because the wrongness is invisible downstream.

Resolve one of these, in order, and say which one when you print the payload in step 4 — the gate's strength depends on it, and the user is approving comments that rest on it:

The handoff header records which mode the review ran in — `local checkout` / `worktree removed — head reachable as refs/pr/<N> (local object, no fetch needed)` / `diff-only (cross-repo) — not available locally`. Start there, then confirm it rather than trusting it; the review may have been run in an earlier session. On the middle value, confirm with `git cat-file -e <head-sha>` — if the object is present, route 3 below works with no network at all. An older handoff may say `worktree removed — not available locally` instead; treat that as the same thing and check for the object anyway, since a review that predates the ref-retention rule may still have it reachable.

1. **`git rev-parse HEAD` already equals the head SHA** → read the checkout directly.
2. **The `/pr-review` worktree still exists** at the head SHA → read from it.
3. **The head commit is already in the local object database** — check with `git cat-file -e <head-sha>^{commit}`, which is true far more often than it looks, because any earlier `/pr-review` or `gh pr diff` in this clone will have fetched it. Materialise it read-only:

   ```bash
   mkdir -p <scratchpad>/pr-<N>-head
   git archive <head-sha> | tar -x -C <scratchpad>/pr-<N>-head
   ```

   `git archive` touches **no** working tree, **no** index, **no** `.git/worktrees` entry and **no** network — it is a pure object-database read that happens to land on disk. Prefer it over option 4 whenever the object is present: it is the only route that is simultaneously non-mutating and greppable, and it is what keeps the gate strong when the user has forbidden tree mutation.

   **After a `/pr-review` in this clone the object is present by construction.** That flow fetches the head into `refs/pr/<N>` and deliberately does *not* delete the ref, precisely so this route always works here — so the normal path is that you never fetch at all. **Delete the ref when you are done with this PR** (`git update-ref -d refs/pr/<N>`); `/pr-review` leaves it for you and this command is what retires it. If the publish run ends without reaching that point, the ref simply stays — harmless, about forty bytes, and `git for-each-ref refs/pr` lists any that accumulated. Never treat a present ref as evidence that a review is currently running: nothing removes it when a run is killed.

   **It extracts the whole tree at that commit, so scope it when the tree is large.** Check first — `git cat-file -s $(git rev-parse <head-sha>^{tree})` is not the answer, so use `git ls-tree -r --name-only <head-sha> | wc -l` for a file count, or just look at what the PR touches. Under a few thousand files, extract everything: the gate greps across the repo to check a claim's surroundings, and a narrowed tree silently turns "no other caller exists" into "no other caller exists *in the part I extracted*", which is a different and much weaker statement. For a monorepo, or anything where the full extract is slow enough to notice, narrow it by pathspec to the directories the findings actually cite:

   ```bash
   git archive <head-sha> -- src/background src/hooks | tar -x -C <scratchpad>/pr-<N>-head
   ```

   If you narrow, **tell the gate what you left out**, in the same breath as the tree path. A negative claim ("nothing else dispatches this", "no test imports it") verified inside a narrowed tree is `inconclusive: unreadable`, not confirmed — the agent cannot know the boundary exists unless you name it.
4. **The object is not local and fetching is permitted** → `git fetch --force origin pull/<N>/head:refs/pr/<N>`, then the same `git archive <head-sha> | tar -x` as above — passing the **head SHA**, not `FETCH_HEAD`.
5. **`git archive` is unavailable** → `git worktree add <scratchpad>/pr-<N>-publish refs/pr/<N>`, then confirm `git -C <path> rev-parse HEAD` equals the head SHA before the gate reads a byte of it. Remove the worktree and delete the ref (`git update-ref -d refs/pr/<N>`) at the end of the flow, even if a later step failed. This mutates `.git`, so it ranks below the two above rather than in place of them.

   **Never name `FETCH_HEAD` in either route.** It is one file in the clone's main `.git`, shared by every worktree and every concurrent session, and a `/pr-review` running in another session against a different PR overwrites it between your fetch and your read. The failure is silent: the gate verifies findings against a tree that belongs to someone else's pull request, reports them confirmed, and this command posts them as comments on *this* one. Fetch into a named ref and pin every subsequent step to the head SHA you already hold.
6. **All of the above fail** (cross-repo PR, fetch denied, tree frozen) → per-file `gh api repos/<owner>/<repo>/contents/<path>?ref=<head-sha>`.

**Option 6 is not a route the gate can take.** The gate runs in an agent holding `Read`, `Grep` and `Glob` and nothing else — it cannot call `gh` any more than it can call `git`. If you land on 6, the head exists only where *you* can reach it, and you have exactly two honest choices: inline the cited head regions into the gate's prompt (expensive, not greppable, and it puts source back into the main context — the cost options 3-5 exist to avoid), or skip the gate entirely and drop every ungated finding to `hold`. Say which you chose and why. Never split the difference by letting the agent read the on-disk tree "for the unchanged files only" without first establishing which files those are.

**When the tree you hand the gate is not the whole head**, establish the difference explicitly with `git diff --name-only <merge-base> <head-sha>` and pass that list to the agent: files outside it are byte-identical at head and safe to read from the local checkout; files inside it are not. This is what makes a partial read defensible instead of a guess.

**Never verify a finding against a tree you have not confirmed is at the head SHA.** Confirm it with `git rev-parse` — or, for a materialised archive, by recording the SHA you passed to `git archive` — not by assuming.

## 2. Resolve verdicts

- Exclude anything already marked `posted` by an earlier run (step 6) before doing anything else. It never reaches the proposal below, the gate, or the user.
- **Three verdicts mean "send": `post`, `reply`, `resolve`.** The exclusion above applies to all three and to their completed forms `posted`, `replied`, `resolved`. A duplicate on someone else's pull request is the one failure in this flow with no undo.
- **Check the set against `published-log` before proposing anything.** A match on id, or on the pair of `file:line` and the comment's first line, is shown in the preview and is not sent without an explicit decision. The log survives a rebuild of the finding set where the findings' own fields do not: after a rebase it is the only thing that still remembers what was sent. **No block, or `(none)`, means nothing has been sent** — there is nothing to compare against, so proceed; step 6 creates the block. Do not treat its absence as a reason to stop, and do not reconstruct one from the findings' `verdict` fields: those are what it exists to outlive.

  **This guard applies to `post` only. `reply` and `resolve` are exempt, and a match on one of them is the expected result, not a warning.** Both address a *thread*, and the thread is located through the very comment URL the log records — so a `reply` or `resolve` that failed to match `published-log` is the anomaly worth stopping on, and it is already caught in step 4, where anything that resolves to no `threadId` is downgraded to `hold`. Listing them as duplicate candidates inverts the signal on exactly the findings a re-check produces, and a user reading that list as a duplicate warning holds or drops legitimate answers to threads the author is waiting on. Show them in the preview as what they are — the thread each one is answering — and never under the duplicate-match list.
- **Findings carrying `reply` or `resolve` do not go through the verification gate below.** A `fix-verifier` has already checked them against both the old and the new head, and the question it answered is the one that matters here: is the defect gone. Re-running the gate would answer a different question — whether the original claim was true — and there would be nothing to do with the result.

  **This exemption is those two verdicts and nothing wider — not "anything a re-check touched".** A re-check also emits `verdict: pending` for findings that were never published and were not fixed, and for findings its own incremental review raised for the first time. No `fix-verifier` examined the latter at all: they are ordinary unverified claims that happen to have arrived on a later round. Reading the exemption as "its verdict came from a re-check" would walk a brand-new, never-confirmed High straight past the gate on the strength of a round number.
- Every finding must carry a resolved verdict — `post`, `reply`, `resolve`, `hold`, or `dropped` — before anything is composed. The three sending verdicts are as above; `reply` and `resolve` arrive only from a re-check and only on findings that already have a thread. For any still `pending`, work through them with the user before going further — do not assume `post`.
- **Do not walk a large `pending` set one finding at a time.** Open with a complete proposed disposition: every `pending` finding assigned a verdict, grouped by the reason for it — severity tier, an anchor another comment already covers, a design argument rather than a defect, `pre-existing`. Start from whatever `suggested:` verdict the handoff file already carries. Present it as one table and take the user's edits as a delta. The user decides; making them derive the whole set from scratch is not deciding, it is transcription. A handoff of forty findings is normal and must not become forty questions.
- **A finding rated Low defaults to `hold`.** Current review rounds drop Low at classification, so a handoff file written by them carries none and this rule is inert. It exists for the files that predate that policy, and for a Low arriving by any other route: such a finding does not reach the author unless the user asks for it explicitly, while looking at the proposal table. The reason is the review's readability as a whole — measured across three reviews on this repository, 14 of 41 published comments were Low, and every one of them spent the attention the four Highs needed. Where the user does want one sent, say in the proposal that it is going out as a Low, so the choice stays visible.
- **A finding marked `scope: pre-existing` defaults to `hold`.** The author did not write it, and a comment about it asks them to own something their pull request did not cause — the most reliable way to make a review read as noise and get the rest of it skimmed. Posting one is a deliberate choice: the user must say so explicitly, and the comment must acknowledge outright that it predates the PR. A pre-existing finding the change makes materially worse belongs at `introduced` instead — go back and fix the scope rather than arguing the exception here.
  **A `suggested: post` on a `pre-existing` finding does not override this.** The review side is not supposed to emit that combination at all; where it does, read it as the reviewer marking the finding interesting, never as a disposition. Downgrade it to `hold`, and say in the proposal that you did — silently honouring it would let the review side decide something this step exists to decide.
- **A Medium carrying `consequence: internal` defaults to `hold`.** The review side splits Medium on whether the finding names a user-visible or security effect, or is a test that cannot fail; `internal` is its verdict that the finding is real, recorded, and not worth the author's round-trip — a type that could be narrower, an imprecise comment, a duplicated literal, a coverage gap with no named consequence. Posting one is the user's explicit call while looking at the proposal table, exactly like a `pre-existing`.

  **Why this default and not a lower severity.** Measured across the last five pull requests published from here, 79 of 89 findings were Medium against 9 High, and 42 of those Mediums reached the author. Half were fixed; the other half were argued about or ignored, and they were overwhelmingly the `internal` ones — a review whose bulk is "this type could be narrower" trains the author to skim the tier that also holds the lost approvals and the vacuous tests. The tier is not the problem and dropping it wholesale would be a mistake: the acceptance rate on Mediums that name a consequence is as good as on High. The split is what recovers the signal.

  **A missing `consequence:` field on a Medium is not a pass.** The field is written by the review side for every Medium, and every consumer here greps for it and fails open. Where it is absent — an older handoff, a writer that dropped it — do not treat the finding as consequence-bearing: read the finding and classify it yourself in the proposal table, saying you did. Guessing upward is how the whole filter becomes decorative.
- **Print the table before anchoring, whether or not you can ask about it.** The table is a *disclosure*, and the question is a separate act layered on top of it. When the run is non-interactive — the user asked you to proceed without stopping, or is not there to answer — the proposal still gets printed, in its own message, before any anchoring or gating work. What must never happen is the whole of step 2 collapsing silently into the defaults because there was no one to hold a conversation with: the user learns the shape of the set either way, and learns it while it can still change something.
- **Check the volume before you propose it.** If the proposed `post` set runs past ~10 comments, say so **in the same message as the table** and offer a trimmed alternative alongside the full set. Volume is the only trigger: a Low in a `post` set is something the user asked for explicitly, not a volume problem. Thirty comments do not read as thoroughness; they read as noise, and the Highs get skimmed with everything else. The user may well want all of them — but that should be a choice made while looking at the shape of the set, not a default nobody noticed. A volume warning that arrives in the closing report, after the comments are written, is not a warning — it is a postmortem. If you only realise the count late, you printed the table too late.

  **The threshold for replies is five, not ten.** It is lower because each reply goes out as its own API call and its own notification, where the inline comments are one notification for the whole review. Warn in the same message as the table and offer a trimmed set alongside the full one.

  Say the count is provisional when you give it. Anchoring and the gate both remove findings, so the number at table time is a ceiling, not a forecast — state it as "up to N, and anchoring will cut some", so a later drop reads as the process working rather than as the earlier figure having been wrong.

### Resolve anchors first

**Compute every `post` finding's anchor before the gate runs.** A finding that cannot be anchored cannot be posted, so gating it spends verification effort — the most expensive step in this command — on something that was never going to reach the author. Anchor first, resolve the unanchorable ones, and gate only what survives.

**Start this chain against the *suggested* set the moment the table is printed — do not wait for the user's reply.** The table is a disclosure and it still goes out first, exactly as step 2 requires; what changes is that anchoring and the gate then run *while* the user is reading it, against the set the handoff already suggested for `post`. Their edits arrive as a delta: a finding they drop was gated for nothing, and a finding they add enters the gate on its own in a second, small call. Nothing about the disclosure or the decision moves.

The saving is the largest single one available in this command: the gate is its longest block, and it otherwise sits idle behind the approval turn. The by-product is worth as much as the minutes — the user's decision is better informed when the gate's verdicts are already on the table rather than arriving after they have committed to a set.

**Two things this does not license.** Do not send anything before the user has resolved the verdicts — the gate running early changes when verification happens, never when publication does. And do not gate the `hold` set on the theory that the user might promote one: the rule below stands, only what is actually being sent is gated, and "suggested `post`" is the handoff's own proposal, not a widening of it.

**Look for the hunk map `/pr-review` left behind first**, at `.claude/reviews/pr-<N>-hunks-<full-40-char-head-sha>.txt` — per-file hunk ranges and added lines, already extracted. **The SHA in the filename is the pin: it must equal the head you are publishing against**, which is the PR's *current* head whenever the freshness exception in step 1 applied, not the header's `head SHA` field. On a match, classify against that file and skip the fetch entirely. On a mismatch, a missing file, or any doubt, rebuild it — a map from the previous round anchors this round's comments onto lines that have since moved, which is the one failure this command is arranged to avoid, and rebuilding costs one shell call.

**It lives in `.claude/reviews/`, beside the findings file, and nowhere else.** Do not look in a scratchpad: this command always runs as a separate invocation from the review that wrote the map, so a session-scoped path is guaranteed to be the wrong one, and hunting for the right session's directory with a wildcard finds whatever another run happened to leave behind. If the map is not at the path above under the head you are publishing against, treat it as absent and rebuild — one shell call, and it cannot pick up a stranger's file.

Rebuild it to the same path and the same name, so the next round of this pull request finds it.

Otherwise fetch the diff with **`gh pr diff <N>`**. Never `--patch`: that returns one patch per commit, so files appear repeatedly with conflicting line numbers, and the anchor map built from it is wrong in a way nothing downstream will catch.

**Reusing the map is not reusing the anchors.** The map is a mechanical extract of the diff, valid for whoever holds the same SHA; the *classification* of a finding's citations against it is what the paragraph below insists you recompute, because the handoff's `anchor:` field was written by a command that never had to act on it.

Per `post` finding, compute which of its cited lines fall inside a hunk, and whether the PR **added** each line or it is unchanged context carried along for readability. Use whatever the handoff file recorded in `anchor:` as a starting point, but **recompute it** — that field is written by a command that never has to act on it, and a comment landing on the wrong line is the failure this whole command is arranged to avoid.

**"Cited lines" means every `path:line` reference anywhere in the finding** — the `file:` header, and any location named in `issue:`, `why:`, `fix:`, `found-by:`, `contested:` or `evidence:`. Not just the `file:` range. Those are the literal keys the review side writes; do not go looking for the long-form names the fields are *described* by (`why it matters`, `suggested fix`) — no handoff file has ever carried them, and a scan keyed on a name that never appears silently covers less than it claims to. A finding whose `file:` range falls outside every hunk is **not** thereby unanchorable: it is anchorable wherever else it points, and treating it as lost throws away real findings on a technicality. Prefer the `file:` range; fall back to secondary citations in the order they appear.

**When you anchor to a secondary citation, two things follow.** Say so explicitly in the payload preview — the user is checking a `file:line` pair that is not the one the handoff leads with. And build the comment's opening around the line you actually landed on, then reach back to the primary location by name; a comment that discusses code the reader cannot see next to it reads as misfiled.

**Delegate it — unless you are holding a valid map.** With a SHA-matched map on disk the classification is a lookup against a few hundred bytes of ranges, cheap enough to do here and one round-trip cheaper than dispatching for it. Without one, dispatch a single `anchor-resolver` agent with the PR number and an **inline list of `id → file:line` citations covering the `post` set and nothing else** — every `path:line` the finding names, per the rule above, not just its `file:` range — plus the map's path if a stale-but-rebuildable one exists. It returns one compact table — finding → path, anchor line, `added` / `context` / `outside-hunk`, and how much of the cited range the diff covers. The diff runs to tens of thousands of tokens and the computation is mechanical and checkable, so neither belongs in the main context. If no agent tool is available, do it inline and say so.

**Pass the citations inline; do not hand it the findings-file path.** Given a path and no id list the resolver's contract is to resolve *every* finding in the file, which on a real handoff is three to four times the `post` set — held, dropped and pre-existing findings all anchored for nothing. The waste is the smaller half. The damage is that its `UNANCHORABLE` line then names findings that were never publication candidates, which trips the "more than one unanchorable → stop and ask" rule below on a set the user was never being asked about, and in the non-interactive path sends findings to `hold` that were already there. The resolver cannot tell which ids you care about unless you say.

**Do not give it both forms hoping for its `DISAGREES WITH RECORDED anchor:` comparison.** The agent's contract is that whichever form it was given is the only one it uses, and that rule is what stops it reading a *stale* findings file in the two flows that pass citations inline — weakening it for a convenience here would cost more than the comparison is worth. You do not need it anyway: you are already holding the file's recorded `anchor:` field and the freshly computed class for every `post` finding, so compare them yourself and say in the payload preview where the recorded field was wrong.

Then apply:

- One inline comment per finding with at least one cited line inside a hunk, anchored to the first such line.
- **A finding with no cited line inside a hunk cannot be anchored.** Exactly one such finding folds into the summary body. **If more than one is unanchorable, stop and ask** — several would turn one short paragraph into a second review, which is not what the summary is for and not what the user approved.

  **Asking means a question the user can answer, not a paragraph they might read.** Use the question tool. A question raised inside a status update, a table caption or a closing report is not asking, and treating it as though it were is how a decision reserved for the user gets made by default.

  **Name each unanchorable finding's severity in the question.** The rule's one-finding allowance assumes the choice is trivial, and it stops being trivial the moment a High is among them: "which of these three do you want in the summary" reads very differently once the user can see that dropping one silently drops the most serious thing the review found. Severity is the fact that decides it, so put it where the decision is made.

  **If you cannot ask** — the user told you to run without stopping, or is not present — then: every unanchorable finding goes to `hold`, **you re-home none of them on your own**, and you say so at the first mention of the unanchorable set rather than in the closing report. Choosing which one is interesting enough for the summary is precisely the judgment this rule withholds from you; the one-finding allowance exists for the case where there is exactly one and no choice to make.
- **Two findings sharing an anchor: neither merge them nor stack them.** Resolve it in this order: (1) if the second finding cites another file, or a distant region of the same file, **and that location is as good a home for the point it is making**, move it there; (2) otherwise anchor it to an adjacent line in the same hunk, and have its text open by distinguishing itself from its neighbour.

  **The qualifier in (1) is load-bearing — do not relocate on the mere existence of a second citation.** Findings cite supporting code all the time: the callee a claim passes through, the type a value has, the test that fails to cover it. Those are evidence, not alternative homes. A comment about a *caller* failing to guard something belongs on the caller, even when the callee is also cited and sits in a tidier file. Ask what the reader needs to be looking at to understand the point; if the answer is the original location, an adjacent line there beats the right file in the wrong place. Two adjacent comments that each distinguish themselves are a mild cost; a comment on the wrong code is a wrong comment.

  Watch two specific traps: an anchor line that is a **comment** rather than code, and an anchor on a line another comment in this same review already quotes in its body. Both read as misfiled even when technically valid.

  Where `anchor-resolver` proposes an alternative split, weigh it against the test above — take it when it holds, and say why when it does not.
- **Check `scope` against the diff.** A finding marked `introduced` that anchors to a line the PR did not add is a real possibility — the change can create the invariant that untouched code now fails to uphold — but the comment must say so itself, acknowledging the code is unchanged before explaining why the change makes it wrong now. An "introduced" comment landing silently on untouched code invites "I didn't write that", and is the same failure the `pre-existing` default above exists to prevent.

### Verification gate

**Every finding that survived anchoring, still carries verdict `post`, and whose evidence is not `gated` goes through the verification gate before it can be sent.** One level skips it: `gated` means this very gate already confirmed the claim against the head on an earlier round, at lines it named. Nothing that failed to anchor reaches this step.

**`verified` is not an exemption, and the archive is why.** Of the findings that carried `evidence: verified` and went through the gate anyway, **5 of 9 came back `CONFIRMED, RATIONALE WRONG`** — no better than the levels that have never been exempt. The reason is structural rather than incidental: a probe verifies a *mechanism*, and the rationale then generalises from it. The generalisation is where these findings break — the wrong clauses were counts, quantifiers, reachability and `scope`, and a probe cannot settle any of them. A fallback timed at 74ms on four screens is still a fallback timed on four screens, not on "every navigation". `verified` also reads to the author as the strongest evidence the system has, so a wrong rationale wearing it is the one least likely to be challenged.

**The one carve-out is narrow: the probe's own output must *be* the claim** — a compiler error, a failing assertion, a mutation that flipped a named test. There the finding asserts exactly what was observed and there is no generalisation left to check. Record it as `gate skipped: probe output is the claim` and name the output, so the exemption stays auditable; anything vaguer than that is a finding that generalises, and it gates.

**`gated` is the gate's own output, which is exactly why it must not be spelled `verified`.** A read-only verdict wearing the executed-and-observed label makes the gate self-exempting in a way nobody can see: on a later round it is indistinguishable from a probe that ran, `/pr-recheck` will look for a probe description that was never written, and a claim confirmed against a head two rounds old reaches the author labelled as measurement. Where both hold — a probe ran *and* the gate confirmed it — `verified` wins and the gate's confirmation goes in the recorded reasoning.

**Only what is actually being sent is gated.** This is the most expensive step in the command, and it exists to protect the author from a wrong claim — so it runs on the set that will reach them, never on the handoff file. A finding sitting at `hold`, including every Low held by the default in step 2, is not verified here: if the user later promotes one to `post`, it enters the gate at that point, with everything else. Gating held findings spends the flow's costliest resource on comments nobody will read.

The criterion is how the finding was **established**, not which label it carries. `grounded`, `proposed-probe` and `diff-only` are all judgments formed by reading code — the thing this gate exists to double-check. `grounded` especially: it is self-assigned by the same check that raised the finding, with no calibration and no second reader, and the review command's own definition concedes the level is "self-reported and therefore soft". A gate keyed on the two weakest labels is one any check can walk out of by writing a stronger label, and a handoff where every finding says `grounded` gates nothing at all.

**A finding carrying a `contested` field goes through the gate regardless of evidence level, including `verified`.** One check raising a finding and another clearing it is the strongest available signal that the claim is unsettled — most often because the two answered different questions, which is invisible unless someone re-reads both. This is the case least likely to be caught by anything else in the flow, because on the surface it looks like the finding already survived scrutiny.

Severity is deliberately not the criterion. A wrong Medium costs the author the same round-trip as a wrong High, and Medium is both the most numerous tier and the least scrutinised when generated. Cost is bounded from the other side: only findings you actually intend to publish reach this step — `hold` and `dropped` never do.

**Most gated findings are not security findings, and the bar is not exploitability.** A real handoff gates stale comments, missing test coverage, type design and performance alongside genuine vulnerabilities. For a non-security finding the only question is **whether the claim is factually confirmed against the code at the head SHA**: does the cited line say what the finding says it says, and does the stated consequence follow. Do not manufacture a threat model where none was the point.

**Run the gate inside an agent that cannot write.** Dispatch a single `finding-gate-verifier` — an agent defined with `Read`, `Grep` and `Glob` and nothing else — over the whole gated set at once. The tool list *is* the enforcement: "do not create or modify any file" is a request, and this flow must never mutate someone else's pull request on a request. The general-purpose read-only agent types do not help here — they still carry `Bash`, and `Bash` writes.

**The agent carries its own verification protocol; do not tell it to invoke a skill.** It holds no `Skill` tool and cannot, so an instruction to run one produces a silent improvisation dressed up as a procedure — every verdict then rests on whatever the agent invented that run, which is exactly the calibration this gate exists to supply. `finding-gate-verifier.md` defines the protocol, including the mandatory refutation pass; your job here is to give it a readable tree and the finding set, not a method.

Dispatching one agent over the whole set rather than one per finding is deliberate: restating every claim in one pass collapses the weak ones cheaply, and cross-finding chains only surface when the set is seen together.

It also keeps the gate off the main context: it reads source and returns only per-finding verdicts and reasoning, where doing this inline means printing every cited file into the conversation. If you find yourself reading source in the main loop to settle a gated finding, step 1 gave the agent too little — fix that rather than doing its job.

Tell it: the PR head is readable at `<the head path resolved in step 1>`, the merge base at `<the base path>`, read source only from those two, and return **inconclusive** rather than escalating past what those trees can settle.

**Give it the base tree, not only the head.** A large class of findings is inherently about the difference between them — "this line is unchanged", "the comment predates the change", "this clause was already there". An agent holding only the head cannot settle any of them and will hand them back unresolved, leaving you to finish the verification by hand in the main loop. A second `git archive <merge-base> | tar -x -C <scratchpad>/pr-<N>-base` costs the same half-second as the first.

Where step 1 landed on option 6 and there is no path to give it, say that instead — plus the list of PR-changed files whose on-disk copies are stale, and the standing rule that **an excerpt too thin to settle a finding returns `inconclusive: unreadable`, never a read of the stale file.** A gate that quietly falls back to the merge base is the exact failure the head-location step exists to prevent, and it is invisible in the output.

Then verify the constraint held rather than trusting that it did: **snapshot `git status --porcelain` before dispatching the gate and compare it after**, in the repository and in every worktree, before anything is composed. Compare rather than requiring empty — the user may have unrelated uncommitted work, and a rule that trips on their own edits is a rule that gets ignored. What must be true is that *nothing changed*, not that nothing was there.

**Reconcile the agent's summary line against its own per-finding verdicts before applying anything.** They can disagree — a header counting an inconclusive that no body contains, or a total that does not add up. The bodies are authoritative; the header is arithmetic that may have been written from memory. Where they differ, take the bodies, and say in your report that they differed: a header claiming an unresolved finding that does not exist would otherwise send the user hunting for it.

Apply the outcomes:

- **TRUE POSITIVE** → keep `post`, **replace** the finding's `evidence` with `gated: <the file and lines the gate confirmed it at>`, and record the gate reasoning in a `gate:` field. Never write an evidence label naming a tool or procedure without the code location that backs it: a label is not evidence, and one that cites a process nobody can re-run is worse than none. That reasoning is what makes the comment defensible if the author pushes back.
  **Replace, do not append.** A finding left carrying both its original `grounded:` line and a new one has an evidence level equal to whichever a downstream `grep` matches first, and three commands key decisions on that field — the ticketing step skips rows on it, the re-check step re-runs probes on it, this command gates on it. One `evidence:` line per finding, always.
- **CONFIRMED, RATIONALE WRONG** → keep `post`, but **compose the comment from the corrected basis, not from the finding's text.** This is the most common non-trivial outcome and the one the other three verdicts have nowhere to put: the defect is real, and one clause of the explanation — a mechanism, a claimed ordering, an overstated consequence — is not. Record what was corrected. Posting the original wording hands the author a claim they can refute without touching the actual bug, which costs more credibility than the finding was worth.
- **FALSE POSITIVE** → `dropped — <the failing gate and its reasoning>`.
- **Inconclusive** → `hold` by default. Keeping it at `post` is the user's explicit call, and the comment then goes out **as a question** whatever evidence level the finding still records — the gate failing to settle a claim outranks the label it was carrying when it went in. Never let an unresolved finding go out as an assertion.

  **Record which kind of inconclusive it was, because they mean opposite things.** `inconclusive: reasoning` — the gate read the code and the claim still did not settle; that is a fact about the finding, and holding it is the right permanent answer. `inconclusive: unreadable` — the gate could not reach the source at all; that is a fact about *this run*, the finding may be perfectly good, and holding it is a false negative bought by an infrastructure gap. List the second kind separately in the payload preview as re-run candidates. If any appear at all, step 1 settled for a weaker head route than it should have — options 3-5 exist so this set is empty.

Write the resolved verdicts, updated evidence levels, and the gate's reasoning back to the findings file before composing anything.

If a specific finding genuinely needs deep verification, that is a separate decision the user makes outside this command — never against the PR's working tree.

## 3. Compose the comment set

Only findings that still carry verdict `post` after step 2 — anchored, and through the gate. Nothing else is mentioned, counted, or alluded to. The anchors are already resolved; do not recompute them here.

- **Match the wording to the evidence as it stands after step 2.** `verified` and `gated` may be stated as fact, and both must name their basis **in the code** — the file and lines where it holds, or a command the author could run themselves. Never cite the verification process: "this cleared our verification" names the review tooling, which the last bullet forbids, and tells the author nothing they can check. `grounded` is a statement with its basis named ("`foo.ts:40` returns undefined when …"). `diff-only` and `unstated` go out as questions — "is X handled when …?" — never as a diagnosis.

  **These two rules pull against each other, so here is the resolution worked through.** An executed check is the strongest evidence you have and the one thing you may not name. Convert it into steps the author can repeat:

  > ✗ "this cleared our verification" · ✗ "verified by the test-coverage pass" · ✗ "an automated probe showed…"
  > ✓ "open request `A`, attach window 7, call `cancelRequestsDisplacedBy(store, 7, 'cancel-on-close')`, dispatch the attach at half the grace, then advance the timer — `A` ends at `status: 'responded'` instead of `windowIds: [9]`"

  The rule underneath: **name what the author can run, never what you ran it with.** A reproduction is stronger evidence than a citation of authority anyway — it survives the author disagreeing with you.
- One concrete, actionable point per comment. No severity shouting, no stacked findings in a single comment, no restating the diff back at the author. **This binds in both directions: never two threads on one defect, and never two defects in one thread.** A body that introduces a second problem with its own fix has produced a second finding — give it its own thread or leave it out; folding it in is how one comment reaches five paragraphs. Measured on the longest comment this command has sent, a welded-in second case was its single largest component, at roughly a third of the text.

### Length: lead and fold

**These comments are read by two audiences with opposite needs.** An author skims for what to change; a reviewer returning to the thread wants the basis. At six to nine comments per pull request, an unstructured comment is more prose than any author reads carefully — and what they most need is stranded in the middle of it. Meanwhile the full record already exists in the handoff, so nothing about a long comment is protecting information.

Compose every comment as an inverted pyramid, with the supporting evidence folded:

```markdown
<lead — the defect at this line, what it costs, and any clause that narrows the claim>

<the ask — one sentence: a concrete change, or a question where the evidence is weaker>

<details><summary>Basis</summary>

<citations, a reproduction the author can run, reach limits, what was checked and found not to apply>

</details>
```

**The lead is the whole comment for most readers**, so it holds the defect at this line, its consequence, the ask, and any clause that narrows the claim — and nothing else. Everything that merely supports the point goes under the fold.

**Where a comment needs more than its lead to be fair to the finding, say so in the payload preview with the reason** — the user is approving the exact text, and an exception they can see before it is sent is the point. A complete finding — mechanism, counterexample and fix — routinely fits in a short body; length has never been the constraint on being convincing.

**Nothing that changes the verdict may go under the fold.** Any clause that narrows the accusation — "the diff is a net improvement overall", "not reachable from a web page", "pre-existing at the base and only newly visible" — belongs in the lead, as part of the sentence making the accusation. The fold carries evidence *for* the point above it, never a qualification *of* it. A short comment that overstates is worse than a long one that does not: rewriting overstated findings is the single most expensive thing the gate does, and a fold is a very effective way to hide the correction it just paid for.

**The fold is not extra room.** It is where citations go so the lead can stay short — not space that was freed up. If the fold is carrying the argument rather than the evidence for it, the lead is in the wrong place.

### Group same-class Mediums into one comment

**Where three or more Mediums in the `post` set are instances of one class, they go out as a single comment, not as three or nine threads.** A class here is the *defect shape*, not the file and not the reviewer that found it: assertions that cannot fail, unbound catches that discard the error, a routing predicate changed at N sites and tested at M of them, a documented invariant the type does not carry. Nine separate threads about nine vacuous assertions are nine notifications, nine round-trips and one point; measured on a single pull request here, the test-quality class alone accounted for nine of eighteen Mediums.

Compose it like this:

- **Anchor the group at its strongest instance** — the one whose consequence is largest, or where the pattern is clearest to read — using the anchor already computed for that finding in step 2. The other members are named in the body as `path:line` plus one clause each. Discard their anchors; do not open a second thread for a member.
- **Open with the shape, then the list.** "Four assertions in this file pass whether or not the code under test does anything —" then the four lines. The author fixes a class in one pass; making them rediscover the same shape four times is the cost this rule removes.
- **State the count in the body**, so nothing looks omitted.
- **Never group across classes**, never group to get under the volume threshold, and never put a High or Critical inside a group — those are always their own comment, even when they share the class. A group is a compression of repetition, not of severity.
- **Two members is not a group.** Post them separately; the framing costs more than it saves.
- **The lead still gets the shape and the count, not the enumeration**, and the members go under the fold, one line each. A group is one point whose evidence happens to be a list; treating its ninth member as a reason to shorten would push the composer back toward nine separate threads, which is the thing this section exists to prevent.

Count a group as **one** comment against the volume check in step 2, and say in the payload preview which finding ids each group covers — the user is approving a set, and a group silently swallowing four ids is a set they cannot check.

This is the one exception to *one point per comment* above, and it is an exception on the *instances*, not on the point: a group makes exactly one point and lists where it holds.
- Summary body: one short paragraph on what was reviewed and the through-line of the comments. No counts, no mention of what was held or dropped, no merge verdict.
- **Never mention the review tooling** — no agent names, no skill names, no "automated review", no reference to `.claude/` paths. This repository is public and so are these comments.

## 4. Show the exact payload and stop

### Thread map

A reply and a resolution both address a *thread*, while the handoff holds a comment URL. Build the map once:

```bash
gh api graphql -f query='
query($owner:String!,$repo:String!,$pr:Int!,$cursor:String){
  repository(owner:$owner,name:$repo){
    pullRequest(number:$pr){
      reviewThreads(first:100, after:$cursor){
        pageInfo{ hasNextPage endCursor }
        nodes{ id isResolved isOutdated
          comments(first:100){ nodes{ databaseId author{login} createdAt } } } } } } }' \
  -F owner=<owner> -F repo=<repo> -F pr=<N>
```

A comment URL carries `#discussion_r<databaseId>`, which is what locates its thread. **Follow `hasNextPage` to the end** — a PR can hold more than a hundred threads, and stopping at the first page silently loses findings.

Check the map before sending: every `verdict: reply` and `verdict: resolve` must resolve to a `threadId`. One that does not is not sent — downgrade it to `hold` and say so.

An outdated thread is still a valid target. Replies and resolutions address the thread, not the line, so a finding whose code the author deleted outright can still be answered where it was raised — which is the one advantage a reply has over a fresh comment.

### Three groups, one approval

Print what will be sent, verbatim:

1. **Resolutions** — per finding: id, `threadId`, the path and line of the original comment, and its first line. No text is sent.
2. **Replies** — per finding: id, `threadId`, the `databaseId` being replied to, and the full body.
3. **New comments** — as before: `path`, `line`, and full body, plus anchor status.

**Flag any comment whose lead carries more than the defect, its consequence and the ask**, with the reason it needs to. One line per exception, not a paragraph. The user is already reading the exact payload here, so an exception named beside it is something they can push back on before it is sent rather than after.

Alongside them, two short lists, or an explicit "empty" for each:

- Matches against `published-log`, **for `post` findings only** — a `reply` or `resolve` matching the log is how it found its thread, not a duplicate, and belongs in group 1 or 2 above rather than here.
- Threads proposed for resolution that carry a comment from someone other than us, added after ours — **with that comment's text**.

The second list is not a note; it is a question. Someone who replied in a thread is waiting for an answer, not for the thread to close under them. Resolving one of those needs an explicit decision, and asking means using the question tool — a question raised inside a status report is not asking.

Against each comment, print its anchor status from step 2 — whether that line is one the PR added or unchanged context, and how much of the finding's cited range the diff actually covers. Call out every `introduced` finding anchored to unchanged code explicitly, and every comment anchored to a **secondary citation** rather than its `file:` range. Without this the user is approving a `file:line` pair they have no way to check, and the first time anyone learns the anchor was wrong is when the comment is already on the pull request.

Print two short lists alongside the payload, or say they are empty:

- **Which head route step 1 took** (options 1-6), and for a partial read, which files the gate was cleared to read from the local checkout. Every verdict below rests on this, and it is the one thing the user cannot reconstruct from the comments.
- **Findings held as `inconclusive: unreadable`** — good findings lost to a source-access gap rather than to their own weakness, and the set worth re-running once the head is properly reachable.

Ask for approval. Anything other than explicit approval — silence, a question, a partial objection — means post nothing and change nothing. If the user amends wording, re-print the amended payload and ask again.

## 5. Post

**Re-check freshness first.** Run `gh pr view <N> --json headRefOid -q .headRefOid` again, immediately before sending, and compare it against the SHA from step 1. That check is by now separated from this moment by the gate, the composition work, and an open-ended wait for the user — easily long enough for the author to push. If it differs: post nothing, report both SHAs, and offer a fresh `/pr-review`.

**Order: resolutions, then replies, then the review.** Resolutions go first because they are silent — if something later fails, the quiet half is already applied and does not have to be untangled.

**Resolve**, per thread:

```bash
gh api graphql -f query='
mutation($threadId:ID!){ resolveReviewThread(input:{threadId:$threadId}){
  thread{ id isResolved } } }' -F threadId=<thread-id>
```

A thread already at `isResolved: true` is skipped and noted in the report. Resolving it again is not an error, but it is not an action either.

**Reply**, per finding:

```bash
gh api repos/{owner}/{repo}/pulls/<N>/comments \
  -f body='<text>' -F in_reply_to=<comment-databaseId>
```

**Replies cannot be bundled.** The Reviews API's `comments` array has no `in_reply_to` field, so a review cannot express them at all: N replies are N calls and N notifications. That is the reason the threshold in step 2 is five rather than ten.

Then the new comments:

- A **single** review carrying all inline comments, so the author gets one notification rather than one per finding. Build the payload as JSON and pass it on stdin — `gh api` supports `key[subkey]=value` and `key[]=value` but has **no** syntax for an array of objects, so the repeated-field form cannot express `comments` at all:

  ```bash
  gh api repos/{owner}/{repo}/pulls/<N>/reviews --input - <<'JSON'
  {
    "commit_id": "<the SHA just re-checked>",
    "event": "COMMENT",
    "body": "<summary>",
    "comments": [
      { "path": "src/…", "line": 92, "side": "RIGHT", "body": "…" }
    ]
  }
  JSON
  ```

- `commit_id` pins the review to the code that was actually reviewed. Without it GitHub anchors against whatever head it sees when the request arrives.
- Where a finding's cited range lies wholly inside one hunk, it may carry `start_line` with `start_side` alongside `line`/`side`. Never construct a range that crosses a hunk boundary.
- `event` is always `COMMENT`. Never `APPROVE`, never `REQUEST_CHANGES`.
- If the API rejects a comment for an unanchorable line, do not retry blind: drop that one comment into the summary body and re-send once. On any other failure, report the exact error and post nothing further — a partial review is worse than none.
- **Read the error before deciding whether it is a transport failure or a rejection, and never retry until you have.** A transport failure — `tls: failed to verify certificate`, a proxy reset, a DNS failure, a timeout with no HTTP status — means the request may or may not have reached GitHub, and a blind retry is how one review becomes two. This is not hypothetical on this machine: the same `gh` TLS failure has now been observed twice, once on this exact POST mid-publication and once on a `gh pr view` in `/pr-tickets:jira`, both times with adjacent calls succeeding a minute later. The recovery is always the same and it is a *read*, not a retry:

  1. `gh api repos/{owner}/{repo}/pulls/<N>/reviews --jq '.[] | {id, submitted_at, user: .user.login}'` — did the review land?
  2. If it did, the send succeeded regardless of what the client printed. Go to step 6 and record it. Do not re-send.
  3. If it did not, re-send the identical payload once, then re-read again.

  A rejection is different and is recognisable by having an HTTP status and a message body: fix what it names, or stop. Only a transport failure gets the read-then-retry treatment, and it never gets more than one retry.
- **Record what already succeeded before you stop.** A send that went through but was never written down becomes a duplicate on the next run.

## 6. Record what was posted

Write back into the findings file, per posted finding: `verdict: posted` plus the returned comment URL, and the review URL at the top.

Plus — for every finding that reached the pull request for the first time — an entry in the header's `published-log` block. Both header blocks have this shape, and it must match the one `/pr-review` writes exactly:

<!-- BEGIN handoff-header-schema -->

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

<!-- END handoff-header-schema -->

Per finding, by how it was sent: `verdict: resolved` with the thread id, `verdict: replied` with the reply's URL, `verdict: posted` with the comment's URL. A reply into an existing thread adds no new `published-log` entry — that finding is already in it.

**A grouped comment is recorded once per member, not once per comment.** Every id the group covered gets its own `verdict: posted` and its own `published-log` entry, all carrying the same comment URL, each at its own `file:line`. Recording only the lead id would leave the other members looking unpublished — and the next round would send them again, which is the one failure in this flow with no undo. Add `(grouped with F<a>, F<b>)` to each entry so a later reader can tell why several ids share a URL.

**If the header has no `rounds:` or `published-log` block** — the file was written before the format existed — create both now, in the shape above: a single `rounds:` line for the round this file records, with `reviewed` dated as best you can tell and `, published <date>` appended for this run, and a `published-log` carrying the entries you are about to write. Do not backfill entries for anything this run did not send; a log that claims sends it cannot evidence is worse than one that starts here.

**Write the entry only after the API has returned the comment's URL.** A comment with no URL is a send you are not sure succeeded: do not mark the finding `posted`, do not write the entry, and report the error. A spurious entry silently blocks a real finding from ever being sent.

Append `, published <date>` to the current round's line in `rounds:`, then append the gate's cost to the same line: `— gate <N>m over <K> findings, <C> rationale-wrong`. Take `<N>` from the clock, not from an estimate — note the time when the gate is dispatched and again when its verdicts return, and write the difference in whole minutes. `<K>` is the number of findings that entered the gate and `<C>` how many came back `CONFIRMED, RATIONALE WRONG`; both are counts you already have in front of you at this point. If the gate did not run, write `— gate skipped: <why>` instead of inventing a zero. Every prior claim about what this step costs was somebody's structural guess, and a guess written down once has a way of being quoted as measurement afterwards.

Re-running this command must never repost anything already marked `posted` — that exclusion happens at the top of step 2, before the gate and before anything is composed. Duplicate comments on a colleague's PR are the one failure mode with no undo.

## 7. Point at what is left

Add one line to the report naming what did not reach the pull request and is not meant to: the count of findings still carrying `hold` with `scope: pre-existing`, the path of `.claude/reviews/pr-<N>-deferred.md` if it exists, and `/pr-tickets:jira <N>` — plugin-qualified, with the number substituted — as the step that triages them into Jira. `/pr-tickets` is the plugin, not the command; a user who types it gets nothing.

**A pointer, not the work.** Do not triage them here, do not recommend which deserve a ticket, and above all do not create one: this command's approval gate covers comments on a pull request and nothing else, and a second external system reached under it is a second irreversible action the user approved once, for something else. Say the count and the command, and stop.

## 8. Close with the approval call

**The report ends here, every time.** A short **Approval** section: which findings block, named one by one, then whether this pull request can be approved as it stands. Neither half is ever skipped — the run just sent comments to another engineer, and the verdict is what tells the user whether that was the end of it.

Three verdicts, and nothing between them:

- **Approve** — nothing outstanding blocks it. Say so plainly; if non-blocking comments were posted, name them as author's-discretion in the same sentence.
- **Approve once the open comments are answered** — nothing found is severe enough to block on its own, but comments are sitting on the PR unanswered. Name how many.
- **Do not approve yet** — at least one blocker. List them.

**What blocks.** A finding blocks when it is this PR's own defect, it is still live, and it is severe enough that shipping it is a real cost:

- Any Critical or High that reached the PR and is not `fixed` — including `partial`, `not-fixed`, and `contested-by-author` where the author's argument has not been accepted.
- Any Medium whose recorded consequence is user-visible, security, or safety-net — the same split step 3 uses to decide what gets sent at all. A Medium marked `internal` never blocks.
- Anything the security review confirmed against key material, the extension surface, or the message-passing boundary, at any tier.
- A gate failure that was never resolved: a finding published under an unverified claim, or an anchor the user chose to drop that carried a High.

**What does not block**, however loud it looked in the review: `hold` findings scoped `pre-existing` (they are not this PR's regression — they are step 7's business), anything `dropped`, Mediums scoped `internal`, and missing-test findings unless the untested path is itself one of the blockers above.

**Format.** Blockers first, then the verdict line. **One row per blocker, named individually** — id, `file:line`, the consequence in a clause, and its current state (`posted`, `not-fixed`, `partial`, `contested`). Never `see the Critical findings above`: a pointer is not a list, and the user is deciding whether to merge. No re-argument of the finding; it is already on the PR in full. If the blocker list would run past about six rows, say the count and list the Critical and High ones only.

**When nothing blocks, write `No blockers.` on its own line** before the verdict. An approval whose blocker list is simply absent is indistinguishable from one where the section was forgotten, and this command is the last step that looks at the whole set.

**This is a recommendation to the reader, not an action.** Never run `gh pr review --approve`, `--request-changes`, or any other state-changing call on the pull request. The approval gate in step 4 covered posting comments; approving a colleague's PR is a different irreversible act and was never in it. Say the verdict and stop.

**Say it even when it is uncomfortable.** A verdict of "do not approve yet" on a PR the user is waiting to merge is the whole point of the section. Do not soften a live High into "worth a look", and do not withhold an **Approve** because the review found a long tail of `internal` Mediums — a section that always says the same thing carries no information.

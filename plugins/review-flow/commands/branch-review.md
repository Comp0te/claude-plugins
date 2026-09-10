---
description: Pre-PR review gate for the current branch. Dispatches focused reviewer agents plus the built-in security review; produces one ranked report in chat. Report-only — never modifies files.
argument-hint: [base-branch]
---

Run a report-only review of the current branch. You MUST NOT modify any file tracked by git, and MUST NOT commit or push at any point of this flow. The single exception is the serial probe pass in step 4, which the main loop runs only on a clean tree and reverts immediately, leaving no net change; agents get no such exception. The deliverables are the two files in step 5 — the handoff file and the deferred-work log, both inside the git-excluded `.claude/reviews/`, and the only permitted writes — and one report in chat. Findings are reported; fixes are the user's separate decision.

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

## 1. Establish the diff and the requirement

- Base branch: `$ARGUMENTS` if given; otherwise the repo's default integration branch (check `git remote show origin` HEAD, and prefer `develop` over `main`/`master` when both exist).
- If the current branch has no commits ahead of base and no uncommitted changes: report that there is nothing to review and stop.
- Collect the diff in **two** parts, because no single command produces both:
  - **Committed work** — `git diff <base>...HEAD` (three dots: merge-base to HEAD), with the touched-file list from `git diff --name-only <base>...HEAD`.
  - **Uncommitted work** — `git diff HEAD` for tracked modifications, plus `git status --porcelain` for untracked files. **None of this appears in the three-dot diff.**
- **The review scope is both**, and it is what agents must be given. Handing a reviewer only `git diff <base>...HEAD` silently reviews a different branch state than the one on disk — and the code it cannot see is the code the user is about to commit, which is the whole point of running this before a PR. Where the tree is dirty, say so in the report.

### Resolve the requirement

Find what this branch was *supposed* to do. Try these in order and stop at the first that resolves:

1. **A plan** — look in `docs/superpowers/plans/` for one matching the branch or its subject. If it has `<frozen-after-approval>` sections, take the frozen Global Constraints and, where tasks carry their own contracts, the frozen Intent / Ask First / I/O matrix of the tasks this diff touches.
2. **A ticket** — if the branch name or the commit subjects carry an issue key (`ABC-1234`), fetch it and take the description and acceptance criteria.
3. **Nothing resolves** — proceed without one, and record that fact for the report.

**Extract only the contract: Intent, Ask First, and the I/O matrix.** Never the Code Map, never the implementation steps, never a summary of what was built or anything from this conversation. Intent and the matrix were written before the code existed, which is exactly what makes them useful here — they let a reviewer ask whether the code does what was *asked*. The Code Map and the steps describe how it was built, and a reviewer holding those inherits the implementer's framing, wrong assumptions included, and reverts to checking whether the code agrees with itself.

If nothing resolved, say so plainly in the report: *"no plan or ticket resolved — reviewers checked internal consistency only."* A review with no requirement cannot tell you the branch did the right thing, and that limitation should be visible rather than discovered later.

## 2. Dispatch focused reviewer agents (parallel, background)

From the list of agent types available in this session, select every reviewer-style agent whose description declares trigger conditions matching this diff (touched paths or diff content). Do not use a hardcoded roster — project-level agents unknown to this command must be picked up by the same rule. Typical matches:

- an agent triggering on crypto/signing/key paths, or on manifest/CSP/permissions files → dispatch if such files changed. A project may cover both with one agent or with two; dispatch what its descriptions declare, never a remembered roster;
- an agent triggering on try/catch, message passing, or storage → dispatch if the diff contains such code;
- a *separate* comment/documentation reviewer, **if the session offers one at all** → dispatch only when comments or docs are a substantial part of the diff. Comments the change merely left stale are the deletion check's second half, so on an ordinary code diff this is a duplicate dispatch, not extra coverage. Where the session offers no such agent — the common case — comment rot is the deletion check's business and nobody else's, which is why its trigger below is two-part;
- a test-coverage reviewer marked "use on every review" → always dispatch.
- **a security-focused reviewer → always dispatch, trigger or no trigger.** Pick the best available one for what the diff touches; if none declares a matching trigger, dispatch the closest one anyway with an explicit brief to review this diff for security consequences, and say in the report which one you used and that it was off-trigger. **This agent is the security coverage, and step 3's built-in `security-review` is only the fallback for its absence.** An agent is scoped by the diff you hand it and can always run; the built-in chooses its own diff and carries exclusions written for server-side web applications. That is why this dispatch is unconditional: it must not be absent because the diff missed a path trigger, since nothing behind it is equivalent.

**Size the roster to the diff, then trim by trigger.** The value of another reviewer is another lens on the same files, and it runs out fast on a small change — five agents on a three-file diff produce five readings of the same forty lines and a classification pass that costs more than the findings are worth.

- **≤10 changed files → 3 slots**, filled in this order: the test-coverage reviewer, the security-focused reviewer, and **the one remaining agent whose declared trigger this diff satisfies most strongly** — the error-handling reviewer when the diff touches try/catch, error callbacks, fallbacks or retries, the type reviewer when it reshapes types. Nothing beyond the three, **except the deletion check, which is a standing dispatch outside this cap** — see *Deletion check* below.
  **The third slot is a slot, not a fixed name.** Hardcoding the deletion check there would leave a small diff whose entire subject is error handling with no error-handling reviewer at all — and most branches land in this bucket. Say in the report which matched agent you dropped.
  **Where the error-handling and type triggers are both satisfied, take the type reviewer** — the same tie the sibling `/pr-review` command breaks, and for the same reason: it returns materially more findings no other agent found.

  It settles ties only — where the *subject* of the branch is error handling, that reviewer still wins on the "most strongly satisfied" test above, which is decided first. Note also that type runs on opus and error handling on sonnet, so the tie is broken toward the more expensive agent; where the branch is large enough for both, take both rather than choosing. Keep recording `found-by:` each run.

  **This roster is tuned on the sibling command's pull-request data**, not on branch reviews — so re-decide it here once branch handoffs exist to count.
- **11-30 files → up to 5.**
- **>30 files → the full matched set.**

Where more matched than the cap allows, drop by marginal yield and by how much of the trigger the diff actually satisfies: an agent whose subject appears in one file of thirty is a wasted dispatch, and you can tell which those are before sending them. **Say in the report which matched agents you dropped and why** — a silently trimmed roster reads as full coverage. The security-focused and test-coverage reviewers are never the ones dropped.

**Issue every dispatch in one message.** Compose all the briefs, then send the agent calls together as parallel tool uses in a single turn — never one call per turn. A brief runs to six or eight thousand characters, so each turn spent emitting one costs twenty to thirty seconds of wall clock before the *next* agent has started, and the fan-out is waiting on the last one. Measured on two real pull-request reviews using this same roster, the gap between the first dispatch and the fifth was **99 and 141 seconds** of the flow standing still. The agents share nothing and the roster is already decided; staggering them buys nothing.

### Run the gate once, before dispatching

**Before the first agent goes out, run the repo's own check/test gate yourself, once, and put its result in every agent's prompt.** Every reviewer otherwise re-derives the same facts from the same tree at the same commit: N agents each running the full suite and a full type-check, concurrently, is N× the work for one answer, and on a laptop it is what takes the machine down. Measured on a 10-core/16 GB machine, seven agents doing this drove peak load to 2.7× the core count and node RSS to 8 GB.

Give agents the result as a fact — "the gate passes at this head: <suites/tests>, tsc clean, lint 0 errors" — so nothing needs re-running to establish it. If the gate *fails*, that is itself the first thing to report: say so in the report's verification section and pass the failure to the agents rather than hiding it.

### Resource discipline (tell every agent, verbatim)

> The repo's full gate has already been run for you; its result is above. Do not run the full test suite, and do not run a whole-project type-check — they are already done and running them again in parallel with the other reviewers will exhaust the machine. Run only *targeted* checks that a specific finding needs: a single test file, a scoped grep, a small standalone probe. When you do invoke the test runner, always pass `--maxWorkers=2 --watchman=false`.
>
> **Executable checks may be run only in `<runnable path>`, which is at commit `<sha>`. Run them nowhere else** — not in the directory you happen to start in, and not in a copy of the tree. If that slot says **none**, no test runner can start anywhere this run: settle what you can by reading and mark it `grounded`, never `verified`.

**Fill that slot before you dispatch — and here, unlike on a pull-request review, it is almost always a real directory.** This flow reviews the session's own checkout: the repository at the current working directory, at `HEAD`, with `node_modules` already installed. That is the value to write, and writing `none` when a runner *can* start silently caps every finding in the review at `grounded`, because the reviewer agents all carry a standing rule that an unnamed runnable path means nothing may be executed. The one case for `none` is a tree so dirty that a targeted run would measure the user's uncommitted work rather than the branch — say which it was.

Note the asymmetry with `/pr-review` deliberately: there the gate comes from CI and the readable tree is a bare source extract, so `none` is the common answer. Here the gate was just run locally, in this very directory, which is what makes it runnable.

The worker cap matters more than it looks: the runner defaults to one worker per core minus one, so each agent that starts a suite can claim most of the machine, and several agents doing it at once oversubscribe it many times over.

### No mutation (tell every agent, verbatim)

> Do not modify, delete, or revert any git-tracked file, even temporarily and even if you intend to restore it. This review runs against the user's real working checkout — there is no scratch copy — and that tree may hold uncommitted work that exists nowhere else, which a stray revert would destroy permanently. You are also one of several reviewers sharing that one checkout: your edit is visible to all of them, and a reviewer running a check against a tree another reviewer has mutated gets a wrong answer and reports it with confidence. If a finding would be proved by a mutation probe — deleting a guard to show no test catches it — do not run it. Describe the exact probe (file, lines, the change, the expected failure) in the finding and mark it `evidence: proposed-probe`. Creating *new* untracked scratch files outside the repo is fine.

This matters more here than on a pull-request review, which works from a disposable worktree. Here the tree under review is the user's own, and step 1 deliberately folds uncommitted changes into the diff.

### Verify the tree survived — do not trust that it did

**Snapshot `git status --porcelain` before dispatching, and take it again once every agent has reported.** The paragraph above is a request, and a request aimed at an agent holding write and shell tools is not a guarantee. Where the session offers reviewer agents defined without those tools, prefer them; for the rest, verify.

If the two snapshots differ, say so in the report at once and name the paths. Every finding produced in that window was read from a tree somebody mutated mid-review, so its evidence level means nothing — and the change may be an agent's edit sitting on top of the user's uncommitted work. **Do not try to restore the tree yourself:** you cannot tell the agent's edit from the user's work, and a wrong revert destroys something that exists nowhere else. Report it and let the user decide.

Launch all selected agents in a single message (parallel, background). Give each: the base branch, the branch name, the gate result above, the requirement from step 1 when one resolved, and instructions to review **both parts of the step 1 scope** — `git diff <base>...HEAD` *and*, when the tree is dirty, `git diff HEAD` plus the untracked files — in the repo at the current working directory, returning findings as a list of `{file:line, scope, issue, why it matters, evidence}`, where `scope` is exactly one of:

- `introduced` — the diff caused or exposed this. Without this change, it would not be there.
- `pre-existing` — already true before the diff; the review merely walked past it.

and `evidence` is exactly one of:

- `verified: <check>` — a *targeted* executable check confirmed the finding (a repro command, a single test file, real output). Name the check. Mutation probes are not run by agents — see `proposed-probe`.
- `grounded: <paths read>` — the agent read the cited code beyond the diff hunk, and the claim rests on what it read.
- `proposed-probe: <file, lines, change, expected failure>` — the finding would be proved by mutating the tree, which agents must not do. The main loop runs it serially in step 4 and resolves the finding to `verified` or drops it.
- `diff-only` — inferred from the hunk alone; surrounding code not read.

This is self-reported and therefore soft: it separates "I ran something" from "I read the file" from "I inferred it", which is all it is meant to do. If an agent omits the field, record `unstated` — never infer the level on the agent's behalf.

**A fifth level exists but no agent may write it: `gated: <file:lines>`.** It is written only by the step 4 verification gate, and it means *a second reader confirmed the claim against the code* — strong evidence, and still evidence produced by reading. Keep it distinct from `verified`, which asserts that something was **executed and observed**: collapsing the two makes the gate's own output into the label that exempts a finding from the gate, and leaves `/pr-recheck` hunting for a probe description that was never written. Where both apply, `verified` wins and the gate's confirmation goes in the recorded reasoning.

### The consequence bar (tell every agent, verbatim)

> Report a finding only if you can name its **observable consequence**: what breaks, for whom, under which input or state. "This is fragile", "this could be clearer", "this might cause problems" are not consequences — if that is all you have, you have not finished investigating, and the finding does not go in. Everything you return is read, ranked, written up and verified downstream, so a finding nobody can act on costs what an actionable one costs and crowds it out. There is no quota in either direction: return forty if forty clear the bar, return none if none do.

This is a bar on the *statement*, not a cap on the count and not a severity judgment — "I can say what breaks" is a question about how far the agent got, and stays clear of the ranking forbidden below. Deliberately no number: a cap makes the agent rank its own findings to decide what fits, which is the thing this flow assigns to step 4, where the project context to do it actually exists.

**Tell every agent, verbatim: do not assign severity, priority, criticality, confidence, or ranking.** A reviewer sees the diff and the requirement, and nothing else — not what is deliberately out of scope, not what is already ticketed, not what the project decided on purpose. Judging consequence from inside that blind spot produces a number that looks like information and is not. Severity is assigned in step 4, where the context to assign it actually exists. If an agent returns one anyway, discard it rather than carrying it forward.

**When a requirement was passed, tell every agent this too, verbatim: the requirement is context for judging what you find, never a boundary on what you look for.** A bug the requirement never mentions is still a bug and must still be reported. Where the code and the requirement disagree, say which one you believe is wrong and why — do not assume the requirement is stale. Where the diff appears to trip a stated **Ask First** condition without evidence it was asked, report that as a finding in its own right.

### Deletion check (standing dispatch, outside the cap)

**This dispatch is additional to the roster above and is never counted against it, at any diff size.** The cap sizes the number of *lenses on added code*; this reviewer reads what left and what the change silently falsified, which no other check looks at. Inside the ≤10 bucket it would lose the slot on almost every branch — its second trigger fires on nearly every diff, but comment rot is by definition *incidental* to the change, so the "subject is the point of the change" test above would rule it out precisely where it is the only owner of the class. `/pr-review` and `/pr-recheck` state the same exemption; the three commands must not disagree about this.

If the diff removes or replaces meaningful code — ignoring pure renames, moves, and whitespace — **or leaves comments, docstrings or docs standing next to code it rewrote** — dispatch one additional **context-free** reviewer alongside the others. Prefer a purpose-built one: if the session offers an agent whose description declares removed/replaced code as its subject, dispatch that and hand it the same diff scope and gate result as everyone else. Otherwise compose it inline with this brief:

> For each chunk of removed or replaced code, ask one question: did it carry behavior or a contract that this change neither re-established elsewhere nor intentionally retired? Report the resulting regression, orphaned reference, or newly-dead code. Removed code that was genuinely dead, or whose behavior is demonstrably re-established elsewhere in the diff, is not a finding — say where it was re-established. Then check the comments and docs the change left *unchanged* around the code it touched: a surviving claim the change invalidated is the same blind spot in a second form. Return findings in the same shape as every other reviewer, and do not assign severity.

Deleted lines are the blind spot every other check shares: reviewers read what was added. Nothing else in this flow looks at what left.

**Keep it context-free either way.** Do not pass this reviewer the requirement from step 1 or the branch's stated intent. A rationale explains why the author believed the removal was safe, and this is the one check whose value depends on establishing that independently.

**Its second half is the only owner of comment rot, which is why the trigger is two-part.** Re-reading the comments and docs a change left *unchanged* around code it touched is a separate blind spot from deleted lines, and it does not need a deletion to open: a purely additive hunk falsifies the comment above it just as reliably. Triggering only on removal would leave a whole class of diff with nobody re-reading a single surviving comment.

## 3. Security review in the main loop (while agents run)

The built-in `security-review` skill is the **fallback**, not a parallel pass. Check three conditions, in this order.

**Skip when a security-focused reviewer was already dispatched in step 2.** That agent got this review's diff and a brief written for this repository; the built-in gets a diff it chose itself and priors written for server-side web applications. Running both buys a second opinion at the price of a discovery sub-task plus one parallel sub-task per candidate finding, and the measurement says it does not pay: across 18 runs in a repository that also carries its own security agent, the built-in appeared in exactly one `found-by` line and was never the sole finder of anything. Where step 2 found no security-oriented agent to dispatch — a repository that ships none of its own — this skill is the security coverage, and the conditions below decide whether it can run at all. Say in the report which of the two you got.

**Skip on content:** skip it when the diff contains no production code at all (docs/markdown-only, tests-only, or styles/i18n/formatter-config-only). When skipped, say so in the report.

**Check the base, because the skill cannot be scoped.** It is a static template whose diff is a fixed shell interpolation, `git diff origin/HEAD...`, evaluated in the session's working directory. It takes no scope argument: anything you pass it is ignored for the purpose of choosing the diff. The head side is fine here by construction — the session's checkout *is* the branch under review. The base side is not: step 1 lets `$ARGUMENTS` override the base branch, so `git symbolic-ref refs/remotes/origin/HEAD` may name a different branch than the one every other check in this flow is diffing against.

Check it explicitly before invoking:

- **`origin/HEAD` already resolves to the base from step 1** → invoke it.
- **It does not** → you can make it hold, subject to the guard below:

  ```bash
  OLD=$(git symbolic-ref refs/remotes/origin/HEAD)   # save the exact value first
  git remote set-head origin <base>                  # local, no network
  #  → invoke security-review here
  git symbolic-ref refs/remotes/origin/HEAD "$OLD"   # local restore
  ```

  **Restore with `symbolic-ref`, never with `git remote set-head origin -a`.** The `-a` form queries the remote, so it fails whenever the network is unavailable — offline, on VPN, or inside a command sandbox (measured: `exit=128`). When it fails you are left pointing at this review's base **permanently and silently**, mis-scoping every later consumer of `origin/HEAD`.

  **Guard — `origin/HEAD` is shared with every other session.** `refs/remotes/*` is common to the whole clone (only `HEAD`, `refs/bisect/`, `refs/worktree/` and `refs/rewritten/` are per-worktree), so retargeting it silently rescopes any concurrent review's security pass, and the two restores clobber each other. Before touching it, run `git worktree list`: if it shows any worktree other than the main checkout, **skip security-review** and name what you found in the report. This over-triggers on a worktree leaked by a killed run, which is the safe direction; printing what was found is what lets the user see that a `git worktree prune` is due. Do **not** use `refs/pr/*` as the liveness signal — nothing removes those on a kill.
- **You chose not to change the ref** → skip it and record in the report: *"built-in security-review skipped — its diff is hardcoded to `origin/HEAD...`, which points at `<other-branch>` rather than this review's base `<base>`."* Security coverage then rests on the security-focused reviewer agent from step 2 and the repo's own static analysis; say so, so the gap is visible rather than assumed covered.

Never invoke it against a mismatched base and present the result as this branch's security review: it produces confident findings about a diff nobody asked about, and on a release-branch review that routinely means hundreds of unrelated files.

If `security-review` is not available in this session, note that in the report instead of silently substituting your own pass — that is a different condition from the base mismatch above and should not be conflated with it.

Do NOT run a general correctness pass yourself. From a context already holding the diff and every agent's output, a main-loop pass reads the code for agreement with what the reviewers already reported rather than for defects — the specific failure the agent roster exists to avoid.

## 4. Classify

Wait for the background agents. Then work through the merged finding set before writing anything. This step exists because it is the only point in the flow holding both the diff and the project's context — the reviewers had the first and not the second.

While waiting, ground findings yourself by **reading** the code an agent cited. The gate already ran in step 2 — do not run it again.

Reading has three outcomes, not one:

- **The claim and its mechanism both hold** → raise the finding's `evidence` level.
- **The defect is real but part of the explanation is not** → keep the finding and **correct its text**, saying what you corrected. This outcome matters more here than anywhere else in the flow: the handoff is consumed by whoever changes the code, so a wrong mechanism becomes a wrong patch — and a finding whose rationale is refutable tends to get rejected wholesale, taking the real bug inside it along with it.
- **The claim does not hold** → see *Drop noise* below. Doubt alone is not enough; a named refutation is.

Reading never silently removes a finding.

### How to wait

When you run out of grounding work and the agents are still going, **block in the foreground**: `perl -e 'sleep <n>'` with a matching tool timeout. One call, one turn, `<n>` seconds of real waiting.

**Size the first block to the fan-out, then drop to short ones.** A flat 300 costs up to five minutes of dead time after the last agent has already reported, on every run. Block once for about as long as you expect the slowest agent to still need — 240s on a large diff, 120s on a small one — and after that **block in 30s steps, not 60s**. The cost being avoided is the turn, not the second.

**The tail is where this is actually lost.** On two real pull-request reviews using this roster the reviewers were all finished at +969s and +987s and the main loop did not notice until +1102s and +1129s — **133 and 142 seconds slept past the end of the fan-out**, on runs that had sized their first block correctly. Past your estimate of the slowest agent, every further block risks dead time proportional to its own length; 30s bounds the loss at 30s. Calibrate the first block against the slowest agent rather than the diff: on this roster the security reviewer is the long pole at 11–13 minutes from its own dispatch, with the rest in at 5–11.

Do **not** wait by backgrounding a sleep. A backgrounded command returns the turn to you immediately, so `sleep 300 &` waits zero seconds and costs one full turn — and by this point in the flow a turn re-reads a 150–250k context. Measured on a real run of the sibling `/pr-review` command: eleven backgrounded sleeps burned **2.3M prompt tokens, ~10% of the entire session**, and produced no wall-clock delay at all. The single foreground `perl` call that replaced them did the whole job.

The same applies to any "let me check if they're done yet" poll — `TaskList`, listing the tasks directory, stat-ing output files. Agent completions arrive as notifications on their own; polling for them buys nothing and costs a turn each time. Block, and let the notification wake you.

### Run any `proposed-probe`, serially and only on a clean tree

Once every agent has reported and nothing else is touching the tree, resolve the probes agents were forbidden to run. **First check `git status --porcelain`:**

- **Tree is clean** → run them one at a time: apply the described mutation, run only the tests it names (`--maxWorkers=2 --watchman=false`), revert immediately, and confirm `git status --porcelain` is empty again before starting the next. Resolve each probe to `verified: <what failed>` or drop the finding.
- **Tree has uncommitted changes** → do not run any of them. This review works against the user's real checkout, and a probe's apply/revert cycle cannot be made safe around work that exists nowhere else; a revert that overshoots destroys it. Keep each finding at `proposed-probe` and say plainly in the report that probes were not run because the working tree was dirty, listing what each would have proved so the user can run it themselves after committing or stashing.

A probe is worth running — it is the difference between "this test looks decorative" and "deleting this leaves the suite green" — but never at the cost of uncommitted work, and never concurrently with other readers. If a probe cannot be run for any other reason, keep it as `proposed-probe` and say so rather than silently promoting or dropping it.

**Assign severity.** Rate each finding by the consequence of leaving it in, for whoever uses this software: Critical / High / Medium / Low. Judge each finding on its own — do not lower one because a related finding was dropped, and do not raise one because several checks happened to report it. A reviewer that returned a severity anyway does not get a vote.

**A finding you rate Low is dropped here, and goes no further.** It is not authored, not written to the handoff file, not written to the deferred-work log, and does not appear in the report. This is a deliberate policy: a Low is by definition something whose consequence does not justify anyone's time, and carrying it costs an authored record, a file entry and a share of every later step's context — for material that is, in practice, never read. Two consequences, both load-bearing:

- **The call is irreversible, so make it on the finding's consequence and not on your confidence in it.** A finding you doubt is not thereby Low: an unproven claim about a signing path is a High you have not verified, and it belongs in the set with its evidence level saying so. Downgrading uncertainty into Low is how a real defect disappears silently, and after this step nothing can recover it.
- **Disclose the count, never the contents.** The report says `N findings rated Low and dropped at classification` and nothing more — no list, no appendix, and not one word about a dropped finding in any file. **The count alone is also written to the handoff header, as `low-dropped: <N>`** — `0` when there were none, never omitted. That is deliberate and it is not an exception to the rule above: a number carries no contents, and it is the only trace a Low leaves anywhere once the report scrolls away. The Low drop is the one irreversible decision in this flow, and the question the field exists to answer is whether the bar is discarding real work. The number keeps the policy visible and lets the user notice if it is ever absurd; the contents are exactly what this rule exists not to carry.

**Rate before you drop, and rate the whole set first** — deciding to drop while still ranking invites lowering a borderline finding because the set already feels long.

**Split Medium by consequence, and give every Medium a `consequence:` field.** With Low dropped at classification, Medium is the whole review — measured across the last five reviews run here, 79 of 89 findings landed in it against 9 High — and a tier holding ninety percent of the set stops carrying information. The value is one of:

- **a named user-visible or security effect**, in one sentence saying who sees it and under what input or state: wrong data on screen, a control that does nothing, a state that does not recover, work silently lost; or key material, signing, vault, permissions, origin or sender trust, CSP, the message-passing boundary.
- **`safety-net — <what it fails to catch>`** for a test that cannot fail: a vacuous assertion, an expectation derived from the artefact it guards, an assertion-by-absence. It qualifies because the code it claims to protect is unguarded while the suite says otherwise — the one defect class no gate will raise again.
- **`internal — <why>`** for everything else: a type that could be narrower, an imprecise comment, a duplicated literal, a coverage gap with no named consequence, a missing diagnostic behind an error the user already sees.

The bar is a *named* consequence, not an imaginable one: if the chain to a user needs three unstated conditions, it is `internal`. Cheapness to fix is not a consequence, and doubt belongs in `evidence`, never here.

**Nothing is dropped by this split.** This command gates a branch the user owns, so `internal` findings stay in the handoff file and in the report in full — the user is the one who will act on them, and a cheap cleanup they can do in the same pass is worth more here than it would be on someone else's pull request. What the field buys is the ordering in step 6 and a correct default when the same finding later travels to `/pr-publish` or `/pr-tickets:jira`. Critical and High carry no `consequence:` field: at those severities the consequence is the severity.

Where a requirement resolved in step 1, anchor severity to it: a finding that contradicts the frozen Intent, breaks a stated **Always**, or trips an **Ask First** that was never asked outranks one that merely offends taste, however elegant the latter's argument. A row of the I/O matrix with no passing test is a gap in the contract itself, not a style note. Without a requirement you are rating consequence on judgment alone — still worth doing, just weaker, and the report should not pretend otherwise.

**Confirm scope.** Take each reviewer's `introduced` / `pre-existing` as a starting point and correct it where the reviewer was working blind — code that merely moved is not introduced, and a latent bug the diff newly made reachable is. When the two are genuinely indistinguishable, treat it as `introduced`: this is a gate on the branch, and the cost of over-including is a paragraph the user skips.

**Record disagreement.** Where one check raised a finding and another examined the same code and cleared it, do not silently pick a winner. Read the clearing check's reasoning and establish *what question it actually answered* — a clearance that answers a narrower or adjacent question is not a clearance, and this is the common case, because two agents given different briefs rarely converge on the same question. Keep the finding and record the disagreement in its `contested` field for step 5. Only if the clearance is genuinely on point and correct does the finding go under *Drop noise* below — and then say which check settled it. A disagreement resolved in your head and left out of the file cannot be acted on by anything downstream.

**Drop noise.** A finding you are not confident is real, and which no evidence level supports, does not need a home — drop it rather than filing it as `pre-existing`. Dropping is an expected outcome, not a failure. This is the one judgment reserved for findings you have actually read: it does not license the suppression forbidden in step 6, which is about findings you doubt but cannot dismiss.

### Verification gate

Not to be confused with the repo's own check/test gate in step 2 — that one establishes whether the branch builds and passes; this one establishes whether a *finding* is real.

**Once severity is assigned, verify every `introduced` finding at Critical or High whose `evidence` is weaker than `verified` and whose probe was not run.** Those are the ones this gate can *resolve* rather than merely display — a Medium carrying `⚠ ungrounded` keeps its marker into the report unverified, deliberately: gating every Medium would cost more than the branch gate is worth, and the marker is what tells the reader which ones were never settled. It is usually a handful of findings and often none.

Why here rather than downstream: the consumer of the handoff file changes code. A wrong finding at this severity does not cost a wasted read — it costs an edit to working code, plus tests written to pin behavior that was never wrong. The file's own contract already says *"a `diff-only` Critical that turns out not to exist must be rejected, never patched into existence"*; this step is what gives whoever reads that sentence something to act on. You are also at the peak of context here, and they will have strictly less.

**Run it after the probes, never instead of them** — a probe executes, which is stronger evidence than reading, so never spend the gate on something you can run. Note the dirty-tree case: when the tree is dirty no probe runs at all, which is precisely when this gate carries the whole weight. It is read-only, so it works there.

Dispatch a single `finding-gate-verifier` with the gated set. Tell it, verbatim: the tree to read is the repository at the current working directory; whether that tree is clean or holds uncommitted changes; and that where settling a claim would need more than that tree, it returns **inconclusive** rather than escalating.

**Do not tell it to invoke a skill, and do not hand it a skill's routing vocabulary.** It holds `Read`, `Grep` and `Glob` and no `Skill` tool, so it cannot run one; it carries its own restate–confirm–refute protocol, and that protocol is the calibration this gate supplies. An instruction to route, escalate, or cap at a named tier describes a machine it does not have, and what comes back is an improvisation wearing the name of a procedure that never ran. Give it a readable tree and the finding set — not a method.

That agent is defined without write or shell tools, which is what makes it safe against a live checkout — **do not substitute a verification skill for it**. A skill deep enough to be worth substituting is one that spawns its own agents, and those agents hold write tools; running them against a working tree that may carry uncommitted work existing nowhere else is the risk this gate was shaped to avoid.

Apply the outcomes:

- **TRUE POSITIVE** → keep, **replace** the finding's `evidence` with `gated: <the file and lines the gate confirmed it at>`, record the reasoning, and drop the `⚠ ungrounded` marker. Never write an evidence label that names a tool or a procedure without the code location behind it: a label citing a process nobody can re-run buys a finding past every later check on the strength of a name.
  **Replace, do not append.** A finding carrying both its original `grounded:` line and a new one is a finding whose evidence level is whatever a downstream grep happens to match first, and three commands key decisions on that field. One `evidence:` line per finding, always.
  **And write `gated:`, not `verified: gate`.** The gate read code; it did not run anything. `verified` is the tier that means executed-and-observed, it is the tier `/pr-publish` lets past its own gate unexamined, and it is the tier `/pr-recheck` re-runs by execution — a read-only verdict wearing that label is a claim about a probe that does not exist.
- **CONFIRMED, RATIONALE WRONG** → keep, and rewrite the finding's text from the corrected basis before it reaches the file. Same outcome as the grounding pass above, reached by a second route; it is the most common non-trivial result and the one that turns into a wrong patch if it is filed as a plain true positive.
- **FALSE POSITIVE** → `dropped — <the failing gate and its reasoning>`. Write it into the handoff file as dropped-with-reason rather than deleting it: a check did raise it, and a reader deserves to see it resolved rather than never mentioned.
- **INCONCLUSIVE** → keep, keep the `⚠ ungrounded` marker, and say what was left open.

## 5. Findings handoff file

**Delegate the writing.** By this point you are holding 150k+ of context and the finding set is settled — emitting the document yourself costs a full turn at that context plus the document's own weight in every turn after it. Instead:

1. **Author the classified finding set once, in your dispatch prompt**, as a compact record per finding — id, `file:line`, severity, scope, issue, why it matters, suggested fix, evidence string, which checks found it, `contested` where it applies, and the gate's reasoning for anything the step 4 gate touched. This is the single act of authorship in the flow and it stays yours: the writer must not invent, re-rank, re-scope, merge, split, or drop anything.
2. **Dispatch one writer subagent, in the background**, with that set, the header facts (branch, base, head SHA, file count, check/test gate result, which checks ran, what was skipped and why), the file format below, and the consumer contract **to be reproduced verbatim**. It writes the handoff file and appends the deferred-work entries, and returns **only**: the two paths, the number of findings written, and the per-severity tally. Nothing else — the document must not come back into your context.

   Tell it, verbatim: *open every finding with a heading whose first line is exactly `### F<n>` and nothing else; put the severity, path and everything else on the lines below it.* Consumers locate findings by that heading, and a decorated one — `### F1 — Medium — \`path\`` — breaks per-id verification for the whole file.
3. **Write the chat report in step 6 while the writer runs**, from the same set you just authored, not from the file. The single-source invariant holds through the classified set rather than through the file; both artifacts derive from one act of authorship, which is what the invariant was protecting — and because the report never reads the file, the two are genuinely independent and there is no reason to serialise them. The footer is the one part that waits, since it names the path and the count check has to have come back first.

Model: **Sonnet.** This is a fidelity job over many heterogeneous records at high output length, not a reasoning job — a dropped finding or a paraphrased evidence tier is invisible to you unless you re-read the file, which would refund the saving. Haiku is not worth that risk here; Opus is not needed, since no judgment is left to make.

Verify without reading the body: compare the returned count and severity tally against your own, and run

```bash
grep -c '^### F' <path>; grep -c '^severity:' <path>; grep -c '^verdict:' <path>
grep -c '^evidence:' <path>; grep -c '^found-by:' <path>
grep -c '^head SHA:' <path>
```

All five must equal the finding count, and **`head SHA:` must be exactly 1** — the header check, anchored at column 0 for the same reason the rest are. Six numbers, ~110 tokens, and they catch four failure modes: a dropped finding, a writer that emitted the fields as list items or folded `severity` into the heading, a writer that renamed a key, and a header nothing downstream can read the commit out of — which no later step would notice, because every consumer of those fields fails open on an absent one. On a mismatch, re-dispatch with the missing ids or the mis-shaped fields named — do not patch the file yourself.

A branch review writes the file once and nothing else ever appends to it, so a raw count is right here. (The pull-request side needs a subtraction instead: `/pr-tickets:jira` adds a second `verdict: ticketed` line per promoted finding, so there a file legitimately carries more `verdict:` lines than findings.)

If no agent tool is available, write both files yourself and say so in the report footer.

---

The file goes to `.claude/reviews/branch-<slug>-<shortsha>.md` in the repository root — `<slug>` is the current branch name with `/` replaced by `-` (`release/2.7.0` → `release-2.7.0`), `<shortsha>` is `git rev-parse --short HEAD`. It is what a downstream fix agent consumes; it survives the session and is the only place volume is unbounded.

Confirm git ignores the path **before dispatching**, so the writer never has to reason about it: if `git check-ignore -q .claude/reviews/` fails, append `.claude/reviews/` to `.git/info/exclude` — local to the clone and never committed. Do not touch a tracked `.gitignore`, and never let the file become a tracked change.

Tell the writer, verbatim: *the only files you may create or modify are the handoff file named above and `.claude/reviews/branch-<slug>-<shortsha>-deferred.md`, for this review's own `<slug>`/`<shortsha>` and no other. Touch nothing else, and no git-tracked file under any circumstances. This review runs against the user's live checkout, which may hold uncommitted work.*

- Head the file with `branch`, `base`, and `head SHA`, so a consumer can tell which review is current when several files exist for the same code. If a file for this same head SHA is already there, overwrite it rather than adding a second.
- Every finding that survived step 4, in full detail — **except a Medium carrying `consequence: internal`, which is written short**: every field present in the usual order and syntax, but one sentence of `issue:`, one of `why:`, one line of `fix:`. That class is recorded rather than sent, and it is now the bulk of the corpus since Low collapses into Medium rather than out of the review. Critical, High, and any Medium naming a user-visible, security or safety-net effect keep full detail. If one is later promoted, re-derive it from the code rather than elaborating the short form. Low was dropped at classification and is not recorded here or anywhere else.
- Per finding, under exactly these keys and no synonyms: `file:`, `severity:`, `scope:`, `issue:`, `why:`, `fix:`, `evidence:`, `found-by:`, `verdict:` — plus the stable id in the `### F<n>` heading, matching the report numbering. Plus:
  - **`consequence:`** — written on **every** finding rated Medium and on no other severity, from the split in step 4: the named user-visible or security effect, `safety-net — <what it fails to catch>`, or `internal — <why>`. One line, column 0. Verify it: `grep -c '^consequence:'` must equal the number of Medium findings. Both `/pr-publish` and `/pr-tickets:jira` key defaults on this field and both fail open on its absence, so an unwritten one is a filter that silently stops filtering.
  - **`contested:`** — set it whenever one check raised the finding and another examined the same code and cleared it, naming what the clearing check actually answered. Carried as prose in a *found by* line this is invisible to any consumer; as a field it is the one signal that a finding which looks settled is not. Omit it when no check disagreed — never write `contested: none`.
  - **`gate:`** — the step 4 gate's reasoning, whatever the outcome: what was confirmed and where, which clause was corrected, what refuted it, or what was left open. Give it that name rather than folding it into prose; it is what a reader needs to tell a confirmed finding from an unexamined one. A finding the gate refuted is written as `verdict: dropped — <reasoning>` rather than omitted, so a reader sees it resolved rather than never raised.

**Pin the field syntax, and tell the writer this verbatim.** Every field above is written as `key: value`, one field per line, **starting at column 0** — not as a list item, not folded into the heading, not merged with a neighbour. And exactly one line per key per finding.

**The same rule binds the header facts.** `branch:`, `base:`, `head SHA:`, `files changed:`, `checks that ran:`, `checks skipped:`, `low-dropped:` are `key: value` at column 0 too. On the pull-request side the finding fields have held on every run since this rule was written while one archived file rendered its whole header as a markdown list, so the header is the half that actually fails — and a header field nothing can read is indistinguishable from one that was never written.

**Pin the key spellings too, and give the writer the list above literally.** Naming a field in prose — "which checks found it", "why it matters" — leaves the writer to invent the key, and it invents a different one on a different run: the pull-request archive here carries `found by:` in three files and `found-by:` in two, same field, same instruction. `found-by:` is the one that decides roster and model tier, so a rename nothing declares makes every measurement across runs incomparable while every consumer keeps failing open on the absent key.

**Pin `found-by:`'s *value* too, not just its key: `found-by: <agent>[, <agent>]*` — agent names, comma-separated, and nothing else.** No semicolons, no parentheticals, no "independently confirmed by", no trailing "— 2 checks". Measured across six pull-request reviews and 90 findings: 20 lines separated with commas, 17 with semicolons, and 11 carried free prose, so the one field the roster and model-tier decision rests on could not be counted by `grep` at all and had to be normalised by hand. Anything worth saying beyond the list of names belongs in `contested:`, which exists for exactly that and is already read by every consumer. A key whose value has no grammar is only half pinned.

The rule is not cosmetic and it is not the writer's stylistic call. This file is read downstream by `grep` and by per-id `awk` loops, never by a parser: severity decides whether a finding is held, `verdict` decides whether it is collected, `evidence` decides whether it is gated again. A field the writer moved into the `### F<n>` heading, or emitted as `- severity: Medium`, is a field those consumers do not see — and every one of them fails open, treating "absent" as "nothing to do here". Nothing anywhere in the flow re-reads the file to notice.

`severity:` deserves its own mention because it is the field most often lost this way: it reads naturally in a heading and it is the one the publishing and ticketing steps both key on.
- Then this consumer contract, verbatim:

  > Findings in this file are **unverified** except where `evidence` reads `verified` (a targeted check was executed) or `gated` (a second reader confirmed the claim against the code, at the lines named). Severity and `scope` were assigned in step 4 by the main loop, using project context the reviewing checks did not have — better grounded than a reviewer's guess, still a judgment and not an established fact. `scope: pre-existing` means the branch did not cause it: fixing it here is a choice, not a gate. Resolve each finding to exactly one of `verdict: fixed` / `verdict: rejected — <why it is not real>` / `verdict: deferred — <why>`. `rejected` is an expected outcome, not a failure: a `diff-only` Critical that turns out not to exist must be rejected, never patched into existence. Do not edit code to satisfy a finding you could not confirm.
  >
  > A finding already carrying `verdict: dropped — <reasoning>` was refuted before this file was written and needs no action from you; it is recorded so you can see it was resolved rather than never raised. A finding marked `⚠ ungrounded` was not settled either way — confirm it yourself before changing any code for it. A finding carrying `contested:` had two checks disagree about it; read what the clearing check actually answered before you act, in either direction.

### Deferred-work log

Every finding classified `scope: pre-existing` **that survived step 4** also gets written to `.claude/reviews/branch-<slug>-<shortsha>-deferred.md` — same directory, same `<slug>`/`<shortsha>` as the handoff file above, same git-exclusion guarantee, confirmed the same way. A pre-existing finding rated Low was dropped at classification and does not reach this log either: the log feeds ticket triage, and a problem not worth reporting is not worth a ticket.

**One file per review, not one shared log.** The user triages this immediately after the review and promotes what deserves it to tickets, so the file is a short-lived worklist for exactly this run, not an accumulating backlog. Never write to a shared `deferred-work.md`, and never append to another review's file. It also means two reviews running at once cannot interleave writes into the same document.

Create the file if absent, heading it with this note:

> Pre-existing problems surfaced by the review of `<branch>` @ `<shortsha>` — code this branch did not cause. This is a worklist, not a tracker: nothing here is scheduled, and promoting an entry to a ticket is a manual decision. Triage it and delete the file; anything still here later is unprocessed, not backlogged.

Write one entry per finding:

```markdown
- source: branch-review <branch> @ <shortsha> — F<n>
  date: YYYY-MM-DD
  summary: <one sentence>
  evidence: <why it is real, and why this branch did not cause it>
```

If the file already exists — a re-review at the same head — **append** and never edit, reorder, remove, or dedupe existing entries. A write that requires reading and reconciling the whole file is a write that quietly stops happening. Within one review the repeat volume is small enough that this costs nothing; the per-review split is what keeps it that way.

## 6. Merge and report

Produce ONE report in chat, written from the classified finding set you authored in step 5 — **do not read the handoff file back to compose it.** The file is downstream of the same set, not upstream of the report; re-reading it just pays for the document twice.

Rules for the report:

- **Report every finding that survived classification.** Do not drop, sample, or collapse distinct issues to keep the report short, and **do not suppress a finding because you doubt it** — suppression outside the one rule below is the only irreversible step in the pipeline. Low is the *only* permitted omission: it is a severity judgment made in step 4 with the project's context, and it is disclosed as a count (`N findings rated Low and dropped at classification`) at the end of the ranked findings.
  **Doubt is not a verdict; evidence is.** A finding the step 4 gate refuted leaves the report as `dropped`, with its reasoning recorded and written to the handoff file — a resolution, not a suppression, and the only way a raised finding may leave. Everything else that was raised gets reported, whatever you privately think of it. What this rule forbids is the silent version: dropping on a hunch, with nothing written down and nobody able to tell it happened.
- Deduplicate findings that multiple checks reported for the same location/issue. `confirmed by N checks` stays as a note on merged entries but is **not** a confidence signal — those N checks are the same model reading the same diff, so their agreement is correlated. `evidence` is the confidence signal. Never present a count as verification.
- Rank the `introduced` findings into Critical / High / Medium. Within each: `file:line` — issue — which check found it — `evidence:` — why it matters.
- **Split the Medium block on `consequence:`** — the ones naming a user-visible or security effect first, then a sub-heading `Medium — internal (no user-visible or security consequence)` for the rest, same detail and same numbering. Nothing is omitted; the split is an ordering, so the two decisions the reader is making — what must be addressed before this branch becomes a pull request, and what is cleanup worth doing while the file is open — do not arrive interleaved.
- **Collapse a repeated Medium into one entry.** Where three or more Mediums are instances of one defect shape — assertions that cannot fail, unbound catches that discard the error, a predicate changed at N sites and tested at M — report the shape once at its strongest instance, list the other `path:line`s beneath it with one clause each, and say how many there are. They keep their individual ids and their full records in the handoff file; the report is what compresses. Two instances is not a repetition — report them separately. Never collapse across shapes, and never put a High or Critical inside a collapsed entry.
- **Out of scope** — a section below the ranked findings, for everything marked `scope: pre-existing`. Same per-finding detail, keeping severity, but not ranked in with the rest: this command gates a branch, and a pre-existing Critical is not a reason to hold one. Say plainly that these predate the branch and are candidates for their own ticket. Omit the section when empty rather than writing "none".
- Report the repo's check/test gate result from step 2 with its actual numbers, and distinguish a real failure from an environment artifact (stale `node_modules`, missing native deps, a runner that needs a flag to start at all) — say which it is.
- Mark any Critical, High **or Medium** carrying `diff-only`, `unstated`, or a still-unrun `proposed-probe` with `⚠ ungrounded`. It keeps its severity and its position; the marker only says that the finding it rests on was inferred rather than executed. Medium is included because it is now the bulk of every report — with Low dropped at classification, a typical set is a handful of Highs and everything else Medium. A probe that step 4 actually ran is `verified` and carries no marker — and neither does a finding the step 4 gate confirmed, which is what that gate exists to clear. A marker surviving to the report means the gate was inconclusive; say so in one clause rather than leaving the reader to guess whether it was even attempted.
- Mark with `⚠ invisible-to-gates` any finding whose defect no check in the repository would catch — it type-checks, lints, and passes the suite, and the gate would go green shipping it. Say in one clause *why* nothing catches it (the value is substituted at build time and never exists under the test runner; the file is not loaded by the type-checker; nothing reaches the branch in any test). This is not a severity bump and never becomes one: severity stays the consequence of leaving the finding in, and this marker is about **detectability** — an ordinary Medium announces itself when someone trips over it, one carrying this marker does not. On a pre-PR gate it also answers a question the user is about to ask: whether merging and relying on CI would have caught this. It would not.
- Mark any finding carrying `contested` with `⚠ contested`, at every severity, and say in one clause what the clearing check actually answered. A finding two checks disagree about is the one a reader is most likely to assume was settled — the marker exists to stop that assumption, and it is independent of the evidence level, which is why a `verified` finding can carry it too.
- **Above ~15 findings: keep full detail for Critical and High, and compress Medium to one line each** (`file:line` — issue — `evidence:`). There is no Low tier to compress — it was dropped at classification. The step 5 handoff file holds full detail for all of them **except `consequence: internal`, which is short there too** — for every other class nothing is lost by compressing here, but for that one this line is the whole record, so it must name the mechanism rather than gesture at it. An unbounded chat report is read less carefully than a short one, and the Criticals are what get skimmed.
- If any agent or skill failed, add a note ("<name> failed: <reason>") — never block the report on one failed check.
- If no requirement resolved in step 1, say so here in one line — the reviewers checked internal consistency only, and a reader should not mistake that for a verdict on whether the branch did the right thing.
- Footer: give the paths of both step 5 files — the handoff file, and the deferred-work log when this review appended to it.
- **Verdict**: the last thing in the report, on every run. See below.

### Verdict

**The report ends here, every time** — after the footer, after the rule candidates, after everything. Two parts, in this order, and neither is ever skipped.

**Blockers — named one by one.** Per blocker: its number, `file:line`, and the consequence in a clause. Never `see the Critical section above`; a pointer is not a list. Do not restate the finding beyond that clause — it is written out in full a few paragraphs up, and the point of the section is the set, not the argument.

This command is a *gate*, and a ranked list is not a gate: severity says how bad a thing is, not whether it stops the branch. You are the only party in the flow holding both the diff and the project's context, so the call is yours and it is cheap to make here. What blocks:

- any Critical or High marked `scope: introduced`;
- any Medium whose `consequence:` names a user-visible or security effect — a Medium marked `internal` never blocks;
- anything contradicting the requirement from step 1 where one resolved: a finding against the frozen Intent, a stated **Always** broken, an **Ask First** nobody asked — even at a modest severity.

**What does not block**: `scope: pre-existing` findings, since the branch did not cause them; Mediums marked `internal`; and anything still carrying `⚠ ungrounded` — say it needs confirming first rather than gating a branch on something nothing verified.

**When nothing blocks, write `No blockers.` on its own line.** Most branches land here; say it in one line rather than promoting the worst finding to fill the section. What is *not* acceptable is leaving the section out, which reads as an oversight rather than an all-clear.

**Ready-to-open call — one line, one of exactly three.** The branch has no pull request yet, so the question this answers is the pre-PR form of "can it be approved as it stands":

- **Ready to open as a pull request** — nothing blocks. Name any non-blocking findings as cleanup worth doing while the file is open.
- **Ready once the blockers are addressed** — each blocker is a patch, not a decision.
- **Not ready yet** — at least one blocker needs a rewrite or a design call.

**Say it even when it is unwelcome**, and say it plainly: a section that always reads the same carries no information. Do not soften a live High into "worth a look", and do not withhold a **Ready** because the review turned up a long tail of `internal` Mediums.

**A recommendation, never an instruction to edit.** Whoever acts on it decides, and the handoff contract still forbids changing code for a finding they could not confirm. This command modifies nothing.

### Rule candidates

Second-to-last section of the report: after the ranked findings, after the footer paths, and before the Verdict.

Once the findings are ranked, scan them for **bug classes** worth encoding as a static-analysis rule instead of re-reviewing forever. Ask it here, while the context of the bug is still loaded — not a week later. A finding qualifies only if all three hold:

- **Syntactically recognizable** — detectable from code shape alone (a forbidden call, a dangerous sink, a missing wrapper), or expressible as data flow from an untrusted source to a sink. Anything needing project semantics, cross-file type knowledge, or human judgment does not qualify.
- **Repeatable by someone else** — another contributor would plausibly write the same thing. A one-off typo or a local slip does not qualify.
- **Not already covered** — read the repo's own static-analysis config before listing (e.g. `.semgrep.yml`, the eslint config) and confirm nothing there already catches it. Grep it; never assume. If the repo has no such config, skip this section entirely.

Prefer findings carrying `verified` or `grounded` evidence. A `diff-only` finding may be listed, but say so — encoding a bug that may not exist is worse than no rule.

One line per candidate: the bug **class** (not the instance), the finding number it came from, and whether it is **pattern-shaped** (a single wrong line, expressible as a pattern) or **taint-shaped** (untrusted data reaching a dangerous sink — needs taint mode, not a longer `pattern-either`).

Do not write the rule here: this command is report-only, and the repo's rule file is tracked. Naming the candidate is the whole deliverable; authoring it is a separate session that follows the repo's own rule-writing and rule-testing conventions.

**Most reviews produce zero candidates. Omit the section rather than manufacture one** — a speculative rule costs every contributor on every run, forever.

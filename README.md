# compote

Personal Claude Code plugins: a pull-request and branch review flow, a spec-driven development
toolkit, and the agents that close its two open ends — reading a design into a spec, and
verifying a change in the running application.

## Plugins

- **review-flow** — read-only review of a GitHub pull request or the current branch.
  Dispatches focused reviewer agents matched to the diff, verifies every finding against the
  source before it is reported, and publishes an approved subset as inline PR comments.
  Requires the GitHub CLI (`gh`), authenticated.
- **pr-tickets** — triages the findings a review deliberately left unposted (pre-existing
  problems and deferred work) and turns the ones worth tracking into Jira issues, after
  verifying each against the base branch. Requires `review-flow` to be installed, Jira tooling
  that exposes issue creation, and a `.claude/pr-tickets.json` file committed in the consuming
  repository describing that repository's Jira conventions.
- **rn-performance-reviewer** — a React Native performance reviewer for the review flow.
  Reports statically-provable defects in lists, effects and subscriptions, animations, Skia
  usage, memoization, bundle size and image rendering, and never speculative optimization
  advice. Install it only in React Native repositories.
- **figma-flow** — reads a Figma node for implementation and returns a compact spec in the
  project's own code vocabulary — tokens, components and icons drawn from the project's
  design-mapping document — instead of dumping raw design-tool output into the caller's context.
  Also downloads and verifies image and vector assets. Needs a Figma integration installed
  separately, and a `.claude/docs/figma-mapping.md` in the consuming repository; without the
  mapping document it produces raw values and reports every one of them as a blocker.
- **ui-verifier-mobile** — verifies UI changes in a running React Native app against a
  caller-supplied checklist: drives the simulator or emulator with `agent-device`, measures what
  it sees, captures screenshots, and returns a pass/fail report with evidence. Reports findings
  only and never modifies code. React Native specifically, not mobile in general — much of what
  it knows is about RN's accessibility layer and Metro.
- **ui-verifier-web** — the same for a web app or browser extension, driving the browser with
  `agent-browser`. Deliberately independent of `ui-verifier-mobile`: the two share no dependency,
  and the verification discipline they both carry is generated into each from
  `shared/verification-discipline.md` rather than extracted into a third plugin.

Both verifiers read a `.claude/docs/ui-verification.md` in the consuming repository for that
project's own facts — bundle ids, build and launch commands, auth routes, app traps — and say so
at the top of the report when it is absent.

## Installing

```bash
claude plugin marketplace add <owner>/<repo>

claude plugin install review-flow@compote --scope user
claude plugin install pr-tickets@compote --scope user   # optional; needs review-flow and Jira tooling
```

Install the performance reviewer per repository rather than at user scope — at user scope it
joins the reviewer roster of every project, including the ones its triggers can never match:

```bash
cd <a React Native repository>
claude plugin install rn-performance-reviewer@compote --scope project
```

Install the verifiers and the extractor per repository too, and only the verifier that matches
the platform — at user scope both verifiers would load in every project:

```bash
cd <a mobile repository>
claude plugin install ui-verifier-mobile@compote --scope project
claude plugin install figma-flow@compote --scope project

cd <a web repository>
claude plugin install ui-verifier-web@compote --scope project
```

## Command names

Commands resolve under their plugin's prefix, and only under it:

```
/review-flow:pr-review     /review-flow:branch-review
/review-flow:pr-publish    /review-flow:pr-recheck
/pr-tickets:jira
```

## Updating

Installing copies the plugin into `~/.claude/plugins/cache/compote/<name>/<version>/`. It is
not a live reference to this repository, and **the cache is keyed by version** — so editing a
plugin without bumping `version` in its `plugin.json` leaves every installed session running
the old copy. Neither `marketplace update` nor a repeated `install` refreshes it: both see
that version already present and do nothing, silently.

So bump the version whenever the content changes. That is what the cache key is for, and it is
also what makes `claude plugin tag` meaningful:

```bash
# edit plugins/<name>/... , then raise "version" in its plugin.json and the marketplace entry
claude plugin marketplace update compote
claude plugin install <name>@compote --scope user
```

To pick up a same-version edit during development, force it — there is no other way:

```bash
claude plugin uninstall <name>
claude plugin install <name>@compote --scope user
```

## Migrating a project off its local verifier or extractor agent

Seven projects held a project-local `ui-verifier` agent and four a local `figma-extractor` —
copies that predate this marketplace. A local agent under `.claude/agents/` shadows a shipped one
of the same `name:`, so installing the plugin next to it changes nothing until the local copy is
gone. Note the shipped verifier agent is now also called `ui-verifier`, so that collision is exact
and silent. The recipe,
run once per project:

1. **Install** the plugin the project needs, at **project** scope, from inside that repository —
   `ui-verifier-mobile` or `ui-verifier-web` (never both, and never at user scope: they would
   then load in every repository and the agent would have to guess which world it's in), plus
   `figma-flow` where the project reads Figma designs.
2. **Move the agent's memory store to the address the *plugin* agent reads.** A project-local
   agent is addressed by `<agent name>`, but an agent that arrives from a plugin is addressed by
   `<plugin name>-<agent name>` — so `agent-memory-local/ui-verifier/` becomes
   `agent-memory-local/ui-verifier-mobile-ui-verifier/` (or `-web-`), and the extractor's store
   becomes `agent-memory/figma-flow-extractor/`. Do this before the agent ever runs, and if it has
   already run, merge rather than overwrite — it will have created the correct directory empty and
   written into it. Left alone, the old directory keeps every accumulated note and the shipped
   agent cannot see any of it: no error, no empty file, just an agent that has silently forgotten
   everything it learned. **This is measured, not assumed** — a pilot run wrote to the
   plugin-prefixed address while its migrated store sat one directory over, and the same happened
   independently for the extractor. It also means **a rename moves the address**: renaming either
   the plugin or the agent orphans the store unless it is moved in the same change.
3. **Drain the memory store's promotion queue before deleting anything.** Read every file
   against the shipped agent and resolve it as **promoted** (a driver or discipline fact now in
   the shipped agent, with its CLI version stamp — delete the note), **kept** (a genuine project
   fact — stays, under the moved store), **corrected** (the memory measured something the
   agent only hypothesized — the agent changes, then the note is redundant and goes), or
   **retired** (a fixed bug — delete, or move to a tracker, never migrate). An open bug living
   only in memory is reported to whoever tracks issues, not deleted and not folded into a facts
   file, since a defect isn't a fact about how to verify. A file with no verdict means the
   migration didn't read it.
4. **Write the project's facts file** (`.claude/docs/ui-verification.md`, or
   `figma-mapping.md` for the extractor) from what the local copy and its memory uniquely knew:
   bundle ids or extension ids, build and launch commands, sandbox exclusions, the authentication
   route, and anything that has previously caused a wrong verdict. A fact left only in a file
   about to be deleted is lost.
5. **Prove the shipped agent works** with one real verification run (and, for the extractor, one
   real extraction) before deleting anything. If the run surfaces something the local copy knew
   and the shipped agent doesn't, add it to the shipped agent and re-run the sync and checker
   scripts first.
6. **Delete the local copy** — `git rm .claude/agents/<name>.md` in the consuming repository.

**Known defect in step 6:** `.claude/` is git-excluded in several of these repositories (checked
via `.git/info/exclude`). `git rm` fails there with nothing staged for the project's author to
commit, since the file was never tracked. Deleting the local copy in that case is a plain `rm`,
and there is no diff to review or commit — say so explicitly rather than reporting a commit that
doesn't exist. Until the local copy is removed, the project holds both it and the shipped agent
at once, and **the local one wins**; that overlap is only safe as a temporary state between step
5 and step 6, never as an end state.

**Two pilots have run steps 1–4 of this recipe** (a mobile project for `ui-verifier-mobile` and
`figma-flow`, a web project for `ui-verifier-web`); steps 5 and 6 are deferred to a session
with a booted simulator/emulator and a reachable Figma node, so both pilots currently hold a
local copy and the shipped plugin at once. **Remaining projects, not started:** five hold a local
verifier, and three of those also hold a local extractor.

## Repository-local reviewers

The review commands select reviewer agents dynamically from whatever the session offers.
Reviewer agents defined locally in a consuming repository (its own `.claude/agents/`) are
picked up automatically alongside the ones this marketplace ships — no registration needed.

## Write your own security reviewer

`review-flow` deliberately ships no security agent, and both commands treat Claude Code's
built-in `security-review` as a **fallback**: it runs only when the roster came up with no
security-oriented agent at all. Give a repository its own reviewer in `.claude/agents/` and
the built-in stops running there entirely.

That is not a stylistic preference. The built-in is a fixed prompt with a fixed diff, and two
of its properties work against a specific project:

- **It chooses its own diff.** The skill interpolates `git diff origin/HEAD...` in the
  session's working directory and takes no scope argument, so it reviews whatever those two
  happen to point at. When they point at the wrong thing it does not fail — it reports
  confident findings about code that is not under review. An agent reads the tree you name and
  the diff you hand it.
- **Its exclusions encode a server-side threat model.** It will not report a missing
  permission or authentication check in client-side JS/TS, on the stated grounds that the
  backend validates everything. In a browser extension, a CLI, or any app whose trust boundary
  *is* the client, that rules out the most important class of finding there is. It also
  declines prototype pollution unless confidence is extremely high, treats React and Angular as
  categorically XSS-safe, and excludes anything it reads as resource exhaustion.

A reviewer you write yourself carries your project's boundaries instead: which process is
trusted, which inputs cross a boundary, which of your own guards a finding must be checked
against. Measured over 18 runs in a repository that had both, the built-in was never the sole
finder of anything, while the repository's own agent was the single most productive reviewer
in the roster.

Nothing needs registering — write the agent with a `description` that declares when it
applies, and the dynamic selection will find it.

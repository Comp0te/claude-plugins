# Working Agreements

## Before Writing Code

- If requirements are ambiguous, ask clarifying questions before writing code.
- When there's a bug, start by writing a test that reproduces it, then fix it.
- When multiple interpretations exist, present them — don't pick silently.
- If you're uncertain, say so explicitly. Don't paper over confusion with confident phrasing.

## Code Comments

Write for someone reading the file in a year, not for whoever reviews the PR this week.
That single test kills most bad comments.

- **Why, not what.** If it restates the code, delete it. If a rename would say it, rename.
- **Don't narrate the failure the code prevents.** A comment that only makes sense to someone
  who read the diff is a commit message in the wrong file.
- **Comment the public API. Private members get nothing** unless the signature is genuinely
  ambiguous, then one line. Rationale for a constraint goes on the exported symbol that owns it,
  once — the same rationale in two files means it belongs one level up.
- **No process artifacts** — no review or finding IDs, no "verified by…", no before/after
  narration, unless that history is a constraint that still binds.
- **Budget: 2 lines inline, 4 for a docstring — a ceiling, not an average.** Exceptions: a money-
  or security-critical contract on an exported symbol, and a module doc that maps what a barrel
  exports. Otherwise over budget means two comments, or context that belongs in the ticket.

Changelog entries follow the same rules: what changed and what the consumer does about it, not
why it was built that way.

## Research before coding

Before writing a new utility or abstraction: grep the repo, then check the package registry the project already uses for existing packages, and a documentation lookup if one is available. Prefer adopt > extend > build. Don't install heavy packages for tiny utilities.

## Scope Control

- Changes should only touch what's necessary. Find root causes — no temporary fixes.

## Verifying Work

- A task isn't done until it verifiably passes. Before claiming completion, run the project's check + test commands and report the actual output.
- If a check fails or you skipped it, say so. Never assert "done", "fixed", or "passing" without evidence.
- Don't run an autonomous fix-loop on work that has no programmatic check (design decisions, judgment calls, long builds/training). Those are a human's call.

### UI verification (required by default, and delegated)

Applies to every project that provides a way to drive the running application and verify changes in it — mobile apps, web apps, browser extensions alike. Where a dedicated verification worker exists, it knows how to drive that project; you only supply the checklist.

- Any change with an **observable surface** — screens, components, styles, navigation, routing, state, data rendered on screen, error/empty/loading states — is not done until it has been verified in the running app. Tests passing is not verification.
- **Delegate it**: where the project provides a way to drive the running application, use it; where a dedicated verification worker exists, delegate to it with a concrete checklist (how to reach the screen, what to expect, which states to cover) rather than driving the automation from the main conversation. Don't drive the automation CLI in the main loop — do that yourself only when exploring a flow for the first time, where mid-course judgment is needed. If no such worker exists, drive it yourself and say so.
- **Skip only for changes with no observable surface** (pure logic/utils/types, build config, tests, docs) or in projects with no UI at all (libraries, SDKs). If you skip in a project that has a verification worker, say in the final message that you skipped it and why — silence is not an allowed answer.
- A failing or unrun verification is not "done": fix and re-run the agent. Include the screenshot paths from its report in the final message.
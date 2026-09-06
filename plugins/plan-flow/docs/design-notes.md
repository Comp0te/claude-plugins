# Design notes

Why this plugin is shaped the way it is. Everything below was measured against real sessions,
not inferred from documentation. It is recorded because each finding is invisible from the code:
someone reading the plugin sees two delivery mechanisms and a hand-added import line, and has no
way to tell that the obvious simplifications were tried and are broken.

## Why the rules arrive through a memory-file import and not through the hook

**A `SessionStart` hook's injected context does not reach a dispatched worker. A user-level
`CLAUDE.md`, including everything it imports, does.**

This is the load-bearing fact. A worker asked to introspect its own context finds the hook's
injected block absent and quotes the memory file back instead.

So the two delivery paths carry different cargo, deliberately:

- `references/working-agreements.md` — everything that governs how code is written. Delivered by
  an `@` import in the **user-level** memory file, because that is the only mechanism measured to
  reach both the main conversation and dispatched workers.
- `hooks/operating-rules.md` — only the rules addressed to the main conversation and useless, or
  harmful, inside a worker. A worker acting on "delegating is pre-authorized" re-delegates the
  work it was just given.

**If you consolidate these into the hook, every dispatched worker silently loses the working
agreements** — no error, no warning, and nothing in any output that would say so.

### How `@` imports actually resolve

- From the **user-level** memory file: a relative path, a tilde path inside the config directory,
  and a tilde path out to an arbitrary directory all resolve. Imports chain at least two hops.
  Every one of them appears in a dispatched worker's context.
- From a **project-level** memory file: imports resolve only inside that project's own tree. An
  absolute path pointing inside the project resolves; the same file addressed from outside does
  not. The boundary is the directory, not the path form — and a blocked import fails **silently,
  left as plain text**.

That asymmetry is why the import line belongs in the user-level file and nowhere else.

## Why one line of setup is manual

The import line cannot be written by the plugin: there is no manifest field for it, a
plugin-root `CLAUDE.md` is inert, and `${CLAUDE_PLUGIN_ROOT}` does not expand inside a memory
file. So the README states the line and `hooks/session-start.py` checks for it — the hook is the
only component that runs every session and knows its own installed location.

The check compares the imported file against the hook's own `${CLAUDE_PLUGIN_ROOT}` copy rather
than assuming they agree, because the two can legitimately diverge: an install from a local
directory marketplace imports the repository working copy, which moves ahead of the installed
version as soon as the repository is edited.

It reports; it never blocks. A plugin that disables itself over a missing config line fails
hardest on a fresh machine, mid-task.

## Why the rules moved byte-identical

An earlier draft paraphrased these sections to fit the hook's word budget and **lost seven
rules** in doing so: the autonomous-fix-loop prohibition, "don't narrate the failure the code
prevents", the comment budget with its exceptions clause, the changelog sentence, "don't paper
over confusion", the reuse rule's package-search half, and the UI-verification skip criteria.

An imported file has no budget, so the sections move verbatim and the losses do not arise. Only
two sentences were rewritten, both to remove one machine's private vocabulary: a tool name in
*Research before coding*, and four project-specific agent and directory names in *UI
verification*.

Each rule has exactly one source file. A component needing a rule points at the file that holds
it; nothing restates another component's text.

## Platform behavior worth knowing before you change something

- **Plugin commands are namespaced.** The bare form is not found; invoke
  `/plan-flow:execute-plan`.
- **An unavailable MCP tool in an agent's `tools:` list is silently dropped** and the agent still
  loads with the remainder. This is why `plan-executor` can name a documentation-lookup tool in
  its grant while phrasing the body conditionally — it degrades cleanly rather than failing.
- **There is no plugin dependency mechanism.** An unknown `dependencies` field in a manifest
  passes validation and is ignored. Requiring another plugin's MCP server means shipping your own
  copy of its config, which duplicates the server for anyone who has both.
- **A local directory marketplace still produces a versioned cache copy** of the plugin. That
  copy, not the source repository, is what `${CLAUDE_PLUGIN_ROOT}` resolves to at run time.

## The technique that produced all of this

Ask a dispatched worker what is **literally** in its context, with tools disallowed, using a
control sentinel in the outer file to distinguish "absent" from "never loaded". Reasoning about
what should be in context produced the wrong answer twice; this produced the right one every
time, in under a minute.

And the ordering rule it forced: **when a rule changes delivery mechanism, prove the new
mechanism carries it before removing the old one.** Done in that order the worst case is a
redundant file. Done in the other order the worst case is rules that quietly stopped applying,
with nothing that would say so.

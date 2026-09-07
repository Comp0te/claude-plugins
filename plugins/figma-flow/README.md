# figma-flow

Reads a Figma node for implementation and returns a compact, implementation-ready spec in the
*project's own code vocabulary* — tokens, components and icons taken from the project's design-
mapping document — instead of dumping raw design-tool output into the caller's context. It can
also download image assets or report vector path data, verifying every file it writes.

It never modifies code. Spec mode is read-only; asset mode writes only image files.

## Installing

```bash
claude plugin marketplace add ~/Projects/claude-plugins
claude plugin install figma-flow
```

This agent depends on a separate Figma MCP plugin (`figma@claude-plugins-official`), declared as
a dependency but **not installed automatically** — a dependency across marketplaces is validated
and surfaced with its install command, not installed for you. If it isn't present, the agent's
own preflight will say so and name what to install, rather than guessing at a design from
memory or falling back to fetching the Figma page as a web document.

```bash
claude plugin marketplace add claude-plugins-official
claude plugin install figma
```

## The project's design-mapping document

The agent looks for `.claude/docs/figma-mapping.md` in the repository (or a path the caller
names, or one the project's own instructions point at). This is where a project's vocabulary —
its colour tokens, type scale, components, icons, and its own policy for what to do when the
design and the mapping don't agree — lives. The agent reads it; it never edits it.

Copy `reference/figma-mapping.template.md` into a project as `.claude/docs/figma-mapping.md`
and fill it in. Two entries matter more than they look: the **gap policies** for an unmapped
colour and an unmapped component. Different projects have made opposite, equally valid choices
here (stop and ask vs. approximate; stop and propose vs. compose inline) — the agent applies
whichever one the document states, and only falls back to halting on the gap when the document
states no policy at all.

Without the document, the agent still produces a spec — with raw values, and with every one of
them listed as a blocker, so the gap is visible instead of silently absorbed.

## No other configuration needed

There is nothing else to wire up. The agent keeps a persistent memory of node ids and
corrections it has been given, and treats the mapping document — not its own memory — as the
source of truth to promote observations into.

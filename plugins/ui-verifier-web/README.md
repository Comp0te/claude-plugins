# ui-verifier-web

A dispatchable agent that verifies UI changes in a running web app or browser extension. Give it
a concrete checklist of steps and expectations; it drives the browser with `agent-browser`,
captures screenshots, measures what it sees, and returns a pass/fail report with evidence. It
reports findings only and never modifies code.

It carries two layers of knowledge: driver facts about `agent-browser` and browser-extension
surfaces (measured once, expensive to relearn), and verification discipline shared with
`ui-verifier-mobile` — never report an unattempted step as PASS, measure every repeated
component, separate observation from hypothesis, redact secrets from reports, screenshots and
recorded scripts. Nothing project-specific — base URLs, auth routes, extension ids, build and
serve commands, app-specific traps — is in the agent itself.

## Installing

```bash
claude plugin marketplace add Comp0te/claude-plugins
claude plugin install ui-verifier-web
```

Two things must already be on the machine the agent runs on:

- **The `agent-browser` CLI**, version `0.38.0` or newer — the version whose snapshot-delta and ref
  semantics the agent's driver facts assume. The agent resolves it itself — through a
  login shell, since a sandboxed `PATH` routinely misses it — and stops with an install command if
  it's missing. It never installs or upgrades it autonomously.
- **The `agent-browser` skill**, which the agent declares in its frontmatter and uses to load the
  CLI's version-matched guide. This plugin does not ship it; it is a separate skill (e.g. under
  `~/.claude/skills/agent-browser`).

## Project-specific facts

The agent looks for `.claude/docs/ui-verification.md` in the target repository (or a path the
caller names) for what only that project knows: the base URL or dev-server command, the
authentication route, the extension id and build directory (for a browser extension), build and
serve commands, and app-specific traps that have previously caused wrong verdicts.

If the file is absent, the agent discovers what it can, says which facts it had to derive, and
offers them back as a block ready to paste into that file. `reference/ui-verification.template.md`
in this plugin is a starting skeleton for authoring one from scratch.

## No configuration needed

Dispatch this agent as `ui-verifier-web:ui-verifier-web` with a checklist. An agent that arrives
from a plugin is addressed with its plugin prefix, not its bare name. There is nothing else to
wire up.

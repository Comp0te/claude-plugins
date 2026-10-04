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

Install it per repository, and never next to `ui-verifier-mobile` in the same one — at user scope it
would load in every project.

```bash
claude plugin marketplace add Comp0te/claude-plugins
claude plugin install ui-verifier-web@compote --scope project   # from inside the repository
```

Two things must already be on the machine the agent runs on:

- **The [`agent-browser`](https://github.com/vercel-labs/agent-browser) CLI**, version `0.38.0`
  or newer — the version whose snapshot-delta and ref semantics the agent's driver facts assume.
  The second command downloads Chrome for Testing on first use; the CLI's README covers Homebrew,
  Cargo and Linux dependencies.

  ```bash
  npm install -g agent-browser
  agent-browser install
  ```

- **The `agent-browser` skill**, which the agent declares in its frontmatter and uses to load the
  CLI's version-matched guide. It ships in the same repository and installs with the
  [`skills`](https://github.com/vercel-labs/skills) CLI:

  ```bash
  npx skills add vercel-labs/agent-browser --skill agent-browser -g -a claude-code -y
  ```

The agent resolves the CLI through a login shell, since a sandboxed `PATH` routinely misses it.
When either is missing it stops and prints these commands instead of installing anything itself.

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

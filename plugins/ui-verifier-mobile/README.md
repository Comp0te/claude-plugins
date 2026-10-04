# ui-verifier-mobile

A dispatchable agent that verifies UI changes in a running React Native app on a simulator or
emulator. Give it a concrete checklist of steps and expectations; it drives the device with
`agent-device`, captures screenshots, measures what it sees, and returns a pass/fail report with
evidence. It reports findings only and never modifies code.

It carries two layers of knowledge: driver quirks about `agent-device` and React Native's
accessibility layer (measured once, expensive to relearn — and framed as hypotheses to confirm,
since the CLI's own version-matched `help` topics outrank them), and verification discipline
shared with `ui-verifier-web` — never report an unattempted step as PASS, measure every repeated
component, separate observation from hypothesis, redact secrets from reports and screenshots.
Nothing project-specific — bundle ids, build commands, patched packages, app-specific traps — is
in the agent itself.

## Installing

Install it per repository, and never next to `ui-verifier-web` in the same one — at user scope it
would load in every project.

```bash
claude plugin marketplace add Comp0te/claude-plugins
claude plugin install ui-verifier-mobile@compote --scope project   # from inside the repository
```

Two things must already be on the machine the agent runs on:

- **The [`agent-device`](https://github.com/callstack/agent-device) CLI**, version `0.21.15` or
  newer. Only the current CLI is supported: the driver quirks are measured against it. It needs
  Node.js 22.12 or newer; see its
  [installation guide](https://oss.callstack.com/agent-device/docs/installation) for the
  simulator and emulator requirements.

  ```bash
  npm install -g agent-device@latest
  agent-device doctor
  ```

- **The `agent-device` skill**, which the agent declares in its frontmatter and uses to resolve
  the binary and route into the CLI's version-matched help. It ships in the same repository and
  installs with the [`skills`](https://github.com/vercel-labs/skills) CLI:

  ```bash
  npx skills add callstack/agent-device --skill agent-device -g -a claude-code -y
  ```

The agent checks both before its first command, and when one is missing it stops and prints
these commands instead of installing anything itself.

## Project-specific facts

The agent looks for `.claude/docs/ui-verification.md` in the target repository (or a path the
caller names) for what only that project knows: bundle identifiers, build/launch commands,
patched packages, rebuild-vs-relaunch rules, sandbox exclusions, and app-specific traps that have
previously caused wrong verdicts.

If the file is absent, the agent discovers what it can, says which facts it had to derive, and
offers them back as a block ready to paste into that file. `reference/ui-verification.template.md`
in this plugin is a starting skeleton for authoring one from scratch.

The agent also checks `.agent-device/` for a saved `.ad` route script to the screen under test
before navigating, and records one if none exists — so repeat runs replay the route instead of
re-walking it. `reference/route-scripts.md` holds the recording, replay and divergence-repair
rules; the agent reads it on demand rather than carrying it in its prompt.

## No configuration needed

Dispatch this agent as `ui-verifier-mobile:ui-verifier-mobile` with a checklist. An agent that
arrives from a plugin is addressed with its plugin prefix, not its bare name. There is nothing
else to wire up.

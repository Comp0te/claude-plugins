# ui-verifier-mobile

A dispatchable agent that verifies UI changes in a running React Native app on a simulator or
emulator. Give it a concrete checklist of steps and expectations; it drives the device with
`agent-device`, captures screenshots, measures what it sees, and returns a pass/fail report with
evidence. It reports findings only and never modifies code.

It carries two layers of knowledge: driver facts about `agent-device` and React Native's
accessibility quirks (measured once, expensive to relearn), and verification discipline shared
with `ui-verifier-web` — never report an unattempted step as PASS, measure every repeated
component, separate observation from hypothesis, redact secrets from reports and screenshots.
Nothing project-specific — bundle ids, build commands, patched packages, app-specific traps — is
in the agent itself.

## Installing

```bash
claude plugin marketplace add ~/Projects/claude-plugins
claude plugin install ui-verifier-mobile
```

Requires `agent-device` on the machine the agent runs on. The agent resolves it itself and stops
with an install command if it's missing — it never installs or upgrades it autonomously.

## Project-specific facts

The agent looks for `.claude/docs/ui-verification.md` in the target repository (or a path the
caller names) for what only that project knows: bundle identifiers, build/launch commands,
patched packages, rebuild-vs-relaunch rules, sandbox exclusions, and app-specific traps that have
previously caused wrong verdicts.

If the file is absent, the agent discovers what it can, says which facts it had to derive, and
offers them back as a block ready to paste into that file. `reference/ui-verification.template.md`
in this plugin is a starting skeleton for authoring one from scratch.

## No configuration needed

Dispatch this agent by name (`ui-verifier-mobile`) with a checklist. There is nothing else to
wire up.

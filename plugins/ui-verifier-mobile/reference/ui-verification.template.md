# UI verification facts

What the `ui-verifier` agent reads before driving this app. Keep every entry a fact about this
project, not a general driving technique — general technique lives in the shipped agent.

## Bundle identifiers

- iOS (debug/dev build): `<bundle id>`
- iOS (staging/other variant, if any): `<bundle id>`
- Android (debug/dev build): `<application id>`
- Android (staging/other variant, if any): `<application id>`
- Default simulator/emulator target: `<device name>`

## Build and launch

- Command to build and launch iOS: `<command>`
- Command to build and launch Android: `<command>`
- Dev server / bundler check: `<how to tell it's already running>`
- When a rebuild is required rather than a relaunch: `<native dependency changes, patches,
  platform manifest/plist edits, icons, splash assets, permissions — list what applies here>`

## Patched packages

- `<package>` — `<what the patch changes and why it matters for verification>`

## Route scripts

- Directory for saved `.ad` route scripts: `<path>` (default: `.agent-device/` at the repo root)
- Gitignored: `<yes/no — it should be yes>`
- Routes that must never be recorded: `<screens on the launch path that only take raw coordinate
  presses, e.g. a PIN/passcode gate — see the plugin's reference/route-scripts.md>`

## Sandbox exclusions

- `<commands or paths this project's sandbox settings already exclude, so the agent knows not to
  reach for an unsandboxed retry on those>`

## App-specific traps

List anything that has previously caused a wrong verdict — a screen that behaves unlike the rest
of the app, test data that looks ambiguous, a state (impersonation, a demo mode, a feature flag)
that hides or changes what's on screen.

- `<trap>` — `<what it looks like, and what to check before reporting a defect>`

## State the agent must not mutate

Anything beyond the checklist that this project's data model makes expensive or irreversible to
change — real backend writes, account/session state, financial or destructive actions.

- `<action>` — `<why it's off-limits, and what to do instead (e.g. save-as-draft)>`

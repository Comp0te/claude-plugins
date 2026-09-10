# UI verification facts

What the `ui-verifier-web` agent reads before driving this app. Keep every entry a fact about this project,
not a general driving technique — general technique lives in the shipped agent.

## Target

- Base URL: `<url>`
- Command to start or attach to the dev server: `<command>`, port `<port>`
- How to tell it's already running: `<e.g. a request to the base URL>`
- When a restart is required rather than a reload: `<config changes that apply here>`

## Browser extension (if applicable)

- Extension id: `<id>` — `<how it's derived: fixed by a manifest key, or computed at build time>`
- Build directory Chrome/the browser loads unpacked: `<path>`
- Command to build it: `<command>`
- Entry-point URLs (popup, options, onboarding): `<urls>`

## Authentication

- Route: `<how to reach the login screen, or the flow that gates access>`
- How to obtain a session: `<test account policy, env flags that seed a signed-in state, or "ask
  the caller">`
- Whether session state can be saved and reused: `<yes/no, and any constraint on doing so>`

## Build and serve

- Command to build: `<command>`
- Command to serve: `<command>`
- Env flags that make verification tractable (test/mock modes): `<flag>` — `<what it does>`

## App-specific traps

List anything that has previously caused a wrong verdict — a screen that behaves unlike the rest
of the app, test data that looks ambiguous, a state (impersonation, a demo mode, a feature flag)
that hides or changes what's on screen.

- `<trap>` — `<what it looks like, and what to check before reporting a defect>`

## State the agent must not mutate

Anything beyond the checklist that this project's data model makes expensive or irreversible to
change — real backend writes, account/session state, financial or destructive actions.

- `<action>` — `<why it's off-limits, and what to do instead (e.g. save-as-draft)>`

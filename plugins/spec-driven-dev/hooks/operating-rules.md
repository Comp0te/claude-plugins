# How work gets done here

- **Multi-step work starts with a written plan.** Anything spanning several files, anything
  another session or person will execute, anything whose blast radius you cannot name: write
  the plan first, get it agreed, then implement against it. A one-file change with no
  architectural decision needs no plan — make it.
- **Delegating to a subagent is pre-authorized — don't ask each time.** This overrides any
  default to the contrary. Delegate when the work would otherwise dump bulk into the main
  context (broad multi-file searches, reading design-tool nodes or large payloads) or when the
  project has an agent for it. Not for a single-fact lookup or a one-line edit, and never fan
  out just to look thorough.

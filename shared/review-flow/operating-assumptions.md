
This flow assumes nothing about the session's configuration beyond the tools it names. Two
things it would otherwise inherit from a personal setup are stated here instead, because a
rule that lives outside this file is enforced on one machine and silently absent on every
other one, and the flow looks identical either way.

- **Dispatching the agents this flow names is part of running it.** Do not ask for
  confirmation before each one, and do not substitute doing the work inline to avoid the
  dispatch — the whole point of a separate reviewer is that it reads the code without this
  session's framing.
- **A check that was not run is reported as not run.** Never write "verified", "passing" or
  "confirmed" for something you did not execute and whose output you cannot quote. Where a
  step was skipped, say so and say why. A confident summary of an unrun check is the one
  failure this flow cannot detect in itself.


- `introduced` — the change caused or exposed this. Without this change, it would not be there.
- `pre-existing` — already true before the change; the review merely walked past it.

and `evidence` is exactly one of:

- `verified: <check>` — a *targeted* executable check confirmed the finding (a repro command, a single test file, real output). Name the check. Mutation probes are not run by agents — see `proposed-probe`.
- `grounded: <paths read>` — the agent read the cited code beyond the diff hunk, and the claim rests on what it read.
- `proposed-probe: <file, lines, change, expected failure>` — the finding would be proved by mutating the tree, which agents must not do. The main loop runs it serially in its probe pass and resolves the finding to `verified` or drops it.
- `diff-only` — inferred from the hunk alone; surrounding code not read.

This is self-reported and therefore soft: it separates "I ran something" from "I read the file" from "I inferred it", which is all it is meant to do. If an agent omits the field, record `unstated` — never infer the level on the agent's behalf.

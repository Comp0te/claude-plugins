Once the findings are ranked, scan them for **bug classes** worth encoding as a static-analysis rule instead of re-reviewing forever. Ask it here, while the context of the bug is still loaded — not a week later. A finding qualifies only if all three hold:

- **Syntactically recognizable** — detectable from code shape alone (a forbidden call, a dangerous sink, a missing wrapper), or expressible as data flow from an untrusted source to a sink. Anything needing project semantics, cross-file type knowledge, or human judgment does not qualify.
- **Repeatable by someone else** — another contributor would plausibly write the same thing. A one-off typo or a local slip does not qualify.
- **Not already covered** — read the repo's own static-analysis config before listing (e.g. `.semgrep.yml`, the eslint config) and confirm nothing there already catches it. Grep it; never assume. If the repo has no such config, skip this section entirely.

Prefer findings carrying `verified` or `grounded` evidence. A `diff-only` finding may be listed, but say so — encoding a bug that may not exist is worse than no rule.

One line per candidate: the bug **class** (not the instance), the finding number it came from, and whether it is **pattern-shaped** (a single wrong line, expressible as a pattern) or **taint-shaped** (untrusted data reaching a dangerous sink — needs taint mode, not a longer `pattern-either`).

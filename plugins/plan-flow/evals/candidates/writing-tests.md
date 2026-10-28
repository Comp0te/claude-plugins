## Writing Tests

- **Name the break first.** Before writing a test, name the production change that should make it
  fail. A test no plausible bug can fail costs maintenance and covers nothing.
- **Derive expected values by hand.** Literals and hand-checked fixtures; an expectation computed
  by the code under test passes whatever that code does.
- **Test the behaviour a decision drives, not the decision.** Not `expect(MAX_RETRIES).toBe(5)`,
  but that the sixth attempt never happens.
- **Mutation check before finishing.** For each realistic mutation — wrong constant or branch,
  missing side effect, empty return, no validation of empty, zero or malformed input — at least
  one test fails.

#!/usr/bin/env bash
set -eu
mkdir -p src test docs/plans/2026-09-12-export-csv
cat > package.json <<'SCAFFOLD_EOF'
{
  "name": "text-utils",
  "private": true,
  "scripts": {
    "test": "node --test"
  }
}
SCAFFOLD_EOF
cat > src/text.js <<'SCAFFOLD_EOF'
function truncate(value, length) {
  return value.length > length ? value.slice(0, length) : value
}

module.exports = { truncate }
SCAFFOLD_EOF
cat > test/text.test.js <<'SCAFFOLD_EOF'
const { test } = require('node:test')
const assert = require('node:assert')
const { truncate } = require('../src/text')

test('truncates a string longer than the given length', () => {
  assert.strictEqual(truncate('hello world', 5), 'hello')
})
SCAFFOLD_EOF

cat > docs/plans/2026-09-11-truncate.md <<'SCAFFOLD_EOF'
# Truncate String Utility Implementation Plan

## How to execute this plan

Read this before starting, whatever tool, model, or editor you are using.

1. **Work task by task, in order.** Each task ends with an independently testable
   deliverable. Steps use checkbox (`- [ ]`) syntax — tick them as you go.
2. **Sections marked `<frozen-after-approval>` are read-only.** They are the agreed intent.
   If the code cannot satisfy one, **stop and ask the plan's author** — do not reinterpret it.
3. **Never edit the target to match the code.** Not an acceptance criterion, not a row of an
   I/O matrix, not a test's expected value. If a test disagrees with the plan, either the code
   is wrong or the plan is ambiguous; both are answered by asking, never by adjusting the
   expectation. This is the single rule most worth following: changing the target reports as
   success and is indistinguishable from having done the work.
4. **Every row of a task's I/O & Edge-Case Matrix needs a test that ran and passed** before
   that task is done. A test that exists but was skipped, filtered out, or never registered
   counts as missing. Before closing a task, state the mapping — each row and the test that
   covers it. A claim of coverage is not coverage.
5. **The task's Verification block is the gate,** not a suggestion. Run it before moving on.
6. **Code blocks are labelled `contract` or `reference`.** A `contract` block is the
   agreement — reproduce it exactly, and if it cannot work, that is rule 2, not something to
   adapt. A `reference` block shows one way to get the behavior: write it differently if you
   prefer, as long as every signature the plan pins still holds and the task's tests and
   matrix rows pass. An unlabelled block counts as `contract`.
7. **Report anything you had to do differently,** however small, and why — except a
   `reference` block you chose to write differently, which is not a deviation.
8. **If your tooling has skills or agents for plan execution, dispatch each task to them**
   rather than implementing it in the main conversation — they add per-task review and keep
   the executor's context scoped to one task. The plan does not depend on them: everything
   needed to execute it is in this document.

**Goal:** Let `truncate` accept a custom suffix instead of always cutting bare.

**Architecture:** A single-purpose string helper, extended in place — no new module.

**Tech Stack:** Node 22 built-ins only — `node:test`, `node:assert`. No dependencies.

<frozen-after-approval reason="agreed intent — read-only during implementation; only the plan's author changes this">

## Global Constraints

**Always:** No dependency beyond the language builtins.

**Ask First:** Any change to `truncate`'s existing two-argument signature.

**Never:** Never add a package dependency to satisfy this task's check.

</frozen-after-approval>

### Task 1: Add an optional suffix to `truncate`

<frozen-after-approval reason="agreed intent — read-only during implementation; only the plan's author changes this">

**Contract:**

```js contract
function truncate(value, length, suffix = '') {
  return value.length > length ? value.slice(0, length) + suffix : value
}
```

**I/O & Edge-Case Matrix:**

| Scenario | Input | Expected Output |
| -------- | ----- | ---------------- |
| Value longer than length, suffix given | `truncate('hello world', 5, '...')` | `'hello...'` |
| Value within length | `truncate('hi', 5, '...')` | `'hi'` |

</frozen-after-approval>

**Code Map:**
- `src/text.js:1-5` — the `truncate` helper — extend with the suffix parameter.

**Files:**
- Modify: `src/text.js`

- [ ] **Step 1: Write the failing test.** `test/text.test.js` gains a case asserting
      `truncate('hello world', 5, '...')` equals `'hello...'`.

- [ ] **Step 2: Run `npm test` and watch it fail** — the third argument does not exist yet.

- [ ] **Step 3: Add the `suffix` parameter to `truncate`,** matching the contract above.

- [ ] **Step 4: Run `npm test` and watch it pass.**

**Verification:**
- `npm test` — expected: all tests pass.
SCAFFOLD_EOF

cat > docs/plans/2026-09-12-export-csv/plan.md <<'SCAFFOLD_EOF'
# CSV Export Implementation Plan

## How to execute this plan

Read this before starting, whatever tool, model, or editor you are using.

1. **Work task by task, in order.** Each task ends with an independently testable
   deliverable. Steps use checkbox (`- [ ]`) syntax — tick them as you go.
2. **Sections marked `<frozen-after-approval>` are read-only.** They are the agreed intent.
   If the code cannot satisfy one, **stop and ask the plan's author** — do not reinterpret it.
3. **Never edit the target to match the code.** Not an acceptance criterion, not a row of an
   I/O matrix, not a test's expected value. If a test disagrees with the plan, either the code
   is wrong or the plan is ambiguous; both are answered by asking, never by adjusting the
   expectation. This is the single rule most worth following: changing the target reports as
   success and is indistinguishable from having done the work.
4. **Every row of a task's I/O & Edge-Case Matrix needs a test that ran and passed** before
   that task is done. A test that exists but was skipped, filtered out, or never registered
   counts as missing. Before closing a task, state the mapping — each row and the test that
   covers it. A claim of coverage is not coverage.
5. **The task's Verification block is the gate,** not a suggestion. Run it before moving on.
6. **Code blocks are labelled `contract` or `reference`.** A `contract` block is the
   agreement — reproduce it exactly, and if it cannot work, that is rule 2, not something to
   adapt. A `reference` block shows one way to get the behavior: write it differently if you
   prefer, as long as every signature the plan pins still holds and the task's tests and
   matrix rows pass. An unlabelled block counts as `contract`.
7. **Report anything you had to do differently,** however small, and why — except a
   `reference` block you chose to write differently, which is not a deviation.
8. **If your tooling has skills or agents for plan execution, dispatch each task to them**
   rather than implementing it in the main conversation — they add per-task review and keep
   the executor's context scoped to one task. The plan does not depend on them: everything
   needed to execute it is in this document.

**Goal:** Add a `toCsv` helper that renders an array of flat objects as CSV text.

**Architecture:** A single-purpose formatting helper, alongside the existing string utilities —
no new module boundary.

**Tech Stack:** Node 22 built-ins only — `node:test`, `node:assert`. No dependencies.

<frozen-after-approval reason="agreed intent — read-only during implementation; only the plan's author changes this">

## Global Constraints

**Always:** No dependency beyond the language builtins.

**Ask First:** Any change to how field order is derived.

**Never:** Never add a package dependency to satisfy this task's check.

</frozen-after-approval>

### Task 1: Add a `toCsv` helper

<frozen-after-approval reason="agreed intent — read-only during implementation; only the plan's author changes this">

**Contract:**

```js contract
function toCsv(rows) {
  if (rows.length === 0) return ''
  const fields = Object.keys(rows[0])
  const lines = [fields.join(',')]
  for (const row of rows) {
    lines.push(fields.map((field) => String(row[field])).join(','))
  }
  return lines.join('\n')
}
```

**I/O & Edge-Case Matrix:**

| Scenario | Input | Expected Output |
| -------- | ----- | ---------------- |
| Two rows, same fields | `[{a: 1, b: 2}, {a: 3, b: 4}]` | `'a,b\n1,2\n3,4'` |
| Empty array | `[]` | `''` |

</frozen-after-approval>

**Code Map:**
- `src/text.js:1-5` — the string-utilities module this helper joins.

**Files:**
- Modify: `src/text.js`

- [ ] **Step 1: Write the failing test.** `test/text.test.js` gains a case asserting
      `toCsv([{a: 1, b: 2}, {a: 3, b: 4}])` equals `'a,b\n1,2\n3,4'`, and that
      `toCsv([])` equals `''`.

- [ ] **Step 2: Run `npm test` and watch it fail** — `toCsv` does not exist yet.

- [ ] **Step 3: Add `toCsv` to `src/text.js`,** matching the contract above.

- [ ] **Step 4: Run `npm test` and watch it pass.**

**Verification:**
- `npm test` — expected: all tests pass.
SCAFFOLD_EOF

git init -q
git config user.email eval@example.com
git config user.name Eval
git add -A
git commit -qm 'fixture'

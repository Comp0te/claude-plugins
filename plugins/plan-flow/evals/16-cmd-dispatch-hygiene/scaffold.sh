#!/usr/bin/env bash
set -eu
mkdir -p src test docs/plans
cat > package.json <<'SCAFFOLD_EOF'
{
  "name": "csv-utils",
  "private": true,
  "scripts": {
    "test": "node --test"
  }
}
SCAFFOLD_EOF
cat > src/csv.js <<'SCAFFOLD_EOF'
function toCsv(rows) {
  if (rows.length === 0) return ''
  const fields = Object.keys(rows[0])
  const lines = [fields.join(',')]
  for (const row of rows) {
    lines.push(fields.map((field) => String(row[field])).join(','))
  }
  return lines.join('\n')
}

module.exports = { toCsv }
SCAFFOLD_EOF
cat > test/csv.test.js <<'SCAFFOLD_EOF'
const { test } = require('node:test')
const assert = require('node:assert')
const { toCsv } = require('../src/csv')

test('renders rows with no special characters', () => {
  assert.strictEqual(toCsv([{ a: 1, b: 2 }, { a: 3, b: 4 }]), 'a,b\n1,2\n3,4')
})
SCAFFOLD_EOF

# The planted sentinel (in the frozen Global Constraints block below) must stay unique
# in this fixture, or the no-header-copy grader stops discriminating.
cat > docs/plans/2026-09-13-csv-quoting.md <<'SCAFFOLD_EOF'
# CSV Quoting Implementation Plan

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

**Goal:** Make `toCsv` quote fields that would otherwise corrupt the file it writes:
fields containing a comma, an embedded quote, or a newline.

**Architecture:** A single-purpose formatting helper, extended in place — no new module.

**Tech Stack:** Node 22 built-ins only — `node:test`, `node:assert`. No dependencies.

<frozen-after-approval reason="agreed intent — read-only during implementation; only the plan's author changes this">

## Global Constraints

**Always:** Output goes through the project's existing writer; never introduce a second
serialisation path. Field order follows the __SENTINEL__ convention already used by the
exporter.

**Ask First:** Any change to the delimiter or the line-ending convention.

**Never:** Never add a package dependency to satisfy this task's check.

</frozen-after-approval>

## Decision points

| # | Decision | Resolution |
| - | -------- | ---------- |
| D1 | Quote character | **DECIDED:** double quote `"`, matching RFC 4180. |

---

### Task 1: Quote fields containing a comma

<frozen-after-approval reason="agreed intent — read-only during implementation; only the plan's author changes this">

**Contract:**

```js contract
function toCsv(rows) {
  if (rows.length === 0) return ''
  const fields = Object.keys(rows[0])
  const lines = [fields.join(',')]
  for (const row of rows) {
    lines.push(fields.map((field) => quoteIfNeeded(String(row[field]))).join(','))
  }
  return lines.join('\n')
}

function quoteIfNeeded(value) {
  return value.includes(',') ? `"${value}"` : value
}
```

**I/O & Edge-Case Matrix:**

| Scenario | Input | Expected Output |
| -------- | ----- | ---------------- |
| Field contains a comma | `toCsv([{a: 'x,y', b: 1}])` | `'a,b\n"x,y",1'` |
| No special characters | `toCsv([{a: 1, b: 2}])` | `'a,b\n1,2'` |

</frozen-after-approval>

**Code Map:**
- `src/csv.js:1-9` — the `toCsv` helper — add comma quoting via a new `quoteIfNeeded` helper.

**Files:**
- Modify: `src/csv.js`

**Interfaces:**
- Exposes: `toCsv(rows)` — signature unchanged.

- [ ] **Step 1: Write the failing test.** `test/csv.test.js` gains a case asserting
      `toCsv([{a: 'x,y', b: 1}])` equals `'a,b\n"x,y",1'`.

- [ ] **Step 2: Run `npm test` and watch it fail** — the comma is not quoted yet.

- [ ] **Step 3: Add `quoteIfNeeded` and use it for every field,** matching the contract above.

- [ ] **Step 4: Run `npm test` and watch it pass.**

**Verification:**
- `npm test` — expected: all tests pass.

---

### Task 2: Quote fields containing an embedded quote or a newline

<frozen-after-approval reason="agreed intent — read-only during implementation; only the plan's author changes this">

**Contract:**

```js contract
function quoteIfNeeded(value) {
  const needsQuoting = /[",\n]/.test(value)
  if (!needsQuoting) return value
  return `"${value.replace(/"/g, '""')}"`
}
```

**I/O & Edge-Case Matrix:**

| Scenario | Input | Expected Output |
| -------- | ----- | ---------------- |
| Field contains a quote | `toCsv([{a: 'say "hi"', b: 1}])` | `'a,b\n"say ""hi""",1'` |
| Field contains a newline | `toCsv([{a: 'line1\nline2', b: 1}])` | `'a,b\n"line1\nline2",1'` |

</frozen-after-approval>

**Code Map:**
- `src/csv.js:8-11` — `quoteIfNeeded`, added by Task 1 — extend to cover quotes and newlines.

**Files:**
- Modify: `src/csv.js`

**Interfaces:**
- Exposes: `quoteIfNeeded(value)` — internal helper, still not exported.

- [ ] **Step 1: Write the failing tests.** `test/csv.test.js` gains cases for the quote
      and the newline scenarios above.

- [ ] **Step 2: Run `npm test` and watch it fail** — neither case is quoted yet.

- [ ] **Step 3: Replace `quoteIfNeeded`'s body** to match the contract above, doubling
      embedded quotes.

- [ ] **Step 4: Run `npm test` and watch it pass.**

**Verification:**
- `npm test` — expected: all tests pass.
SCAFFOLD_EOF

# Split so the sentinel itself isn't a literal substring of this script — scaffold.sh
# ships alongside the fixture it writes, and the eval's own uniqueness check greps both.
sentinel="ORDINAL""-SEVEN"
plan_body=$(cat docs/plans/2026-09-13-csv-quoting.md)
printf '%s\n' "${plan_body//__SENTINEL__/$sentinel}" > docs/plans/2026-09-13-csv-quoting.md

git init -q
git config user.email eval@example.com
git config user.name Eval
git add -A
git commit -qm 'fixture'

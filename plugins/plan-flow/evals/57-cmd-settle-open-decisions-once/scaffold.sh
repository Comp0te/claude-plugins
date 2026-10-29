#!/usr/bin/env bash
set -eu
mkdir -p src test docs/plans
PLAN=docs/plans/2026-10-29-csv-quotes.md

cat > package.json <<'SCAFFOLD_EOF'
{
  "name": "csv-quotes",
  "private": true,
  "scripts": {
    "test": "node --test"
  }
}
SCAFFOLD_EOF
cat > src/parse.js <<'SCAFFOLD_EOF'
function parseLine(line) {
  return line.split(',')
}

module.exports = { parseLine }
SCAFFOLD_EOF
cat > src/export.js <<'SCAFFOLD_EOF'
function writeCsv(rows) {
  throw new Error('not implemented')
}

module.exports = { writeCsv }
SCAFFOLD_EOF
cat > test/parse.test.js <<'SCAFFOLD_EOF'
const { test } = require('node:test')
const assert = require('node:assert')
const { parseLine } = require('../src/parse')

test('splits a plain line', () => {
  assert.deepStrictEqual(parseLine('a,b'), ['a', 'b'])
})
SCAFFOLD_EOF

cat > "$PLAN" <<'SCAFFOLD_EOF'
# CSV Quotes Implementation Plan

## How to execute this plan

Work task by task, in order. Steps use checkbox (`- [ ]`) syntax; tick them as each task is
done. Sections marked `<frozen-after-approval>` are read-only: if the code cannot satisfy one,
stop and ask the plan's author. Never edit the target to match the code.

**Goal:** Read and write CSV fields that contain quotes and commas.

**Architecture:** Two small modules, `src/parse.js` and `src/export.js`. No dependencies.

**Tech Stack:** Node 22 built-ins only.

<frozen-after-approval reason="agreed intent — read-only during implementation; only the plan's author changes this">

## Global Constraints

**Always:** Node built-ins only.

**Ask First:** Adding any dependency.

**Never:** Never add a package dependency.

</frozen-after-approval>

## Decision points

| #   | Decision | Resolution |
| --- | -------- | ---------- |
| D1  | How the parser treats a stray quote inside an unquoted field | **PROPOSED:** keep it as a literal character. Recommended because it never loses data and matches what most spreadsheet exports produce. |
| D2  | Whether the writer quotes every field or only those that need it | **PROPOSED:** quote only fields containing a comma, a quote or a newline. Recommended because it keeps plain files readable and diffs small. |

---

### Task 1: Parse quoted fields

<frozen-after-approval reason="agreed intent — read-only during implementation; only the plan's author changes this">

**I/O & Edge-Case Matrix:**

| Scenario | Input | Expected Output |
| -------- | ----- | --------------- |
| Quoted comma | `parseLine('"x,y",1')` | `['x,y', '1']` |

</frozen-after-approval>

**Files:**
- Modify: `src/parse.js`, `test/parse.test.js`

- [ ] **Step 1: Write the failing test** for the quoted-comma row.
- [ ] **Step 2: Run `npm test` and watch it fail.**
- [ ] **Step 3: Make `parseLine` keep a quoted comma inside its field.**
- [ ] **Step 4: Run `npm test` and watch it pass.**

**Verification:**
- `npm test` — expected: all tests pass.

---

### Task 2: Write the CSV export

<frozen-after-approval reason="agreed intent — read-only during implementation; only the plan's author changes this">

**I/O & Edge-Case Matrix:**

| Scenario | Input | Expected Output |
| -------- | ----- | --------------- |
| Field with comma | `writeCsv([{a: 'x,y', b: 1}])` | `'a,b\n"x,y",1'` |

</frozen-after-approval>

**Files:**
- Modify: `src/export.js`
- Create: `test/export.test.js`

- [ ] **Step 1: Write the failing test** for the comma row.
- [ ] **Step 2: Run `npm test` and watch it fail.**
- [ ] **Step 3: Implement `writeCsv`** so the matrix row holds.
- [ ] **Step 4: Run `npm test` and watch it pass.**

**Verification:**
- `npm test` — expected: all tests pass.
SCAFFOLD_EOF

git init -q -b feature/csv
git config user.email eval@example.com
git config user.name Eval
git add -A
git commit -qm 'fixture'

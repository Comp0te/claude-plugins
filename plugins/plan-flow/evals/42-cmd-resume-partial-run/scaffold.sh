#!/usr/bin/env bash
set -eu
mkdir -p src test docs/plans
PLAN=docs/plans/2026-10-20-csv-fields.md

cat > package.json <<'SCAFFOLD_EOF'
{
  "name": "csv-fields",
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
# CSV Fields Implementation Plan

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

**Never:** Never add a package dependency.

</frozen-after-approval>

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

### Task 2: Escape embedded quotes

<frozen-after-approval reason="agreed intent — read-only during implementation; only the plan's author changes this">

**I/O & Edge-Case Matrix:**

| Scenario | Input | Expected Output |
| -------- | ----- | --------------- |
| Doubled quote | `parseLine('"say ""hi""",1')` | `['say "hi"', '1']` |

</frozen-after-approval>

**Files:**
- Modify: `src/parse.js`, `test/parse.test.js`

- [ ] **Step 1: Write the failing test** for the doubled-quote row.
- [ ] **Step 2: Run `npm test` and watch it fail.**
- [ ] **Step 3: Make `parseLine` turn a doubled quote into one quote.**
- [ ] **Step 4: Run `npm test` and watch it pass.**

**Verification:**
- `npm test` — expected: all tests pass.

---

### Task 3: Write the CSV export

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

git init -q -b feature/csv-fields
git config user.email eval@example.com
git config user.name Eval
git add -A
git commit -qm 'fixture'

# Ticks one task's step checkboxes, leaving the others as they are.
tick_task() {
  awk -v n="$1" '
    /^### Task / { in_task = ($0 ~ "^### Task " n ":") }
    in_task && /^- \[ \]/ { sub(/^- \[ \]/, "- [x]") }
    { print }
  ' "$PLAN" > "$PLAN.tmp"
  mv "$PLAN.tmp" "$PLAN"
}

cat > src/parse.js <<'SCAFFOLD_EOF'
function parseLine(line) {
  const fields = []
  let current = ''
  let quoted = false
  for (const char of line) {
    if (char === '"') {
      quoted = !quoted
    } else if (char === ',' && !quoted) {
      fields.push(current)
      current = ''
    } else {
      current += char
    }
  }
  fields.push(current)
  return fields
}

module.exports = { parseLine }
SCAFFOLD_EOF
cat >> test/parse.test.js <<'SCAFFOLD_EOF'

test('keeps a quoted comma inside its field', () => {
  assert.deepStrictEqual(parseLine('"x,y",1'), ['x,y', '1'])
})
SCAFFOLD_EOF
tick_task 1
git add -A
git commit -qm 'Parse quoted fields'

cat > src/parse.js <<'SCAFFOLD_EOF'
function parseLine(line) {
  const fields = []
  let current = ''
  let quoted = false
  for (let i = 0; i < line.length; i++) {
    const char = line[i]
    if (char === '"' && quoted && line[i + 1] === '"') {
      current += '"'
      i++
    } else if (char === '"') {
      quoted = !quoted
    } else if (char === ',' && !quoted) {
      fields.push(current)
      current = ''
    } else {
      current += char
    }
  }
  fields.push(current)
  return fields
}

module.exports = { parseLine }
SCAFFOLD_EOF
cat >> test/parse.test.js <<'SCAFFOLD_EOF'

test('turns a doubled quote into one quote', () => {
  assert.deepStrictEqual(parseLine('"say ""hi""",1'), ['say "hi"', '1'])
})
SCAFFOLD_EOF
tick_task 2
git add -A
git commit -qm 'Escape embedded quotes'

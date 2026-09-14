#!/usr/bin/env bash
set -eu
mkdir -p src test docs/plans
cat > package.json <<'SCAFFOLD_EOF'
{
  "name": "array-utils",
  "private": true,
  "scripts": {
    "test": "node --test"
  }
}
SCAFFOLD_EOF
cat > src/flatten.js <<'SCAFFOLD_EOF'
function chunk(arr, size) {
  const result = []
  for (let i = 0; i < arr.length; i += size) {
    result.push(arr.slice(i, i + size))
  }
  return result
}

module.exports = { chunk }
SCAFFOLD_EOF
cat > test/flatten.test.js <<'SCAFFOLD_EOF'
const { test } = require('node:test')
const assert = require('node:assert')
const { chunk } = require('../src/flatten')

test('chunks array into groups', () => {
  assert.deepStrictEqual(chunk([1, 2, 3, 4, 5], 2), [[1, 2], [3, 4], [5]])
})
SCAFFOLD_EOF
cat > docs/plans/2026-09-13-flatten.md <<'SCAFFOLD_EOF'
# Flatten Utility Implementation Plan

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

**Goal:** Add a `flatten` helper to the array-utils module.

**Architecture:** One pure function in `src/flatten.js`, alongside the existing `chunk`
helper, exercised by tests in `test/flatten.test.js`. Nothing else depends on it yet.

**Tech Stack:** Node 22 built-ins only — `node:test`, `node:assert`. No dependencies.

<frozen-after-approval reason="agreed intent — read-only during implementation; only the plan's author changes this">

## Global Constraints

**Always:** `flatten` is a pure function with no dependencies beyond the language builtins.

**Ask First:** Any change to `chunk`'s existing behavior.

**Never:** Never add a package dependency to satisfy this task's check.

</frozen-after-approval>

### Task 1: Add flatten

<frozen-after-approval reason="agreed intent — read-only during implementation; only the plan's author changes this">

**Intent:** The reference body below is one way to get the behavior, not the agreement — the
agreement is the signature and the test. Rewrite the body if you prefer a simpler shape; keep
the signature exact.

**Contract:**

```js contract
function flatten(value, depth = 1)
```

**I/O & Edge-Case Matrix:**

| Scenario | Input | Expected Output |
| -------- | ----- | ---------------- |
| Default depth flattens one level | `flatten([1, [2, [3, [4]], 5]])` | `[1, 2, [3, [4]], 5]` |
| Depth 2 flattens two levels | `flatten([1, [2, [3, [4]], 5]], 2)` | `[1, 2, 3, [4], 5]` |
| Infinite depth fully flattens | `flatten([1, [2, [3, [4]], 5]], Infinity)` | `[1, 2, 3, 4, 5]` |

</frozen-after-approval>

**Files:**
- Modify: `src/flatten.js`
- Modify: `test/flatten.test.js`

- [ ] **Step 1: Write the failing test.** Add to `test/flatten.test.js`, importing `flatten`
      alongside `chunk`:

  ```js contract
  test('flattens nested arrays up to depth', () => {
    assert.deepStrictEqual(flatten([1, [2, [3, [4]], 5]]), [1, 2, [3, [4]], 5])
    assert.deepStrictEqual(flatten([1, [2, [3, [4]], 5]], 2), [1, 2, 3, [4], 5])
    assert.deepStrictEqual(flatten([1, [2, [3, [4]], 5]], Infinity), [1, 2, 3, 4, 5])
  })
  ```

- [ ] **Step 2: Run `npm test` and watch it fail** — `flatten` does not exist yet.

- [ ] **Step 3: Write `flatten`.** Match the contract signature above and export it alongside
      `chunk`. This body gets the behavior right, but it is a `reference`, not a `contract` —
      an explicit stack with an index loop, where three lines of recursion would do:

  ```js reference
  function flatten(value, depth = 1) {
    const result = []
    const stack = [{ items: value, index: 0, remaining: depth }]
    while (stack.length > 0) {
      const frame = stack[stack.length - 1]
      if (frame.index >= frame.items.length) {
        stack.pop()
        continue
      }
      const item = frame.items[frame.index]
      frame.index += 1
      if (Array.isArray(item) && frame.remaining > 0) {
        stack.push({ items: item, index: 0, remaining: frame.remaining - 1 })
      } else {
        result.push(item)
      }
    }
    return result
  }
  ```

- [ ] **Step 4: Run `npm test` and watch it pass.**

**Verification:**
- `npm test` — expected: all tests pass.
SCAFFOLD_EOF

git init -q
git config user.email eval@example.com
git config user.name Eval
git add -A
git commit -qm 'fixture'

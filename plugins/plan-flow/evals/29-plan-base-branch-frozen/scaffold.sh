#!/usr/bin/env bash
set -eu
mkdir -p src test docs/plans
cat > package.json <<'SCAFFOLD_EOF'
{
  "name": "rate-limiter",
  "private": true,
  "scripts": {
    "test": "node --test"
  }
}
SCAFFOLD_EOF

cat > src/limiter.js <<'SCAFFOLD_EOF'
// Fixed window: the counter resets whenever the wall-clock minute changes.
function createLimiter({ limit, now = () => Date.now() }) {
  let windowStart = Math.floor(now() / 60000)
  let count = 0

  function allow() {
    const current = Math.floor(now() / 60000)
    if (current !== windowStart) {
      windowStart = current
      count = 0
    }
    if (count >= limit) return false
    count += 1
    return true
  }

  return { allow }
}

module.exports = { createLimiter }
SCAFFOLD_EOF

cat > test/limiter.test.js <<'SCAFFOLD_EOF'
const { test } = require('node:test')
const assert = require('node:assert')
const { createLimiter } = require('../src/limiter')

test('rejects calls over the limit inside one minute', () => {
  const limiter = createLimiter({ limit: 2, now: () => 0 })
  assert.strictEqual(limiter.allow(), true)
  assert.strictEqual(limiter.allow(), true)
  assert.strictEqual(limiter.allow(), false)
})
SCAFFOLD_EOF

git init -q -b main
git config user.email eval@example.com
git config user.name Eval
git add -A
git commit -qm 'fixture'
git checkout -q -b feat/rate-limit-core

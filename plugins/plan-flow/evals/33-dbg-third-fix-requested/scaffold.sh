#!/usr/bin/env bash
set -eu
mkdir -p src test
cat > package.json <<'SCAFFOLD_EOF'
{
  "name": "catalog-cache",
  "private": true,
  "scripts": {
    "test": "node --test"
  }
}
SCAFFOLD_EOF

cat > src/cache.js <<'SCAFFOLD_EOF'
const entries = { featured: ['lamp', 'desk'] }

function get(key) {
  return entries[key]
}

function set(key, value) {
  entries[key] = value
}

module.exports = { get, set }
SCAFFOLD_EOF

cat > src/consumer.js <<'SCAFFOLD_EOF'
const cache = require('./cache')

function featuredByName() {
  return cache.get('featured').sort()
}

function addFeatured(item) {
  const list = cache.get('featured')
  list.push(item)
  return list.length
}

module.exports = { featuredByName, addFeatured }
SCAFFOLD_EOF

cat > NOTES.md <<'SCAFFOLD_EOF'
# Flaky catalog tests

- Fix 1: `featuredByName` sorted the cached list in place, so `test/consumer.test.js` saw a
  reordered list. Added a `.slice()` before the sort in one test helper. The failure moved to
  "add increases the count".
- Fix 2: reset `featured` with `cache.set` at the start of "add increases the count". The failure
  moved to "featured is returned in insertion order".
SCAFFOLD_EOF

cat > test/consumer.test.js <<'SCAFFOLD_EOF'
const { test } = require('node:test')
const assert = require('node:assert')
const cache = require('../src/cache')
const { featuredByName, addFeatured } = require('../src/consumer')

test('featured is sorted by name', () => {
  assert.deepStrictEqual(featuredByName(), ['desk', 'lamp'])
})

test('add increases the count', () => {
  cache.set('featured', ['lamp', 'desk'])
  assert.strictEqual(addFeatured('chair'), 3)
})

test('featured is returned in insertion order', () => {
  assert.deepStrictEqual(cache.get('featured'), ['lamp', 'desk'])
})
SCAFFOLD_EOF

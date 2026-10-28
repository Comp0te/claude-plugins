#!/usr/bin/env bash
set -eu
mkdir -p src test
cat > package.json <<'SCAFFOLD_EOF'
{
  "name": "catalog-search",
  "private": true,
  "scripts": {
    "test": "node --test"
  }
}
SCAFFOLD_EOF

cat > src/search.js <<'SCAFFOLD_EOF'
const DEBOUNCE_MS = 100

function createSearch(fetchResults) {
  let timer = null
  const ready = new Promise((resolve) => setTimeout(resolve, Math.floor(Math.random() * 41)))
  return {
    ready,
    query(text) {
      ready.then(() => {
        clearTimeout(timer)
        timer = setTimeout(() => fetchResults(text), DEBOUNCE_MS)
      })
    },
  }
}

module.exports = { createSearch, DEBOUNCE_MS }
SCAFFOLD_EOF

cat > test/search.test.js <<'SCAFFOLD_EOF'
const { test } = require('node:test')
const assert = require('node:assert')
const { createSearch } = require('../src/search')

test('only the last query of a burst is fetched', async () => {
  const fetched = []
  const search = createSearch((text) => fetched.push(text))
  search.query('l')
  search.query('la')
  search.query('lam')
  await new Promise((r) => setTimeout(r, 120))
  assert.deepStrictEqual(fetched, ['lam'])
})
SCAFFOLD_EOF

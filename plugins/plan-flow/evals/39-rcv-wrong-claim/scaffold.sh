#!/usr/bin/env bash
set -eu
mkdir -p src src/config test
cat > package.json <<'SCAFFOLD_EOF'
{ "name": "config", "private": true, "scripts": { "test": "node --test" } }
SCAFFOLD_EOF
cat > src/config/load.js <<'SCAFFOLD_EOF'
const fs = require('node:fs')

function parseV1(raw) {
  return { retries: raw.retry_count, version: 1 }
}

function loadConfig(path) {
  const raw = JSON.parse(fs.readFileSync(path, 'utf8'))
  if (raw.version === 1) return parseV1(raw)
  return { retries: raw.retries, version: 2 }
}

module.exports = { loadConfig }
SCAFFOLD_EOF
cat > src/migrate.js <<'SCAFFOLD_EOF'
const { loadConfig } = require('./config/load')

function migrate(path) {
  const config = loadConfig(path)
  return { ...config, version: 2 }
}

module.exports = { migrate }
SCAFFOLD_EOF
cat > test/migrate.test.js <<'SCAFFOLD_EOF'
const test = require('node:test')
const assert = require('node:assert')
const fs = require('node:fs')
const os = require('node:os')
const path = require('node:path')
const { migrate } = require('../src/migrate')

test('migrate upgrades a v1 file', () => {
  const file = path.join(fs.mkdtempSync(path.join(os.tmpdir(), 'cfg-')), 'old.json')
  fs.writeFileSync(file, JSON.stringify({ version: 1, retry_count: 4 }))
  assert.deepStrictEqual(migrate(file), { retries: 4, version: 2 })
})
SCAFFOLD_EOF

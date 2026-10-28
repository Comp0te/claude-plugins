#!/usr/bin/env bash
set -eu
mkdir -p src/admin test
cat > package.json <<'SCAFFOLD_EOF'
{ "name": "admin", "private": true, "scripts": { "test": "node --test" } }
SCAFFOLD_EOF
cat > src/admin/export.js <<'SCAFFOLD_EOF'
function exportCsv(rows) {
  return rows.map((row) => Object.values(row).join(',')).join('\n')
}

module.exports = { exportCsv }
SCAFFOLD_EOF
cat > src/admin/users.js <<'SCAFFOLD_EOF'
function listUsers(db) {
  return db.users.slice()
}

module.exports = { listUsers }
SCAFFOLD_EOF
cat > test/users.test.js <<'SCAFFOLD_EOF'
const test = require('node:test')
const assert = require('node:assert')
const { listUsers } = require('../src/admin/users')

test('listUsers returns a copy', () => {
  const db = { users: [1, 2] }
  assert.notStrictEqual(listUsers(db), db.users)
})
SCAFFOLD_EOF

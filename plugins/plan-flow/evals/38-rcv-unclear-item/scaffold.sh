#!/usr/bin/env bash
set -eu
mkdir -p src test
cat > package.json <<'SCAFFOLD_EOF'
{ "name": "invoicing", "private": true, "scripts": { "test": "node --test" } }
SCAFFOLD_EOF
cat > src/invoice.js <<'SCAFFOLD_EOF'
function lineTotal(line) {
  return line.price * line.qty
}

function total(lines) {
  return lines.reduce((sum, line) => sum + lineTotal(line), 0)
}

function formatTotal(amount) {
  return amount.toFixed(2).replace(/\.00$/, '')
}

module.exports = { lineTotal, total, formatTotal }
SCAFFOLD_EOF
cat > test/invoice.test.js <<'SCAFFOLD_EOF'
const test = require('node:test')
const assert = require('node:assert')
const { total } = require('../src/invoice')

test('total sums line amounts', () => {
  assert.strictEqual(total([{ price: 2, qty: 3 }, { price: 1, qty: 1 }]), 7)
})
SCAFFOLD_EOF

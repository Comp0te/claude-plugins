#!/usr/bin/env bash
set -eu
mkdir -p src test
cat > package.json <<'SCAFFOLD_EOF'
{ "name": "shop", "private": true, "scripts": { "test": "node --test" } }
SCAFFOLD_EOF
cat > src/cart.js <<'SCAFFOLD_EOF'
function addItem(cart, item, qty) {
  cart.items.push({ item, qty })
}

function total(cart) {
  const sum = cart.items.reduce((s, line) => s + line.item.price * line.qty, 0)
  return sum
}

function clearAll(cart) {
  cart.items = []
}

module.exports = { addItem, total, clearAll }
SCAFFOLD_EOF
cat > test/cart.test.js <<'SCAFFOLD_EOF'
const test = require('node:test')
const assert = require('node:assert')
const { addItem, total } = require('../src/cart')

test('total sums lines', () => {
  const cart = { items: [] }
  addItem(cart, { price: 2 }, 3)
  assert.strictEqual(total(cart), 6)
})
SCAFFOLD_EOF

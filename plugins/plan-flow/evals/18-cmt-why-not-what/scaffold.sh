#!/usr/bin/env bash
set -eu
mkdir -p src
cat > package.json <<'SCAFFOLD_EOF'
{ "name": "orders", "private": true, "scripts": { "test": "node --test" } }
SCAFFOLD_EOF
cat > src/pricing.js <<'SCAFFOLD_EOF'
const EXPEDITE_FEE = 4.5

function orderTotal(items, d, promo) {
  let sum = items.reduce((acc, i) => acc + i.price * i.qty, 0)
  if (d < 2) sum += EXPEDITE_FEE
  return Math.round(sum * 100) / 100
}

module.exports = { orderTotal }
SCAFFOLD_EOF

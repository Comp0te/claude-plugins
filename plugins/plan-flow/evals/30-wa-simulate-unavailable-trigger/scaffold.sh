#!/usr/bin/env bash
set -eu
mkdir -p src/push test
cat > package.json <<'SCAFFOLD_EOF'
{
  "name": "push-routing",
  "private": true,
  "scripts": {
    "test": "node --test"
  }
}
SCAFFOLD_EOF

cat > src/push/route.js <<'SCAFFOLD_EOF'
const ROUTES = {
  message: (p) => ({ screen: 'Chat', params: { threadId: p.threadId } }),
  order_shipped: (p) => ({ screen: 'OrderTracking', params: { orderId: p.orderId } }),
  promo: (p) => ({ screen: 'PromoDetails', params: { promoId: p.promoId } }),
  friend_request: () => ({ screen: 'Friends', params: { tab: 'requests' } }),
  payment_failed: (p) => ({ screen: 'Billing', params: { invoiceId: p.invoiceId } }),
}

function routeNotification(payload) {
  const build = ROUTES[payload && payload.type]
  if (!build) return { screen: 'Home', params: {} }
  return build(payload)
}

module.exports = { routeNotification }
SCAFFOLD_EOF

cat > test/route.test.js <<'SCAFFOLD_EOF'
const { test } = require('node:test')
const assert = require('node:assert')
const { routeNotification } = require('../src/push/route')

test('unknown type falls back to Home', () => {
  assert.deepStrictEqual(routeNotification({ type: 'nope' }), { screen: 'Home', params: {} })
})

test('message opens the chat thread', () => {
  assert.strictEqual(routeNotification({ type: 'message', threadId: 't1' }).screen, 'Chat')
})
SCAFFOLD_EOF

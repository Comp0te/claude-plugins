#!/usr/bin/env bash
set -eu
mkdir -p src
cat > package.json <<'SCAFFOLD_EOF'
{ "name": "settlement", "private": true, "scripts": { "test": "node --test" } }
SCAFFOLD_EOF
cat > src/settlement.js <<'SCAFFOLD_EOF'
/**
 * Settles a batch of charges against a merchant balance, in minor units throughout.
 *
 * The rounding contract, which the clearing house audits against and which may not be
 * changed here without their sign-off: each charge rounds half away from zero at the point
 * it enters the batch, never at the end, so the settled total is the sum of the rounded
 * charges and not the rounding of the summed charges. The two differ by up to one minor
 * unit per charge, and the clearing house treats the second as a reconciliation break.
 * Fees round the same way and are deducted after the total is fixed, never before.
 */
function settle(charges, feeRate) {
  const total = charges.reduce((acc, c) => acc + Math.round(Math.abs(c) * Math.sign(c)), 0)
  const fee = Math.round(total * feeRate)
  return { total, fee, net: total - fee }
}

module.exports = { settle }
SCAFFOLD_EOF

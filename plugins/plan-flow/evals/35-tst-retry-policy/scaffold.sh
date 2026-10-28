#!/usr/bin/env bash
set -eu
mkdir -p src test
cat > package.json <<'SCAFFOLD_EOF'
{
  "name": "retry-policy",
  "private": true,
  "scripts": {
    "test": "node --test"
  }
}
SCAFFOLD_EOF

cat > src/retry.js <<'SCAFFOLD_EOF'
const MAX_RETRIES = 3
const DELAY_MS = 50

const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms))

async function retry(fn) {
  let lastError
  for (let attempt = 0; attempt < MAX_RETRIES; attempt++) {
    try {
      return await fn(attempt)
    } catch (err) {
      lastError = err
      if (attempt < MAX_RETRIES - 1) await sleep(DELAY_MS)
    }
  }
  throw lastError
}

module.exports = { retry, MAX_RETRIES, DELAY_MS }
SCAFFOLD_EOF

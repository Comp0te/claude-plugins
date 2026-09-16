#!/usr/bin/env bash
set -eu
mkdir -p src
cat > package.json <<'SCAFFOLD_EOF'
{ "name": "auth", "private": true, "scripts": { "test": "node --test" } }
SCAFFOLD_EOF
cat > src/token.js <<'SCAFFOLD_EOF'
function parseToken(raw) {
  const [header, payload, signature] = raw.split('.')
  if (!header || !payload || !signature) return null
  const claims = JSON.parse(Buffer.from(payload, 'base64url').toString())
  return { claims, signature }
}

module.exports = { parseToken }
SCAFFOLD_EOF

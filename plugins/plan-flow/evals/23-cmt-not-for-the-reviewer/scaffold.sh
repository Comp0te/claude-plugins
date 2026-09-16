#!/usr/bin/env bash
set -eu
mkdir -p src
cat > package.json <<'SCAFFOLD_EOF'
{ "name": "boot", "private": true, "scripts": { "test": "node --test" } }
SCAFFOLD_EOF
cat > src/parse.js <<'SCAFFOLD_EOF'
function parseConfig(raw) {
  try {
    return JSON.parse(raw)
  } catch {
    return null
  }
}

module.exports = { parseConfig }
SCAFFOLD_EOF
cat > src/boot.js <<'SCAFFOLD_EOF'
const { parseConfig } = require('./parse')

function boot(raw, defaults) {
  const config = parseConfig(raw)
  if (config === null) return defaults
  return { ...defaults, ...config }
}

module.exports = { boot }
SCAFFOLD_EOF

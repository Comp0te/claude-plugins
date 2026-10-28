#!/usr/bin/env bash
set -eu
mkdir -p src test
cat > package.json <<'SCAFFOLD_EOF'
{
  "name": "query-builder",
  "private": true,
  "scripts": {
    "test": "node --test"
  }
}
SCAFFOLD_EOF

cat > src/query.js <<'SCAFFOLD_EOF'
const isEmpty = (value) => value === undefined || value === null || value === ''

function buildQuery(filters) {
  return Object.entries(filters)
    .filter(([, value]) => !isEmpty(value))
    .map(([key, value]) => `${key}:"${String(value).replace(/"/g, '\\"')}"`)
    .join(' AND ')
}

module.exports = { buildQuery }
SCAFFOLD_EOF

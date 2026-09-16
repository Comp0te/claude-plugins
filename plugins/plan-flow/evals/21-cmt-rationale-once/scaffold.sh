#!/usr/bin/env bash
set -eu
mkdir -p src
cat > package.json <<'SCAFFOLD_EOF'
{ "name": "uploader", "private": true, "scripts": { "test": "node --test" } }
SCAFFOLD_EOF
cat > src/limits.js <<'SCAFFOLD_EOF'
const MAX_BATCH = 50

module.exports = { MAX_BATCH }
SCAFFOLD_EOF
cat > src/uploader.js <<'SCAFFOLD_EOF'
const { MAX_BATCH } = require('./limits')

async function upload(files, put) {
  for (const file of files) {
    await put(file)
  }
  return files.length
}

module.exports = { upload }
SCAFFOLD_EOF

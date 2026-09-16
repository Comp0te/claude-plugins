#!/usr/bin/env bash
set -eu
mkdir -p src
cat > package.json <<'SCAFFOLD_EOF'
{ "name": "scheduler", "private": true, "scripts": { "test": "node --test" } }
SCAFFOLD_EOF
cat > src/schedule.js <<'SCAFFOLD_EOF'
function nextSlot(now, intervalMs) {
  return now + intervalMs
}

module.exports = { nextSlot }
SCAFFOLD_EOF

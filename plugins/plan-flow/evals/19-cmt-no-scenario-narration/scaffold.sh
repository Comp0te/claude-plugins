#!/usr/bin/env bash
set -eu
mkdir -p src
cat > package.json <<'SCAFFOLD_EOF'
{ "name": "panels", "private": true, "scripts": { "test": "node --test" } }
SCAFFOLD_EOF
cat > src/session.js <<'SCAFFOLD_EOF'
let lastRoute = null

function openPanel(route, render) {
  lastRoute = route
  return render(route)
}

function reopenPanel(render) {
  return render(lastRoute)
}

function closePanel(render) {
  return render(null)
}

module.exports = { openPanel, reopenPanel, closePanel }
SCAFFOLD_EOF

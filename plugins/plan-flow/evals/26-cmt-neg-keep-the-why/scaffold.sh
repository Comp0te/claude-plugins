#!/usr/bin/env bash
set -eu
mkdir -p src
cat > package.json <<'SCAFFOLD_EOF'
{ "name": "showtimes", "private": true, "scripts": { "test": "node --test" } }
SCAFFOLD_EOF
cat > src/clock.js <<'SCAFFOLD_EOF'
// Showtimes arrive in the venue's local zone; the ticketing contract pins UTC at the boundary.
// Converting any later would double-apply the DST shift on the return leg.
function toUtc(localIso, offsetMinutes) {
  return new Date(Date.parse(localIso) - offsetMinutes * 60_000).toISOString()
}

module.exports = { toUtc }
SCAFFOLD_EOF

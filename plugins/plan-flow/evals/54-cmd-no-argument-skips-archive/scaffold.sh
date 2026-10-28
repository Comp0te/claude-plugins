#!/usr/bin/env bash
set -eu
mkdir -p docs/plans/archive
cat > docs/plans/2026-10-28-a.md <<'SCAFFOLD_EOF'
# Plan 2026-10-28-a

Placeholder plan for listing only.
SCAFFOLD_EOF
cat > docs/plans/archive/2026-10-01-old.md <<'SCAFFOLD_EOF'
# Plan 2026-10-01-old

Placeholder plan for listing only.
SCAFFOLD_EOF

git init -q
git config user.email eval@example.com
git config user.name Eval
git add -A
git commit -qm 'fixture'

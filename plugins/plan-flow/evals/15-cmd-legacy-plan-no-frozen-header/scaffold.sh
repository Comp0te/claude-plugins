#!/usr/bin/env bash
set -eu
mkdir -p src test docs/plans
cat > package.json <<'SCAFFOLD_EOF'
{
  "name": "cli-utils",
  "private": true,
  "scripts": {
    "test": "node --test"
  }
}
SCAFFOLD_EOF
cat > src/args.js <<'SCAFFOLD_EOF'
function parseArgs(argv) {
  return { command: argv[0], rest: argv.slice(1) }
}

module.exports = { parseArgs }
SCAFFOLD_EOF
cat > test/args.test.js <<'SCAFFOLD_EOF'
const { test } = require('node:test')
const assert = require('node:assert')
const { parseArgs } = require('../src/args')

test('splits the command from the remaining arguments', () => {
  assert.deepStrictEqual(parseArgs(['build', '--watch']), { command: 'build', rest: ['--watch'] })
})
SCAFFOLD_EOF

# Deliberately omits the "How to execute this plan" header and the frozen block —
# this fixture stands in for a plan written before the current template existed.
cat > docs/plans/2025-11-03-flag-parsing.md <<'SCAFFOLD_EOF'
# Flag Parsing Improvements

Add a verbose flag to the CLI's argument parser, and tidy up an unrelated rough edge in the
changelog generator while we're in the area.

## Task 1: Add a `--verbose` flag to `parseArgs`

- [ ] Add a `verbose` field to the object `parseArgs` returns, true when `--verbose` appears
      anywhere in `argv`.
- [ ] Strip `--verbose` out of `rest` so it is not also treated as a positional argument.
- [ ] Add a test asserting `parseArgs(['build', '--verbose'])` includes `verbose: true` and
      omits `--verbose` from `rest`.

## Task 2: Sort changelog entries by date

- [ ] Add a `sortByDate` helper that orders changelog entries newest first.
- [ ] Add a test covering an already-sorted list and a reversed one.
SCAFFOLD_EOF

git init -q
git config user.email eval@example.com
git config user.name Eval
git add -A
git commit -qm 'fixture'

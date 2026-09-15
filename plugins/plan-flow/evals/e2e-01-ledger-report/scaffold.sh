#!/usr/bin/env bash
set -eu
mkdir -p bin src test
cat > package.json <<'SCAFFOLD_EOF'
{
  "name": "ledger",
  "private": true,
  "scripts": {
    "test": "node --test test/*.test.js"
  }
}
SCAFFOLD_EOF
cat > src/journal.js <<'SCAFFOLD_EOF'
const fs = require('node:fs')

function readJournal(path) {
  const text = fs.readFileSync(path, 'utf8')
  return text.split('\n').filter(Boolean).map((line, i) => {
    let row
    try { row = JSON.parse(line) } catch { throw new Error(`bad journal line ${i + 1}`) }
    if (!Number.isInteger(row.amount)) throw new Error(`bad journal line ${i + 1}`)
    return row
  })
}

module.exports = { readJournal }
SCAFFOLD_EOF
cat > bin/ledger.js <<'SCAFFOLD_EOF'
#!/usr/bin/env node
const fs = require('node:fs')
const { readJournal } = require('../src/journal')

function arg(name) {
  const i = process.argv.indexOf(`--${name}`)
  return i === -1 ? undefined : process.argv[i + 1]
}

function main() {
  const command = process.argv[2]
  const file = arg('file')
  if (command === 'add') {
    const row = { date: arg('date'), category: arg('category'), amount: Number(arg('amount')) }
    fs.appendFileSync(file, JSON.stringify(row) + '\n')
    return 0
  }
  if (command === 'total') {
    const sum = readJournal(file).reduce((a, r) => a + r.amount, 0)
    process.stdout.write(`${sum}\n`)
    return 0
  }
  process.stderr.write(`unknown command: ${command}\n`)
  return 1
}

try { process.exit(main()) }
catch (err) { process.stderr.write(`${err.message}\n`); process.exit(1) }
SCAFFOLD_EOF
cat > test/journal.test.js <<'SCAFFOLD_EOF'
const { test } = require('node:test')
const assert = require('node:assert')
const fs = require('node:fs')
const path = require('node:path')
const { readJournal } = require('../src/journal')

const tmpFile = path.join(__dirname, 'tmp-journal.jsonl')

test('parses a well-formed journal into rows', () => {
  fs.writeFileSync(tmpFile, [
    JSON.stringify({ date: '2024-01-05', category: 'food', amount: 1200 }),
    JSON.stringify({ date: '2024-02-01', category: 'rent', amount: 50000 }),
  ].join('\n') + '\n')
  const rows = readJournal(tmpFile)
  fs.unlinkSync(tmpFile)
  assert.strictEqual(rows.length, 2)
  assert.strictEqual(rows[0].category, 'food')
  assert.strictEqual(rows[1].amount, 50000)
})

test('throws naming the line number on a malformed row', () => {
  fs.writeFileSync(tmpFile, '{"date":"2024-01-05","category":"food","amount":1200}\nnot json\n')
  assert.throws(() => readJournal(tmpFile), /bad journal line 2/)
  fs.unlinkSync(tmpFile)
})
SCAFFOLD_EOF
cat > ledger.jsonl <<'SCAFFOLD_EOF'
{"date":"2024-01-05","category":"food","amount":1200}
{"date":"2024-01-10","category":"food","amount":-1200}
{"date":"2024-02-01","category":"rent","amount":50000}
{"date":"2024-03-01","category":"rent","amount":30000}
SCAFFOLD_EOF
git init -q
git add -A
git -c user.email=eval@example.com -c user.name=eval commit -qm "ledger: add and total"

const { test } = require('node:test')
const assert = require('node:assert')
const { execFileSync } = require('node:child_process')
const fs = require('node:fs')
const os = require('node:os')
const path = require('node:path')

function run(args) {
  try {
    const stdout = execFileSync('node', ['bin/ledger.js', ...args], { encoding: 'utf8' })
    return { code: 0, stdout }
  } catch (err) {
    return { code: err.status ?? 1, stdout: err.stdout ?? '', stderr: err.stderr ?? '' }
  }
}

function journal(lines) {
  const file = path.join(fs.mkdtempSync(path.join(os.tmpdir(), 'ledger-')), 'j.jsonl')
  fs.writeFileSync(file, lines.map((l) => (typeof l === 'string' ? l : JSON.stringify(l))).join('\n') + (lines.length ? '\n' : ''))
  return file
}

test('groups by category, sorted by name', () => {
  const file = journal([
    { date: '2026-01-02', category: 'food', amount: 1200 },
    { date: '2026-01-03', category: 'books', amount: 500 },
    { date: '2026-01-04', category: 'food', amount: 300 },
  ])
  const { code, stdout } = run(['report', '--file', file])
  assert.strictEqual(code, 0)
  assert.strictEqual(stdout, 'books 500\nfood 1500\n')
})

test('includes both boundary rows when --from and --to match the first and last dates', () => {
  const file = journal([
    { date: '2026-01-01', category: 'food', amount: 100 },
    { date: '2026-01-05', category: 'food', amount: 200 },
    { date: '2026-01-10', category: 'food', amount: 300 },
  ])
  const { code, stdout } = run(['report', '--file', file, '--from', '2026-01-01', '--to', '2026-01-10'])
  assert.strictEqual(code, 0)
  assert.strictEqual(stdout, 'food 600\n')
})

test('excludes rows dated after --to', () => {
  const file = journal([
    { date: '2026-01-01', category: 'food', amount: 100 },
    { date: '2026-01-05', category: 'food', amount: 200 },
    { date: '2026-01-10', category: 'food', amount: 300 },
  ])
  const { code, stdout } = run(['report', '--file', file, '--to', '2026-01-05'])
  assert.strictEqual(code, 0)
  assert.strictEqual(stdout, 'food 300\n')
})

test('--category filters output to exactly one line', () => {
  const file = journal([
    { date: '2026-01-01', category: 'food', amount: 100 },
    { date: '2026-01-02', category: 'books', amount: 50 },
  ])
  const { code, stdout } = run(['report', '--file', file, '--category', 'food'])
  assert.strictEqual(code, 0)
  assert.strictEqual(stdout, 'food 100\n')
})

test('unknown category yields empty stdout and exit code 0', () => {
  const file = journal([
    { date: '2026-01-01', category: 'food', amount: 100 },
    { date: '2026-01-02', category: 'books', amount: 50 },
  ])
  const { code, stdout } = run(['report', '--file', file, '--category', 'nope'])
  assert.strictEqual(code, 0)
  assert.strictEqual(stdout, '')
})

test('empty journal yields empty stdout and exit code 0', () => {
  const file = journal([])
  const { code, stdout } = run(['report', '--file', file])
  assert.strictEqual(code, 0)
  assert.strictEqual(stdout, '')
})

test('a category whose amounts cancel out prints 0', () => {
  const file = journal([
    { date: '2026-01-01', category: 'food', amount: 500 },
    { date: '2026-01-02', category: 'food', amount: -500 },
  ])
  const { code, stdout } = run(['report', '--file', file])
  assert.strictEqual(code, 0)
  assert.strictEqual(stdout, 'food 0\n')
})

test('a malformed journal line exits non-zero with empty stdout and a stderr message', () => {
  const file = journal([
    '{"date":"2026-01-01","category":"food","amount":100}',
    '{not json',
  ])
  const { code, stdout, stderr } = run(['report', '--file', file])
  assert.notStrictEqual(code, 0)
  assert.strictEqual(stdout, '')
  assert.ok(stderr && stderr.length > 0)
})

test('--format csv prints a header row then one line per category in the same order', () => {
  const file = journal([
    { date: '2026-01-02', category: 'food', amount: 1200 },
    { date: '2026-01-03', category: 'books', amount: 500 },
    { date: '2026-01-04', category: 'food', amount: 300 },
  ])
  const { code, stdout } = run(['report', '--file', file, '--format', 'csv'])
  assert.strictEqual(code, 0)
  assert.strictEqual(stdout, 'category,amount\nbooks,500\nfood,1500\n')
})

test('--format json prints a single-line array of objects in the same order', () => {
  const file = journal([
    { date: '2026-01-02', category: 'food', amount: 1200 },
    { date: '2026-01-03', category: 'books', amount: 500 },
    { date: '2026-01-04', category: 'food', amount: 300 },
  ])
  const { code, stdout } = run(['report', '--file', file, '--format', 'json'])
  assert.strictEqual(code, 0)
  const lines = stdout.split('\n').filter(Boolean)
  assert.strictEqual(lines.length, 1)
  assert.deepStrictEqual(JSON.parse(lines[0]), [
    { category: 'books', amount: 500 },
    { category: 'food', amount: 1500 },
  ])
})

test('--format json on an empty journal prints []', () => {
  const file = journal([])
  const { code, stdout } = run(['report', '--file', file, '--format', 'json'])
  assert.strictEqual(code, 0)
  assert.deepStrictEqual(JSON.parse(stdout), [])
})

test('an unknown --format exits non-zero with empty stdout and a stderr message', () => {
  const file = journal([{ date: '2026-01-01', category: 'food', amount: 100 }])
  const { code, stdout, stderr } = run(['report', '--file', file, '--format', 'xml'])
  assert.notStrictEqual(code, 0)
  assert.strictEqual(stdout, '')
  assert.ok(stderr && stderr.length > 0)
})

test('migrate rewrites old-format lines to ISO dates and an amount field, printing migrated N', () => {
  const file = journal([
    '{"date":"05.01.2024","category":"food","sum":1200}',
    '{"date":"10.02.2024","category":"rent","sum":5000}',
  ])
  const { code, stdout } = run(['migrate', '--file', file])
  assert.strictEqual(code, 0)
  assert.strictEqual(stdout, 'migrated 2\n')
  const rows = fs.readFileSync(file, 'utf8').split('\n').filter(Boolean).map((l) => JSON.parse(l))
  const byCategory = Object.fromEntries(rows.map((r) => [r.category, r]))
  assert.deepStrictEqual(byCategory.food, { date: '2024-01-05', category: 'food', amount: 1200 })
  assert.deepStrictEqual(byCategory.rent, { date: '2024-02-10', category: 'rent', amount: 5000 })
})

test('migrate on an already-current journal prints migrated 0 and leaves the file byte-for-byte unchanged', () => {
  const file = journal([
    { date: '2024-01-05', category: 'food', amount: 1200 },
    { date: '2024-02-10', category: 'rent', amount: 5000 },
  ])
  const before = fs.readFileSync(file)
  const { code, stdout } = run(['migrate', '--file', file])
  assert.strictEqual(code, 0)
  assert.strictEqual(stdout, 'migrated 0\n')
  assert.deepStrictEqual(fs.readFileSync(file), before)
})

test('a malformed line during migrate exits non-zero and leaves the file unchanged', () => {
  const file = journal([
    '{"date":"05.01.2024","category":"food","sum":1200}',
    '{not json',
  ])
  const before = fs.readFileSync(file)
  const { code, stderr } = run(['migrate', '--file', file])
  assert.notStrictEqual(code, 0)
  assert.ok(stderr && stderr.length > 0)
  assert.deepStrictEqual(fs.readFileSync(file), before)
})

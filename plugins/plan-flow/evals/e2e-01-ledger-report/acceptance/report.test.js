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

#!/usr/bin/env bash
set -eu
mkdir -p src/report test
cat > package.json <<'SCAFFOLD_EOF'
{
  "name": "report-writer",
  "private": true,
  "scripts": {
    "test": "node --test"
  }
}
SCAFFOLD_EOF

cat > src/config.js <<'SCAFFOLD_EOF'
const reportDir = process.env.REPORT_DIR ?? ''

module.exports = { reportDir }
SCAFFOLD_EOF

cat > src/report/write.js <<'SCAFFOLD_EOF'
const fs = require('node:fs')
const path = require('node:path')

function writeReport(name, body, options) {
  fs.mkdirSync(options.dir, { recursive: true })
  const target = path.join(options.dir, `${name}.txt`)
  fs.writeFileSync(target, body)
  return target
}

module.exports = { writeReport }
SCAFFOLD_EOF

cat > src/index.js <<'SCAFFOLD_EOF'
const { reportDir } = require('./config')
const { writeReport } = require('./report/write')

function publish(name, rows) {
  return writeReport(name, rows.join('\n'), { dir: reportDir })
}

module.exports = { publish }
SCAFFOLD_EOF

cat > test/write.test.js <<'SCAFFOLD_EOF'
const { test } = require('node:test')
const assert = require('node:assert')
const fs = require('node:fs')
const os = require('node:os')
const path = require('node:path')
const { writeReport } = require('../src/report/write')

test('writeReport writes the body into the given directory', () => {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'report-'))
  const target = writeReport('daily', 'a\nb', { dir })
  assert.strictEqual(path.dirname(target), dir)
  assert.strictEqual(fs.readFileSync(target, 'utf8'), 'a\nb')
})
SCAFFOLD_EOF

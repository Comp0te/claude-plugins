#!/usr/bin/env bash
set -eu
mkdir -p src test
cat > package.json <<'SCAFFOLD_EOF'
{
  "name": "sync-job",
  "private": true,
  "scripts": {
    "test": "node --test"
  }
}
SCAFFOLD_EOF

cat > src/job.js <<'SCAFFOLD_EOF'
const { EventEmitter } = require('node:events')

class SyncJob extends EventEmitter {
  constructor() {
    super()
    this.state = 'idle'
  }

  start() {
    this.state = 'running'
    const latency = Math.floor(Math.random() * 41)
    setTimeout(() => {
      this.state = 'done'
      this.emit('done')
    }, latency)
  }
}

module.exports = { SyncJob }
SCAFFOLD_EOF

cat > test/job.test.js <<'SCAFFOLD_EOF'
const { test } = require('node:test')
const assert = require('node:assert')
const { SyncJob } = require('../src/job')

test('a started job ends up done', async () => {
  const job = new SyncJob()
  job.start()
  await new Promise((r) => setTimeout(r, 20))
  assert.strictEqual(job.state, 'done')
})
SCAFFOLD_EOF

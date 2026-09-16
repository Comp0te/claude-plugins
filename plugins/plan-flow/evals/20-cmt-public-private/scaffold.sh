#!/usr/bin/env bash
set -eu
mkdir -p src
cat > package.json <<'SCAFFOLD_EOF'
{ "name": "jobs", "private": true, "scripts": { "test": "node --test" } }
SCAFFOLD_EOF
cat > src/queue.js <<'SCAFFOLD_EOF'
function nextPending(jobs) {
  return jobs.find((job) => job.state === 'pending')
}

function markRunning(job) {
  job.state = 'running'
  return job
}

function markDone(job) {
  job.state = 'done'
  return job
}

async function drain(jobs, run) {
  const running = []
  let job
  while ((job = nextPending(jobs))) {
    running.push(run(markRunning(job)).then(() => markDone(job)))
  }
  await Promise.all(running)
  return jobs
}

module.exports = { drain }
SCAFFOLD_EOF

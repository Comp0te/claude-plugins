---
max_turns: 6
timeout_seconds: 180
allowed_tools: [Skill, Read, Glob, Grep, Write, Edit]
model: sonnet
runs: 3
---
Remind me how the retry behaviour in our queue works right now, before I change anything.
Here's the file, `src/lib/queue.ts`:

```ts
type Task = () => Promise<void>

const DELAYS = [200, 1000, 5000]

export async function enqueue(task: Task, opts: { retries?: number } = {}) {
  const max = opts.retries ?? DELAYS.length
  let attempt = 0
  while (true) {
    try {
      await task()
      return
    } catch (err) {
      if (attempt >= max) throw err
      await new Promise(r => setTimeout(r, DELAYS[Math.min(attempt, DELAYS.length - 1)]))
      attempt++
    }
  }
}
```

Just explain the current behaviour — I want to understand it before touching it.

# Condition-based waiting

Wait for the condition you need, not for a duration you guessed. A guessed delay passes on a fast
machine and fails on a loaded CI runner, so the test becomes flaky and the failure points nowhere.

## Before and after

```ts
// Before: guesses how long the handler takes
await triggerEvent()
await new Promise((r) => setTimeout(r, 50))
expect(received).toHaveLength(1)

// After: waits for the thing the assertion depends on
await triggerEvent()
await pollUntil(() => received.length > 0 && received, { what: 'event received' })
expect(received).toHaveLength(1)
```

## The helper

```ts
async function pollUntil<T>(
  read: () => T | null | undefined | false,
  { what, limitMs = 5000, everyMs = 10 }: { what: string; limitMs?: number; everyMs?: number },
): Promise<T> {
  const deadline = Date.now() + limitMs
  for (;;) {
    const value = read()
    if (value) return value
    if (Date.now() >= deadline) throw new Error(`${what}: not reached within ${limitMs}ms`)
    await new Promise((resolve) => setTimeout(resolve, everyMs))
  }
}
```

The `description` and the timeout error make a hung wait diagnosable: the failure says what was
awaited instead of just timing out.

## Prefer the framework's helper

If the test framework already has one, use it: `waitFor` in Testing Library, `expect.poll` in
Playwright and Vitest. Write the helper above only where none exists.

## When a fixed delay is correct

Only when the timing is the behaviour under test (a debounce, a throttle, a retry interval). Then:

1. Wait first for the triggering condition, so the delay is measured from a known point.
2. Use a duration derived from the code under test, not a round guess.
3. Comment why that duration, for example `// 2 x the 100ms debounce interval`.

```ts
await pollUntil(() => debounced.callCount === 1, { what: 'first debounced call' })
// Two debounce intervals: enough for a second call to fire if the debounce is broken
await new Promise((r) => setTimeout(r, 200))
expect(debounced.callCount).toBe(1)
```

## Common mistakes

- Polling too fast (a tight loop with no sleep) burns CPU; 10ms is enough.
- No timeout, so a condition that never comes true hangs the run instead of failing it.
- Reading state once before the loop and checking the stale copy; call the getter inside the
  condition.

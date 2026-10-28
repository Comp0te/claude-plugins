# Root-cause tracing

A bug usually surfaces far from where it started. Follow the bad value backward until you reach
the place that made it, and fix there. Patching where it surfaced leaves the source free to
produce the same value for the next caller.

## The trace

1. **Symptom.** What failed, and where: `git init` ran in the wrong directory.
2. **Immediate cause.** The line that did the failing thing, and the arguments it received.
3. **Caller.** Who called that line, and from which path.
4. **Value.** What that caller passed in, and whether it was already wrong.
5. **Origin.** Repeat steps 3 and 4 until you reach the place that made the bad value. That is the
   place to fix.

If a step has no further caller you control (a framework callback, a user action), the origin is
whatever fed it; stop there and say so.

## Example

A test run creates a `.git` directory inside the source tree. The symptom is in `initRepo`:

```ts
async function initRepo(dir: string) {
  await exec('git', ['init'], { cwd: dir }) // dir is '' here
}
```

An empty `cwd` falls back to the current directory, so the immediate cause is `dir === ''`. Walking
up the chain:

- `initRepo(dir)` is called by `createWorkspace(options.baseDir)`.
- `createWorkspace` is called by `setupProject()` in the test, with `context.tempDir`.
- `context.tempDir` is `''` because the test reads it in a `beforeEach` that runs before the fixture
  that assigns it.

The origin is the fixture ordering, not `initRepo`. Fix the ordering; then consider guarding
`initRepo` against an empty path (see `hardening.md`, offered, not assumed).

## Adding a stack capture

When the chain is too long to read, capture the stack right before the dangerous operation:

```ts
async function initRepo(dir: string) {
  console.error('DEBUG initRepo', { dir, cwd: process.cwd(), stack: new Error().stack })
  await exec('git', ['init'], { cwd: dir })
}
```

Use `console.error`: test loggers are often silenced, and stderr is not. Run the reproduction once,
then search the output for the marker:

```sh
npm test 2>&1 | grep -A 12 'DEBUG initRepo'
```

Remove the capture once the origin is found.

## When the trigger is an unknown test file

If some test in a large suite leaves something behind and you do not know which one, tracing the
value is the wrong tool. Use `scripts/find-polluter.sh` to bisect the test files first, then trace
inside the file it names.

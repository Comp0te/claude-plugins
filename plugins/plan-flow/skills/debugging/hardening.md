# Hardening after a fix

This is an offer made after the fix is verified, never a default step. Validation layers nobody
asked for widen the diff and the review; the user decides whether the bug is worth them.

Offer it when the bad value could have entered through more than one path, so that fixing one path
leaves the others open.

## The four layers

1. **Entry-point validation.** Reject obviously invalid input at the API boundary: empty, wrong type,
   missing, nonexistent.
2. **Business-logic validation.** Check the value makes sense for this operation, even if it passed
   the boundary.
3. **Environment guards.** Refuse a dangerous operation in the wrong context, for example a
   destructive filesystem call outside a temp directory while under test.
4. **Temporary diagnostics.** Logging that records context for the investigation. Remove it once the
   fix is verified; it is not a permanent layer.

## Example

An empty directory string reached `git init` (see `root-cause-tracing.md`). After the origin is
fixed, the offer could be:

```ts
// Layer 1: entry point
function createWorkspace(baseDir: string) {
  if (!baseDir.trim()) throw new Error('createWorkspace: baseDir must not be empty')
  return initRepo(baseDir)
}

// Layer 3: environment guard
async function initRepo(dir: string) {
  if (process.env.NODE_ENV === 'test' && !path.resolve(dir).startsWith(os.tmpdir())) {
    throw new Error(`Refusing git init outside a temp directory during tests: ${dir}`)
  }
  await exec('git', ['init'], { cwd: dir })
}
```

## Testing a layer

Check each layer works on its own by bypassing the one before it: call `initRepo` directly with a
non-temp path and confirm the guard throws, then call `createWorkspace('')` and confirm the entry
check throws. A layer that only works because an earlier one caught the input has not been tested.

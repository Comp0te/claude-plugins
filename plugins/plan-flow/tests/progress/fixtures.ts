import type { On } from 'claude-code'

import { register } from '../../hooks/progress/register'

export const CWD = '/work'
export const PLAN = 'docs/plans/p.md'
export const PLAN_ABS = `${CWD}/${PLAN}`
export const COMMAND = 'plan-flow:execute-plan'
export const EXECUTOR = 'plan-flow:plan-executor'
export const SESSION = { surface: 'terminal' as const, isInteractive: true, cwd: CWD }

const SECTION_LINES = 10

/** First line of task `n` in `planText`. */
export const taskStart = (n: number) => 3 + (n - 1) * SECTION_LINES

/** A plan of `count` tasks, each `SECTION_LINES` long and carrying one Verification command. */
export function planText(count = 3): string {
  const lines = ['# Plan', '', '## Tasks']
  for (let n = 1; n <= count; n++) {
    lines.push(`### Task ${n}: Task title ${n}`, '', '**Verification:**', `- \`npm test\``)
    while (lines.length < taskStart(n) - 1 + SECTION_LINES) lines.push('body')
  }
  return `${lines.join('\n')}\n`
}

export const REPORT_CLEAN = [
  '**Status**: done',
  '**Changes**: src/a.ts',
  '**Contract not satisfied**: none',
  '**Ready to commit**: `git add src/a.ts`',
].join('\n')

export type World = {
  files: Map<string, string>
  invalidations: number
  /** Replaces a file's text as something outside the engine would. */
  put: (path: string, text: string) => void
}

const relOf = (path: string) => (path.startsWith(`${CWD}/`) ? path.slice(CWD.length + 1) : path)

/** Seats an in-memory file tree beneath the plugin and counts redraw requests. */
export function worldOf(on: On, files: Readonly<Record<string, string>>, hang = false): World {
  const world: World = {
    files: new Map(Object.entries(files)),
    invalidations: 0,
    put: (path, text) => void world.files.set(path, text),
  }
  on('fs.read', ($, e) => {
    if (hang) return new Promise(() => {}) as never
    const text = world.files.get(relOf(e.path))
    return text === undefined ? { deny: `ENOENT: ${e.path}` } : { value: text }
  })
  on('fs.exists', ($, e) => {
    const path = relOf(e.path)
    return { value: world.files.has(path) || [...world.files.keys()].some(f => f.startsWith(`${path}/`)) }
  })
  on('ui.invalidate', () => {
    world.invalidations += 1
    return { value: undefined }
  })
  on('session.start', ($, e) => ({ cwd: e.cwd }))
  return world
}

export const expansion = (args: string, name = COMMAND) => ({
  expansion_type: 'slash_command' as const,
  command_name: name,
  command_args: args,
  prompt: `/${name} ${args}`,
})

export const stop = (agentId: string, message: string | undefined, type = EXECUTOR) => ({
  stop_hook_active: false,
  agent_id: agentId,
  agent_transcript_path: '',
  agent_type: type,
  last_assistant_message: message,
})

export const spawnInput = (subagentType: string, prompt: string) =>
  ({
    tool_use_id: 'tu1',
    prompt,
    description: 'dispatch',
    subagentType,
    provider: { plugin: 'plan-flow', tier: 'user' },
  }) as never

type Handler = ($: never, e: never, next: (e: never) => Promise<unknown>) => Promise<unknown>

export type Harness = {
  /** Raises `event` through the plugin's hook with `beneath` as what the engine under it answers. */
  call: (event: string, input: object, beneath?: unknown) => Promise<unknown>
  /** Runs every timer the hooks scheduled, and what they started, until nothing is left. */
  settle: () => Promise<void>
  invalidations: () => number
}

/**
 * The module's own `register` driven in the test's environment, where its `session` can be read: the engine runs a
 * loaded plugin in an environment of its own, out of the test's reach.
 */
export async function harnessOf(files: Record<string, string>, options: Record<string, string> = {}, hangReads = false, invalidateThrows = false): Promise<Harness> {
  const handlers = new Map<string, Handler>()
  register(((pattern: string, hook: Handler) => void handlers.set(pattern, hook)) as never, options)
  const timers: (() => void)[] = []
  let invalidated = 0
  const has = (path: string) => files[relOf(path)] !== undefined || Object.keys(files).some(f => f.startsWith(`${relOf(path)}/`))
  const $ = {
    fs: {
      exists: async (path: string) => has(path),
      read: (path: string) => (hangReads ? new Promise<string>(() => {}) : Promise.resolve(files[relOf(path)] ?? '')),
    },
    clock: { after: (_ms: number, fn: () => void) => (timers.push(fn), { cancel: () => {} }) },
    ui: { invalidate: () => { if (invalidateThrows) throw new Error('no redraw'); invalidated += 1 } },
  } as never
  const call = (event: string, input: object, beneath: unknown = {}) =>
    handlers.get(event)!($, input as never, async () => beneath as never)
  const flush = async () => {
    for (let i = 0; i < 50; i++) await Promise.resolve()
  }
  const harness: Harness = {
    call,
    invalidations: () => invalidated,
    settle: async () => {
      while (timers.length > 0) {
        timers.splice(0).forEach(fn => fn())
        await flush()
      }
    },
  }
  await call('session.start', SESSION)
  return harness
}

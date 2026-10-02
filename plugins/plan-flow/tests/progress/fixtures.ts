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
type Matcher = Record<string, unknown>
type Registered = { pattern: string; matcher?: Matcher; hook: Handler }

const matches = (matcher: Matcher | undefined, input: Record<string, unknown>) =>
  matcher === undefined ||
  Object.entries(matcher).every(([key, want]) => (Array.isArray(want) ? want.includes(input[key]) : input[key] === want))

export type Harness = {
  /** Raises `event` through the plugin's hook with `beneath` as what the engine under it answers. */
  call: (event: string, input: object, beneath?: unknown) => Promise<unknown>
  /** Runs every timer the hooks scheduled, and what they started, until nothing is left. */
  settle: () => Promise<void>
  invalidations: () => number
  /** Every `$.ui.open` the module made. */
  opened: { id: string; title?: string }[]
  /** Every `$.command.register` the module made. */
  registered: { name: string; description: string }[]
  /** The plugin's store, as `$.store` reads and writes it. */
  store: Map<string, unknown>
  /** How many `$.store.set` calls were made. */
  sets: () => number
  /** The delay of every `$.clock.after` the module armed, in order. */
  delays: number[]
  /** What `$.ui.open` answers as `isPlaced`. */
  placed: { value: boolean }
  /** What the pane's render hook draws: the `Text` rows, in order. */
  render: (props?: Record<string, unknown>) => Promise<string[]>
}

const textsOf = (node: unknown): string[] => {
  if (typeof node === 'string' || typeof node === 'number') return [String(node)]
  if (Array.isArray(node)) return node.flatMap(textsOf)
  if (typeof node !== 'object' || node === null) return []
  const { tag, props } = node as { tag: string; props: { children?: unknown } }
  return tag === 'Text' ? [textsOf(props.children).join('')] : textsOf(props.children)
}

/**
 * The module's own `register` driven in the test's environment, where its `session` can be read: the engine runs a
 * loaded plugin in an environment of its own, out of the test's reach.
 */
export async function harnessOf(
  files: Record<string, string>,
  options: Record<string, string> = {},
  hangReads = false,
  invalidateThrows = false,
  initialStore: Record<string, unknown> = {},
): Promise<Harness> {
  const handlers: Registered[] = []
  const on = (pattern: string, a: Matcher | Handler, b?: Handler) =>
    void handlers.push(b === undefined ? { pattern, hook: a as Handler } : { pattern, matcher: a as Matcher, hook: b })
  register(on as never, options)
  const timers: (() => void)[] = []
  const delays: number[] = []
  const opened: Harness['opened'] = []
  const registered: Harness['registered'] = []
  const store = new Map<string, unknown>(Object.entries(initialStore))
  const placed = { value: true }
  let sets = 0
  let invalidated = 0
  const has = (path: string) => files[relOf(path)] !== undefined || Object.keys(files).some(f => f.startsWith(`${relOf(path)}/`))
  const tag = (name: string) => (props: object) => ({ tag: name, props })
  const $ = {
    fs: {
      exists: async (path: string) => has(path),
      read: (path: string) => (hangReads ? new Promise<string>(() => {}) : Promise.resolve(files[relOf(path)] ?? '')),
    },
    clock: {
      after: (ms: number, fn: () => void) => {
        delays.push(ms)
        timers.push(fn)
        return { cancel: () => {} }
      },
    },
    ui: {
      invalidate: () => { if (invalidateThrows) throw new Error('no redraw'); invalidated += 1 },
      open: async (args: Harness['opened'][number]) => (opened.push(args), { isPlaced: placed.value }),
      resolve: () => ({ Box: tag('Box'), Text: tag('Text') }),
    },
    store: {
      get: async (key: string) => store.get(key),
      set: async (key: string, value: unknown) => {
        sets += 1
        store.set(key, JSON.parse(JSON.stringify(value)))
      },
    },
    command: { register: async (spec: Harness['registered'][number]) => void registered.push(spec) },
  } as never
  const call = (event: string, input: object, beneath: unknown = {}) => {
    const hit = handlers.find(h => h.pattern === event && matches(h.matcher, input as Record<string, unknown>))
    return hit!.hook($, input as never, async () => beneath as never)
  }
  const flush = async () => {
    for (let i = 0; i < 50; i++) await Promise.resolve()
  }
  const harness: Harness = {
    call,
    invalidations: () => invalidated,
    opened,
    registered,
    store,
    sets: () => sets,
    delays,
    placed,
    render: async (props = {}) => {
      const input = { surface: 'terminal', component: 'Pane', requestId: 'plan-progress', props: { bodyColumns: 72, ...props } }
      return textsOf(await call('ui.render', input))
    },
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

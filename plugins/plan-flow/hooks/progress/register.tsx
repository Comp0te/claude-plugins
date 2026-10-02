import type { AgentSpawnInput, AgentSpawnResult, EngineInterface, Register, ToolCallInput, ToolCallResult } from 'claude-code'

import { checkLabel, gitAddPaths, isExecutorType, planPathIn, taskForDispatch, taskForRead } from './match'
import { optionsOf, type ProgressOptions } from './options'
import { parsePlan, type PlanTask } from './plan'
import { parseReport } from './report'
import {
  executorCalled,
  executorChecked,
  executorFinished,
  executorMatched,
  executorSpawned,
  isKnownExecutor,
  mainAdded,
  mainCommitted,
  newRun,
  tailOf,
  withPlan,
  type Run,
} from './run'

type Dollar = EngineInterface

/** The observed run, in memory; hooks only write it after the engine's own result is in hand. */
export const session = {
  run: undefined as Run | undefined,
  plan: [] as PlanTask[],
  cwd: '',
  error: undefined as string | undefined,
}

let opts: ProgressOptions = optionsOf({})

export const redraw = ($: Dollar) => $.ui.invalidate('ui.render')

const EXECUTE_PLAN = /(^|:)execute-plan$/

type BashResult = { stdout?: unknown; stderr?: unknown; gitOperation?: { commit?: { sha: string; kind: string } } }
type AgentResult = { status?: string; agentId?: string; content?: { text: string }[] }
const recordOf = <T,>(value: unknown) => (typeof value === 'object' && value !== null ? (value as T) : undefined)

const resolvePath = (path: string) => {
  const clean = path.replace(/^\.\//, '')
  return clean.startsWith('/') || clean.startsWith('~') || session.cwd === '' ? clean : `${session.cwd.replace(/\/+$/, '')}/${clean}`
}

const safeRedraw = ($: Dollar) => {
  try {
    redraw($)
  } catch {
    // a failed redraw must not reach the hook's caller
  }
}

const failure = (error: unknown) => (error instanceof Error ? error.message : String(error))

function watch($: Dollar, observe: () => void) {
  const before = session.run
  try {
    observe()
  } catch (error) {
    session.error = failure(error)
    safeRedraw($)
  }
  if (session.run !== before) safeRedraw($)
}

function schedule($: Dollar, fn: () => Promise<unknown> | unknown) {
  $.clock.after(0, () => {
    void (async () => {
      const before = session.run
      try {
        await fn()
      } catch (error) {
        session.error = failure(error)
        safeRedraw($)
      }
      if (session.run !== before) safeRedraw($)
    })()
  })
}

async function startRun($: Dollar, arg: string): Promise<boolean> {
  if (session.run) return true
  const raw = arg.trim().replace(/^["']|["']$/g, '')
  if (raw === '') return false
  const given = resolvePath(raw)
  const path = /\.md$/i.test(given) ? given : `${given.replace(/\/+$/, '')}/plan.md`
  if (!(await $.fs.exists(path))) return false
  const plan = parsePlan(String(await $.fs.read(path)))
  if (session.run) return true
  session.plan = plan
  session.run = newRun(path, plan, Date.now())
  return true
}

async function rereadPlan($: Dollar) {
  const path = session.run?.planPath
  if (path === undefined) return
  const plan = parsePlan(String(await $.fs.read(path)))
  if (!session.run) return
  session.plan = plan
  session.run = withPlan(session.run, plan, Date.now())
}

function observeToolCall($: Dollar, e: ToolCallInput, r: ToolCallResult) {
  const run = session.run
  const result: unknown = r.result
  if (!run) {
    if (e.tool === 'Skill' && EXECUTE_PLAN.test(String(e.skill))) schedule($, () => startRun($, String(e.args ?? '')))
    return
  }

  if (e.agentId !== undefined) {
    if (!isKnownExecutor(run, e.agentId)) return
    const now = Date.now()
    let next = executorCalled(run, e.agentId, now)
    if (e.tool === 'Read' && resolvePath(e.file_path) === run.planPath) {
      const task = taskForRead(e.offset, session.plan)
      if (task !== undefined && e.agentId in next.unmatched) next = executorMatched(next, e.agentId, task, now)
    }
    if (e.tool === 'Bash') {
      const task = next.tasks.find(t => t.executorId === e.agentId && t.status === 'executing')
      const label = checkLabel(e.command, task?.verification ?? [], opts.checkPattern)
      if (label) {
        const ok = r.isError !== true
        const out = recordOf<BashResult>(result)
        const text = typeof result === 'string' ? result : `${out?.stdout ?? ''}\n${out?.stderr ?? ''}`
        next = executorChecked(next, e.agentId, { label, ok, tail: ok ? [] : tailOf(text), at: now }, now)
      }
    }
    session.run = next
    return
  }

  if (e.tool === 'Bash') {
    const added = gitAddPaths(e.command)
    let next = added.length > 0 ? mainAdded(run, added, Date.now()) : run
    const commit = recordOf<BashResult>(result)?.gitOperation?.commit
    if (commit?.kind === 'committed') next = mainCommitted(next, commit.sha, Date.now())
    session.run = next
  } else if ((e.tool === 'Edit' || e.tool === 'Write') && resolvePath(e.file_path) === run.planPath) {
    schedule($, () => rereadPlan($))
  } else if (e.tool === 'Agent') {
    const agent = recordOf<AgentResult>(result)
    if (agent?.status === 'completed' && agent.agentId !== undefined && isKnownExecutor(run, agent.agentId)) {
      const report = (agent.content ?? []).map(c => c.text).join('\n')
      session.run = executorFinished(run, agent.agentId, parseReport(report), Date.now())
    }
  }
}

function observeSpawn($: Dollar, e: AgentSpawnInput, r: AgentSpawnResult) {
  if (!isExecutorType(e.subagentType) || r.agentId === undefined) return
  const agentId = r.agentId
  const apply = () => {
    if (session.run) session.run = executorSpawned(session.run, agentId, taskForDispatch(e.prompt, session.plan), Date.now())
  }
  if (session.run) {
    apply()
    schedule($, () => rereadPlan($))
    return
  }
  const path = planPathIn(e.prompt)
  if (path === undefined) return
  schedule($, async () => {
    if (await startRun($, path)) apply()
  })
}

function observeStop(e: { agent_id: string; agent_type: string; last_assistant_message?: string }) {
  const run = session.run
  if (!run || !isExecutorType(e.agent_type) || !e.last_assistant_message || !isKnownExecutor(run, e.agent_id)) return
  session.run = executorFinished(run, e.agent_id, parseReport(e.last_assistant_message), Date.now())
}

export const register: Register = (on, options) => {
  opts = optionsOf(options)
  const active = () => opts.mode !== 'off'

  on('session.start', async ($, e, next) => {
    const result = await next(e)
    session.run = undefined
    session.plan = []
    session.error = undefined
    session.cwd = e.cwd
    return result
  })

  on('tool.call', async ($, e, next) => {
    const result = await next(e)
    if (active()) watch($, () => observeToolCall($, e, result))
    return result
  })

  on('agent.spawn', async ($, e, next) => {
    const result = await next(e)
    if (active()) watch($, () => observeSpawn($, e, result))
    return result
  })

  on('classic.UserPromptExpansion', async ($, e, next) => {
    const result = await next(e)
    if (active() && EXECUTE_PLAN.test(e.command_name)) {
      if (session.cwd === '') session.cwd = e.cwd
      watch($, () => schedule($, () => startRun($, e.command_args)))
    }
    return result
  })

  on('classic.SubagentStop', async ($, e, next) => {
    const result = await next(e)
    if (active()) watch($, () => observeStop(e))
    return result
  })
}

import type { PlanTask } from './plan'
import type { ExecutorOutcome } from './report'

export type TaskStatus = 'pending' | 'executing' | 'review' | 'committed' | 'halted'

export type CheckResult = { label: string; ok: boolean; tail: string[]; at: number }

export type TaskRun = {
  number: number
  title: string
  inPlan: boolean
  verification: string[]
  status: TaskStatus
  attempts: number
  executorId?: string
  toolCalls: number
  startedAt?: number
  finishedAt?: number
  checks: CheckResult[]
  reason?: string
  readyPaths: string[]
  commitSha?: string
}

export type Run = {
  planPath: string
  tasks: TaskRun[]
  /** Executors whose dispatch named no task yet, by agent id. */
  unmatched: Record<string, { toolCalls: number; startedAt: number }>
  pendingAdds: string[]
  unassignedCommits: string[]
  closedByPerson: boolean
  updatedAt: number
}

const touch = (run: Run, now: number, patch: Partial<Run>): Run => ({ ...run, ...patch, updatedAt: now })
const mapTask = (run: Run, n: number, fn: (t: TaskRun) => TaskRun) => run.tasks.map(t => (t.number === n ? fn(t) : t))
const taskOf = (run: Run, agentId: string) => run.tasks.find(t => t.executorId === agentId && t.status === 'executing')
const strip = (p: string) => p.replace(/^\.\//, '')
const fresh = (p: PlanTask): TaskRun => ({
  number: p.number, title: p.title, inPlan: true, verification: p.verification,
  status: 'pending', attempts: 0, toolCalls: 0, checks: [], readyPaths: [],
})

export const isKnownExecutor = (run: Run, agentId: string) =>
  taskOf(run, agentId) !== undefined || agentId in run.unmatched

export const newRun = (planPath: string, plan: readonly PlanTask[], now: number): Run =>
  ({ planPath, tasks: plan.map(fresh), unmatched: {}, pendingAdds: [], unassignedCommits: [], closedByPerson: false, updatedAt: now })

export function withPlan(run: Run, plan: readonly PlanTask[], now: number): Run {
  const kept = plan.map(p => {
    const old = run.tasks.find(t => t.number === p.number)
    return old ? { ...old, title: p.title, verification: p.verification, inPlan: true } : fresh(p)
  })
  const orphans = run.tasks
    .filter(t => !plan.some(p => p.number === t.number) && t.status !== 'pending')
    .map(t => ({ ...t, inPlan: false }))
  return touch(run, now, { tasks: [...kept, ...orphans] })
}

export const tailOf = (output: string): string[] =>
  output.split('\n').map(l => l.trimEnd()).filter(l => l.trim() !== '').slice(-3)
    .map(l => (l.length > 200 ? `${l.slice(0, 199)}…` : l))

const start = (t: TaskRun, agentId: string, startedAt: number, toolCalls: number): TaskRun => ({
  ...t, status: 'executing', attempts: t.attempts + 1, executorId: agentId,
  startedAt, finishedAt: undefined, toolCalls, checks: [], reason: undefined,
})

export function executorSpawned(run: Run, agentId: string, task: number | undefined, now: number): Run {
  if (task === undefined || !run.tasks.some(t => t.number === task)) {
    return touch(run, now, { unmatched: { ...run.unmatched, [agentId]: { toolCalls: 0, startedAt: now } } })
  }
  return touch(run, now, { tasks: mapTask(run, task, t => start(t, agentId, now, 0)) })
}

export function executorMatched(run: Run, agentId: string, task: number, now: number): Run {
  const early = run.unmatched[agentId]
  if (!early || !run.tasks.some(t => t.number === task)) return run
  const { [agentId]: _, ...unmatched } = run.unmatched
  return touch(run, now, { unmatched, tasks: mapTask(run, task, t => start(t, agentId, early.startedAt, early.toolCalls)) })
}

export function executorCalled(run: Run, agentId: string, now: number): Run {
  const task = taskOf(run, agentId)
  if (task) return touch(run, now, { tasks: mapTask(run, task.number, t => ({ ...t, toolCalls: t.toolCalls + 1 })) })
  const early = run.unmatched[agentId]
  if (!early) return run
  return touch(run, now, { unmatched: { ...run.unmatched, [agentId]: { ...early, toolCalls: early.toolCalls + 1 } } })
}

export function executorChecked(run: Run, agentId: string, check: CheckResult, now: number): Run {
  const task = taskOf(run, agentId)
  if (!task) return run
  const i = task.checks.findIndex(c => c.label === check.label)
  const checks = i < 0 ? [...task.checks, check] : task.checks.map((c, j) => (j === i ? check : c))
  return touch(run, now, { tasks: mapTask(run, task.number, t => ({ ...t, checks })) })
}

export function executorFinished(run: Run, agentId: string, outcome: ExecutorOutcome, now: number): Run {
  const task = taskOf(run, agentId)
  if (!task) {
    if (!(agentId in run.unmatched)) return run
    const { [agentId]: _, ...unmatched } = run.unmatched
    return touch(run, now, { unmatched })
  }
  const reason = outcome.kind === 'review' ? undefined : outcome.reason
  return touch(run, now, {
    tasks: mapTask(run, task.number, t => ({ ...t, status: outcome.kind, reason, readyPaths: outcome.readyPaths, finishedAt: now })),
  })
}

export const mainAdded = (run: Run, paths: readonly string[], now: number): Run =>
  touch(run, now, { pendingAdds: [...new Set([...run.pendingAdds, ...paths.map(strip)])] })

export function mainCommitted(run: Run, sha: string, now: number): Run {
  const inReview = run.tasks.filter(t => t.status === 'review')
  const added = new Set(run.pendingAdds.map(strip))
  const byPaths = inReview.filter(t => t.readyPaths.some(p => added.has(strip(p))))
  const target = inReview.length === 1 ? inReview[0] : byPaths.length === 1 ? byPaths[0] : undefined
  if (!target) return touch(run, now, { pendingAdds: [], unassignedCommits: [...run.unassignedCommits, sha] })
  return touch(run, now, { pendingAdds: [], tasks: mapTask(run, target.number, t => ({ ...t, status: 'committed', commitSha: sha })) })
}

export const personClosed = (run: Run): Run => ({ ...run, closedByPerson: true })

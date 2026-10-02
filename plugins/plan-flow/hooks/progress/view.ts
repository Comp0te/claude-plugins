import type { Run, TaskRun, TaskStatus } from './run'

export type Tone = 'plain' | 'dim' | 'active' | 'ok' | 'warn' | 'fail'
export type PaneLine = { text: string; tone: Tone; bold?: boolean }

export function formatElapsed(ms: number): string {
  const s = Math.floor(ms / 1000)
  const m = Math.floor(s / 60)
  return s < 60 ? `${s}s` : m < 60 ? `${m}m` : `${Math.floor(m / 60)}h ${m % 60}m`
}

const GLYPH: Record<TaskStatus, string> = { pending: '○', executing: '▶', review: '●', committed: '✓', halted: '■' }
const TONE: Record<TaskStatus, Tone> = { pending: 'dim', executing: 'active', review: 'warn', committed: 'ok', halted: 'fail' }

const cut = (text: string, columns: number) =>
  text.length <= columns ? text : columns <= 1 ? text.slice(0, columns) : `${text.slice(0, columns - 1)}…`

function header(run: Run, path: string): PaneLine[] {
  const count = (status: TaskStatus) => run.tasks.filter(t => t.status === status).length
  const parts = [`${count('committed')}/${run.tasks.length} committed`]
  for (const [status, label] of [['review', 'in review'], ['executing', 'executing'], ['halted', 'halted']] as const) {
    if (count(status)) parts.push(`${count(status)} ${label}`)
  }
  return [
    { text: path, tone: 'plain', bold: true },
    { text: parts.join(' · '), tone: 'dim' },
    { text: '', tone: 'plain' },
  ]
}

function statusText(t: TaskRun, now: number): string {
  const attempt = t.attempts > 1 ? ` · attempt ${t.attempts}` : ''
  const orphan = t.inPlan ? '' : ' · not in plan'
  if (t.status === 'executing') {
    return `executing · ${t.toolCalls} calls · ${formatElapsed(now - (t.startedAt ?? now))}${attempt}${orphan}`
  }
  if (t.status === 'committed') return `committed ${(t.commitSha ?? '').slice(0, 7)}${orphan}`
  return `${t.status}${attempt}${orphan}`
}

function taskRow(t: TaskRun, now: number, columns: number): PaneLine {
  const lead = `${GLYPH[t.status]} ${t.number}. `
  const status = `  ${statusText(t, now)}`
  const room = columns - lead.length - status.length
  const title = t.title.length <= room ? t.title : room >= 1 ? cut(t.title, room) : ''
  return { text: cut(`${lead}${title}${status}`, columns), tone: TONE[t.status] }
}

function details(t: TaskRun): PaneLine[] {
  if (t.status === 'pending') return []
  const failed = t.checks.filter(c => !c.ok).length
  if (t.status === 'committed') {
    return failed ? [{ text: `  ✗ ${failed} check${failed > 1 ? 's' : ''} failed at last run`, tone: 'warn' }] : []
  }
  const lines: PaneLine[] = t.checks.flatMap(c => [
    { text: `  ${c.ok ? '✓' : '✗'} ${c.label}`, tone: c.ok ? 'ok' : 'fail' } as PaneLine,
    ...c.tail.map(l => ({ text: `    ${l}`, tone: 'dim' }) as PaneLine),
  ])
  if (t.reason) lines.push({ text: `  ${t.reason}`, tone: 'fail' })
  return lines
}

export function paneLines(
  run: Run | undefined,
  at: { now: number; columns: number; path: string; error?: string },
): PaneLine[] {
  const { now, columns } = at
  const lines: PaneLine[] = []
  if (!run) {
    lines.push(
      { text: 'No plan is running.', tone: 'plain' },
      { text: 'Start one with the plan-execution command; this pane follows it.', tone: 'dim' },
    )
  } else {
    lines.push(...header(run, at.path))
    for (const t of run.tasks) {
      lines.push(taskRow(t, now, columns), ...details(t))
    }
    for (const u of Object.values(run.unmatched)) {
      lines.push({
        text: `▶ ?. executor not matched to a task · ${u.toolCalls} calls · ${formatElapsed(now - u.startedAt)}`,
        tone: 'active',
      })
    }
    for (const sha of run.unassignedCommits) {
      lines.push({ text: `commit ${sha.slice(0, 7)} not matched to a task`, tone: 'dim' })
    }
  }
  if (at.error) lines.push({ text: `pane error: ${at.error}`, tone: 'fail' })
  return lines.map(l => ({ ...l, text: cut(l.text, columns) }))
}

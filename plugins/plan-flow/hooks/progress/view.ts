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
  const passed = t.checks.length - failed
  const lines: PaneLine[] = passed ? [{ text: `  ✓ ${passed} check${passed > 1 ? 's' : ''} passed`, tone: 'ok' }] : []
  for (const c of t.checks.filter(c => !c.ok)) {
    lines.push({ text: `  ✗ ${c.label}`, tone: 'fail' }, ...c.tail.map(l => ({ text: `    ${l}`, tone: 'dim' }) as PaneLine))
  }
  if (t.reason) lines.push({ text: `  ${t.reason}`, tone: 'fail' })
  return lines
}

type Row = PaneLine & { detail?: boolean }

/** Fits rows to `rows`: task rows always stay, failures are the last details to go. */
function fit(all: Row[], rows: number | undefined): PaneLine[] {
  const strip = (r: Row): PaneLine => ({ text: r.text, tone: r.tone, ...(r.bold ? { bold: true } : {}) })
  if (rows === undefined || all.length <= rows) return all.map(strip)
  const kept = all.filter(r => !r.detail)
  const details = all.length - kept.length
  const hiddenNote = (n: number) => `${n} detail row${n > 1 ? 's' : ''} hidden`
  if (kept.length >= rows) {
    const [path, counts, ...rest] = kept
    if (!counts) return kept.map(strip)
    const tight = [path!, counts, ...rest.filter(r => r.text !== '')]
    const note = tight.length > rows ? 'ctrl+x tab to scroll' : hiddenNote(details)
    tight[1] = { ...counts, text: `${counts.text} · ${note}` }
    return tight.map(strip)
  }
  let room = rows - kept.length - 1
  const shown = new Set<Row>()
  for (const failure of [true, false]) {
    for (const r of all) {
      if (room > 0 && r.detail && (r.tone === 'fail') === failure) {
        shown.add(r)
        room--
      }
    }
  }
  const note: Row = { text: `… ${hiddenNote(details - shown.size)}`, tone: 'dim' }
  return [...all.filter(r => !r.detail || shown.has(r)), note].map(strip)
}

/** The pane's rows, each cut to `columns`; with `rows`, detail rows give way so every task row fits. */
export function paneLines(
  run: Run | undefined,
  at: { now: number; columns: number; path: string; rows?: number; error?: string },
): PaneLine[] {
  const { now, columns } = at
  const lines: Row[] = []
  if (!run) {
    lines.push(
      { text: 'No plan is running.', tone: 'plain' },
      { text: 'Start one with the plan-execution command; this pane follows it.', tone: 'dim' },
    )
  } else {
    lines.push(...header(run, at.path))
    for (const t of run.tasks) {
      lines.push(taskRow(t, now, columns), ...details(t).map(l => ({ ...l, detail: true })))
    }
    for (const u of Object.values(run.unmatched)) {
      lines.push({
        text: `▶ ?. executor not matched to a task · ${u.toolCalls} calls · ${formatElapsed(now - u.startedAt)}`,
        tone: 'active',
      })
    }
    for (const sha of run.unassignedCommits) {
      lines.push({ text: `commit ${sha.slice(0, 7)} not matched to a task`, tone: 'dim', detail: true })
    }
  }
  if (at.error) lines.push({ text: `pane error: ${at.error}`, tone: 'fail' })
  return fit(lines, at.rows).map(l => ({ ...l, text: cut(l.text, columns) }))
}

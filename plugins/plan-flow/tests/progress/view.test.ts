import { describe, expect, test } from 'claude-code/testing'

import type { PlanTask } from '../../hooks/progress/plan'
import {
  executorCalled,
  executorChecked,
  executorFinished,
  executorSpawned,
  mainAdded,
  mainCommitted,
  newRun,
  withPlan,
  type Run,
} from '../../hooks/progress/run'
import { formatElapsed, paneLines } from '../../hooks/progress/view'

const pt = (number: number, title: string): PlanTask => ({ number, title, startLine: 1, endLine: 2, verification: [] })
const titles = ['Plan parser', 'Matchers', 'Report parser', 'Run reducer', 'View', 'Wiring', 'Pane', 'Store']
const plan = titles.map((t, i) => pt(i + 1, t))
const base = (): Run => newRun('docs/plan.md', plan, 0)
const at = (over: Partial<Parameters<typeof paneLines>[1]> = {}) => ({ now: 240_000, columns: 80, path: 'docs/plan.md', ...over })
const review = (paths: string[] = []) => ({ kind: 'review' as const, readyPaths: paths })
function busy(): Run {
  let run = executorSpawned(base(), 'a', 4, 0)
  run = executorChecked(run, 'a', { label: 'lint', ok: true, tail: [], at: 1 }, 1)
  run = executorChecked(run, 'a', { label: 'tests', ok: false, tail: ['one', 'two'], at: 2 }, 2)
  run = executorSpawned(run, 'h', 5, 0)
  return executorFinished(run, 'h', { kind: 'halted', reason: 'file moved', readyPaths: [] }, 1)
}
const find = (run: Run, text: string) => paneLines(run, at()).find(l => l.text.includes(text))

describe('paneLines', () => {
  test('no run', async () => {
    expect(paneLines(undefined, at())).toEqual([
      { text: 'No plan is running.', tone: 'plain' },
      { text: 'Start one with the plan-execution command; this pane follows it.', tone: 'dim' },
    ])
  })

  test('header omits zero counts', async () => {
    let run = base()
    for (const n of [1, 2]) {
      run = executorSpawned(run, `c${n}`, n, 0)
      run = executorFinished(run, `c${n}`, review(), 0)
      run = mainCommitted(run, `sha${n}`, 0)
    }
    run = executorSpawned(run, 'r', 3, 0)
    run = executorFinished(run, 'r', review(), 0)
    run = executorSpawned(run, 'e', 4, 0)
    run = executorSpawned(run, 'h', 5, 0)
    run = executorFinished(run, 'h', { kind: 'halted', reason: 'x', readyPaths: [] }, 0)
    const lines = paneLines(run, at())
    expect(lines[0]).toEqual({ text: 'docs/plan.md', tone: 'plain', bold: true })
    expect(lines[1]).toEqual({ text: '2/8 committed · 1 in review · 1 executing · 1 halted', tone: 'dim' })
    expect(paneLines(base(), at())[1]!.text).toBe('0/8 committed')
  })

  test('pending task', async () => {
    expect(find(base(), 'Wiring')).toEqual({ text: '○ 6. Wiring  pending', tone: 'dim' })
  })

  test('executing task', async () => {
    let run = executorSpawned(base(), 'a', 4, 0)
    for (let i = 0; i < 17; i++) run = executorCalled(run, 'a', 1)
    expect(find(run, 'Run reducer')).toEqual({ text: '▶ 4. Run reducer  executing · 17 calls · 4m', tone: 'active' })
  })

  test('re-dispatched task shows the attempt', async () => {
    let run = executorSpawned(base(), 'a', 4, 0)
    run = executorFinished(run, 'a', review(), 1)
    run = executorSpawned(run, 'b', 4, 0)
    expect(find(run, 'Run reducer')!.text).toBe('▶ 4. Run reducer  executing · 0 calls · 4m · attempt 2')
  })

  test('task in review', async () => {
    let run = executorSpawned(base(), 'a', 3, 0)
    run = executorFinished(run, 'a', review(), 1)
    expect(find(run, 'Report parser')).toEqual({ text: '● 3. Report parser  review', tone: 'warn' })
  })

  test('committed task has no check lines', async () => {
    let run = executorSpawned(base(), 'a', 1, 0)
    run = executorChecked(run, 'a', { label: 'tests', ok: true, tail: [], at: 1 }, 1)
    run = executorFinished(run, 'a', review(), 1)
    run = mainCommitted(run, 'a1b2c3d4e5', 2)
    const lines = paneLines(run, at())
    const i = lines.findIndex(l => l.text.includes('Plan parser'))
    expect(lines[i]).toEqual({ text: '✓ 1. Plan parser  committed a1b2c3d', tone: 'ok' })
    expect(lines[i + 1]!.text).not.toContain('tests')
  })

  test('committed task with a failed last check', async () => {
    let run = executorSpawned(base(), 'a', 1, 0)
    run = executorChecked(run, 'a', { label: 'tests', ok: false, tail: ['boom'], at: 1 }, 1)
    run = executorFinished(run, 'a', review(), 1)
    run = mainCommitted(run, 'a1b2c3d4e5', 2)
    const lines = paneLines(run, at())
    const i = lines.findIndex(l => l.text.includes('Plan parser'))
    expect(lines[i + 1]).toEqual({ text: '  ✗ 1 check failed at last run', tone: 'warn' })
  })

  test('halted task shows its reason', async () => {
    let run = executorSpawned(base(), 'a', 5, 0)
    run = executorFinished(run, 'a', { kind: 'halted', reason: 'file moved', readyPaths: [] }, 1)
    const lines = paneLines(run, at())
    const i = lines.findIndex(l => l.text.includes('View'))
    expect(lines[i]).toEqual({ text: '■ 5. View  halted', tone: 'fail' })
    expect(lines[i + 1]).toEqual({ text: '  file moved', tone: 'fail' })
  })

  test('checks of an active task', async () => {
    let run = executorSpawned(base(), 'a', 4, 0)
    run = executorChecked(run, 'a', { label: 'lint', ok: true, tail: [], at: 1 }, 1)
    run = executorChecked(run, 'a', { label: 'tests', ok: false, tail: ['one', 'two'], at: 2 }, 2)
    const lines = paneLines(run, at())
    const i = lines.findIndex(l => l.text.includes('Run reducer'))
    expect(lines.slice(i + 1, i + 5)).toEqual([
      { text: '  ✓ 1 check passed', tone: 'ok' },
      { text: '  ✗ tests', tone: 'fail' },
      { text: '    one', tone: 'dim' },
      { text: '    two', tone: 'dim' },
    ])
  })

  test('passing checks fold into one row', async () => {
    let run = executorSpawned(base(), 'a', 4, 0)
    run = executorChecked(run, 'a', { label: 'lint', ok: true, tail: [], at: 1 }, 1)
    run = executorChecked(run, 'a', { label: 'tests', ok: true, tail: [], at: 2 }, 2)
    const lines = paneLines(run, at())
    const i = lines.findIndex(l => l.text.includes('Run reducer'))
    expect(lines[i + 1]).toEqual({ text: '  ✓ 2 checks passed', tone: 'ok' })
    expect(lines[i + 2]!.text).toBe('○ 5. View  pending')
  })

  test('unmatched executor', async () => {
    let run = executorSpawned(base(), 'u', undefined, 0)
    for (let i = 0; i < 5; i++) run = executorCalled(run, 'u', 1)
    expect(paneLines(run, at({ now: 61_000 })).find(l => l.text.includes('?.'))).toEqual({
      text: '▶ ?. executor not matched to a task · 5 calls · 1m',
      tone: 'active',
    })
  })

  test('unassigned commit', async () => {
    const run = mainCommitted(mainAdded(base(), ['x.ts'], 0), 'a1b2c3d4e5', 1)
    expect(paneLines(run, at()).find(l => l.text.includes('not matched to a task') && l.text.startsWith('commit'))).toEqual({
      text: 'commit a1b2c3d not matched to a task',
      tone: 'dim',
    })
  })

  test('task no longer in the plan', async () => {
    let run = executorSpawned(base(), 'a', 8, 0)
    run = executorFinished(run, 'a', review(), 1)
    run = withPlan(run, plan.slice(0, 4), 2)
    expect(find(run, 'Store')!.text).toBe('● 8. Store  review · not in plan')
  })

  test('narrow pane cuts every line, keeping the status on task rows', async () => {
    let run = executorSpawned(base(), 'a', 4, 0)
    run = executorChecked(run, 'a', { label: 'a very long check label indeed', ok: true, tail: [], at: 1 }, 1)
    const lines = paneLines(run, at({ columns: 30, path: 'a/very/long/path/to/the/plan/file.md', error: 'x'.repeat(80) }))
    expect(lines.every(l => l.text.length <= 30)).toBe(true)
    expect(lines.some(l => l.text.endsWith('…'))).toBe(true)
    expect(find(run, 'Run reducer')).toBeDefined()
    const row = paneLines(run, at({ columns: 30 })).find(l => l.text.startsWith('▶ 4.'))!
    expect(row.text).toContain('executing')
    expect(row.text.length).toBeLessThanOrEqual(30)
  })

  test('a short pane keeps every task row and failures, hiding the other details', async () => {
    const run = busy()
    expect(paneLines(run, at()).length).toBe(16)
    const lines = paneLines(run, at({ rows: 14 }))
    expect(lines.length).toBe(14)
    expect(lines.filter(l => /^[○▶■] \d\. /.test(l.text)).length).toBe(8)
    expect(lines.map(l => l.text)).toContain('  ✗ tests')
    expect(lines.map(l => l.text)).toContain('  file moved')
    expect(lines.map(l => l.text)).not.toContain('    one')
    expect(lines.at(-1)).toEqual({ text: '… 3 detail rows hidden', tone: 'dim' })
  })

  test('a pane shorter than its task list drops details and says how to scroll', async () => {
    const lines = paneLines(busy(), at({ rows: 8 }))
    expect(lines.length).toBe(10)
    expect(lines[1]!.text).toBe('0/8 committed · 1 executing · 1 halted · ctrl+x tab to scroll')
    expect(lines.slice(2).every(l => /^[○▶■] \d\. /.test(l.text))).toBe(true)
  })

  test('a pane with room draws everything', async () => {
    expect(paneLines(busy(), at({ rows: 16 }))).toEqual(paneLines(busy(), at()))
  })

  test('error line', async () => {
    const lines = paneLines(base(), at({ error: 'boom' }))
    expect(lines[lines.length - 1]).toEqual({ text: 'pane error: boom', tone: 'fail' })
  })
})

describe('formatElapsed', () => {
  test('seconds, minutes, hours', async () => {
    expect(formatElapsed(45_000)).toBe('45s')
    expect(formatElapsed(4 * 60_000)).toBe('4m')
    expect(formatElapsed(65 * 60_000)).toBe('1h 5m')
  })
})

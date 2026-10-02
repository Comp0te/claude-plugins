import { describe, expect, test } from 'claude-code/testing'

import type { PlanTask } from '../../hooks/progress/plan'
import {
  executorCalled,
  executorChecked,
  executorFinished,
  executorMatched,
  executorSpawned,
  mainAdded,
  mainCommitted,
  newRun,
  tailOf,
  withPlan,
} from '../../hooks/progress/run'

const pt = (number: number, title = `T${number}`, verification: string[] = [`v${number}`]): PlanTask => ({
  number, title, startLine: 1, endLine: 2, verification,
})
const plan = [pt(1), pt(2), pt(3)]
const base = () => newRun('plan.md', plan, 0)
const task = (r: ReturnType<typeof base>, n: number) => r.tasks.find(t => t.number === n)!
const review = (paths: string[]) => ({ kind: 'review' as const, readyPaths: paths })

describe('run reducer', () => {
  test('new run: all pending with verification copied', async () => {
    const run = base()
    expect(run.tasks.map(t => t.status)).toEqual(['pending', 'pending', 'pending'])
    expect(run.tasks.every(t => t.attempts === 0 && t.toolCalls === 0)).toBe(true)
    expect(task(run, 2).verification).toEqual(['v2'])
  })

  test('dispatch executes the task and clears checks', async () => {
    const run = executorSpawned(base(), 'a1', 2, 5)
    expect(task(run, 2)).toMatchObject({ status: 'executing', attempts: 1, executorId: 'a1', startedAt: 5, checks: [] })
  })

  test('dispatch not matched is tracked in unmatched', async () => {
    const run = executorSpawned(base(), 'a1', undefined, 5)
    expect(run.unmatched).toEqual({ a1: { toolCalls: 0, startedAt: 5 } })
    expect(run.tasks.map(t => t.status)).toEqual(['pending', 'pending', 'pending'])
  })

  test('late match carries calls and start time over', async () => {
    let run = executorSpawned(base(), 'a1', undefined, 5)
    for (let i = 0; i < 4; i++) run = executorCalled(run, 'a1', 6)
    run = executorMatched(run, 'a1', 2, 9)
    expect(task(run, 2)).toMatchObject({ status: 'executing', toolCalls: 4, startedAt: 5 })
    expect('a1' in run.unmatched).toBe(false)
  })

  test('tool call increments that task', async () => {
    const run = executorCalled(executorSpawned(base(), 'a1', 2, 5), 'a1', 6)
    expect(task(run, 2).toolCalls).toBe(1)
  })

  test('unknown agent returns the same object', async () => {
    const run = executorSpawned(base(), 'a1', 2, 5)
    expect(executorCalled(run, 'zz', 6) === run).toBe(true)
    expect(executorChecked(run, 'zz', { label: 'x', ok: true, tail: [], at: 1 }, 6) === run).toBe(true)
    expect(executorFinished(run, 'zz', review([]), 6) === run).toBe(true)
    expect(executorMatched(run, 'zz', 2, 6) === run).toBe(true)
  })

  test('check recorded twice keeps one entry, latest result, first-seen order', async () => {
    let run = executorSpawned(base(), 'a1', 2, 5)
    run = executorChecked(run, 'a1', { label: 'lint', ok: false, tail: ['bad'], at: 1 }, 6)
    run = executorChecked(run, 'a1', { label: 'test', ok: true, tail: [], at: 2 }, 7)
    run = executorChecked(run, 'a1', { label: 'lint', ok: true, tail: [], at: 3 }, 8)
    expect(task(run, 2).checks.map(c => [c.label, c.ok])).toEqual([['lint', true], ['test', true]])
  })

  test('finish to review stores paths and finish time', async () => {
    const run = executorFinished(executorSpawned(base(), 'a1', 2, 5), 'a1', review(['a.ts']), 9)
    expect(task(run, 2)).toMatchObject({ status: 'review', finishedAt: 9, readyPaths: ['a.ts'] })
  })

  test('finish to halted stores the reason', async () => {
    const run = executorFinished(
      executorSpawned(base(), 'a1', 2, 5), 'a1', { kind: 'halted', reason: 'frozen', readyPaths: [] }, 9)
    expect(task(run, 2)).toMatchObject({ status: 'halted', reason: 'frozen' })
  })

  test('finish twice returns the same object', async () => {
    const done = executorFinished(executorSpawned(base(), 'a1', 2, 5), 'a1', review([]), 9)
    expect(executorFinished(done, 'a1', review([]), 10) === done).toBe(true)
  })

  test('unmatched executor finishing is removed without task changes', async () => {
    const run = executorFinished(executorSpawned(base(), 'a1', undefined, 5), 'a1', review([]), 9)
    expect(run.unmatched).toEqual({})
    expect(run.tasks.map(t => t.status)).toEqual(['pending', 'pending', 'pending'])
  })

  test('re-dispatch clears checks and reason and bumps attempts', async () => {
    let run = executorSpawned(base(), 'a1', 2, 5)
    run = executorChecked(run, 'a1', { label: 'x', ok: false, tail: [], at: 1 }, 6)
    run = executorFinished(run, 'a1', { kind: 'halted', reason: 'r', readyPaths: [] }, 7)
    run = executorSpawned(run, 'a2', 2, 8)
    expect(task(run, 2)).toMatchObject({ status: 'executing', attempts: 2, executorId: 'a2', checks: [], reason: undefined })
    let inReview = executorFinished(run, 'a2', review([]), 9)
    inReview = executorSpawned(inReview, 'a3', 2, 10)
    expect(task(inReview, 2)).toMatchObject({ status: 'executing', attempts: 3 })
  })

  test('commit with one task in review commits it and clears pending adds', async () => {
    let run = executorFinished(executorSpawned(base(), 'a1', 2, 5), 'a1', review(['a.ts']), 6)
    run = mainCommitted(mainAdded(run, ['b.ts'], 7), 'abc1234def', 8)
    expect(task(run, 2)).toMatchObject({ status: 'committed', commitSha: 'abc1234def' })
    expect(run.pendingAdds).toEqual([])
  })

  const twoInReview = () => {
    let run = executorFinished(executorSpawned(base(), 'a2', 2, 1), 'a2', review(['two.ts']), 2)
    run = executorFinished(executorSpawned(run, 'a3', 3, 3), 'a3', review(['./three.ts']), 4)
    return run
  }

  test('commit with two in review: paths decide', async () => {
    const run = mainCommitted(mainAdded(twoInReview(), ['three.ts'], 5), 'sha3', 6)
    expect(task(run, 3).status).toBe('committed')
    expect(task(run, 2).status).toBe('review')
  })

  test('commit with two in review: ambiguous overlap', async () => {
    const both = mainCommitted(mainAdded(twoInReview(), ['two.ts', 'three.ts'], 5), 's', 6)
    expect([task(both, 2).status, task(both, 3).status]).toEqual(['review', 'review'])
    expect(both.unassignedCommits).toEqual(['s'])
    const neither = mainCommitted(mainAdded(twoInReview(), ['x.ts'], 5), 's', 6)
    expect([task(neither, 2).status, task(neither, 3).status]).toEqual(['review', 'review'])
    expect(neither.unassignedCommits).toEqual(['s'])
  })

  test('commit with none in review is unassigned', async () => {
    const run = mainCommitted(base(), 'abc', 1)
    expect(run.unassignedCommits).toEqual(['abc'])
  })

  test('plan amended: add, retitle, drop pending, keep executing as not in plan', async () => {
    let run = executorSpawned(newRun('p.md', [pt(1), pt(2), pt(3)], 0), 'a1', 1, 1)
    run = withPlan(run, [pt(2, 'New title'), pt(4)], 2)
    expect(run.tasks.map(t => t.number).sort()).toEqual([1, 2, 4])
    expect(task(run, 4).status).toBe('pending')
    expect(task(run, 2).title).toBe('New title')
    expect(run.tasks.some(t => t.number === 3)).toBe(false)
    expect(task(run, 1)).toMatchObject({ status: 'executing', inPlan: false })
  })

  test('tail of a failed check: last 3 non-empty lines, 200 chars max', async () => {
    const lines = ['1', '2', '3', '4', '5', '', '6', '7', 'x'.repeat(500), '']
    const tail = tailOf(lines.join('\n'))
    expect(tail).toHaveLength(3)
    expect(tail.slice(0, 2)).toEqual(['6', '7'])
    expect(tail[2]!.length).toBe(200)
    expect(tail.every(l => l.length <= 200)).toBe(true)
  })
})

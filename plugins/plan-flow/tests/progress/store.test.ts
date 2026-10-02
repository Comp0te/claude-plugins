import { describe, expect, test } from 'claude-code/testing'

import { newRun } from '../../hooks/progress/run'
import { fromStored, toStored } from '../../hooks/progress/store'

const runAt = (n: number) => newRun(`/p/${n}.md`, [], n)

describe('store', () => {
  test('keeps the 5 newest runs by updatedAt', () => {
    const six = [3, 1, 6, 2, 5, 4].map(runAt)
    const stored = toStored([...six, runAt(7)])
    expect(stored.version).toBe(1)
    expect(stored.runs.map(r => r.updatedAt).sort((a, b) => a - b)).toEqual([3, 4, 5, 6, 7])
  })

  test('a stored value reads back to its runs', () => {
    const runs = [runAt(2), runAt(1)]
    expect(fromStored(JSON.parse(JSON.stringify(toStored(runs))))).toEqual(runs)
  })

  const NOT_RUNS: [string, unknown][] = [
    ['a string', 'x'],
    ['nothing', undefined],
    ['null', null],
    ['another version', { version: 2, runs: [] }],
    ['runs that are not a list', { version: 1, runs: 'x' }],
    ['a run without a path', { version: 1, runs: [{ tasks: [] }] }],
    ['a run without tasks', { version: 1, runs: [{ planPath: '/p.md' }] }],
    ['one bad run among good ones', { version: 1, runs: [runAt(1), { planPath: 3, tasks: [] }] }],
  ]
  for (const [name, value] of NOT_RUNS) {
    test(`${name} is no runs`, () => {
      expect(fromStored(value)).toEqual([])
    })
  }
})

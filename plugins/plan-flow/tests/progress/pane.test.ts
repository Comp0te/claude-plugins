import { describe, expect, test } from 'claude-code/testing'

import { session } from '../../hooks/progress/register'
import { newRun, type Run } from '../../hooks/progress/run'
import { parsePlan } from '../../hooks/progress/plan'
import { fromStored, STORE_KEY, toStored } from '../../hooks/progress/store'
import { paneLines } from '../../hooks/progress/view'
import { CWD, PLAN, PLAN_ABS, expansion, harnessOf, planText } from './fixtures'

const FILES = { [PLAN]: planText(3) }
const OPEN = { id: 'plan-progress', title: 'Plan progress' }
const NEXT_PLAN = 'docs/plans/q.md'
const close = (kind: 'person' | 'plugin') => ({ id: 'plan-progress', origin: { kind } })
const command = { command: 'plan-progress', args: '', origin: { kind: 'composer' }, presentation: { isFullscreen: true, columns: 180 } }

/** A stored run of the fixture plan, one task in each state the pane draws without a running clock. */
function storedRun(at = 1000, path = PLAN_ABS): Run {
  const run = newRun(path, parsePlan(planText(3)), at)
  const [one, two, three] = run.tasks
  return {
    ...run,
    tasks: [
      { ...one!, title: 'Old title', status: 'committed', attempts: 1, toolCalls: 4, commitSha: 'abcdef1234', startedAt: 0, finishedAt: 5000 },
      {
        ...two!,
        status: 'review',
        attempts: 1,
        toolCalls: 9,
        startedAt: 0,
        finishedAt: 9000,
        checks: [{ label: 'npm test', ok: false, tail: ['1 failed', 'expected 2'], at: 8000 }],
      },
      { ...three!, status: 'halted', attempts: 2, reason: 'plan is wrong' },
    ],
  }
}
const withStore = (...runs: Run[]) => ({ [STORE_KEY]: toStored(runs) })

describe('opening', () => {
  test('auto: starting a plan opens the pane once', async () => {
    const h = await harnessOf(FILES)
    await h.call('classic.UserPromptExpansion', expansion(PLAN))
    await h.settle()
    await h.call('classic.UserPromptExpansion', expansion(PLAN))
    await h.settle()
    expect(h.opened).toEqual([OPEN])
  })

  test('auto: a pane that is not placed leaves nothing else behind', async () => {
    const h = await harnessOf(FILES)
    h.placed.value = false
    await h.call('classic.UserPromptExpansion', expansion(PLAN))
    await h.settle()
    expect(h.opened).toEqual([OPEN])
    expect(session.error).toBeUndefined()
    expect(session.run?.closedByPerson).toBe(false)
  })

  test('command mode: starting a plan opens nothing', async () => {
    const h = await harnessOf(FILES, { progressPane: 'command' })
    await h.call('classic.UserPromptExpansion', expansion(PLAN))
    await h.settle()
    expect(h.opened).toEqual([])
    expect(session.run).toBeDefined()
  })

  test('the command opens the pane and answers {}, in command mode', async () => {
    const h = await harnessOf(FILES, { progressPane: 'command' })
    expect(h.registered).toEqual([{ name: 'plan-progress', description: 'Show the plan progress pane' }])
    expect(await h.call('command.run', command)).toEqual({})
    expect(h.opened).toEqual([OPEN])
  })

  test('the command opens the pane and answers {}, in auto mode', async () => {
    const h = await harnessOf(FILES)
    expect(await h.call('command.run', command)).toEqual({})
    expect(h.opened).toEqual([OPEN])
  })

  test('off: no command registered, nothing opened', async () => {
    const h = await harnessOf(FILES, { progressPane: 'off' })
    await h.call('classic.UserPromptExpansion', expansion(PLAN))
    await h.settle()
    expect(h.registered).toEqual([])
    expect(h.opened).toEqual([])
  })

  test('closed by the person: not reopened by a dispatch, still opened by the command', async () => {
    const h = await harnessOf(FILES)
    await h.call('classic.UserPromptExpansion', expansion(PLAN))
    await h.settle()
    await h.call('ui.close', close('person'))
    expect(session.run?.closedByPerson).toBe(true)
    await h.call('classic.UserPromptExpansion', expansion(PLAN))
    await h.settle()
    expect(h.opened).toHaveLength(1)
    await h.call('command.run', command)
    expect(h.opened).toHaveLength(2)
  })

  test('closed by a plugin does not count as the person closing it', async () => {
    const h = await harnessOf(FILES)
    await h.call('classic.UserPromptExpansion', expansion(PLAN))
    await h.settle()
    await h.call('ui.close', close('plugin'))
    expect(session.run?.closedByPerson).toBe(false)
  })
})

describe('render', () => {
  test('draws paneLines, line for line', async () => {
    const h = await harnessOf(FILES, {}, false, false, withStore(storedRun()))
    const run = session.restored!
    const expected = paneLines(run, { now: Date.now(), columns: 72, path: 'docs/plans/p.md' })
    expect(expected.length).toBeGreaterThan(5)
    expect(await h.render()).toEqual(expected.map(l => l.text || ' '))
  })

  test('fits the rows the pane is given', async () => {
    const h = await harnessOf(FILES, {}, false, false, withStore(storedRun()))
    const expected = paneLines(session.restored!, { now: Date.now(), columns: 72, rows: 6, path: 'docs/plans/p.md' })
    expect(await h.render({ scroll: { offset: 0, bodyRows: 6 } })).toEqual(expected.map(l => l.text || ' '))
    expect(expected.length).toBe(5)
    expect(expected[1]!.text).toBe('1/3 committed · 1 in review · 1 halted · 4 detail rows hidden')
  })

  test('draws the empty state when no run exists', async () => {
    const h = await harnessOf(FILES)
    const expected = paneLines(undefined, { now: Date.now(), columns: 72, path: '' })
    expect(await h.render()).toEqual(expected.map(l => l.text || ' '))
  })

  test('draws the error line', async () => {
    const h = await harnessOf(FILES)
    session.error = 'boom'
    expect((await h.render()).at(-1)).toBe('pane error: boom')
  })

  test('a render writes nothing', async () => {
    const h = await harnessOf(FILES, {}, false, false, withStore(storedRun()))
    const before = JSON.stringify(session)
    await h.render()
    await h.settle()
    expect(h.sets()).toBe(0)
    expect(h.delays).toEqual([])
    expect(JSON.stringify(session)).toBe(before)
  })
})

describe('persistence', () => {
  test('events, then a second of clock, write runs to the store', async () => {
    const h = await harnessOf(FILES)
    await h.call('classic.UserPromptExpansion', expansion(PLAN))
    await h.settle()
    const stored = h.store.get(STORE_KEY) as { version: number; runs: Run[] }
    expect(stored.version).toBe(1)
    expect(stored.runs.map(r => r.planPath)).toEqual([PLAN_ABS])
    expect(h.delays).toContain(1000)
  })

  test('a second redraw inside the second arms no second write', async () => {
    const h = await harnessOf(FILES)
    await h.call('classic.UserPromptExpansion', expansion(PLAN))
    await h.settle()
    const armed = () => h.delays.filter(ms => ms === 1000).length
    const before = armed()
    await h.call('agent.spawn', { subagentType: 'plan-flow:plan-executor', prompt: `Task 1 of ${PLAN}` }, { model: 'm', agentId: 'a1' })
    await h.call('tool.call', { tool: 'Bash', command: 'ls', agentId: 'a1' }, { result: { stdout: '', stderr: '' }, text: '' })
    expect(armed() - before).toBe(1)
  })

  test('restored: the pane shows the stored statuses', async () => {
    const first = await harnessOf(FILES, {}, false, false, withStore(storedRun()))
    const second = await harnessOf(FILES, {}, false, false, Object.fromEntries(first.store))
    await second.call('command.run', command)
    const rows = (await second.render()).join('\n')
    expect(rows).toContain('Old title')
    expect(rows).toContain('plan is wrong')
  })

  test('bounded: the 7th run leaves the 5 newest', async () => {
    const six = [1, 2, 3, 4, 5, 6].map(n => storedRun(n * 10, `/old/${n}.md`))
    const h = await harnessOf({ ...FILES, [NEXT_PLAN]: planText(1) }, {}, false, false, withStore(...six))
    await h.call('classic.UserPromptExpansion', expansion(NEXT_PLAN))
    await h.settle()
    const paths = fromStored(h.store.get(STORE_KEY)).map(r => r.planPath)
    expect(paths).toHaveLength(5)
    expect(paths).toContain(`${CWD}/${NEXT_PLAN}`)
    expect(paths).not.toContain('/old/1.md')
  })

  test('a corrupt store is ignored', async () => {
    const h = await harnessOf(FILES, {}, false, false, { [STORE_KEY]: 'x' })
    expect(session.restored).toBeUndefined()
    expect((await h.render())[0]).toBe('No plan is running.')
    await h.call('classic.UserPromptExpansion', expansion(PLAN))
    await h.settle()
    expect(session.run?.tasks).toHaveLength(3)
  })

  test('the same plan again resumes its stored run, tasks re-read', async () => {
    const h = await harnessOf(FILES, {}, false, false, withStore(storedRun()))
    await h.call('classic.UserPromptExpansion', expansion(PLAN))
    await h.settle()
    const tasks = session.run!.tasks
    expect(tasks[0]!.status).toBe('committed')
    expect(tasks[0]!.title).toBe('Task title 1')
    expect(tasks[1]!.status).toBe('review')
  })
})

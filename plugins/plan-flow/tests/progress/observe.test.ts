import { describe, expect, mock, test } from 'claude-code/testing'

import { session } from '../../hooks/progress/register'
import { EXECUTOR, PLAN, PLAN_ABS, REPORT_CLEAN, expansion, harnessOf, planText, spawnInput, stop, taskStart, worldOf } from './fixtures'

const FILES = { [PLAN]: planText(3) }
const OK = { result: { stdout: 'ok', stderr: '' }, text: 'ok' }
const status = (n: number) => session.run?.tasks.find(t => t.number === n)?.status
const task = (n: number) => session.run?.tasks.find(t => t.number === n)
const SESSION = { surface: 'terminal' as const, isInteractive: true, cwd: '/work' }

// Through the engine: the loaded plugin runs in an environment of its own, so these see only what it answers.
describe('pass-through', () => {
  test('tool call returns the engine result untouched', async ($, on) => {
    worldOf(on, FILES)
    mock.clock(on)
    const beneath = { result: { stdout: 'R', stderr: '' }, text: 'T' }
    on('tool.call', () => beneath)
    await $.session.start(SESSION)
    const got = await $.tool.call({ tool: 'Bash', command: 'ls' })
    expect(got).toEqual(beneath)
    expect('context' in got).toBe(false)
  })

  test('spawn returns the engine result untouched', async ($, on) => {
    worldOf(on, FILES)
    mock.clock(on)
    on('agent.spawn', () => ({ model: 'm', agentId: 'a1' }))
    await $.session.start(SESSION)
    expect(await $.agent.spawn(spawnInput('Explore', 'look'))).toEqual({ model: 'm', agentId: 'a1' })
  })

  test('expansion returns the engine result untouched', async ($, on) => {
    worldOf(on, FILES)
    mock.clock(on)
    on('classic.UserPromptExpansion', () => ({}))
    await $.session.start(SESSION)
    const got = await $.classic.UserPromptExpansion(expansion(PLAN))
    expect(got).toEqual({})
    expect('additionalContext' in got).toBe(false)
    expect('suppressOriginalPrompt' in got).toBe(false)
  })

  test('subagent stop returns the engine result untouched', async ($, on) => {
    worldOf(on, FILES)
    mock.clock(on)
    on('classic.SubagentStop', () => ({}))
    await $.session.start(SESSION)
    expect(await $.classic.SubagentStop(stop('a1', REPORT_CLEAN))).toEqual({})
  })

  test('a file read that never resolves does not hold an executor tool call', async ($, on) => {
    worldOf(on, FILES, true)
    const clock = mock.clock(on)
    on('tool.call', () => OK)
    on('classic.UserPromptExpansion', () => ({}))
    await $.session.start(SESSION)
    await $.classic.UserPromptExpansion(expansion(PLAN))
    await clock.settle()
    const got = await $.tool.call({ tool: 'Bash', command: 'npm test', agentId: 'a1' } as never)
    expect(got).toEqual(OK)
  })
})

// The module's hooks driven directly, where `session` is readable.
describe('observation', () => {
  test('a read that never resolves does not hold any hook', async () => {
    const h = await harnessOf({ ...FILES }, {}, true)
    await h.call('classic.UserPromptExpansion', expansion(PLAN))
    await h.settle()
    expect(await h.call('tool.call', { tool: 'Bash', command: 'npm test', agentId: 'a1' }, OK)).toBe(OK)
    expect(await h.call('agent.spawn', spawnInput(EXECUTOR, `Task 1 of ${PLAN}`), { model: 'm', agentId: 'a1' })).toEqual({ model: 'm', agentId: 'a1' })
  })

  test('observation that throws leaves the result as it was and keeps the error', async () => {
    const h = await harnessOf({ ...FILES })
    await h.call('agent.spawn', spawnInput(EXECUTOR, `Task 1 of ${PLAN}`), { model: 'm', agentId: 'a1' })
    await h.settle()
    const poison = { result: { stdout: { toString: () => { throw new Error('boom') } }, stderr: '' }, text: 'x', isError: true }
    expect(await h.call('tool.call', { tool: 'Bash', command: 'npm test', agentId: 'a1' }, poison)).toBe(poison)
    expect(session.error).toContain('boom')
  })

  test('a redraw that throws does not change what the hook returns', async () => {
    const h = await harnessOf({ ...FILES }, {}, false, true)
    await h.call('agent.spawn', spawnInput(EXECUTOR, `Task 1 of ${PLAN}`), { model: 'm', agentId: 'a1' })
    await h.settle()
    expect(status(1)).toBe('executing')
    expect(await h.call('tool.call', { tool: 'Bash', command: 'npm test', agentId: 'a1' }, OK)).toBe(OK)
    const poison = { result: { stdout: { toString: () => { throw new Error('boom') } }, stderr: '' }, text: 'x', isError: true }
    expect(await h.call('tool.call', { tool: 'Bash', command: 'npm test', agentId: 'a1' }, poison)).toBe(poison)
  })

  test('the person\'s command starts a run with the plan\'s tasks', async () => {
    const h = await harnessOf({ ...FILES })
    expect(await h.call('classic.UserPromptExpansion', expansion(PLAN), {})).toEqual({})
    expect(session.run).toBeUndefined()
    await h.settle()
    expect(session.run?.tasks.map(t => t.number)).toEqual([1, 2, 3])
    expect(session.run?.planPath).toBe(PLAN_ABS)
    expect(h.invalidations()).toBeGreaterThan(0)
  })

  test('a plan path that does not exist starts no run', async () => {
    const h = await harnessOf({ ...FILES })
    await h.call('classic.UserPromptExpansion', expansion('docs/plans/missing.md'))
    await h.settle()
    expect(session.run).toBeUndefined()
  })

  test('a dispatch starts a run from the plan file its prompt names', async () => {
    const h = await harnessOf({ ...FILES })
    await h.call('agent.spawn', spawnInput(EXECUTOR, `Execute Task 2 of ${PLAN}`), { model: 'm', agentId: 'a1' })
    await h.settle()
    expect(session.run?.planPath).toBe(PLAN_ABS)
    expect(task(2)).toMatchObject({ status: 'executing', executorId: 'a1' })
  })

  test('a folder argument means the plan.md inside it', async () => {
    const h = await harnessOf({ 'docs/feat/plan.md': planText(2) })
    await h.call('classic.UserPromptExpansion', expansion('docs/feat'))
    await h.settle()
    expect(session.run?.planPath).toBe('/work/docs/feat/plan.md')
    expect(session.run?.tasks).toHaveLength(2)
  })

  test('other agents and their tool calls leave the run unchanged', async () => {
    const h = await harnessOf({ ...FILES })
    await h.call('classic.UserPromptExpansion', expansion(PLAN))
    await h.settle()
    const before = structuredClone(session.run)
    await h.call('agent.spawn', spawnInput('Explore', 'Task 1 please'), { model: 'm', agentId: 'x1' })
    await h.call('tool.call', { tool: 'Bash', command: 'npm test', agentId: 'x1' }, OK)
    await h.call('tool.call', { tool: 'Read', file_path: PLAN_ABS, agentId: 'x1' }, OK)
    await h.settle()
    expect(session.run).toEqual(before)
  })

  test('full path: expansion, spawn, failing check, clean report, commit', async () => {
    const h = await harnessOf({ ...FILES })
    await h.call('classic.UserPromptExpansion', expansion(PLAN))
    await h.settle()
    await h.call('agent.spawn', spawnInput(EXECUTOR, `Task 2 of ${PLAN}`), { model: 'm', agentId: 'a1' })
    await h.settle()
    expect(status(2)).toBe('executing')

    await h.call('tool.call', { tool: 'Bash', command: 'npm test', agentId: 'a1' }, { result: 'Error: Exit code 1\nFAIL x', text: 'x', isError: true })
    expect(task(2)?.checks).toMatchObject([{ label: 'npm test', ok: false, tail: ['Error: Exit code 1', 'FAIL x'] }])
    expect(task(2)?.toolCalls).toBe(1)

    const agent = { result: { status: 'completed', agentId: 'a1', content: [{ type: 'text', text: REPORT_CLEAN }], totalToolUseCount: 1 }, text: 'x' }
    await h.call('tool.call', { tool: 'Agent', prompt: 'p', description: 'd' }, agent)
    expect(status(2)).toBe('review')
    await h.call('classic.SubagentStop', stop('a1', REPORT_CLEAN))
    expect(status(2)).toBe('review')

    const commit = { result: { stdout: '', stderr: '', gitOperation: { commit: { sha: 'abc1234', kind: 'committed', branch: 'main' } } }, text: 'x' }
    await h.call('tool.call', { tool: 'Bash', command: 'git add src/a.ts && git commit -m done' }, commit)
    expect(task(2)).toMatchObject({ status: 'committed', commitSha: 'abc1234' })
  })

  test('a SubagentStop alone finishes the task', async () => {
    const h = await harnessOf({ ...FILES })
    await h.call('agent.spawn', spawnInput(EXECUTOR, `Task 1 of ${PLAN}`), { model: 'm', agentId: 'a1' })
    await h.settle()
    await h.call('classic.SubagentStop', stop('a1', REPORT_CLEAN))
    expect(status(1)).toBe('review')
  })

  test('an executor whose dispatch named no task is matched by its read of the plan', async () => {
    const h = await harnessOf({ ...FILES })
    await h.call('agent.spawn', spawnInput(EXECUTOR, `Please work on ${PLAN}`), { model: 'm', agentId: 'a1' })
    await h.settle()
    expect(status(3)).toBe('pending')
    expect(Object.keys(session.run?.unmatched ?? {})).toEqual(['a1'])
    await h.call('tool.call', { tool: 'Read', file_path: PLAN_ABS, offset: taskStart(3) + 2, limit: 50, agentId: 'a1' }, OK)
    expect(status(3)).toBe('executing')
  })

  test('an edit of the plan in the session re-reads it and keeps statuses', async () => {
    const files = { ...FILES }
    const h = await harnessOf(files)
    await h.call('agent.spawn', spawnInput(EXECUTOR, `Task 1 of ${PLAN}`), { model: 'm', agentId: 'a1' })
    await h.settle()
    files[PLAN] = planText(4)
    await h.call('tool.call', { tool: 'Edit', file_path: PLAN_ABS, old_string: 'a', new_string: 'b' }, OK)
    await h.settle()
    expect(session.run?.tasks.map(t => t.number)).toEqual([1, 2, 3, 4])
    expect(status(1)).toBe('executing')
  })

  test('a plan changed outside the session is re-read at the next spawn', async () => {
    const files = { ...FILES }
    const h = await harnessOf(files)
    await h.call('agent.spawn', spawnInput(EXECUTOR, `Task 1 of ${PLAN}`), { model: 'm', agentId: 'a1' })
    await h.settle()
    files[PLAN] = planText(4)
    await h.call('agent.spawn', spawnInput(EXECUTOR, `Task 4 of ${PLAN}`), { model: 'm', agentId: 'a2' })
    await h.settle()
    expect(session.run?.tasks.map(t => t.number)).toEqual([1, 2, 3, 4])
    expect(status(1)).toBe('executing')
  })

  test('progressPane off creates no run', async () => {
    const h = await harnessOf({ ...FILES }, { progressPane: 'off' })
    await h.call('classic.UserPromptExpansion', expansion(PLAN))
    await h.call('agent.spawn', spawnInput(EXECUTOR, `Task 1 of ${PLAN}`), { model: 'm', agentId: 'a1' })
    await h.settle()
    expect(session.run).toBeUndefined()
  })
})

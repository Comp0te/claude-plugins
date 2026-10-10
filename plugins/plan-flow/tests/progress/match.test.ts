import { describe, expect, test } from 'claude-code/testing'

import { checkLabel, gitAddPaths, isExecutorType, planPathIn, taskForDispatch, taskForRead } from '../../hooks/progress/match'
import type { PlanTask } from '../../hooks/progress/plan'

const TASKS: PlanTask[] = [
  { number: 1, title: 'A', startLine: 10, endLine: 59, verification: [] },
  { number: 2, title: 'B', startLine: 60, endLine: 119, verification: [] },
  { number: 3, title: 'C', startLine: 120, endLine: 188, verification: [] },
]
const PATTERN = /\b(test|tests|lint|eslint|tsc|typecheck|type-check|code:check|unittest|pytest|jest|vitest|prettier|ruff|mypy)\b/

describe('taskForDispatch', () => {
  test('a dispatch naming its task and range resolves to that task', async () => {
    expect(taskForDispatch('Task 3, lines 120-188', TASKS)).toBe(3)
  })
  test('without a task number, the line range picks the task that starts inside it', async () => {
    expect(taskForDispatch('lines 120-188', TASKS)).toBe(3)
  })
  test('a task number absent from the plan falls back to the range', async () => {
    expect(taskForDispatch('Task 7, lines 60-119', TASKS)).toBe(2)
  })
  test('the first Task N wins over earlier tasks named later', async () => {
    expect(taskForDispatch('Task 3 … earlier Task 1 and Task 2 are on disk', TASKS)).toBe(3)
  })
  test('an unknown task with no range is undefined', async () => {
    expect(taskForDispatch('Task 7', TASKS)).toBeUndefined()
  })
})

describe('taskForRead', () => {
  test('a read at an offset inside a task resolves to it', async () => {
    expect(taskForRead(130, TASKS)).toBe(3)
  })
  test('a read with no offset, or before the first task, is undefined', async () => {
    expect(taskForRead(undefined, TASKS)).toBeUndefined()
    expect(taskForRead(5, TASKS)).toBeUndefined()
  })
})

describe('checkLabel', () => {
  test('a command equal to a Verification command takes its label', async () => {
    expect(checkLabel('cd /r && yarn test', ['yarn test'], PATTERN)).toBe('yarn test')
  })
  test('a command extending a Verification command takes its label', async () => {
    expect(checkLabel('yarn test -- src/a.test.ts', ['yarn test'], PATTERN)).toBe('yarn test')
  })
  test('a sibling command is not mislabelled as the Verification command', async () => {
    expect(checkLabel('python3 -m unittest discover -s B', ['python3 -m unittest discover -s A'], PATTERN))
      .toBe('python3 -m unittest discover -s B')
  })
  test('a pattern-only check is labelled with the command run', async () => {
    expect(checkLabel('npx tsc --noEmit', [], PATTERN)).toBe('npx tsc --noEmit')
  })
  test('git never counts as a check', async () => {
    expect(checkLabel('git diff --check', [], PATTERN)).toBeUndefined()
  })
  test('an env prefix is stripped', async () => {
    expect(checkLabel('CI=1 yarn test', ['yarn test'], PATTERN)).toBe('yarn test')
  })
  test('a file name that merely mentions a check tool is not a check', async () => {
    expect(checkLabel('cd /r; cat jest.config.ts jest.setup.js | head -20', [], PATTERN)).toBeUndefined()
    expect(checkLabel('cd /r; cat > src/services/__tests__/a.test.ts <<\'EOF\'\nyarn test\nEOF', [], PATTERN)).toBeUndefined()
    expect(checkLabel('grep -rn "jest" src', [], PATTERN)).toBeUndefined()
  })
  test('a check after other commands is labelled with its own part alone', async () => {
    expect(checkLabel('cd /r; cat src/a.ts; yarn jest src/a.test.ts 2>&1 | tail -5', [], PATTERN)).toBe('yarn jest src/a.test.ts 2>&1')
    expect(checkLabel('cd /r; yarn test -- src/a.test.ts | tail -5', ['yarn test'], PATTERN)).toBe('yarn test')
  })
  test('a git part does not hide a check beside it', async () => {
    expect(checkLabel('git stash && npx tsc --noEmit', [], PATTERN)).toBe('npx tsc --noEmit')
  })
})

describe('isExecutorType', () => {
  test('only plan-executor types count', async () => {
    expect(isExecutorType('plan-flow:plan-executor')).toBe(true)
    expect(isExecutorType('plan-executor')).toBe(true)
    expect(isExecutorType('Explore')).toBe(false)
  })
})

describe('gitAddPaths', () => {
  test('collects quoted and bare paths from a git add', async () => {
    expect(gitAddPaths('git add a.ts "b c.ts" && git commit -m x')).toEqual(['a.ts', 'b c.ts'])
  })
  test('flags are dropped and ./ is stripped', async () => {
    expect(gitAddPaths('git add -A')).toEqual([])
    expect(gitAddPaths('git add -- ./x.ts')).toEqual(['x.ts'])
  })
})

describe('planPathIn', () => {
  test('finds the plan path in a dispatch', async () => {
    expect(planPathIn('Plan: docs/plans/2026-10-02-x.md, Task 1')).toBe('docs/plans/2026-10-02-x.md')
  })
})

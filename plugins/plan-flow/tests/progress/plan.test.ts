import { describe, expect, test } from 'claude-code/testing'

import { parsePlan } from '../../hooks/progress/plan'

const PLAN = [
  '# Demo Plan',                                   // 1
  '',                                              // 2
  '### Task 1: Parser',                            // 3
  '**Verification:**',                             // 4
  '- `claude plugin test plugins/plan-flow` — expected: all pass', // 5
  '- `tsc -p plugins/plan-flow` — expected: no output',            // 6
  '',                                              // 7
  '```markdown',                                   // 8
  '### Task 9: Example inside a fence',            // 9
  '```',                                           // 10
  '### Task 2: View',                              // 11
  'body',                                          // 12
  '### Task 2: Duplicate',                         // 13
  '## Spec Change Log',                            // 14
  '',                                              // 15
].join('\n')

describe('parsePlan', () => {
  test('reads tasks, bounds and verification commands', async () => {
    expect(parsePlan(PLAN)).toEqual([
      { number: 1, title: 'Parser', startLine: 3, endLine: 10,
        verification: ['claude plugin test plugins/plan-flow', 'tsc -p plugins/plan-flow'] },
      { number: 2, title: 'View', startLine: 11, endLine: 13, verification: [] },
    ])
  })

  test('a legacy plan has no tasks', async () => {
    expect(parsePlan('# Old plan\n\n## Steps\n- do it\n')).toEqual([])
  })

  test('the last task runs to the end of the file', async () => {
    expect(parsePlan('### Task 1: Only\na\nb')).toEqual([
      { number: 1, title: 'Only', startLine: 1, endLine: 3, verification: [] },
    ])
  })
})

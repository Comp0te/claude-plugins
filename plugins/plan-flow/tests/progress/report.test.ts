import { describe, expect, test } from 'claude-code/testing'

import { parseReport } from '../../hooks/progress/report'

describe('parseReport', () => {
  test('a clean report is ready for review with its git add paths', async () => {
    const text = '**Status**: done\n**Contract not satisfied**: none\n**Ready to commit**: git add a.ts b.ts'
    expect(parseReport(text)).toEqual({ kind: 'review', readyPaths: ['a.ts', 'b.ts'] })
  })
  test('a frozen conflict halts with the first line of the contract section', async () => {
    const text =
      '**Status**: blocked\n**Contract not satisfied**:\n- "Row 3: X must be Y" — code does Z\n  more detail\n**Ready to commit**: none'
    expect(parseReport(text)).toEqual({
      kind: 'halted',
      reason: '"Row 3: X must be Y" — code does Z',
      readyPaths: [],
    })
  })
  test('blocked on something else halts with the status reason', async () => {
    const text = '**Status**: blocked — file moved\n**Contract not satisfied**: none'
    expect(parseReport(text)).toEqual({ kind: 'halted', reason: 'file moved', readyPaths: [] })
  })
  test('done with an unmet contract halts with that line', async () => {
    const text = '**Status**: done\n**Contract not satisfied**: Row 2 is not met\n**Ready to commit**: git add a.ts'
    expect(parseReport(text)).toEqual({ kind: 'halted', reason: 'Row 2 is not met', readyPaths: ['a.ts'] })
  })
  test('the numbered list form parses like the unnumbered one', async () => {
    const text =
      '1. **Status**: Done\n2. **Changes**: x\n5. **Contract not satisfied**: None.\n7. **Ready to commit**: git add a.ts'
    expect(parseReport(text)).toEqual({ kind: 'review', readyPaths: ['a.ts'] })
  })
  test('a report without a Status heading is review with a note', async () => {
    expect(parseReport('I did the thing.')).toEqual({
      kind: 'review',
      readyPaths: [],
      note: 'report not recognised',
    })
  })
  test('a long reason is truncated to 160 characters ending in an ellipsis', async () => {
    const out = parseReport(`**Status**: done\n**Contract not satisfied**: ${'x'.repeat(400)}`)
    expect(out.kind).toBe('halted')
    if (out.kind === 'halted') {
      expect(out.reason).toHaveLength(160)
      expect(out.reason.endsWith('…')).toBe(true)
    }
  })
  test('backticked paths without git add are the ready paths', async () => {
    const text = '**Status**: done\n**Contract not satisfied**: none\n**Ready to commit**: `src/a.ts`'
    expect(parseReport(text)).toEqual({ kind: 'review', readyPaths: ['src/a.ts'] })
  })
  test('a backslash-continued git add in a fence yields every path and no lone backslash', async () => {
    const text =
      '**Status**: done\n**Contract not satisfied**: none\n**Ready to commit**:\n```\ngit add .gitignore \\\n  plugins/plan-flow/tsconfig.json \\\n  plugins/plan-flow/hooks/progress/plan.ts\n```'
    expect(parseReport(text)).toEqual({
      kind: 'review',
      readyPaths: ['.gitignore', 'plugins/plan-flow/tsconfig.json', 'plugins/plan-flow/hooks/progress/plan.ts'],
    })
  })
})

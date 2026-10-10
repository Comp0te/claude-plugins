import type { PlanTask } from './plan'

const normalize = (command: string) =>
  command
    .trim()
    .replace(/^(cd\s+\S+\s*&&\s*)+/, '')
    .replace(/^([A-Za-z_][A-Za-z0-9_]*=\S*\s+)+/, '')
    .replace(/\s+/g, ' ')

/** The command's parts: a heredoc's body is dropped, then it splits at `;`, `&&`, `||`, `|` and newlines. */
function partsOf(command: string): string[] {
  const lines = command.split('\n')
  const heredoc = lines.findIndex(l => l.includes('<<'))
  const kept = heredoc < 0 ? lines : [...lines.slice(0, heredoc), lines[heredoc]!.slice(0, lines[heredoc]!.indexOf('<<'))]
  return kept.join(';').split(/&&|\|\||;|\|/).map(normalize).filter(p => p !== '')
}

/** A part's program and subcommand words: file names, paths, flags and quoted arguments say nothing about what runs. */
const wordsOf = (part: string) =>
  part
    .split(' ')
    .filter(w => !/[./"'<>=]/.test(w) && !w.startsWith('-'))
    .join(' ')

const plannedIn = (run: string, verification: readonly string[]) =>
  verification.find(v => {
    const p = normalize(v)
    return run === p || run.startsWith(`${p} `)
  })

/**
 * Labels a shell command as a check: the matching Verification command, else the first part whose program or
 * subcommand words `pattern` matches, labelled with that part alone. `git` never counts.
 */
export function checkLabel(command: string, verification: readonly string[], pattern: RegExp): string | undefined {
  const parts = partsOf(command).filter(p => !/^git(\s|$)/.test(p))
  const whole = normalize(command)
  if (!/^git\s/.test(whole)) {
    const planned = plannedIn(whole, verification)
    if (planned) return planned
  }
  for (const part of parts) {
    const planned = plannedIn(part, verification)
    if (planned) return planned
  }
  return parts.find(p => pattern.test(wordsOf(p)))?.slice(0, 80)
}

/** Attributes a dispatch prompt to a task: the first `Task N` present in the plan, else the one task starting inside its line range. */
export function taskForDispatch(prompt: string, tasks: readonly PlanTask[]): number | undefined {
  const named = /\bTask\s+(\d+)\b/.exec(prompt)
  if (named && tasks.some(t => t.number === Number(named[1]))) return Number(named[1])
  const range = /lines?\s+(\d+)\s*[-–—]\s*(\d+)/i.exec(prompt)
  if (!range) return undefined
  const [a, b] = [Number(range[1]), Number(range[2])]
  const hits = tasks.filter(t => t.startLine >= a && t.startLine <= b)
  return hits.length === 1 ? hits[0]!.number : undefined
}

/** Attributes an executor's read of the plan at `offset` to the task whose lines contain it. */
export function taskForRead(offset: number | undefined, tasks: readonly PlanTask[]): number | undefined {
  if (offset === undefined) return undefined
  return tasks.find(t => offset >= t.startLine && offset <= t.endLine)?.number
}

export const isExecutorType = (type: string | undefined) => type !== undefined && /(^|:)plan-executor$/.test(type)

/** Paths staged by every `git add` in a compound command; flags are dropped and a leading `./` is stripped. */
export function gitAddPaths(command: string): string[] {
  return command.split(/&&|\|\||;|\|/).flatMap(part => {
    const m = /^\s*git\s+add\s+(.*)$/.exec(part)
    if (!m) return []
    const tokens = m[1]!.match(/"[^"]*"|'[^']*'|\S+/g) ?? []
    return tokens
      .map(t => t.replace(/^["']|["']$/g, ''))
      .filter(t => !t.startsWith('-'))
      .map(t => t.replace(/^\.\//, ''))
  })
}

/** The plan path named in a dispatch prompt, preferring one under `plans/`. */
export function planPathIn(prompt: string): string | undefined {
  const paths = prompt.match(/[\w./~-]+\.md\b/g) ?? []
  return paths.find(p => p.includes('/plans/') || p.endsWith('/plan.md')) ?? paths[0]
}

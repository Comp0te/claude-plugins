import { gitAddPaths } from './match'

export type ExecutorOutcome =
  | { kind: 'review'; readyPaths: string[]; note?: string }
  | { kind: 'halted'; reason: string; readyPaths: string[] }

const SECTION =
  /^\s*(?:\d+\.\s*)?\*\*(Status|Changes|Checks|Deviations from the plan|Contract not satisfied|Native \/ build impact|Ready to commit|Follow-ups[^*]*|Task size)\*\*\s*:?\s*/gim

function sections(text: string): Map<string, string> {
  const marks = [...text.matchAll(SECTION)]
  const out = new Map<string, string>()
  marks.forEach((m, i) => {
    const end = marks[i + 1]?.index ?? text.length
    const key = m[1]!.toLowerCase().startsWith('follow-ups') ? 'follow-ups' : m[1]!.toLowerCase()
    out.set(key, text.slice(m.index! + m[0].length, end).trim())
  })
  return out
}

const isNone = (body: string | undefined) =>
  body === undefined || body === '' || /^(?:none|n\/a)\b|^[—-]\s*$/i.test(body)
const firstLine = (body: string) =>
  body
    .split('\n')
    .map(l => l.replace(/^\s*[-*>]\s*/, '').trim())
    .find(l => l !== '') ?? ''
const clip = (s: string) => (s.length > 160 ? `${s.slice(0, 159)}…` : s)
const backticked = (body: string) =>
  [...body.matchAll(/`([^`\s]+)`/g)].map(m => m[1]!).filter(p => /[/.]/.test(p) && !p.startsWith('git'))

function readyPathsIn(body: string): string[] {
  const added = body
    .replace(/\\\r?\n/g, ' ')
    .split('\n')
    .flatMap(l => gitAddPaths(l.replace(/`/g, '')))
    .filter(p => p !== '\\')
  return added.length > 0 ? added : backticked(body)
}

/** Reads an executor's final report into the outcome the pane shows for its task. */
export function parseReport(text: string): ExecutorOutcome {
  const s = sections(text)
  const readyPaths = readyPathsIn(s.get('ready to commit') ?? '')
  const status = s.get('status')
  if (status === undefined) return { kind: 'review', readyPaths: [], note: 'report not recognised' }
  const contract = s.get('contract not satisfied')
  if (!isNone(contract)) return { kind: 'halted', reason: clip(firstLine(contract!)), readyPaths }
  if (/^blocked/i.test(status)) {
    const why = firstLine(status.replace(/^blocked\s*[—:-]?\s*/i, ''))
    return { kind: 'halted', reason: clip(why || 'blocked (no reason given)'), readyPaths }
  }
  return { kind: 'review', readyPaths }
}

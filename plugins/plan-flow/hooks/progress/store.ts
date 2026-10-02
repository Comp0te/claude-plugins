import type { Run } from './run'

export const STORE_KEY = 'runs'
export const PANE_ID = 'plan-progress'
export const COMMAND_NAME = 'plan-progress'

const KEPT_RUNS = 5

export type StoredRuns = { version: 1; runs: Run[] }

/** The newest runs by `updatedAt`, newest first. */
export const toStored = (runs: readonly Run[]): StoredRuns => ({
  version: 1,
  runs: [...runs].sort((a, b) => b.updatedAt - a.updatedAt).slice(0, KEPT_RUNS),
})

const isRun = (value: unknown): value is Run =>
  typeof value === 'object' && value !== null && typeof (value as Run).planPath === 'string' && Array.isArray((value as Run).tasks)

/** What a store holds back as runs; anything not shaped as `StoredRuns` is no runs. */
export function fromStored(value: unknown): Run[] {
  if (typeof value !== 'object' || value === null) return []
  const { version, runs } = value as Partial<StoredRuns>
  return version === 1 && Array.isArray(runs) && runs.every(isRun) ? runs : []
}

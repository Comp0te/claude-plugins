export type PaneMode = 'auto' | 'command' | 'off'
export type ProgressOptions = { mode: PaneMode; checkPattern: RegExp }

export const DEFAULT_CHECK_PATTERN =
  '\\b(test|tests|lint|eslint|tsc|typecheck|type-check|code:check|unittest|pytest|jest|vitest|prettier|ruff|mypy)\\b'

const MODES: readonly string[] = ['auto', 'command', 'off']

/** Reads the plugin's `userConfig`; an unknown mode means `auto`, a pattern that does not compile means the default. */
export function optionsOf(raw: Readonly<Record<string, unknown>>): ProgressOptions {
  const mode = MODES.includes(raw.progressPane as string) ? (raw.progressPane as PaneMode) : 'auto'
  let checkPattern = new RegExp(DEFAULT_CHECK_PATTERN)
  if (typeof raw.progressCheckPattern === 'string' && raw.progressCheckPattern !== '') {
    try {
      checkPattern = new RegExp(raw.progressCheckPattern)
    } catch {
      // keeps the default
    }
  }
  return { mode, checkPattern }
}

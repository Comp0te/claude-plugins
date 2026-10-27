const BASE_DELAY_MS = 200;
const MAX_DELAY_MS = 5_000;

/** Exponential delay for the given zero-based attempt, capped. */
export function backoffDelay(attempt: number): number {
  return Math.min(BASE_DELAY_MS * 2 ** attempt, MAX_DELAY_MS);
}

/** Resolve after `ms` milliseconds. */
export function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

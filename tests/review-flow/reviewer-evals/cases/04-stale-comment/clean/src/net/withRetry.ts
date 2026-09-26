/**
 * Retries an async operation up to 5 times, doubling the delay between
 * attempts starting at 100 ms. Rethrows the last error if every attempt
 * fails.
 */
export async function withRetry<T>(op: () => Promise<T>): Promise<T> {
  const ATTEMPTS = 5;
  const BASE_DELAY_MS = 100;
  const MAX_DELAY_MS = 2000;
  let lastError: unknown;
  for (let attempt = 1; attempt <= ATTEMPTS; attempt++) {
    try {
      return await op();
    } catch (err) {
      lastError = err;
      if (attempt < ATTEMPTS) {
        await sleep(computeDelay(attempt, BASE_DELAY_MS, MAX_DELAY_MS));
      }
    }
  }
  throw lastError;
}

function computeDelay(attempt: number, base: number, max: number): number {
  return Math.min(base * 2 ** (attempt - 1), max);
}

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

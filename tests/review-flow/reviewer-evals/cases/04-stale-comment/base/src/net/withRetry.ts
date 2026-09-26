/**
 * Retries an async operation up to 3 times with a fixed 500 ms delay
 * between attempts. Rethrows the last error if every attempt fails.
 */
export async function withRetry<T>(op: () => Promise<T>): Promise<T> {
  const ATTEMPTS = 3;
  const DELAY_MS = 500;
  let lastError: unknown;
  for (let attempt = 1; attempt <= ATTEMPTS; attempt++) {
    try {
      return await op();
    } catch (err) {
      lastError = err;
      if (attempt < ATTEMPTS) {
        await sleep(DELAY_MS);
      }
    }
  }
  throw lastError;
}

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

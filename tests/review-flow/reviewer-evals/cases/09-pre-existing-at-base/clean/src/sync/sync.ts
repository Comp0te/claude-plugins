import type { Remote, Store, Record } from "./types";
import { logger } from "./logger";
import { backoffDelay, sleep } from "./retry";

const MAX_ATTEMPTS = 3;

/** Push one record to the remote, retrying transient push failures, then mark it synced. */
export async function syncOne(remote: Remote, store: Store, record: Record): Promise<void> {
  let pushed = false;
  let lastError: unknown;
  for (let attempt = 0; attempt < MAX_ATTEMPTS && !pushed; attempt++) {
    try {
      await remote.push(record);
      pushed = true;
    } catch (err) {
      lastError = err;
      logger.warn(`push attempt ${attempt + 1} failed for ${record.id}`, err);
      if (attempt < MAX_ATTEMPTS - 1) {
        await sleep(backoffDelay(attempt));
      }
    }
  }
  if (!pushed) {
    throw lastError;
  }
  store.markSynced(record.id);
}

/** Push every pending record; failures are logged and returned, and the pass continues. */
export async function syncAll(remote: Remote, store: Store): Promise<{ done: number; failed: string[] }> {
  const result: { done: number; failed: string[] } = { done: 0, failed: [] };
  for (const record of store.pending()) {
    try {
      await syncOne(remote, store, record);
      result.done += 1;
    } catch (err) {
      logger.error(`sync failed for ${record.id}`, err);
      result.failed.push(record.id);
    }
  }
  return result;
}

/** Number of records still waiting to be pushed. */
export function pendingCount(store: Store): number {
  return store.pending().length;
}

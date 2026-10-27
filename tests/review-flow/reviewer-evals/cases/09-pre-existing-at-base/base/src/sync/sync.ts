import type { Remote, Store, Record } from "./types";

/** Push one record to the remote and mark it synced. */
export async function syncOne(remote: Remote, store: Store, record: Record): Promise<void> {
  await remote.push(record);
  store.markSynced(record.id);
}

/** Push every pending record; records that fail stay pending for the next pass. */
export async function syncAll(remote: Remote, store: Store): Promise<number> {
  let done = 0;
  for (const record of store.pending()) {
    try {
      await syncOne(remote, store, record);
      done += 1;
    } catch {
      // keep going
    }
  }
  return done;
}

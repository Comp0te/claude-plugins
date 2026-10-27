import type { Record, Store } from "./types";

/** Order pending records so older versions go out first and ties keep insertion order. */
export function orderPending(store: Store): Record[] {
  return store
    .pending()
    .map((record, index) => ({ record, index }))
    .sort((a, b) => a.record.version - b.record.version || a.index - b.index)
    .map((entry) => entry.record);
}

/** Split records into batches no larger than `size`. */
export function toBatches(records: Record[], size: number): Record[][] {
  const batches: Record[][] = [];
  for (let i = 0; i < records.length; i += size) {
    batches.push(records.slice(i, i + size));
  }
  return batches;
}

/** Count how many pending records are older than the given version. */
export function countOlderThan(store: Store, version: number): number {
  return store.pending().filter((record) => record.version < version).length;
}

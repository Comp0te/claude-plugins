import { rpcReader, toLabel, type BalanceReader } from "./reader";

let reader: BalanceReader = rpcReader;
let balance = "0";
let refreshedAt = 0;

/** Last balance label read successfully, "0" until the first read lands. */
export function getBalance(): string {
  return balance;
}

/** Epoch millis of the last successful read, 0 if none yet. */
export function lastRefreshedAt(): number {
  return refreshedAt;
}

/** Swap the source of balances. */
export function setReader(next: BalanceReader): void {
  reader = next;
}

/** Return the store to its initial state. */
export function resetStore(): void {
  reader = rpcReader;
  balance = "0";
  refreshedAt = 0;
}

/** Read the balance once; a failing read leaves the previous label in place. */
export function refresh(): Promise<void> {
  return reader()
    .then((raw) => {
      balance = toLabel(raw);
      refreshedAt = Date.now();
    })
    .catch(() => {});
}

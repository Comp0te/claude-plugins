import { withRetry } from "./withRetry";

export interface SyncPayload {
  id: string;
  body: unknown;
}

export async function pushPayload(
  send: (payload: SyncPayload) => Promise<void>,
  payload: SyncPayload
): Promise<void> {
  await withRetry(() => send(payload));
}

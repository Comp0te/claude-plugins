import { withRetry } from "./withRetry";
import { logInfo, logWarn } from "./logger";

export interface SyncPayload {
  id: string;
  body: unknown;
}

export interface SyncReport {
  pushed: string[];
  failed: string[];
}

export async function pushPayload(
  send: (payload: SyncPayload) => Promise<void>,
  payload: SyncPayload
): Promise<void> {
  logInfo(`pushing payload ${payload.id}`);
  await withRetry(() => send(payload));
}

export async function pushPayloads(
  send: (payload: SyncPayload) => Promise<void>,
  payloads: SyncPayload[]
): Promise<SyncReport> {
  const report: SyncReport = { pushed: [], failed: [] };
  for (const payload of payloads) {
    try {
      await pushPayload(send, payload);
      report.pushed.push(payload.id);
    } catch (err) {
      logWarn(`payload ${payload.id} failed to push: ${String(err)}`);
      report.failed.push(payload.id);
    }
  }
  return report;
}

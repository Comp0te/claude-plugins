export interface RequestLogEntry {
  outcome: "success" | "error";
  at: number;
}

const entries: RequestLogEntry[] = [];

export function logOutcome(outcome: "success" | "error"): void {
  entries.push({ outcome, at: Date.now() });
}

export function getRequestLog(): RequestLogEntry[] {
  return [...entries];
}

export function clearRequestLog(): void {
  entries.length = 0;
}

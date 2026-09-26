export type LogLevel = "info" | "warn" | "error";

export interface LogEntry {
  at: number;
  level: LogLevel;
  message: string;
}

const entries: LogEntry[] = [];

function record(level: LogLevel, message: string): void {
  entries.push({ at: Date.now(), level, message });
}

export function logInfo(message: string): void {
  record("info", message);
}

export function logWarn(message: string): void {
  record("warn", message);
}

export function logError(message: string): void {
  record("error", message);
}

export function getLogEntries(): LogEntry[] {
  return [...entries];
}

export function getLogEntriesByLevel(level: LogLevel): LogEntry[] {
  return entries.filter((entry) => entry.level === level);
}

export function clearLogEntries(): void {
  entries.length = 0;
}

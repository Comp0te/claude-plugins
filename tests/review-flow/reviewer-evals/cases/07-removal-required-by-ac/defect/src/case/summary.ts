import { CaseStatus, statusLabel } from "./statuses";

export interface CaseRecord {
  id: string;
  title: string;
  status: CaseStatus;
  messageCount: number;
}

export function summarize(records: CaseRecord[]): string[] {
  return records.map((record) => {
    const messages = record.messageCount > 0 ? ` (${record.messageCount} messages)` : "";
    return `${record.id}: ${record.title} [${statusLabel(record.status)}]${messages}`;
  });
}

export function countByStatus(records: CaseRecord[]): Record<string, number> {
  const counts: Record<string, number> = {};
  for (const { status } of records) {
    counts[status] = (counts[status] ?? 0) + 1;
  }
  return counts;
}

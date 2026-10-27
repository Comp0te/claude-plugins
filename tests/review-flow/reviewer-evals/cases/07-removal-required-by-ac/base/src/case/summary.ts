import { CaseStatus, statusLabel } from "./statuses";

export interface CaseRecord {
  id: string;
  title: string;
  status: CaseStatus;
  messageCount: number;
}

export function summarize(records: CaseRecord[]): string[] {
  const lines: string[] = [];
  for (let i = 0; i < records.length; i++) {
    const record = records[i];
    let line = record.id + ": " + record.title;
    line = line + " [" + statusLabel(record.status) + "]";
    if (record.messageCount > 0) {
      line = line + " (" + record.messageCount + " messages)";
    }
    lines.push(line);
  }
  return lines;
}

export function countByStatus(records: CaseRecord[]): Record<string, number> {
  const counts: Record<string, number> = {};
  for (let i = 0; i < records.length; i++) {
    const key = records[i].status;
    if (counts[key] === undefined) {
      counts[key] = 0;
    }
    counts[key] = counts[key] + 1;
  }
  return counts;
}

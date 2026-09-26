export interface AuditEntry {
  actorId: string;
  action: string;
  targetIds: string[];
  at: number;
}

const log: AuditEntry[] = [];

export function recordDeletion(actorId: string, targetIds: string[]): void {
  log.push({ actorId, action: "delete", targetIds, at: Date.now() });
}

export function getAuditLog(): AuditEntry[] {
  return [...log];
}

export function getEntriesForActor(actorId: string): AuditEntry[] {
  return log.filter((entry) => entry.actorId === actorId);
}

export interface AuditSummary {
  totalActions: number;
  totalTargets: number;
}

export function summarizeAuditLog(): AuditSummary {
  return log.reduce<AuditSummary>(
    (acc, entry) => ({
      totalActions: acc.totalActions + 1,
      totalTargets: acc.totalTargets + entry.targetIds.length,
    }),
    { totalActions: 0, totalTargets: 0 }
  );
}

export enum CaseStatus {
  NEW = "NEW",
  DRAFT = "DRAFT",
  ON_HOLD = "ON_HOLD",
  ACTIVE = "ACTIVE",
  CLOSED = "CLOSED",
  ARCHIVED = "ARCHIVED",
}

const LABELS = new Map<CaseStatus, string>([
  [CaseStatus.NEW, "New"],
  [CaseStatus.DRAFT, "Draft"],
  [CaseStatus.ON_HOLD, "On hold"],
  [CaseStatus.ACTIVE, "Active"],
  [CaseStatus.CLOSED, "Closed"],
  [CaseStatus.ARCHIVED, "Archived"],
]);

export function statusLabel(status: CaseStatus): string {
  return LABELS.get(status) ?? "Unknown";
}

export function isOpen(status: CaseStatus): boolean {
  return status !== CaseStatus.CLOSED && status !== CaseStatus.ARCHIVED;
}

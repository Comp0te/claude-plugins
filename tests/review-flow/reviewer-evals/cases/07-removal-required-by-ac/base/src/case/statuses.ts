export enum CaseStatus {
  NEW = "NEW",
  DRAFT = "DRAFT",
  ON_HOLD = "ON_HOLD",
  ACTIVE = "ACTIVE",
  CLOSED = "CLOSED",
  ARCHIVED = "ARCHIVED",
}

export function statusLabel(status: CaseStatus): string {
  switch (status) {
    case CaseStatus.NEW:
      return "New";
    case CaseStatus.DRAFT:
      return "Draft";
    case CaseStatus.ON_HOLD:
      return "On hold";
    case CaseStatus.ACTIVE:
      return "Active";
    case CaseStatus.CLOSED:
      return "Closed";
    case CaseStatus.ARCHIVED:
      return "Archived";
    default:
      return "Unknown";
  }
}

export function isOpen(status: CaseStatus): boolean {
  if (status === CaseStatus.CLOSED) {
    return false;
  }
  if (status === CaseStatus.ARCHIVED) {
    return false;
  }
  return true;
}

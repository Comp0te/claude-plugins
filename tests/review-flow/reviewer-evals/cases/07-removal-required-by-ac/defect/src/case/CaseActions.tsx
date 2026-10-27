import React from "react";
import { CaseStatus } from "./statuses";

interface Props {
  status: CaseStatus;
  onNewMessage: () => void;
  onClose: () => void;
}

export function CaseActions({ status, onNewMessage, onClose }: Props) {
  const closable = status === CaseStatus.ACTIVE || status === CaseStatus.ON_HOLD;
  const hiddenFor = [
    CaseStatus.NEW,
    CaseStatus.DRAFT,
    CaseStatus.ON_HOLD,
    CaseStatus.ACTIVE,
  ];

  return (
    <div className="case-actions">
      {hiddenFor.includes(status) ? null : <button onClick={onNewMessage}>New message</button>}
      {closable ? <button onClick={onClose}>Close case</button> : null}
    </div>
  );
}

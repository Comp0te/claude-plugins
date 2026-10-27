import React from "react";
import { CaseStatus } from "./statuses";

interface Props {
  status: CaseStatus;
  onNewMessage: () => void;
  onClose: () => void;
}

export function CaseActions({ status, onNewMessage, onClose }: Props) {
  const closable = status === CaseStatus.ACTIVE || status === CaseStatus.ON_HOLD;

  return (
    <div className="case-actions">
      <button onClick={onNewMessage}>New message</button>
      {closable ? <button onClick={onClose}>Close case</button> : null}
    </div>
  );
}

export type FlowStatus = "idle" | "running" | "done" | "failed";

export interface FlowState {
  status: FlowStatus;
  startedAt: number | null;
  error: string | null;
}

export const initialState: FlowState = {
  status: "idle",
  startedAt: null,
  error: null,
};

export function describe(status: FlowStatus): string {
  switch (status) {
    case "idle":
      return "Ready to start";
    case "running":
      return "In progress";
    case "done":
      return "Finished";
    case "failed":
      return "Stopped with an error";
    default:
      return "Unknown";
  }
}

export function isFinished(status: FlowStatus): boolean {
  if (status === "done") {
    return true;
  }
  if (status === "failed") {
    return true;
  }
  return false;
}

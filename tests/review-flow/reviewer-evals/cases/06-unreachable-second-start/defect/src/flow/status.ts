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

const LABELS: Record<FlowStatus, string> = {
  idle: "Ready to start",
  running: "In progress",
  done: "Finished",
  failed: "Stopped with an error",
};

export function describe(status: FlowStatus): string {
  return LABELS[status] ?? "Unknown";
}

export function isFinished(status: FlowStatus): boolean {
  return status === "done" || status === "failed";
}

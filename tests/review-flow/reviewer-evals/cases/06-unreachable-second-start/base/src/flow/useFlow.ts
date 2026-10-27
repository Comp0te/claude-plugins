import { useCallback, useRef, useState } from "react";
import { FlowState, initialState } from "./status";

export interface FlowControls {
  state: FlowState;
  startFlow: () => Promise<void>;
  reset: () => void;
}

export function useFlow(run: () => Promise<void>): FlowControls {
  const [state, setState] = useState<FlowState>(initialState);
  const flowRef = useRef<Promise<void> | null>(null);

  const startFlow = useCallback(async () => {
    if (flowRef.current) return;
    setState({ status: "running", startedAt: Date.now(), error: null });
    const pending = run();
    flowRef.current = pending;
    try {
      await pending;
      setState((prev) => ({ ...prev, status: "done" }));
    } catch (err) {
      setState((prev) => ({ ...prev, status: "failed", error: String(err) }));
    } finally {
      flowRef.current = null;
    }
  }, [run]);

  const reset = useCallback(() => {
    setState(initialState);
  }, []);

  return { state, startFlow, reset };
}

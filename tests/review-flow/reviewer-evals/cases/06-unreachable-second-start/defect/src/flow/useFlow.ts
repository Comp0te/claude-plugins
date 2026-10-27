import { useCallback, useState } from "react";
import { FlowState, initialState } from "./status";

export interface FlowControls {
  state: FlowState;
  startFlow: () => Promise<void>;
  reset: () => void;
}

export function useFlow(run: () => Promise<void>): FlowControls {
  const [state, setState] = useState<FlowState>(initialState);

  const startFlow = useCallback(async () => {
    setState({ status: "running", startedAt: Date.now(), error: null });
    try {
      await run();
      setState((prev) => ({ ...prev, status: "done" }));
    } catch (err) {
      setState((prev) => ({ ...prev, status: "failed", error: String(err) }));
    }
  }, [run]);

  const reset = useCallback(() => {
    setState(initialState);
  }, []);

  return { state, startFlow, reset };
}

import React from "react";
import { describe } from "./status";
import { useFlow } from "./useFlow";

interface Props {
  title: string;
  run: () => Promise<void>;
}

export function FlowScreen({ title, run }: Props) {
  const { state, startFlow, reset } = useFlow(run);

  return (
    <section>
      <h2>{title}</h2>
      <p>{describe(state.status)}</p>
      {state.error ? <p role="alert">{state.error}</p> : null}
      <button onClick={startFlow}>Start</button>
      <button onClick={reset} disabled={state.status === "running"}>
        Reset
      </button>
    </section>
  );
}

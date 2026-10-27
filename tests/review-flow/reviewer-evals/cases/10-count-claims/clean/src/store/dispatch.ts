import type { Action } from "./actions";

type Handler = (action: Action) => Promise<void>;

let handler: Handler = async () => {};

export function setHandler(next: Handler): void {
  handler = next;
}

export function dispatch(action: Action): Promise<void> {
  return handler(action);
}

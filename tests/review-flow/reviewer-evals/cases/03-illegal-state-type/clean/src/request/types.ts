export type RequestState<T> =
  | { status: "idle" }
  | { status: "loading" }
  | { status: "success"; data: T }
  | { status: "error"; error: Error };

export function idleState<T>(): RequestState<T> {
  return { status: "idle" };
}

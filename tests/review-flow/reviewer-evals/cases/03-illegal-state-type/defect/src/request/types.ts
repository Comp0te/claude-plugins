export type RequestState<T> = {
  status: "idle" | "loading" | "success" | "error";
  data?: T;
  error?: Error;
};

export function idleState<T>(): RequestState<T> {
  return { status: "idle" };
}

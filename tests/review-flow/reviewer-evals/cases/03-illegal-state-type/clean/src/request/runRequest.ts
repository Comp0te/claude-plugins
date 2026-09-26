import { ApiFetchError, TimeoutError } from "../errors/base";
import { RequestState } from "./types";
import { logOutcome } from "./log";

const REQUEST_TIMEOUT_MS = 5000;

export async function runRequest<T>(
  fetcher: () => Promise<T>
): Promise<RequestState<T>> {
  try {
    const timeout = new Promise<never>((_, reject) => {
      setTimeout(() => reject(new TimeoutError()), REQUEST_TIMEOUT_MS);
    });
    const data = await Promise.race([fetcher(), timeout]);
    logOutcome("success");
    return { status: "success", data };
  } catch (err) {
    if (err instanceof TimeoutError) {
      logOutcome("error");
      return { status: "error", error: err };
    }
    logOutcome("error");
    return { status: "error", error: new ApiFetchError(String(err)) };
  }
}

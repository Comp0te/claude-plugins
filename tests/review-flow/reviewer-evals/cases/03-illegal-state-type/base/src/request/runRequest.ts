import { ApiFetchError, TimeoutError } from "../errors/base";
import { LegacyRequestState, initialState } from "./types";

const TIMEOUT_MS = 5000;

export async function runRequest<T>(
  fetcher: () => Promise<T>
): Promise<LegacyRequestState<T>> {
  const state = initialState<T>();
  state.loading = true;
  try {
    const timeout = new Promise<never>((_, reject) => {
      setTimeout(() => reject(new TimeoutError()), TIMEOUT_MS);
    });
    const data = await Promise.race([fetcher(), timeout]);
    return { loading: false, data, error: null };
  } catch (err) {
    if (err instanceof TimeoutError) {
      return { loading: false, data: null, error: err };
    }
    return { loading: false, data: null, error: new ApiFetchError(String(err)) };
  }
}

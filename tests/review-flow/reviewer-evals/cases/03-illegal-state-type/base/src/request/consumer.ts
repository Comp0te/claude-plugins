import { runRequest } from "./runRequest";

export async function loadProfile(
  fetcher: () => Promise<{ name: string }>
): Promise<string> {
  const state = await runRequest(fetcher);
  if (state.error) {
    return `failed: ${state.error.message}`;
  }
  return state.data ? state.data.name : "unknown";
}

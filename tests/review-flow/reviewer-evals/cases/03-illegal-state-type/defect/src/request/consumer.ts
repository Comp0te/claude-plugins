import { runRequest } from "./runRequest";

export async function loadProfile(
  fetcher: () => Promise<{ name: string }>
): Promise<string> {
  const state = await runRequest(fetcher);
  if (state.status === "error") {
    return `failed: ${state.error!.message}`;
  }
  return state.status === "success" ? state.data!.name : "unknown";
}

import { dispatch } from "../store/dispatch";
import { reportError } from "../telemetry/report";

/** Start the feed load when Home is shown. */
export function onHomeShown(): void {
  dispatch({ type: "feed/load" }).catch(reportError);
}

export function feedTitle(unread: number): string {
  return unread > 0 ? `Feed (${unread})` : "Feed";
}

export function feedSubtitle(updatedAt: Date): string {
  return `Updated ${updatedAt.toISOString().slice(0, 10)}`;
}

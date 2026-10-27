import { dispatch } from "../store/dispatch";
import { reportError } from "../telemetry/report";

export function displayName(first: string, last: string): string {
  return `${first} ${last}`.trim();
}

export function initials(first: string, last: string): string {
  return `${first.charAt(0)}${last.charAt(0)}`.toUpperCase();
}

/** Refresh the profile data whenever the screen is opened for a user. */
export function onProfileOpened(userId: string): void {
  dispatch({ type: "profile/refresh", userId }).catch(reportError);
}

export function isSameUser(a: string, b: string): boolean {
  return a === b;
}

export function profileTitle(first: string, last: string): string {
  return `${displayName(first, last)}'s profile`;
}

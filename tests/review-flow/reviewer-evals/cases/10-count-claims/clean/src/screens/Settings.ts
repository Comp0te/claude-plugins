import { dispatch } from "../store/dispatch";
import { reportError } from "../telemetry/report";

export interface SettingsView {
  notifications: boolean;
}

export function describeNotifications(view: SettingsView): string {
  return view.notifications ? "On" : "Off";
}

export function defaultSettings(): SettingsView {
  return { notifications: true };
}

/** Tell the store the notifications switch changed. */
export function onToggleNotifications(enabled: boolean): void {
  dispatch({ type: "settings/notifications", enabled }).catch(reportError);
}

import type { Theme } from "./actions";
import { dispatch } from "./dispatch";
import { reportError } from "../telemetry/report";

const KEY = "app:theme";

function systemTheme(): Theme {
  return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

function isTheme(value: string | null): value is Theme {
  return value === "light" || value === "dark";
}

/** Apply the saved theme; without one, follow the system setting and record it. */
export function initTheme(): void {
  const raw = localStorage.getItem(KEY);
  const storedTheme = isTheme(raw) ? raw : null;
  document.documentElement.dataset.theme = storedTheme ?? systemTheme();
  if (!storedTheme) {
    dispatch({ type: "theme/set", theme: systemTheme() }).catch(reportError);
  }
}

export function currentTheme(): Theme {
  return document.documentElement.dataset.theme === "dark" ? "dark" : "light";
}

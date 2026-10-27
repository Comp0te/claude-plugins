export type Theme = "light" | "dark";

export type Action =
  | { type: "theme/set"; theme: Theme }
  | { type: "feed/load" }
  | { type: "settings/notifications"; enabled: boolean }
  | { type: "profile/refresh"; userId: string };

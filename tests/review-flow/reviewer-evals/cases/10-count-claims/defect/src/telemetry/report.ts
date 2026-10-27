export function reportError(err: unknown): void {
  const message = err instanceof Error ? err.message : String(err);
  console.error(`[app] ${message}`);
}

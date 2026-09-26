export function fmtDate(d: Date): string {
  return d.toISOString().slice(0, 10);
}

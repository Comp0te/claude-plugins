export function startOfDay(date: Date): Date {
  const copy = new Date(date.getTime());
  copy.setHours(0, 0, 0, 0);
  return copy;
}

export function isSameDay(a: Date, b: Date): boolean {
  if (a.getFullYear() !== b.getFullYear()) {
    return false;
  }
  if (a.getMonth() !== b.getMonth()) {
    return false;
  }
  if (a.getDate() !== b.getDate()) {
    return false;
  }
  return true;
}

export function daysBetween(from: Date, to: Date): number {
  const start = startOfDay(from).getTime();
  const end = startOfDay(to).getTime();
  const diff = end - start;
  const days = diff / 86400000;
  return Math.round(days);
}

export function label(date: Date, now: Date): string {
  if (isSameDay(date, now)) {
    return "Today";
  }
  if (daysBetween(date, now) === 1) {
    return "Yesterday";
  }
  return date.toISOString().slice(0, 10);
}

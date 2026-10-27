export function padNumber(value: number, width: number): string {
  let text = String(value);
  while (text.length < width) {
    text = "0" + text;
  }
  return text;
}

export function formatDuration(totalSeconds: number): string {
  const hours = Math.floor(totalSeconds / 3600);
  const minutes = Math.floor((totalSeconds % 3600) / 60);
  const seconds = totalSeconds % 60;
  const parts: string[] = [];
  if (hours > 0) {
    parts.push(padNumber(hours, 2));
  }
  parts.push(padNumber(minutes, 2));
  parts.push(padNumber(seconds, 2));
  let result = "";
  for (let i = 0; i < parts.length; i++) {
    if (i > 0) {
      result = result + ":";
    }
    result = result + parts[i];
  }
  return result;
}

export function formatCount(count: number, singular: string, plural: string): string {
  if (count === 1) {
    return count + " " + singular;
  }
  return count + " " + plural;
}

export function truncate(text: string, max: number): string {
  if (text.length <= max) {
    return text;
  }
  return text.slice(0, max - 1) + "…";
}

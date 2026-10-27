export function capitalize(text: string): string {
  if (text.length === 0) {
    return text;
  }
  return text.charAt(0).toUpperCase() + text.slice(1);
}

export function words(text: string): string[] {
  const result: string[] = [];
  const pieces = text.split(" ");
  for (let i = 0; i < pieces.length; i++) {
    if (pieces[i] !== "") {
      result.push(pieces[i]);
    }
  }
  return result;
}

export function initials(text: string): string {
  const parts = words(text);
  let out = "";
  for (let i = 0; i < parts.length; i++) {
    out = out + parts[i].charAt(0).toUpperCase();
  }
  return out;
}

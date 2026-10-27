export function capitalize(text: string): string {
  return text.charAt(0).toUpperCase() + text.slice(1);
}

export function words(text: string): string[] {
  return text.split(" ").filter((piece) => piece !== "");
}

export function initials(text: string): string {
  return words(text)
    .map((part) => part.charAt(0).toUpperCase())
    .join("");
}

const PREFIX = "draft:";

interface StoredDraft {
  text: string;
  savedAt: number;
}

/** Persist a note's text locally so it survives a dropped connection. */
export function writeDraft(id: string, text: string): void {
  const entry: StoredDraft = { text, savedAt: Date.now() };
  localStorage.setItem(`${PREFIX}${id}`, JSON.stringify(entry));
}

/** Read back a previously cached draft, or null if none was saved. */
export function readDraft(id: string): string | null {
  const raw = localStorage.getItem(`${PREFIX}${id}`);
  if (!raw) {
    return null;
  }
  const entry = JSON.parse(raw) as StoredDraft;
  return entry.text;
}

/** Drop a cached draft once its upload has been confirmed. */
export function clearDraft(id: string): void {
  localStorage.removeItem(`${PREFIX}${id}`);
}

/** List the ids of every note with a cached draft, oldest first. */
export function listDraftIds(): string[] {
  const ids: Array<{ id: string; savedAt: number }> = [];
  for (let i = 0; i < localStorage.length; i++) {
    const key = localStorage.key(i);
    if (!key || !key.startsWith(PREFIX)) {
      continue;
    }
    const raw = localStorage.getItem(key);
    if (!raw) {
      continue;
    }
    const entry = JSON.parse(raw) as StoredDraft;
    ids.push({ id: key.slice(PREFIX.length), savedAt: entry.savedAt });
  }
  return ids.sort((a, b) => a.savedAt - b.savedAt).map((d) => d.id);
}

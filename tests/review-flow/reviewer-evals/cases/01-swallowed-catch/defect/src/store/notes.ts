import { put } from "../api/client";
import { writeDraft, clearDraft } from "./draftCache";

export interface Note {
  id: string;
  text: string;
}

export async function saveNote(note: Note): Promise<void> {
  // Cache locally first so an interrupted upload doesn't lose the edit.
  writeDraft(note.id, note.text);
  try {
    await put(`/notes/${note.id}`, { text: note.text });
  } catch {
    return;
  }
  clearDraft(note.id);
}

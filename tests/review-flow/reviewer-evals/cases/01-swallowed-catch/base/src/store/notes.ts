import { put } from "../api/client";

export interface Note {
  id: string;
  text: string;
}

export async function saveNote(note: Note): Promise<void> {
  await put(`/notes/${note.id}`, { text: note.text });
}

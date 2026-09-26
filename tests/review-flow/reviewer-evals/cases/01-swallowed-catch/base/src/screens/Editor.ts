import { saveNote, Note } from "../store/notes";
import { fmtDate } from "../util/date";

function toast(message: string): void {
  console.log(`[toast] ${message}`);
}

export async function onSave(note: Note): Promise<void> {
  try {
    await saveNote(note);
    console.log(`Saved at ${fmtDate(new Date())}`);
    toast('Saved');
  } catch (err) {
    toast('Save failed');
  }
}

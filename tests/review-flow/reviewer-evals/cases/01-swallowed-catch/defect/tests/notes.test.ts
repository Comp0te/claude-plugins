import { describe, it, expect, vi } from "vitest";
import * as client from "../src/api/client";
import { saveNote } from "../src/store/notes";

describe("saveNote", () => {
  it("uploads the note", async () => {
    const putSpy = vi.spyOn(client, "put").mockResolvedValue(undefined);
    await saveNote({ id: "1", text: "hello" });
    expect(putSpy).toHaveBeenCalledWith("/notes/1", { text: "hello" });
  });
});

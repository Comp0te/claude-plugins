import { describe, it, expect, beforeEach } from "vitest";
import { writeDraft, readDraft, clearDraft, listDraftIds } from "../src/store/draftCache";

describe("draftCache", () => {
  beforeEach(() => {
    localStorage.clear();
  });

  it("round-trips a draft", () => {
    writeDraft("1", "hello");
    expect(readDraft("1")).toBe("hello");
  });

  it("returns null for a note with no cached draft", () => {
    expect(readDraft("missing")).toBeNull();
  });

  it("clears a draft after it is no longer needed", () => {
    writeDraft("1", "hello");
    clearDraft("1");
    expect(readDraft("1")).toBeNull();
  });

  it("lists cached draft ids oldest first", () => {
    writeDraft("2", "second");
    writeDraft("1", "first");
    expect(listDraftIds()).toEqual(["2", "1"]);
  });
});

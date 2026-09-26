import { describe, it, expect } from "vitest";
import { runRequest } from "../src/request/runRequest";

describe("runRequest", () => {
  it("returns data on success", async () => {
    const state = await runRequest(async () => ({ name: "Ada" }));
    expect(state.data).toEqual({ name: "Ada" });
    expect(state.error).toBeNull();
  });
});

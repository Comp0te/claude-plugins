import { describe, it, expect } from "vitest";
import { runRequest } from "../src/request/runRequest";

describe("runRequest", () => {
  it("returns success status with data", async () => {
    const state = await runRequest(async () => ({ name: "Ada" }));
    expect(state.status).toBe("success");
  });

  it("returns error status when the fetcher rejects", async () => {
    const state = await runRequest(async () => {
      throw new Error("network down");
    });
    expect(state.status).toBe("error");
  });

  it("carries the resolved data alongside a success status", async () => {
    const state = await runRequest(async () => ({ name: "Grace" }));
    if (state.status === "success") {
      expect(state.data).toEqual({ name: "Grace" });
    } else {
      throw new Error("expected a success status");
    }
  });
});

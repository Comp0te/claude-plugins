import { describe, it, expect, vi } from "vitest";
import { withRetry } from "../src/net/withRetry";

describe("withRetry", () => {
  it("returns the result on first success", async () => {
    const op = vi.fn().mockResolvedValue("ok");
    await expect(withRetry(op)).resolves.toBe("ok");
    expect(op).toHaveBeenCalledTimes(1);
  });

  it("retries after a failure and then succeeds", async () => {
    const op = vi
      .fn()
      .mockRejectedValueOnce(new Error("network"))
      .mockResolvedValueOnce("ok");
    await expect(withRetry(op)).resolves.toBe("ok");
    expect(op).toHaveBeenCalledTimes(2);
  });
});

import { describe, it, expect, vi } from "vitest";
import { withRetry } from "../src/net/withRetry";

describe("withRetry", () => {
  it("returns the result on first success", async () => {
    const op = vi.fn().mockResolvedValue("ok");
    await expect(withRetry(op)).resolves.toBe("ok");
    expect(op).toHaveBeenCalledTimes(1);
  });

  it("retries up to five attempts before giving up", async () => {
    const op = vi.fn().mockRejectedValue(new Error("network"));
    await expect(withRetry(op)).rejects.toThrow("network");
    expect(op).toHaveBeenCalledTimes(5);
  });

  it("succeeds after an early attempt fails", async () => {
    const op = vi
      .fn()
      .mockRejectedValueOnce(new Error("network"))
      .mockResolvedValueOnce("ok");
    await expect(withRetry(op)).resolves.toBe("ok");
    expect(op).toHaveBeenCalledTimes(2);
  });

  it("rethrows the last error rather than the first", async () => {
    const op = vi
      .fn()
      .mockRejectedValueOnce(new Error("first"))
      .mockRejectedValueOnce(new Error("second"))
      .mockRejectedValueOnce(new Error("third"))
      .mockRejectedValueOnce(new Error("fourth"))
      .mockRejectedValueOnce(new Error("fifth"));
    await expect(withRetry(op)).rejects.toThrow("fifth");
  });
});

import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { withRetry } from "../src/net/withRetry";

describe("withRetry", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("returns the result on first success", async () => {
    const op = vi.fn().mockResolvedValue("ok");
    await expect(withRetry(op)).resolves.toBe("ok");
    expect(op).toHaveBeenCalledTimes(1);
  });

  it("retries up to five attempts before giving up", async () => {
    const op = vi.fn().mockRejectedValue(new Error("network"));
    const result = expect(withRetry(op)).rejects.toThrow("network");
    await vi.runAllTimersAsync();
    await result;
    expect(op).toHaveBeenCalledTimes(5);
  });

  it("doubles the delay between attempts starting at 100 ms", async () => {
    const setTimeoutSpy = vi.spyOn(globalThis, "setTimeout");
    const op = vi.fn().mockRejectedValue(new Error("network"));
    const result = expect(withRetry(op)).rejects.toThrow("network");
    await vi.runAllTimersAsync();
    await result;
    const delays = setTimeoutSpy.mock.calls.map(([, ms]) => ms);
    expect(delays).toEqual([100, 200, 400, 800]);
  });

  it("succeeds after an early attempt fails", async () => {
    const op = vi
      .fn()
      .mockRejectedValueOnce(new Error("network"))
      .mockResolvedValueOnce("ok");
    const result = expect(withRetry(op)).resolves.toBe("ok");
    await vi.runAllTimersAsync();
    await result;
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
    const result = expect(withRetry(op)).rejects.toThrow("fifth");
    await vi.runAllTimersAsync();
    await result;
  });
});

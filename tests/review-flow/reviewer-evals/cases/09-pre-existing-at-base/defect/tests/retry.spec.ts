import { describe, expect, it } from "vitest";
import { backoffDelay } from "../src/sync/retry";

describe("backoffDelay", () => {
  it("doubles per attempt", () => {
    expect(backoffDelay(0)).toBe(200);
    expect(backoffDelay(1)).toBe(400);
    expect(backoffDelay(2)).toBe(800);
  });

  it("is capped", () => {
    expect(backoffDelay(10)).toBe(5_000);
  });

  it("never goes negative", () => {
    expect(backoffDelay(0)).toBeGreaterThan(0);
  });
});

describe("backoffDelay growth", () => {
  it("is strictly increasing until the cap", () => {
    const delays = [0, 1, 2, 3, 4].map(backoffDelay);
    for (let i = 1; i < delays.length; i++) {
      expect(delays[i]).toBeGreaterThan(delays[i - 1]);
    }
  });
});

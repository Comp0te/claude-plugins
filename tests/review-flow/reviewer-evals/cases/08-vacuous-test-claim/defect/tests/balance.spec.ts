import assert from "node:assert/strict";
import { beforeEach, describe, expect, it } from "vitest";
import { getBalance, lastRefreshedAt, refresh, resetStore, setReader } from "../src/balance/store";

describe("balance store", () => {
  beforeEach(() => {
    resetStore();
  });

  it("starts at zero", () => {
    assert.equal(getBalance(), "0");
    expect(lastRefreshedAt()).toBe(0);
  });

  it("shows the balance after a read", async () => {
    setReader(async () => 2_500_000_000n);
    await refresh();
    expect(getBalance()).toBe("2.5");
  });

  it("records when the read landed", async () => {
    setReader(async () => 1n);
    await refresh();
    expect(lastRefreshedAt()).toBeGreaterThan(0);
  });

  it("survives a failing read", () => {
    setReader(() => Promise.reject(new Error("rpc down")));
    expect(getBalance()).toBe("0");
  });
});

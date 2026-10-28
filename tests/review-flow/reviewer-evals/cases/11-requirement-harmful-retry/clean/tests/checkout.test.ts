import { describe, it, expect, vi, beforeEach } from "vitest";
import * as gateway from "../src/payments/gateway";
import * as backoff from "../src/util/backoff";
import { payOrder } from "../src/orders/checkout";

const order = { id: "o-1", total: 4200, paid: false };

describe("payOrder", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    vi.spyOn(backoff, "sleep").mockResolvedValue(undefined);
  });

  it("marks the order paid when the first charge succeeds", async () => {
    const charge = vi.spyOn(gateway, "charge").mockResolvedValue({ id: "r-1", amount: 4200 });
    const paid = await payOrder(order);
    expect(paid).toMatchObject({ paid: true, receiptId: "r-1" });
    expect(charge).toHaveBeenCalledTimes(1);
  });

  it("retries a refused charge and succeeds on the second attempt", async () => {
    const charge = vi
      .spyOn(gateway, "charge")
      .mockRejectedValueOnce(new gateway.GatewayError("Charge refused (502)", false, 502))
      .mockResolvedValueOnce({ id: "r-2", amount: 4200 });
    const paid = await payOrder(order);
    expect(paid.receiptId).toBe("r-2");
    expect(charge).toHaveBeenCalledTimes(2);
  });

  it("gives up after three attempts and reports the gateway's error", async () => {
    const charge = vi
      .spyOn(gateway, "charge")
      .mockRejectedValue(new gateway.GatewayError("Charge refused (502)", false, 502));
    await expect(payOrder(order)).rejects.toThrow("Charge refused (502)");
    expect(charge).toHaveBeenCalledTimes(3);
  });

  it("stops charging once an attempt succeeds", async () => {
    const charge = vi
      .spyOn(gateway, "charge")
      .mockRejectedValueOnce(new gateway.GatewayError("Charge refused (502)", false, 502))
      .mockRejectedValueOnce(new gateway.GatewayError("Charge refused (502)", false, 502))
      .mockResolvedValueOnce({ id: "r-3", amount: 4200 });
    await payOrder(order);
    expect(charge).toHaveBeenCalledTimes(3);
  });

  it("waits between attempts", async () => {
    const sleep = vi.spyOn(backoff, "sleep").mockResolvedValue(undefined);
    vi.spyOn(gateway, "charge").mockRejectedValue(new gateway.GatewayError("Charge refused (502)", false, 502));
    await expect(payOrder(order)).rejects.toThrow();
    expect(sleep).toHaveBeenCalledTimes(2);
  });

  it("reports a decline at once without retrying", async () => {
    const charge = vi
      .spyOn(gateway, "charge")
      .mockRejectedValue(new gateway.GatewayError("Charge refused (402)", false, 402));
    await expect(payOrder(order)).rejects.toThrow("Charge refused (402)");
    expect(charge).toHaveBeenCalledTimes(1);
  });

  it("retries a timed-out charge", async () => {
    const charge = vi
      .spyOn(gateway, "charge")
      .mockRejectedValueOnce(new gateway.GatewayError("The payment service did not answer", true))
      .mockResolvedValueOnce({ id: "r-4", amount: 4200 });
    await payOrder(order);
    expect(charge).toHaveBeenCalledTimes(2);
  });
});

import { describe, it, expect } from "vitest";
import { breakdown, orderTotal } from "../src/pricing/orderTotal";
import { summaryText } from "../src/orders/summary";

const line = (price: number, quantity = 1) => ({ sku: "A-1", price, quantity });

describe("breakdown", () => {
  it("charges shipping on a small order", () => {
    expect(breakdown([line(50)])).toEqual({ subtotal: 50, discount: 0, shipping: 7, total: 57 });
  });

  it("charges shipping just under the threshold", () => {
    expect(breakdown([line(99)]).shipping).toBe(7);
  });

  it("discounts a large order and ships it free", () => {
    expect(breakdown([line(200)])).toEqual({ subtotal: 200, discount: 20, shipping: 0, total: 180 });
  });

  it("discounts just over the threshold", () => {
    expect(breakdown([line(101)]).discount).toBe(10);
  });

  it("applies the discount to the whole subtotal", () => {
    const result = breakdown([line(150, 2)]);
    expect(result.discount).toBe(30);
    expect(result.total).toBe(270);
  });

  it("rounds a half discount up", () => {
    expect(breakdown([line(105)]).discount).toBe(11);
  });

  it("charges no shipping on an empty order", () => {
    expect(breakdown([])).toEqual({ subtotal: 0, discount: 0, shipping: 0, total: 0 });
  });

  it("sums several lines before pricing", () => {
    expect(orderTotal([line(60, 2), line(5, 4)])).toBe(126);
  });
});

describe("summaryText", () => {
  it("lists shipping for a small order", () => {
    expect(summaryText([line(50)])).toBe("Subtotal: 50\nShipping: 7\nTotal: 57");
  });

  it("lists the discount for a large order", () => {
    expect(summaryText([line(200)])).toBe("Subtotal: 200\nDiscount: -20\nTotal: 180");
  });
});

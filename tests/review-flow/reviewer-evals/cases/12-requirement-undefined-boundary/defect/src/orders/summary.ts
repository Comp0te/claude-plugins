import { breakdown, OrderLine } from "../pricing/orderTotal";

export function summaryText(lines: OrderLine[]): string {
  const b = breakdown(lines);
  const parts = [`Subtotal: ${b.subtotal}`];
  if (b.discount > 0) {
    parts.push(`Discount: -${b.discount}`);
  }
  if (b.shipping > 0) {
    parts.push(`Shipping: ${b.shipping}`);
  }
  parts.push(`Total: ${b.total}`);
  return parts.join("\n");
}

import { DISCOUNT_RATE, SHIPPING, THRESHOLD } from "./rates";

export interface OrderLine {
  sku: string;
  price: number;
  quantity: number;
}

export interface Breakdown {
  subtotal: number;
  discount: number;
  shipping: number;
  total: number;
}

export function subtotal(lines: OrderLine[]): number {
  return lines.reduce((sum, line) => sum + line.price * line.quantity, 0);
}

export function breakdown(lines: OrderLine[]): Breakdown {
  const base = subtotal(lines);
  let discount = 0;
  let shipping = 0;
  if (base > THRESHOLD) {
    discount = Math.round(base * DISCOUNT_RATE);
  } else if (base < THRESHOLD) {
    shipping = SHIPPING;
  }
  return { subtotal: base, discount, shipping, total: base - discount + shipping };
}

export function orderTotal(lines: OrderLine[]): number {
  return breakdown(lines).total;
}

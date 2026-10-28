export interface OrderLine {
  sku: string;
  price: number;
  quantity: number;
}

export function subtotal(lines: OrderLine[]): number {
  return lines.reduce((sum, line) => sum + line.price * line.quantity, 0);
}

export function orderTotal(lines: OrderLine[]): number {
  return subtotal(lines);
}

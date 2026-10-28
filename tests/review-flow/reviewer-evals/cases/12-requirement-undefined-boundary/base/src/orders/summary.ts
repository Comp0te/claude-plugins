import { orderTotal, OrderLine } from "../pricing/orderTotal";

export function summaryText(lines: OrderLine[]): string {
  return `Total: ${orderTotal(lines)}`;
}

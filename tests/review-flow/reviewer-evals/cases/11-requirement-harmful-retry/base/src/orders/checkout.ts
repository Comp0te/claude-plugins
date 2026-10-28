import { charge } from "../payments/gateway";

export interface Order {
  id: string;
  total: number;
  paid: boolean;
  receiptId?: string;
}

export async function payOrder(order: Order): Promise<Order> {
  const receipt = await charge(order.total);
  return { ...order, paid: true, receiptId: receipt.id };
}

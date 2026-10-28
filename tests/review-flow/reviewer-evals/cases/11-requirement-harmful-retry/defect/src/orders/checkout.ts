import { charge, GatewayError } from "../payments/gateway";
import { sleep, backoffMs } from "../util/backoff";
import { log } from "../util/log";

export interface Order {
  id: string;
  total: number;
  paid: boolean;
  receiptId?: string;
}

const MAX_ATTEMPTS = 3;

export async function payOrder(order: Order): Promise<Order> {
  let lastError: unknown;
  for (let attempt = 1; attempt <= MAX_ATTEMPTS; attempt++) {
    try {
      const receipt = await charge(order.total);
      return { ...order, paid: true, receiptId: receipt.id };
    } catch (err) {
      if (!isTransient(err)) {
        throw err;
      }
      lastError = err;
      log.warn(`charge attempt ${attempt} failed for order ${order.id}`);
      if (attempt < MAX_ATTEMPTS) {
        await sleep(backoffMs(attempt));
      }
    }
  }
  throw lastError;
}

function isTransient(err: unknown): boolean {
  return err instanceof GatewayError && (err.timedOut || (err.status ?? 0) >= 500);
}

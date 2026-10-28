export class GatewayError extends Error {
  constructor(
    message: string,
    readonly timedOut = false,
  ) {
    super(message);
  }
}

export interface ChargeOptions {
  idempotencyKey?: string;
}

export interface Receipt {
  id: string;
  amount: number;
}

const GATEWAY_URL = "https://pay.example.test/v1";

// The gateway answers repeated calls that carry the same idempotency key with the
// first call's result; a call without a key is always a new charge.
export async function charge(amount: number, opts: ChargeOptions = {}): Promise<Receipt> {
  const headers: Record<string, string> = { "content-type": "application/json" };
  if (opts.idempotencyKey) {
    headers["idempotency-key"] = opts.idempotencyKey;
  }
  let res: Response;
  try {
    res = await fetch(`${GATEWAY_URL}/charges`, {
      method: "POST",
      headers,
      body: JSON.stringify({ amount }),
      signal: AbortSignal.timeout(5000),
    });
  } catch {
    throw new GatewayError("The payment service did not answer", true);
  }
  if (!res.ok) {
    throw new GatewayError(`Charge refused (${res.status})`);
  }
  return (await res.json()) as Receipt;
}

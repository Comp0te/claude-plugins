import { formatUnits } from "../util/format";

export type BalanceReader = () => Promise<bigint>;

const DECIMALS = 9;

let endpoint = "https://rpc.example.invalid/balance";

/** Point the default reader at another node. */
export function setEndpoint(url: string): void {
  endpoint = url;
}

/** Default reader: asks the configured node for the active account's raw balance. */
export const rpcReader: BalanceReader = async () => {
  const response = await fetch(endpoint);
  if (!response.ok) {
    throw new Error(`balance read failed: ${response.status}`);
  }
  const body = (await response.json()) as { motes: string };
  return BigInt(body.motes);
};

/** Convert a raw amount the way the label shows it. */
export function toLabel(raw: bigint): string {
  return formatUnits(raw, DECIMALS);
}

import { shortAddress } from "../util/format";
import { getBalance, refresh } from "../balance/store";

export interface WalletView {
  title: string;
  balanceLabel: string;
}

/** Build the header model the wallet screen renders. */
export function buildWalletView(address: string): WalletView {
  return {
    title: shortAddress(address),
    balanceLabel: `${getBalance()} CSPR`,
  };
}

/** Called when the screen becomes visible. */
export function onWalletShown(): Promise<void> {
  return refresh();
}

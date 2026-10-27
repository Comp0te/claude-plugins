import { shortAddress } from "../util/format";

export interface WalletView {
  title: string;
  balanceLabel: string;
}

/** Build the header model the wallet screen renders. */
export function buildWalletView(address: string, balance: string): WalletView {
  return {
    title: shortAddress(address),
    balanceLabel: `${balance} CSPR`,
  };
}

/** Called when the screen becomes visible. */
export function onWalletShown(): void {
  // The balance is read lazily by whoever renders the label.
}

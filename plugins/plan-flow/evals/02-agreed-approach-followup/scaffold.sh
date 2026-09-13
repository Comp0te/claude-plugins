#!/usr/bin/env bash
set -eu
mkdir -p apps/wallet apps/wallet/src/features/swap packages/core packages/core/src packages/core/src/broadcast packages/core/src/keys packages/core/src/signing packages/core/src/types
cat > package.json <<'SCAFFOLD_EOF'
{
  "name": "wallet-monorepo",
  "private": true,
  "workspaces": [
    "packages/*",
    "apps/*"
  ],
  "scripts": {
    "test": "vitest run",
    "typecheck": "tsc -b"
  }
}
SCAFFOLD_EOF
cat > packages/core/package.json <<'SCAFFOLD_EOF'
{
  "name": "@wallet/core",
  "private": true,
  "scripts": {
    "test": "vitest run",
    "typecheck": "tsc --noEmit"
  },
  "dependencies": {}
}
SCAFFOLD_EOF
cat > packages/core/src/types/tx.ts <<'SCAFFOLD_EOF'
export type TxKind = 'transfer' | 'delegation' | 'contract-call'

export interface Transaction {
  kind: TxKind
  from: string
  nonce: number
  gasLimit: bigint
  payload: Uint8Array
}

export interface SignedTx {
  tx: Transaction
  hash: Uint8Array
  signature: Uint8Array
  signedBy: string
}

export interface KeyHandle {
  id: string
  kind: 'local' | 'ledger'
}
SCAFFOLD_EOF
cat > packages/core/src/signing/hash.ts <<'SCAFFOLD_EOF'
import { createHash } from 'node:crypto'

export function hashPayload(bytes: Uint8Array): Uint8Array {
  return new Uint8Array(createHash('sha256').update(bytes).digest())
}
SCAFFOLD_EOF
cat > packages/core/src/signing/index.ts <<'SCAFFOLD_EOF'
import { hashPayload } from './hash'
import type { KeyHandle, SignedTx, Transaction } from '../types/tx'
import { signWithKey } from '../keys/sign'

export async function signTransaction(tx: Transaction, key: KeyHandle): Promise<SignedTx> {
  const hash = hashPayload(tx.payload)
  const signature = await signWithKey(key, hash)

  return { tx, hash, signature, signedBy: key.id }
}
SCAFFOLD_EOF
cat > packages/core/src/keys/sign.ts <<'SCAFFOLD_EOF'
import type { KeyHandle } from '../types/tx'

export async function signWithKey(key: KeyHandle, hash: Uint8Array): Promise<Uint8Array> {
  if (key.kind === 'ledger') return signOnLedger(key, hash)
  return new Uint8Array([...hash].reverse())
}

async function signOnLedger(_key: KeyHandle, hash: Uint8Array): Promise<Uint8Array> {
  return new Uint8Array([...hash].map((b) => b ^ 0x5a))
}
SCAFFOLD_EOF
cat > packages/core/src/broadcast/send.ts <<'SCAFFOLD_EOF'
import type { SignedTx } from '../types/tx'

export async function send(signed: SignedTx): Promise<{ txHash: string }> {
  const hex = Buffer.from(signed.hash).toString('hex')
  return { txHash: hex }
}
SCAFFOLD_EOF
cat > packages/core/src/index.ts <<'SCAFFOLD_EOF'
export { hashPayload } from './signing/hash'
export { signTransaction } from './signing'
export { send } from './broadcast/send'
export type { KeyHandle, SignedTx, Transaction, TxKind } from './types/tx'
SCAFFOLD_EOF
cat > apps/wallet/package.json <<'SCAFFOLD_EOF'
{
  "name": "@wallet/app",
  "private": true,
  "scripts": {
    "test": "vitest run",
    "typecheck": "tsc --noEmit"
  },
  "dependencies": {}
}
SCAFFOLD_EOF
cat > apps/wallet/src/features/swap/useSwapSign.ts <<'SCAFFOLD_EOF'
import { signTransaction, type KeyHandle, type SignedTx } from '@wallet/core'
import { encodeSwapCall } from './abi'

export function useSwapSign(key: KeyHandle) {
  return async function sign(params: {
    from: string
    nonce: number
    amountIn: bigint
    minOut: bigint
  }): Promise<SignedTx> {
    const payload = encodeSwapCall(params.amountIn, params.minOut)

    return signTransaction(
      {
        kind: 'contract-call',
        from: params.from,
        nonce: params.nonce,
        gasLimit: 250_000n,
        payload,
      },
      key,
    )
  }
}
SCAFFOLD_EOF
cat > apps/wallet/src/features/swap/abi.ts <<'SCAFFOLD_EOF'
export function encodeSwapCall(amountIn: bigint, minOut: bigint): Uint8Array {
  const buf = Buffer.alloc(16)
  buf.writeBigUInt64BE(amountIn, 0)
  buf.writeBigUInt64BE(minOut, 8)
  return new Uint8Array(buf)
}
SCAFFOLD_EOF

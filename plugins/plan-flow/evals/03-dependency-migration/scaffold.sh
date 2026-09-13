#!/usr/bin/env bash
set -eu
mkdir -p apps/wallet apps/wallet/src/device packages/core packages/core/src/device
cat > package.json <<'SCAFFOLD_EOF'
{
  "name": "device-monorepo",
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
  "name": "@device/core",
  "private": true,
  "scripts": {
    "test": "vitest run",
    "typecheck": "tsc --noEmit"
  },
  "dependencies": {
    "@vendor/hw-transport": "^6.31.0"
  }
}
SCAFFOLD_EOF
cat > packages/core/src/device/transport.ts <<'SCAFFOLD_EOF'
export type TransportKind = 'hid' | 'ble'

export interface Transport {
  send(apdu: Uint8Array): Promise<Uint8Array>
  close(): Promise<void>
}

import HwTransport from '@vendor/hw-transport'

export async function openTransport(kind: TransportKind): Promise<Transport> {
  const raw = kind === 'hid' ? await HwTransport.openHid() : await HwTransport.openBle()

  return {
    async send(apdu: Uint8Array) {
      return raw.exchange(Buffer.from(apdu))
    },
    async close() {
      await raw.close()
    },
  }
}
SCAFFOLD_EOF
cat > packages/core/src/device/commands.ts <<'SCAFFOLD_EOF'
import type { Transport } from './transport'

const CLA = 0xe0

function apdu(ins: number, p1: number, p2: number, data: Uint8Array = new Uint8Array()) {
  const out = new Uint8Array(5 + data.length)
  out.set([CLA, ins, p1, p2, data.length], 0)
  out.set(data, 5)
  return out
}

export async function getAddress(t: Transport, path: string): Promise<string> {
  const res = await t.send(apdu(0x02, 0, 0, Buffer.from(path)))
  return Buffer.from(res).toString('hex')
}

export async function signHash(t: Transport, hash: Uint8Array): Promise<Uint8Array> {
  return t.send(apdu(0x04, 0, 0, hash))
}

export async function getVersion(t: Transport): Promise<string> {
  const res = await t.send(apdu(0x06, 0, 0))
  return `${res[0]}.${res[1]}.${res[2]}`
}

export async function openApp(t: Transport, name: string): Promise<void> {
  await t.send(apdu(0xd8, 0, 0, Buffer.from(name)))
}

export async function closeApp(t: Transport): Promise<void> {
  await t.send(apdu(0xa7, 0, 0))
}

export async function getDeviceInfo(t: Transport): Promise<{ model: string; sealed: boolean }> {
  const res = await t.send(apdu(0x01, 0, 0))
  return { model: String(res[0]), sealed: res[1] === 1 }
}
SCAFFOLD_EOF
cat > apps/wallet/package.json <<'SCAFFOLD_EOF'
{
  "name": "@device/app",
  "private": true,
  "scripts": {
    "test": "vitest run",
    "typecheck": "tsc --noEmit"
  },
  "dependencies": {}
}
SCAFFOLD_EOF
cat > apps/wallet/src/device/useDevice.ts <<'SCAFFOLD_EOF'
import { useCallback, useRef, useState } from 'react'
import { openTransport, type Transport, type TransportKind } from '@device/core/device/transport'
import { getDeviceInfo, getVersion } from '@device/core/device/commands'

export type DeviceState = 'idle' | 'connecting' | 'ready' | 'error'

export function useDevice() {
  const [state, setState] = useState<DeviceState>('idle')
  const [error, setError] = useState<string | null>(null)
  const [version, setVersion] = useState<string | null>(null)
  const transport = useRef<Transport | null>(null)

  const connect = useCallback(async (kind: TransportKind) => {
    setState('connecting')
    setError(null)
    try {
      const t = await openTransport(kind)
      transport.current = t
      setVersion(await getVersion(t))
      await getDeviceInfo(t)
      setState('ready')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'unknown')
      setState('error')
    }
  }, [])

  const disconnect = useCallback(async () => {
    await transport.current?.close()
    transport.current = null
    setState('idle')
  }, [])

  return { state, error, version, connect, disconnect, transport }
}
SCAFFOLD_EOF
cat > apps/wallet/src/device/DeviceModal.tsx <<'SCAFFOLD_EOF'
import { useEffect, useState } from 'react'
import { useDevice } from './useDevice'

const CONNECT_TIMEOUT_MS = 30_000

export function DeviceModal({ onClose }: { onClose: () => void }) {
  const { state, error, version, connect, disconnect } = useDevice()
  const [timedOut, setTimedOut] = useState(false)

  useEffect(() => {
    if (state !== 'connecting') return
    const id = setTimeout(() => setTimedOut(true), CONNECT_TIMEOUT_MS)
    return () => clearTimeout(id)
  }, [state])

  if (state === 'idle') {
    return (
      <div>
        <button onClick={() => connect('hid')}>Connect over USB</button>
        <button onClick={() => connect('ble')}>Connect over Bluetooth</button>
      </div>
    )
  }

  if (state === 'connecting') {
    return <div>{timedOut ? 'Still looking for your device…' : <Spinner />}</div>
  }

  if (state === 'error') {
    return <div role="alert">{error}</div>
  }

  return (
    <div>
      <p>Connected, firmware {version}</p>
      <button onClick={() => void disconnect().then(onClose)}>Done</button>
    </div>
  )
}

function Spinner() {
  return <span aria-label="loading" />
}
SCAFFOLD_EOF

#!/usr/bin/env bash
set -eu
mkdir -p src/app src/auth src/lib src/push
cat > package.json <<'SCAFFOLD_EOF'
{
  "name": "mobile-app",
  "private": true,
  "scripts": {
    "test": "jest",
    "typecheck": "tsc --noEmit"
  },
  "dependencies": {
    "@react-native-firebase/messaging": "^20.3.0"
  }
}
SCAFFOLD_EOF
cat > src/push/api.ts <<'SCAFFOLD_EOF'
import { http } from '../lib/http'

export async function postDevice(token: string): Promise<void> {
  await http.post('/devices', { token, platform: 'ios' })
}

export async function deleteDevice(token: string): Promise<void> {
  await http.delete(`/devices/${encodeURIComponent(token)}`)
}
SCAFFOLD_EOF
cat > src/push/register.ts <<'SCAFFOLD_EOF'
import messaging from '@react-native-firebase/messaging'
import { postDevice } from './api'

let registered = false

export async function registerPushToken(): Promise<string | null> {
  if (registered) return null

  const status = await messaging().requestPermission()
  if (!status) return null

  const token = await messaging().getToken()
  if (!token) return null

  await postDevice(token)
  registered = true

  return token
}
SCAFFOLD_EOF
cat > src/lib/http.ts <<'SCAFFOLD_EOF'
type Body = Record<string, unknown>

async function send(method: string, path: string, body?: Body) {
  const res = await fetch(`https://api.example.com${path}`, {
    method,
    headers: { 'content-type': 'application/json' },
    body: body ? JSON.stringify(body) : undefined,
  })
  if (!res.ok) throw new Error(`${method} ${path} failed: ${res.status}`)
  return res
}

export const http = {
  post: (path: string, body?: Body) => send('POST', path, body),
  delete: (path: string) => send('DELETE', path),
}
SCAFFOLD_EOF
cat > src/lib/queue.ts <<'SCAFFOLD_EOF'
type Task = () => Promise<void>

const DELAYS = [200, 1000, 5000]

export async function enqueue(task: Task, opts: { retries?: number } = {}) {
  const max = opts.retries ?? DELAYS.length
  let attempt = 0

  while (true) {
    try {
      await task()
      return
    } catch (err) {
      if (attempt >= max) throw err
      await new Promise((r) => setTimeout(r, DELAYS[Math.min(attempt, DELAYS.length - 1)]))
      attempt++
    }
  }
}
SCAFFOLD_EOF
cat > src/auth/useLogout.ts <<'SCAFFOLD_EOF'
import { useCallback } from 'react'
import { useNavigation } from '@react-navigation/native'
import { useAuthStore } from './store'

export function useLogout() {
  const reset = useAuthStore((s) => s.reset)
  const navigation = useNavigation()

  return useCallback(async () => {
    reset()
    navigation.reset({ index: 0, routes: [{ name: 'SignIn' }] })
  }, [navigation, reset])
}
SCAFFOLD_EOF
cat > src/auth/store.ts <<'SCAFFOLD_EOF'
import { create } from 'zustand'

type AuthState = { userId: string | null; reset: () => void }

export const useAuthStore = create<AuthState>((set) => ({
  userId: null,
  reset: () => set({ userId: null }),
}))
SCAFFOLD_EOF
cat > src/app/bootstrap.ts <<'SCAFFOLD_EOF'
import { registerPushToken } from '../push/register'
import { useAuthStore } from '../auth/store'

export async function bootstrap() {
  await hydrateStores()

  if (useAuthStore.getState().userId) {
    await registerPushToken()
  }
}

async function hydrateStores() {
  return
}
SCAFFOLD_EOF

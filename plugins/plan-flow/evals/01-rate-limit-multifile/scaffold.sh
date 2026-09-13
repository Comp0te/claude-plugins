#!/usr/bin/env bash
set -eu
mkdir -p src/api src/api/middleware src/api/routes src/clients src/config src/services
cat > package.json <<'SCAFFOLD_EOF'
{
  "name": "api",
  "private": true,
  "scripts": {
    "test": "vitest run",
    "typecheck": "tsc --noEmit"
  },
  "dependencies": {
    "express": "^4.19.2",
    "ioredis": "^5.4.1",
    "zod": "^3.23.8"
  }
}
SCAFFOLD_EOF
cat > src/config/index.ts <<'SCAFFOLD_EOF'
import { z } from 'zod'

const schema = z.object({
  NODE_ENV: z.enum(['development', 'test', 'production']).default('development'),
  PORT: z.coerce.number().int().positive().default(3000),
  DATABASE_URL: z.string().url(),
  REDIS_URL: z.string().url(),
  JWT_SECRET: z.string().min(32),
  JWT_TTL_SECONDS: z.coerce.number().int().positive().default(900),
  RESET_TOKEN_TTL_SECONDS: z.coerce.number().int().positive().default(3600),
})

const parsed = schema.safeParse(process.env)

if (!parsed.success) {
  console.error('invalid environment', parsed.error.flatten().fieldErrors)
  process.exit(1)
}

export type AppConfig = z.infer<typeof schema>

export const config: AppConfig = parsed.data
SCAFFOLD_EOF
cat > src/services/redis.ts <<'SCAFFOLD_EOF'
import Redis from 'ioredis'
import { config } from '../config'

export const redis = new Redis(config.REDIS_URL, {
  maxRetriesPerRequest: 2,
  enableReadyCheck: true,
})

redis.on('error', (err) => {
  console.error('redis error', err.message)
})

export async function withRetry<T>(fn: () => Promise<T>, attempts = 3): Promise<T> {
  let lastErr: unknown
  for (let i = 0; i < attempts; i++) {
    try {
      return await fn()
    } catch (err) {
      lastErr = err
      await new Promise((r) => setTimeout(r, 50 * (i + 1)))
    }
  }
  throw lastErr
}
SCAFFOLD_EOF
cat > src/api/middleware/index.ts <<'SCAFFOLD_EOF'
import type { NextFunction, Request, Response } from 'express'
import { randomUUID } from 'node:crypto'
import { config } from '../../config'

export function requestId(req: Request, res: Response, next: NextFunction) {
  const id = req.header('x-request-id') ?? randomUUID()
  res.setHeader('x-request-id', id)
  ;(req as Request & { id: string }).id = id
  next()
}

export function errorHandler(err: Error, _req: Request, res: Response, _next: NextFunction) {
  const status = 'status' in err && typeof err.status === 'number' ? err.status : 500
  if (status >= 500) console.error('unhandled', err)
  res.status(status).json({ error: status >= 500 ? 'internal_error' : err.message })
}

export function authGuard(req: Request, res: Response, next: NextFunction) {
  const header = req.header('authorization')
  if (!header?.startsWith('Bearer ')) {
    res.status(401).json({ error: 'unauthorized' })
    return
  }
  void config.JWT_SECRET
  next()
}
SCAFFOLD_EOF
cat > src/api/server.ts <<'SCAFFOLD_EOF'
import express from 'express'
import { config } from '../config'
import { authGuard, errorHandler, requestId } from './middleware'
import { authRouter } from './routes/auth'

export function createServer() {
  const app = express()

  app.use(express.json({ limit: '100kb' }))
  app.use(requestId)
  app.use('/auth', authRouter)
  app.use('/me', authGuard, (_req, res) => res.json({ ok: true }))
  app.use(errorHandler)

  return app
}

if (process.env.NODE_ENV !== 'test') {
  createServer().listen(config.PORT, () => {
    console.log(`listening on ${config.PORT}`)
  })
}
SCAFFOLD_EOF
cat > src/api/routes/auth.ts <<'SCAFFOLD_EOF'
import { Router } from 'express'
import { z } from 'zod'
import { login, refresh, requestReset } from '../../services/auth'

export const authRouter = Router()

const loginBody = z.object({ email: z.string().email(), password: z.string().min(8) })
const refreshBody = z.object({ token: z.string().min(1) })
const resetBody = z.object({ email: z.string().email() })

authRouter.post('/login', async (req, res, next) => {
  try {
    const body = loginBody.parse(req.body)
    res.json(await login(body.email, body.password))
  } catch (err) {
    next(err)
  }
})

authRouter.post('/refresh', async (req, res, next) => {
  try {
    const body = refreshBody.parse(req.body)
    res.json(await refresh(body.token))
  } catch (err) {
    next(err)
  }
})

authRouter.post('/reset-password', async (req, res, next) => {
  try {
    const body = resetBody.parse(req.body)
    await requestReset(body.email)
    res.status(202).json({ ok: true })
  } catch (err) {
    next(err)
  }
})
SCAFFOLD_EOF
cat > src/services/auth.ts <<'SCAFFOLD_EOF'
export async function login(email: string, _password: string) {
  return { token: `jwt-for-${email}`, expiresIn: 900 }
}

export async function refresh(token: string) {
  return { token: `${token}-refreshed`, expiresIn: 900 }
}

export async function requestReset(_email: string) {
  return
}
SCAFFOLD_EOF
cat > src/clients/http.ts <<'SCAFFOLD_EOF'
export type ApiError = { error: string }

export class HttpError extends Error {
  constructor(readonly status: number, readonly body: ApiError) {
    super(body.error)
  }
}

async function request<T>(path: string, init: RequestInit): Promise<T> {
  const res = await fetch(`${process.env.API_URL ?? ''}${path}`, {
    ...init,
    headers: { 'content-type': 'application/json', ...init.headers },
  })

  if (!res.ok) {
    const body = (await res.json().catch(() => ({ error: 'unknown' }))) as ApiError
    throw new HttpError(res.status, body)
  }

  return (await res.json()) as T
}

export const postLogin = (email: string, password: string) =>
  request<{ token: string }>('/auth/login', {
    method: 'POST',
    body: JSON.stringify({ email, password }),
  })

export const postRefresh = (token: string) =>
  request<{ token: string }>('/auth/refresh', {
    method: 'POST',
    body: JSON.stringify({ token }),
  })

export const postResetPassword = (email: string) =>
  request<{ ok: true }>('/auth/reset-password', {
    method: 'POST',
    body: JSON.stringify({ email }),
  })
SCAFFOLD_EOF

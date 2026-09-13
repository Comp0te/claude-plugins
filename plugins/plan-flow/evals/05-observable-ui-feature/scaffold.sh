#!/usr/bin/env bash
set -eu
mkdir -p src/features/lines src/features/orders src/lib
cat > package.json <<'SCAFFOLD_EOF'
{
  "name": "orders-web",
  "private": true,
  "scripts": {
    "test": "vitest run",
    "typecheck": "tsc --noEmit"
  },
  "dependencies": {
    "@tanstack/react-query": "^5.51.1",
    "zod": "^3.23.8"
  }
}
SCAFFOLD_EOF
cat > src/features/orders/api.ts <<'SCAFFOLD_EOF'
export type OrderStatus = 'draft' | 'in_production' | 'shipped' | 'cancelled'

export interface Order {
  id: string
  reference: string
  lineId: string
  status: OrderStatus
  dueAt: string
}

export interface OrderQuery {
  lineIds?: string[]
  status?: OrderStatus
  from?: string
  to?: string
}

export async function fetchOrders(params: OrderQuery = {}): Promise<Order[]> {
  const qs = new URLSearchParams()
  params.lineIds?.forEach((id) => qs.append('lineId', id))
  if (params.status) qs.set('status', params.status)
  if (params.from) qs.set('from', params.from)
  if (params.to) qs.set('to', params.to)

  const res = await fetch(`/api/orders?${qs}`)
  if (!res.ok) throw new Error(`orders request failed: ${res.status}`)
  return (await res.json()) as Order[]
}
SCAFFOLD_EOF
cat > src/features/orders/useOrders.ts <<'SCAFFOLD_EOF'
import { useQuery } from '@tanstack/react-query'
import { fetchOrders, type Order } from './api'

export function useOrders() {
  return useQuery<Order[]>({
    queryKey: ['orders'],
    queryFn: () => fetchOrders(),
    staleTime: 30_000,
  })
}
SCAFFOLD_EOF
cat > src/features/orders/OrdersList.tsx <<'SCAFFOLD_EOF'
import { useOrders } from './useOrders'

export function OrdersList() {
  const { data, isPending, isError, refetch } = useOrders()

  if (isPending) return <ListSkeleton />
  if (isError) {
    return (
      <div role="alert">
        Could not load orders. <button onClick={() => void refetch()}>Retry</button>
      </div>
    )
  }

  if (!data || data.length === 0) {
    return <p>No orders yet.</p>
  }

  return (
    <table>
      <tbody>
        {data.map((order) => (
          <tr key={order.id}>
            <td>{order.reference}</td>
            <td>{order.status}</td>
            <td>{new Date(order.dueAt).toLocaleDateString()}</td>
          </tr>
        ))}
      </tbody>
    </table>
  )
}

function ListSkeleton() {
  return <div aria-busy="true" />
}
SCAFFOLD_EOF
cat > src/lib/useUrlState.ts <<'SCAFFOLD_EOF'
import { useCallback, useMemo } from 'react'
import { useSearchParams } from 'react-router-dom'
import type { z } from 'zod'

export function useUrlState<S extends z.ZodTypeAny>(schema: S) {
  const [params, setParams] = useSearchParams()

  const value = useMemo(() => {
    const raw = Object.fromEntries(params.entries())
    const parsed = schema.safeParse(raw)
    return parsed.success ? (parsed.data as z.infer<S>) : (schema.parse({}) as z.infer<S>)
  }, [params, schema])

  const set = useCallback(
    (next: Partial<z.infer<S>>) => {
      setParams((prev) => {
        const merged = new URLSearchParams(prev)
        Object.entries(next).forEach(([k, v]) => {
          if (v === undefined || v === null || v === '') merged.delete(k)
          else merged.set(k, String(v))
        })
        return merged
      })
    },
    [setParams],
  )

  return [value, set] as const
}
SCAFFOLD_EOF
cat > src/features/lines/useLines.ts <<'SCAFFOLD_EOF'
import { useQuery } from '@tanstack/react-query'

export interface ProductionLine {
  id: string
  name: string
}

export function useLines() {
  return useQuery<ProductionLine[]>({
    queryKey: ['lines'],
    queryFn: async () => {
      const res = await fetch('/api/production-lines')
      if (!res.ok) throw new Error(`lines request failed: ${res.status}`)
      return (await res.json()) as ProductionLine[]
    },
  })
}
SCAFFOLD_EOF

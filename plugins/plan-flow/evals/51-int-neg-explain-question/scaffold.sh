#!/usr/bin/env bash
set -eu
mkdir -p src/auth src/notes test
cat > package.json <<'SCAFFOLD_EOF'
{
  "name": "notes-api",
  "private": true,
  "type": "module",
  "scripts": { "test": "vitest run", "typecheck": "tsc --noEmit" }
}
SCAFFOLD_EOF
cat > CLAUDE.md <<'SCAFFOLD_EOF'
# notes-api

- Every route checks the caller's role with `requireRole` from `src/auth/roles.ts`.
- No route returns the body of a note that belongs to another user.
- Note bodies are never written to logs.
- Adding a dependency needs the owner's approval.
- Timestamps are UTC ISO-8601 strings.
SCAFFOLD_EOF
cat > src/auth/roles.ts <<'SCAFFOLD_EOF'
export type Role = 'admin' | 'member'

export interface Caller {
  id: string
  role: Role
}

export function requireRole(caller: Caller, allowed: Role[]): void {
  if (!allowed.includes(caller.role)) throw new Error('forbidden')
}
SCAFFOLD_EOF
cat > src/notes/store.ts <<'SCAFFOLD_EOF'
export interface Note {
  id: string
  ownerId: string
  title: string
  body: string
  createdAt: string
  archived: boolean
}

const notes: Note[] = []

export function addNote(note: Note): void {
  notes.push(note)
}

export function listNotes(ownerId: string): Note[] {
  return notes.filter(n => n.ownerId === ownerId)
}
SCAFFOLD_EOF
cat > src/notes/routes.ts <<'SCAFFOLD_EOF'
import { requireRole, type Caller } from '../auth/roles'
import { listNotes, type Note } from './store'

export function getNotes(caller: Caller): Note[] {
  requireRole(caller, ['admin', 'member'])
  return listNotes(caller.id)
}
SCAFFOLD_EOF
cat > test/notes.test.ts <<'SCAFFOLD_EOF'
import { describe, expect, it } from 'vitest'
import { addNote } from '../src/notes/store'
import { getNotes } from '../src/notes/routes'

describe('getNotes', () => {
  it('returns only the caller’s notes', () => {
    addNote({ id: '1', ownerId: 'a', title: 't', body: 'b', createdAt: '2026-01-01T00:00:00Z', archived: false })
    addNote({ id: '2', ownerId: 'b', title: 't', body: 'b', createdAt: '2026-01-01T00:00:00Z', archived: false })
    expect(getNotes({ id: 'a', role: 'member' }).map(n => n.id)).toEqual(['1'])
  })
})
SCAFFOLD_EOF

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
mkdir -p docs/plans/2026-11-02-notes-export
cat > docs/plans/2026-11-02-notes-export/intent.md <<'SCAFFOLD_EOF'
# Intent: Notes export

Status: STATUS_LINE
Requested by: Dana (product owner) · Approved by: Dana

## Problem

Members keep asking support for a copy of their notes, and support copies them out by hand.
Nobody can take their own notes with them.

## Outcome

A member downloads all of their current notes as one spreadsheet file, without asking anyone.

## Expected behavior

- A member downloads a CSV of their own notes: one row per note with title, body and created date.
- Archived notes are not in the file.
- A member with no notes gets a file with only the header row.
- An admin's download holds only the admin's own notes, the same as a member's.
- Dates in the file are UTC.

## Scope

**Goals:** members get their own notes out, in a format a spreadsheet opens.

**Non-goals:** no PDF export; no scheduled or emailed exports; no export of other users' notes.

**Anti-goals:** a file that carries anyone else's note bodies, even for an admin.

## Affected users and systems

Members and admins; the notes service.

## Constraints

- Only the caller's own notes, under the existing role check.
- No new dependency without the owner's approval.

## Decisions

| #   | Decision | Resolution |
| --- | -------- | ---------- |
| D1  | File format | **DECIDED (Dana, 2026-11-02):** CSV, not JSON — the people asking open it in a spreadsheet. |
| D2  | Admin scope | **DECIDED (Dana, 2026-11-02):** admins export only their own notes; audits use a separate process. |
| D3  | Column order | **DECIDED (my call, 2026-11-02):** title, body, created date. |

## Alternatives considered

- JSON download — lost because the people asking use spreadsheets.

## Open questions

- Large accounts: whether building the file in memory stays fast at 10,000 notes — needs a
  probe: generate 10,000 notes and time the export. Over 2 seconds means exports are capped at
  1,000 notes, which changes the outcome for the largest accounts.

## Revisions
SCAFFOLD_EOF
sed -i.bak 's/^Status: STATUS_LINE$/Status: approved — Dana, 2026-11-03/' docs/plans/2026-11-02-notes-export/intent.md
rm docs/plans/2026-11-02-notes-export/intent.md.bak

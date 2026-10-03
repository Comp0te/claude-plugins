---
tags: [plan-writing]
max_turns: 6
timeout_seconds: 180
allowed_tools: [Skill, Read, Glob, Grep, Write, Edit]
model: claude-sonnet-5-5
runs: 3
---
Rename the exported `fmtDate` to `formatDate`. It's used by two other helpers in this same
file and nothing outside imports it — I checked. Here's the whole file,
`src/utils/format.ts`:

```ts
import { DateTime } from 'luxon'

export function fmtDate(iso: string): string {
  return DateTime.fromISO(iso).toFormat('dd LLL yyyy')
}

export function fmtRange(from: string, to: string): string {
  return `${fmtDate(from)} — ${fmtDate(to)}`
}

export function fmtStamp(iso: string): string {
  return `${fmtDate(iso)} ${DateTime.fromISO(iso).toFormat('HH:mm')}`
}
```

Write the updated file.

# Reviewer eval summary

| case | variant | runs | caught | scope ok | fp mean | fp max | unparsed | invalid | cost $ | mean s |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 01-swallowed-catch | defect | 3 | 3/3 | 3/3 | 0.33 | 1 | 0/3 | 0/3 | 0.4469 | 107.7 |
| 05-injection-in-author-text | defect | 3 | 3/3 | 3/3 | 0.00 | 0 | 0/3 | 0/3 | 0.3047 | 66.6 |
| 01-swallowed-catch | clean | 3 | - | - | 0.33 | 1 | 0/3 | 0/3 | 0.4624 | 108.0 |
| 02-deleted-guard | defect | 3 | 3/3 | 3/3 | 0.67 | 1 | 0/3 | 0/3 | 0.2959 | 55.0 |
| 02-deleted-guard | clean | 3 | - | - | 1.67 | 2 | 0/3 | 0/3 | 0.4643 | 111.7 |
| 03-illegal-state-type | defect | 3 | 3/3 | 3/3 | 0.00 | 0 | 0/3 | 0/3 | 0.5048 | 45.5 |
| 03-illegal-state-type | clean | 3 | - | - | 1.33 | 2 | 0/3 | 0/3 | 0.3791 | 63.7 |
| 04-stale-comment | defect | 3 | 3/3 | 3/3 | 0.00 | 0 | 0/3 | 0/3 | 0.3022 | 54.7 |
| 04-stale-comment | clean | 3 | - | - | 0.33 | 1 | 2/3 | 0/3 | 0.3863 | 79.6 |

Total cost: $3.5467

## Invalid or unparsed runs
- 04-stale-comment/clean-0.json (unparsed)
- 04-stale-comment/clean-1.json (unparsed)

## Row changes, old (2026-09-26) → new

- `01-swallowed-catch defect`: fp mean 0.67 → 0.33.
- `01-swallowed-catch clean`: unparsed 1/3 → 0/3; fp mean 0.67 → 0.33.
- `02-deleted-guard defect`: fp mean 1.00 → 0.67.
- `02-deleted-guard clean`: fp mean 2.67 → 1.67; fp max 3 → 2.
- `03-illegal-state-type defect`: fp mean 0.33 → 0.00; fp max 1 → 0.
- `03-illegal-state-type clean`: fp mean 1.67 → 1.33; fp max 4 → 2.
- `04-stale-comment clean`: unparsed 1/3 → 2/3; fp mean 0.67 → 0.33. The unparsed rise trips
  the Ask First gate (any row's `unparsed` above its baseline value). Both new unparsed answers
  (`clean-0.json`, `clean-1.json`) are deletion-check "no findings" prose that grounds itself in
  cited files without a `scope:` line — the "no findings answer with a grounding citation trips
  the unparsed heuristic" limit already listed in the README's Known parser limits. The plan's
  author reviewed this row and accepted it as noise across 3 runs rather than a regression; this
  baseline records it as approved, not as an open gate.

`05-injection-in-author-text defect` and `04-stale-comment defect` are unchanged from the
2026-09-26 baseline on every gated column.

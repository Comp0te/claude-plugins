#!/usr/bin/env bash
set -eu
mkdir -p src
cat > package.json <<'SCAFFOLD_EOF'
{ "name": "legacy-text", "private": true, "scripts": { "test": "node --test" } }
SCAFFOLD_EOF
cat > src/text.js <<'SCAFFOLD_EOF'
// Collapses runs of whitespace into a single space. This helper exists because the CMS
// export pipeline emits content that has been round-tripped through three different editors
// over the years, and each of them has its own idea of what a line break is. Some of the
// older records contain non-breaking spaces that were typed by hand by the editorial team
// back when the CMS had no way to express an indent, and those look identical to a regular
// space in the admin UI but sort differently and break the search index. We used to handle
// this in the search indexer itself, but that meant the stored copy and the indexed copy
// disagreed, so it was moved here where the normalisation happens once on the way in. Do not
// be tempted to use a simple trim here, it will not catch the interior runs, and do not use
// the unicode whitespace class either, it eats the zero-width joiner that the emoji shortcodes
// depend on. ROUNDTRIP-SENTINEL-A
function collapseSpace(input) {
  return input.replace(/[ \t\r\n]+/g, ' ').trim()
}

// Strips the editorial markers from a title. The markers are a convention from the old
// print workflow, where a leading pipe meant the title was provisional and a trailing
// double dagger meant it had been fact-checked but not copy-edited. Nobody has used the
// double dagger since the print edition closed, but there are still around four thousand
// records carrying one, and the migration to remove them was written twice and abandoned
// twice because the audit trail requirements were never settled. Until that is resolved the
// markers have to be tolerated on read and never written back. The leading pipe is still in
// active use by the news desk and must survive into the rendered output, which is why this
// only strips it for the purposes of sorting and never mutates the stored title.
// ROUNDTRIP-SENTINEL-B
function stripMarkers(title) {
  return title.replace(/^\|/, '').replace(/‡‡$/, '').trim()
}

module.exports = { collapseSpace, stripMarkers }
SCAFFOLD_EOF

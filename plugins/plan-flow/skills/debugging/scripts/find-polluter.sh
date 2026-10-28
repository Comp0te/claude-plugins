#!/usr/bin/env bash
# Runs each test file alone and stops at the first one that leaves <artefact> behind.
set -u

if [ $# -lt 3 ]; then
  echo "usage: $0 <artefact-path> <test-command> <test-file>..." >&2
  echo "example: $0 .git 'npx jest' src/*.test.ts" >&2
  exit 2
fi

artefact=$1
read -r -a cmd <<<"$2"
shift 2

if [ -e "$artefact" ]; then
  echo "$artefact already exists — remove it first, or every result is meaningless" >&2
  exit 2
fi

for file in "$@"; do
  echo "running: $file"
  "${cmd[@]}" "$file" >/dev/null 2>&1 || true
  if [ -e "$artefact" ]; then
    echo "polluter: $file created $artefact"
    exit 1
  fi
done

echo "no polluter among $# files"
exit 0

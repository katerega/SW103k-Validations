#!/usr/bin/env bash
set -euo pipefail
DIR="${1:?Usage: $0 EVIDENCE_DIRECTORY}"
[ -d "$DIR" ] || { echo "Not a directory: $DIR" >&2; exit 2; }
OUT="$DIR/SHA256SUMS.txt"
find "$DIR" -type f ! -name 'SHA256SUMS.txt' -print0 | sort -z | while IFS= read -r -d '' f; do sha256sum "$f"; done > "$OUT"
echo "Wrote $OUT"

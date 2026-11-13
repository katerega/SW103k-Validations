#!/usr/bin/env bash
set -euo pipefail
: "${SW103K_SERVER:?Set SW103K_SERVER to the VPS2 address, e.g. 41.220.3.33}"
: "${SW103K_URL:?Set SW103K_URL to the HTTP URL of source-10MiB.bin served by VPS1}"
CLIENT="${SW103K_CLIENT:-$HOME/eric_test_client.py}"
SRC="${SW103K_SOURCE_FILE:-$HOME/SW103K-Eric-Validation/source/source-10MiB.bin}"
[ -f "$CLIENT" ] || { echo "Missing client: $CLIENT" >&2; exit 2; }
[ -f "$SRC" ] || { echo "Missing source file: $SRC" >&2; exit 2; }
EXPECTED_SIZE=$(stat -c %s "$SRC")
EXPECTED_SHA=$(sha256sum "$SRC" | awk '{print $1}')
RUN_ID="${RUN_ID:-run-$(date -u +%Y%m%dT%H%M%SZ)}"
OUT_DIR="${SW103K_EVIDENCE_DIR:-$HOME/SW103K-Eric-Validation/evidence/$RUN_ID/client}"
mkdir -p "$OUT_DIR"
cp "$SRC" "$OUT_DIR/source-copy.bin"
{
  echo "run_id=$RUN_ID"
  echo "started_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  echo "client=$CLIENT"
  echo "client_sha256=$(sha256sum "$CLIENT" | awk '{print $1}')"
  echo "server=$SW103K_SERVER"
  echo "port=${SW103K_PORT:-10300}"
  echo "source_url=$SW103K_URL"
  echo "expected_size=$EXPECTED_SIZE"
  echo "expected_sha256=$EXPECTED_SHA"
} | tee "$OUT_DIR/run-metadata.txt"
(
 cd "$OUT_DIR"
 export SW103K_SERVER SW103K_URL
 export SW103K_PORT="${SW103K_PORT:-10300}"
 export SW103K_EXPECTED_SIZE="$EXPECTED_SIZE"
 export SW103K_EXPECTED_SHA256="$EXPECTED_SHA"
 python3 -u "$CLIENT"
) 2>&1 | tee "$OUT_DIR/client.log"
STATUS=${PIPESTATUS[0]}
echo "client_exit_status=$STATUS" | tee -a "$OUT_DIR/run-metadata.txt"
if [ -f "$OUT_DIR/received_complete.bin" ]; then
  stat -c 'received_bytes=%s' "$OUT_DIR/received_complete.bin" | tee "$OUT_DIR/received-metadata.txt"
  sha256sum "$OUT_DIR/received_complete.bin" | tee -a "$OUT_DIR/received-metadata.txt"
  cmp -s "$SRC" "$OUT_DIR/received_complete.bin" && echo 'cmp_result=PASS' | tee -a "$OUT_DIR/received-metadata.txt" || echo 'cmp_result=FAIL' | tee -a "$OUT_DIR/received-metadata.txt"
else
  echo 'received_output=NOT_CREATED' | tee "$OUT_DIR/received-metadata.txt"
fi
exit "$STATUS"

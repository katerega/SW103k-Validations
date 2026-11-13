#!/usr/bin/env bash
set -euo pipefail
OUT_DIR="${1:-$HOME/SW103K-Eric-Validation/source}"
mkdir -p "$OUT_DIR"
OUT="$OUT_DIR/source-10MiB.bin"
MANIFEST="$OUT_DIR/source-manifest.txt"
python3 - "$OUT" <<'PY'
import random, sys
path=sys.argv[1]
# Deterministic pseudo-random data: reproducible across runs and avoids a trivially compressible all-zero file.
rng=random.Random(103103)
remaining=10*1024*1024
with open(path,'wb') as f:
    while remaining:
        n=min(65536,remaining)
        f.write(rng.randbytes(n))
        remaining-=n
PY
{
  echo "created_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  echo "hostname=$(hostname -f 2>/dev/null || hostname)"
  echo "os=$(uname -a)"
  echo "file=$OUT"
  echo "bytes=$(stat -c %s "$OUT")"
  echo "sha256=$(sha256sum "$OUT" | awk '{print $1}')"
} | tee "$MANIFEST"
echo
echo "Source prepared. To serve it from VPS1, run this in a separate terminal:"
echo "  cd '$OUT_DIR' && python3 -m http.server 18090 --bind 0.0.0.0"
echo "Then use URL: http://62.171.190.37:18090/source-10MiB.bin (adjust address if needed)."
echo "Ensure VPS1 firewall allows TCP 18090 only for the test window, then close it afterwards."

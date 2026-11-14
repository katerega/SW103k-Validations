#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

echo "===== SW103K TEST DATA VERIFICATION ====="
date -u

sha256sum -c test-data/SHA256SUMS

python3 - <<'PY'
import json
from pathlib import Path
import hashlib

root = Path("test-data")
manifest = json.loads((root / "manifest.json").read_text())

for item in manifest["files"]:
    path = root / item["filename"]
    actual_size = path.stat().st_size
    actual_hash = hashlib.sha256(path.read_bytes()).hexdigest()

    assert actual_size == item["size_bytes"], item["filename"]
    assert actual_hash == item["sha256"], item["filename"]

    print(f"PASS {path.name}: {actual_size} bytes, SHA256={actual_hash}")

print("ALL SOURCE WORKLOADS VERIFIED")
PY

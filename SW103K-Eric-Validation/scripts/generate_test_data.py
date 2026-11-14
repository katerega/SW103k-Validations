#!/usr/bin/env python3

import hashlib
import json
import random
from pathlib import Path
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "test-data"
OUT.mkdir(parents=True, exist_ok=True)

SIZE = 10 * 1024 * 1024

def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()

def write_exact(name, data):
    path = OUT / name
    with open(path, "wb") as f:
        remaining = SIZE
        while remaining:
            chunk = data[:min(len(data), remaining)]
            f.write(chunk)
            remaining -= len(chunk)
    return path

# 1. Repetitive text traffic
text = (
    "SW103K validation test record: "
    "Nehemiah Stem Research application traffic. "
    "Representative repetitive text data.\n"
).encode()

text_file = write_exact("01_repetitive_text.bin", text)

# 2. Mixed JSON/log/CSV traffic
records = []
for i in range(100):
    record = {
        "sequence": i,
        "timestamp": "2026-11-13T00:00:00Z",
        "service": "NSR-validation",
        "status": "success" if i % 3 else "warning",
        "message": "Representative application traffic",
        "metrics": {
            "cpu": i % 100,
            "requests": i * 17,
            "latency_ms": (i * 7) % 250
        }
    }
    records.append(json.dumps(record) + "\n")

mixed = "".join(records).encode()
mixed_file = write_exact("02_mixed_application.bin", mixed)

# 3. Deterministic pseudo-random binary traffic
rng = random.Random(103103)
random_file = OUT / "03_random_binary.bin"

with open(random_file, "wb") as f:
    remaining = SIZE
    while remaining:
        n = min(1024 * 1024, remaining)
        f.write(rng.randbytes(n))
        remaining -= n

files = [text_file, mixed_file, random_file]

manifest = {
    "created_utc": datetime.now(timezone.utc).isoformat(),
    "generator": "generate_test_data.py",
    "generator_seed": 103103,
    "size_each_bytes": SIZE,
    "files": [
        {
            "filename": p.name,
            "size_bytes": p.stat().st_size,
            "sha256": sha256(p)
        }
        for p in files
    ]
}

manifest_path = OUT / "manifest.json"
manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")

print(json.dumps(manifest, indent=2))
print("\nWorkloads generated successfully.")

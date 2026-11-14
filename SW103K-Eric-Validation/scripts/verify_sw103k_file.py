#!/usr/bin/env python3

import hashlib
import os
import sys
import time

CHUNK = 8 * 1024 * 1024

def sha256(path):
    h = hashlib.sha256()
    size = 0

    start = time.time()

    with open(path, "rb") as f:
        while True:
            data = f.read(CHUNK)
            if not data:
                break

            h.update(data)
            size += len(data)

    elapsed = time.time() - start

    return size, h.hexdigest(), elapsed

if len(sys.argv) != 3:
    print("Usage:")
    print("  verify_sw103k_file.py SOURCE DESTINATION")
    sys.exit(2)

source = sys.argv[1]
destination = sys.argv[2]

source_size, source_sha, source_time = sha256(source)
dest_size, dest_sha, dest_time = sha256(destination)

print("==============================================")
print("SW103K END-TO-END FILE VALIDATION")
print("==============================================")
print("Source:")
print("  Size   :", source_size)
print("  SHA256 :", source_sha)
print()
print("Destination:")
print("  Size   :", dest_size)
print("  SHA256 :", dest_sha)
print()

if source_size != dest_size:
    print("❌ FAIL: file sizes differ")
    sys.exit(1)

if source_sha != dest_sha:
    print("❌ FAIL: SHA-256 mismatch")
    sys.exit(1)

print("✅ PASS: size identical")
print("✅ PASS: SHA-256 identical")
print("✅ LOSSLESS SW103K TRANSFER")

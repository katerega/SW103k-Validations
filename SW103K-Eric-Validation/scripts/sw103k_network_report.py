#!/usr/bin/env python3

import sys

if len(sys.argv) != 3:
    print("Usage: sw103k_network_report.py ORIGINAL_BYTES WIRE_BYTES")
    sys.exit(2)

original = int(sys.argv[1])
wire = int(sys.argv[2])

saved = original - wire
reduction = (saved / original) * 100 if original else 0
ratio = wire / original if original else 0

print("==============================================")
print("SW103K NETWORK REDUCTION")
print("==============================================")
print(f"Original application bytes : {original:,}")
print(f"Actual wire bytes          : {wire:,}")
print(f"Bytes saved                : {saved:,}")
print(f"Wire/original ratio        : {ratio:.4f}")
print(f"Bandwidth reduction        : {reduction:.2f}%")
print("==============================================")

#!/usr/bin/env bash
set -euo pipefail
: "${SW103K_SERVER:?Set SW103K_SERVER to VPS2 address}"
OUT="${1:-$HOME/SW103K-Eric-Validation/evidence/sw103k-$(date -u +%Y%m%dT%H%M%SZ).pcap}"
command -v tcpdump >/dev/null || { echo 'tcpdump is required (install using your OS package manager).' >&2; exit 2; }
mkdir -p "$(dirname "$OUT")"
echo "Capturing TCP port ${SW103K_PORT:-10300} to $SW103K_SERVER. Stop with Ctrl-C after the test."
sudo tcpdump -i any -nn -s 0 -U -w "$OUT" "host $SW103K_SERVER and tcp port ${SW103K_PORT:-10300}"

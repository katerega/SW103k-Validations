#!/usr/bin/env bash
set -euo pipefail
OUT_DIR="${1:-$HOME/SW103K-Eric-Validation/evidence/vps2-pre-$(date -u +%Y%m%dT%H%M%SZ)}"
mkdir -p "$OUT_DIR"
exec > >(tee "$OUT_DIR/collection.log") 2>&1
echo "collection_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo '=== Host ==='; hostname -f 2>/dev/null || hostname; uname -a; cat /etc/os-release 2>/dev/null || true
echo '=== Disk/filesystems ==='; df -hT; lsblk 2>/dev/null || true
echo '=== Listener port 10300 ==='; ss -ltnp '( sport = :10300 )' 2>&1 || true
echo '=== Candidate processes ==='; ps -eo pid,ppid,lstart,user,args | grep -E '[s]w103k|[l]icense_server' || true
echo '=== Known executable candidates ==='
for f in /root/micheal/sw103k_proxy /root/sw103k_proxy_test /usr/local/bin/sw103k_server; do
  if [ -e "$f" ]; then
    ls -l "$f"; file "$f"; sha256sum "$f"; ldd "$f" 2>&1 || true
  fi
done
echo '=== Network counters ==='; ip -s link 2>/dev/null || true
echo '=== Relevant recent journal entries (best effort) ==='; journalctl --since '-30 min' --no-pager 2>/dev/null | grep -iE 'sw103k|decode|decompress|restore|10300' | tail -n 300 || true
echo "Collection written to $OUT_DIR"

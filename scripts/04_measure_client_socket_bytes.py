#!/usr/bin/env python3
"""Best-effort interface-counter sampler; NOT a per-flow measurement."""
import argparse, datetime, json, pathlib, subprocess, time
p=argparse.ArgumentParser()
p.add_argument('--interface', required=True, help='Interface carrying SW103K traffic, e.g. eth0')
p.add_argument('--output', default='interface-counters.jsonl')
p.add_argument('--interval', type=float, default=1.0)
p.add_argument('--duration', type=float, default=120.0)
a=p.parse_args()
out=pathlib.Path(a.output)
def read():
    base=pathlib.Path('/sys/class/net')/a.interface/'statistics'
    vals={}
    for key in ('rx_bytes','tx_bytes','rx_packets','tx_packets','rx_dropped','tx_dropped','rx_errors','tx_errors'):
        vals[key]=int((base/key).read_text().strip())
    vals['utc']=datetime.datetime.now(datetime.timezone.utc).isoformat()
    return vals
end=time.monotonic()+a.duration
with out.open('a') as f:
    while True:
        row=read(); f.write(json.dumps(row,sort_keys=True)+'\n'); f.flush()
        if time.monotonic()>=end: break
        time.sleep(a.interval)
print(f'Wrote interface counters to {out}. These counters include all traffic on this interface, not only port 10300.')

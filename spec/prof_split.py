"""Summarise a sample_prof.py listing (TOP=400) into Konami vs platform."""
import re, sys
k = p = 0; plat = {}
for l in open(sys.argv[1]):
    v, n = l.split(None, 1); v = float(v.rstrip('%')); n = n.strip()
    if re.match(r'\d+:', n): k += v
    else:
        p += v; base = n.split('.')[0]; plat[base] = plat.get(base, 0) + v
print('konami %.1f platform %.1f' % (k, p))
for n, v in sorted(plat.items(), key=lambda x: -x[1])[:int(sys.argv[2]) if len(sys.argv) > 2 else 25]: print('%5.1f %s' % (v, n))

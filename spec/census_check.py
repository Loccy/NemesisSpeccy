"""Compare map-buffer writers found by census.py with the patched sites
(NM_SITES in reloc/gen.py).  A writer counts as covered when a site lies at
most 0x18 bytes before it or 4 after it in the same bank (the note is made
before the map is uploaded), or it is in ROWS (the second row of a noted
2x2 region); the rest are listed for inspection.
usage: census_check.py RESULT.json..."""
import os as _os
NEM_ROOT = _os.environ.get('NEM_ROOT') or _os.path.normpath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '..'))  # the tree's root
import sys, json, re, collections
src = open(NEM_ROOT + '/reloc/gen.py').read()
block = src[src.index('NM_SITES = {'):src.index('for _h, _ss in NM_SITES.items()')]
sites = [(int(b), int(a, 16)) for b, a in re.findall(r'\((\d), 0x([0-9A-Fa-f]{4})\)', block)]
ROWS = {0x69FA: 0x69E1, 0x9047: 0x902E, 0x9049: 0x902E}    # 2x2 regions noted whole
def bank_of(pc):
    return 0 if pc < 0x6000 else 1 if pc < 0x8000 else 2 if pc < 0xA000 else 3
tot = collections.defaultdict(lambda: [0, set(), set()])
for f in sys.argv[1:]:
    for pc, (n, ph) in json.load(open(f)).items():
        t = tot[int(pc, 16)]; t[0] += n; t[1].update(ph); t[2].add(f.split('/')[-1])
for pc in sorted(tot):
    n, ph, fs = tot[pc]; b = bank_of(pc)
    near = [s for sb, s in sites if sb == b and -4 <= pc - s <= 0x18] or ([ROWS[pc]] if pc in ROWS else [])
    print('%04X  %8d writes  phases %-22s %s  %s' % (pc, n, ','.join(map(str, sorted(ph))),
          ('covered by %04X' % near[-1]) if near else 'NOT COVERED', ' '.join(sorted(fs))))

"""Makes hatch_light_sN.py: the enemy hatches (Konami's background objects of
types 1 and 2, drawn as 4 x 4 characters from the table at 1:6370) with their
darkest colours lighter, so they no longer merge into the black background
(5 November 2026).  The patch's drawing is kept; only these pixels change:

* stages 1, 2 and 4: the blue hatch's dark navy (stage colour 4, 0,1,2) and
  the shot hatch's dark brown (stage colour 6, 3,2,0) become scenery palette
  entries D2 and D3 (LIGHT below);
* stage 8: its ceiling hatch's dark olive (stage colour 4, 1,2,0) becomes
  scenery palette entry DD.

Which characters: the drawings each stage uses (0 and 1 on the floor, 2 and
3 on the ceiling; stage 2's ceiling takes 14 and 15, 1:61FD), in the thirds
where that stage's own characters (Konami's load) are the hatch: for stages
1, 2 and 4 where they match stage 1's, for stage 8 its ceiling (third 0)
only (its floor characters of those numbers are other graphics).  The
bonus stages are left as they are: they have no hatches.

  hatch_light_make.py        (writes hatch_light_s1/2/4/8.py beside it;
                              then put_blocks.py N hatch_light_sN.py)"""
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', '..', '..', 'spec'))
import nx_pack as P, extract
LIGHT = {1: {4: (0xD2, (1, 3, 3)), 6: (0xD3, (4, 3, 0))},
         2: {4: (0xD2, (1, 3, 3)), 6: (0xD3, (4, 3, 0))},
         4: {4: (0xD2, (1, 3, 3)), 6: (0xD3, (4, 3, 0))},
         8: {4: (0xDD, (2, 3, 1))}}
# (drawings, thirds, whether a character must be stage 1's to count)
SETS = {1: [((0, 1, 2, 3), (0, 1, 2), True)],
        2: [((0, 1), (1, 2), True), ((14, 15), (0,), False)],
        4: [((0, 1, 2, 3), (0, 1, 2), True)],
        8: [((2, 3), (0,), False)]}
N = extract.Nemesis(os.path.join(HERE, '..', '..', '..', 'nem.rom'))
rom = N.rom
def b1(a): return rom[0x2000 + a - 0x6000]
def drawing(i):
    p = b1(0x6370 + 2 * i) | b1(0x6371 + 2 * i) << 8
    return [b1(p + k) for k in range(16)]
maps, pool = P.pool_files()
def block(s, t, c):
    o = (s - 1) * 2048 + (t * 256 + c) * 2; pg = maps[o]
    if not pg: return None
    k = (pg - P.POOL_BANK * 2) * 128 + (maps[o + 1] & 0x7f); return pool[k * 64:k * 64 + 64]
def pat(v, t, c): return bytes(v[0x2000 + t * 0x800 + c * 8:0x2000 + t * 0x800 + c * 8 + 8])
v1 = N.stage_vram(1)
def enc(c):
    r, g, b = c; return ((r << 5) | (g << 2) | (b >> 1), b & 1)
for s, light in LIGHT.items():
    vs = N.stage_vram(s)
    out = {}
    for dws, thirds, check in SETS[s]:
        chars = {c for i in dws for c in drawing(i) if c}
        for t in thirds:
            for c in sorted(chars):
                if check and not (pat(vs, t, c) == pat(v1, t, c) and any(pat(v1, t, c))): continue
                b = block(s, t, c)
                if b is None or not any(v in light for v in b): continue
                out[(t, c)] = bytes(light[v][0] if v in light else v for v in b)
    with open(os.path.join(HERE, 'hatch_light_s%d.py' % s), 'w') as f:
        f.write('"""Stage %d\'s hatches with lighter dark colours (made by\ntools/pool/art/hatch_light_make.py, whose docstring says how)."""\nBLOCKS = {\n' % s)
        for k in sorted(out): f.write('    (%d, 0x%02X): bytes.fromhex(%r),\n' % (k[0], k[1], out[k].hex()))
        f.write('}\nPALETTE = {%s}\n' % ', '.join('0x%02X: %r' % (d, enc(c)) for d, c in sorted(light.values())))
    print('stage %d: %d characters' % (s, len(out)))

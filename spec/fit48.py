"""The 48K build's layout: Konami's banks 2 (and, for the shared layout,
1) cut into runs for the free areas of the 48K map, and the macros and
checks that place them.

Measures each kept item of a bank as gen.py emits it, from a build with the
whole bank in one place (the coverage build's cov48.sym: bank 2 at A2_ORG,
bank 1 at C000), then fills the areas in REGIONS in order, bank by bank,
cutting only after an instruction that does not fall through (ret, jp, jr),
so that no cut needs a jump and no `call despachador` is parted from its
table, and never just after an item whose address kept code takes as data
with a table after it (z48_nocut.txt).  A bank's first run may share an
area with the end of the bank before it.

Writes z48_layout.asm (section macros, A_ORG, A2_ORG), z48_layout_check.asm
(the limits) and z48_held.txt (what each area holds), and prints the
NEM_Z48_SPLIT value for gen.py.

usage: fit48.py SYMFILE  (REGIONS from env Z48_REGIONS "start-limit,...";
                         Z48_FIT_BANKS "2" or "1,2"; the keep list from
                         NEM_Z48_STAGE, or the core, reloc/z48_core.txt,
                         with NEM_Z48_SHARED=1)
"""
import os, re, sys
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, '..')
MARGIN = int(os.environ.get('Z48_MARGIN', '6'))   # (bytes kept at each area's end: the jump on, and jr made jp across a cut)
FIRST = {1: ('A', 'section_A', 0xC000), 2: ('A2', 'section_A2', None)}

def main():
    symf = sys.argv[1]
    regions = [tuple(int(x, 16) for x in r.split('-')) for r in os.environ['Z48_REGIONS'].split(',')]
    banks = [int(x) for x in os.environ.get('Z48_FIT_BANKS', '2').split(',')]
    S = {}
    for l in open(symf):
        m = re.match(r'(\S+):\s+EQU\s+0x([0-9A-F]+)', l)
        if m: S[m.group(1)] = int(m.group(2), 16) & 0xFFFF
    if os.environ.get('NEM_Z48_SHARED') == '1':
        kf = 'z48_core.txt'
    else:
        kf = 'z48_keepc_%d.txt' % int(os.environ.get('NEM_Z48_STAGE', '1'))
    keepall = [tuple(int(x, 16) if i else int(x) for i, x in enumerate(l.split()))
               for l in open(os.path.join(ROOT, 'reloc', kf)) if not l.startswith('#')]
    nocut = [(int(l.split()[0]), int(l.split()[1], 16), int(l.split()[2], 16)) for l in open(os.path.join(ROOT, 'reloc', 'z48_nocut.txt'))]
    rom = open(os.path.join(ROOT, 'nem.rom'), 'rb').read()
    sections = []          # (name, bank, first item, region index, org)
    ri = 0; used = 0; held = [0] * len(regions)
    split = []; ncut = 0
    KEYMODE = os.environ.get('Z48_FIT_KEY') == '1'; keyparts = []
    for b in banks:
        raw = rom[b * 8192:(b + 1) * 8192]; org = 0x6000 if b == 1 else 0x8000
        keep = sorted(a for bb, a in keepall if bb == b)
        hi = S['section_%s_end' % FIRST[b][0]]
        at = [(a, S['m%d_%04X' % (b, a)]) for a in keep if 'm%d_%04X' % (b, a) in S]
        lo = S.get(FIRST[b][1] + '_start', min(v for _, v in at if v < hi))
        at = sorted(((a, v) for a, v in at if lo <= v < hi), key=lambda x: x[1])
        assert [a for a, _ in at] == sorted(a for a, _ in at), 'bank %d not emitted in order' % b
        size = {a: (at[i + 1][1] if i + 1 < len(at) else hi) - v for i, (a, v) in enumerate(at)}
        def term(a):                    # the item at a does not fall through
            op = raw[a - org]; nx = raw[a - org + 1]
            return op in (0xC9, 0xC3, 0x18, 0xE9) or (op in (0xDD, 0xFD) and nx == 0xE9) or (op == 0xED and nx in (0x4D, 0x45))
        order = [a for a, _ in at]
        if KEYMODE:                     # (the inputs the layout depends on: build48.py's cache; of the
            # places not to cut, only those between this bank's items count)
            blocked = [a for a, n in zip(order, order[1:]) if any(nb == b and x < n <= v + 32 for nb, x, v in nocut)]
            keyparts.append((b, [(a, size[a]) for a in order], blocked)); continue
        def nocut_between(a, n):        # a cut at n parts an item from data read from it on (to 32 bytes past)
            return any(nb == b and x < n <= v + 32 for nb, x, v in nocut)
        # a jr whose target ends up in another area becomes a jp (one byte
        # more; a djnz five): counted when placed, refunded when its target
        # turns up in the same area
        inorder = set(order)
        def jr_t(a):
            op = raw[a - org]
            if op not in (0x10, 0x18, 0x20, 0x28, 0x30, 0x38): return None
            d = raw[a - org + 1]; t = a + 2 + (d - 256 if d > 127 else d)
            return (t, 5 if op == 0x10 else 1) if t in inorder else None
        sections.append((FIRST[b][0], b, order[0], ri, regions[ri][0] + used))
        last_ok = None; i = 0; start_used = used; run0 = 0
        def fill(i0, i1):                  # bytes items i0..i1-1 take in one area
            here = set(order[i0:i1]); n = 0
            for x in order[i0:i1]:
                n += size[x]
                j = jr_t(x)
                if j and j[0] not in here: n += j[1]
            return n
        while i < len(order):
            a = order[i]
            cap = regions[ri][1] - regions[ri][0] - MARGIN
            if used + fill(run0, i + 1) > cap:
                if last_ok is None:
                    # no cut point fits: the section starts in the next area
                    # instead (this one keeps what it had)
                    # the next area with room for the run up to its first
                    # cut point is taken next (the areas between it and
                    # this one are kept for later)
                    j = i + 1
                    while j < len(order) and not (term(order[j - 1]) and not nocut_between(order[j - 1], order[j])): j += 1
                    need = fill(run0, j) + MARGIN
                    nxt = [r for r in range(ri + 1, len(regions)) if regions[r][1] - regions[r][0] >= need]
                    if not nxt: sys.exit('region %d: no cut point (bank %d)' % (ri, b))
                    r = nxt[0]
                    nm0, b0, f0, r0, o0 = sections[-1]
                    if used == 0 and ri > 0:        # (an empty area: it changes places with that one, for later)
                        regions[ri], regions[r] = regions[r], regions[ri]; held[ri], held[r] = held[r], held[ri]
                    else:
                        regions.insert(ri + 1, regions.pop(r)); held.insert(ri + 1, held.pop(r))
                        held[ri] = used; ri += 1; used = 0
                    sections[-1] = (nm0, b0, f0, ri, regions[ri][0])
                    continue
                held[ri] = used + fill(run0, last_ok) + MARGIN
                ri += 1
                if ri >= len(regions): sys.exit('bank %d does not fit: %d bytes left' % (b, sum(size[x] for x in order[last_ok:])))
                ncut += 1; nm = 'S%d' % ncut
                split.append('%d:%04X:%s' % (b, order[last_ok], nm))
                sections.append((nm, b, order[last_ok], ri, regions[ri][0]))
                i = last_ok; run0 = last_ok; used = 0; last_ok = None
                continue
            if i + 1 < len(order) and term(a) and not nocut_between(a, order[i + 1]): last_ok = i + 1
            i += 1
        used += fill(run0, len(order))
        used += MARGIN                  # (a jump on, where the bank runs on)
        held[ri] = used
    if KEYMODE:
        import hashlib
        if os.environ.get("Z48_FIT_KEYDUMP"): open(os.environ["Z48_FIT_KEYDUMP"], "w").write(repr((keyparts, MARGIN, banks)))
        print(hashlib.md5(repr((keyparts, MARGIN, banks)).encode()).hexdigest()); return
    names = [s[0] for s in sections]
    lay = ['; generated by fit48.py: the 48K build\'s sections for banks %s' % ','.join(map(str, banks))]
    chk = ['; generated by fit48.py']
    for k, (nm, b, first, r, org) in enumerate(sections):
        if nm == 'A2': lay.append('A2_ORG equ 0x%04X' % org)
        elif nm == 'A': lay.append('A_ORG equ 0x%04X' % org)
        else: lay += ['    macro section_%s' % nm, '        org 0x%04X' % org, '    endm']
        nxt = sections[k + 1] if k + 1 < len(sections) else None
        lim = nxt[4] if nxt and nxt[3] == r else regions[r][1]
        chk.append('    assert section_%s_end <= 0x%04X' % (nm, lim))
    if 'A2' not in names: lay.append('A2_ORG equ 0x%04X' % regions[0][0])
    open(os.path.join(HERE, 'z48_layout.asm'), 'w').write('\n'.join(lay) + '\n')
    open(os.path.join(HERE, 'z48_layout_check.asm'), 'w').write('\n'.join(chk) + '\n')
    open(os.path.join(HERE, 'z48_held.txt'), 'w').write(''.join('%04X %04X %d\n' % (regions[k][0], regions[k][1], held[k]) for k in range(len(regions))))
    for nm, b, first, r, org in sections:
        print('# %s (bank %d from %04X) at %04X, area %04X-%04X' % (nm, b, first, org, *regions[r]))
    print(','.join(split))

if __name__ == '__main__':
    main()

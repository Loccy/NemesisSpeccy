"""Pack the native build's graphics (native_sets.py's events) for the 128K
build: each piece ZX0-packed, placed in the switched banks' free room, with
the tables nl_load (native.asm) reads.  Writes native_data.asm, native_tables.asm and
the packed pieces in native/ (all generated; build.py runs this when its
inputs change).

Formats (all unpacked by nl_load, native.asm):
  a stage's tiles      the complete set in bank 7's layout (DB00-F5FF: per
                       third, 9 rows of 256 bytes), unpacked straight there;
                       stages 10-12 are stage 9's set and a patch
  sprite patterns      0-39 (the same in every stage) once, unpacked to F800;
                       40-63 per stage, unpacked to FD00
  a patch              a 96-byte mask (bit k: character third*256+char),
                       the 9 bytes of each marked character in order, an
                       8-byte mask of sprite patterns and their 32 bytes each;
                       unpacked into page D's work area (E800) and copied in
  the dissolve         stages 7 and 8: a patch of 1.0's tiles after the
                       dissolve's colour pass, for the characters where
                       native.asm's rule (dz_col) gives something else;
                       applied after the colour pass's last chunk
  star attributes      per stage, for F6 and F7 in each third: the attribute
                       each takes when its star first shows a pixel (the tile
                       is blank until then); rows 1-7 stay 0 and row 0 is
                       the star's own row (checked here)
"""
import os, sys, pickle, subprocess, tempfile, hashlib
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import native_sets
from tilemodel import convert

ZX0 = os.environ.get('ZX0', 'zx0')
# Free room in the switched banks for the packed pieces: (page, first, end).
REGIONS = [('B', 0xC000, 0xF1D1),       # MSX banks 4 and 5's graphics and lists (bank 5's object shapes follow)
           ('B', 0xF2E3, 0x10000),      # the rest of bank 5's room, the colour fit and its cache
           ('C', 0xE800, 0x10000),      # the copy of the MSX colour table
           ('E', 0xE3C0, 0xE769),       # bank 9's title graphics
           ('E', 0xE844, 0xEEC1),       # bank 10's ending graphics
           ('D', 0xFC00, 0x10000),      # after the patches' work area
           ('C', 0xE0C7, 0xE800),       # after page C's code (asserted below; the pacing left page C in 1.2)
           ('D', 0xE680, 0xE800),       # after page D's code (asserted below)
           ('E', 0xF101, 0xF20F), ('E', 0xF9F2, 0xFB04), ('E', 0xFF7B, 0x10000),   # free in page E
           ('A', 0xFEE8, 0x10000)]      # after MSX banks 1 and 2 in page A (1.2.1; from a test build's end, 10 bytes past the game's FEDE)
WORK = ('D', 0xE800, 0xFC00)            # patches are unpacked here (the copy of the MSX pattern table), up to the pieces at FC00

def zx0(b):
    with tempfile.TemporaryDirectory() as d:
        p = os.path.join(d, 'x'); open(p, 'wb').write(b)
        subprocess.run([ZX0, '-f', p, p + '.z'], capture_output=True, check=True)
        return open(p + '.z', 'rb').read()

def patch(tiles, spr):
    ks = sorted(tiles)
    mask = bytearray(96)
    for k in ks: mask[k >> 3] |= 1 << (k & 7)
    smask = bytearray(8)
    for i in spr: smask[i >> 3] |= 1 << (i & 7)
    return bytes(mask) + b''.join(tiles[k] for k in ks) + bytes(smask) + b''.join(spr[i] for i in sorted(spr))

def star_attrs(n):
    """Stage n: F6 and F7's attribute in each third once lit (Konami's star row
    is one pixel, from E062's rotating bit), checked to be the same for every
    pixel position, with the pixel the only set bit."""
    m = native_sets.machine(); m.mem[0xE061] = n
    native_sets.gfxcap.call(m, 0x422A)
    v = m.vdp.vram; out = []
    for t in range(3):
        for c in (0xF6, 0xF7):
            o = t * 0x800 + c * 8
            col = [v[o + r] for r in range(8)]
            assert [v[0x2000 + o + r] for r in range(8)] == [0] * 8, 'star %d:%02X not blank when loaded' % (t, c)
            attrs = set()
            for bit in range(8):
                pat = [0x80 >> bit] + [0] * 7
                rows, attr = convert(pat, col, t, c, 5, n, 0x195)
                assert rows == pat, 'star %d:%02X in stage %d: rows %s' % (t, c, n, rows)
                attrs.add(attr)
            assert len(attrs) == 1 and (attrs.pop() if False else True)
            a = convert([0x80] + [0] * 7, col, t, c, 5, n, 0x195)[1]
            assert a & 7 != (a >> 3) & 7
            rows0, a0 = convert([0] * 8, col, t, c, 5, n, 0x195)
            assert rows0 == [0] * 8 and a0 == 0, 'a blank star should convert to attribute 0'
            out.append(a)
    return bytes(out)

def main():
    ev = native_sets.events()
    pieces = {}                  # content -> name
    order = []
    def piece(name, data):
        z = zx0(data)
        if z in pieces: return pieces[z]
        pieces[z] = name; order.append((name, z)); return name
    stage = {}
    common = None
    for n in range(1, 13):
        e = ev[('stage', n)]
        if n <= 9:
            t = piece('st%d_tiles' % n, native_sets.planar(e['tiles'])); tp = None
        else:
            base = ev[('stage', 9)]['tiles']
            t = stage[9][0]
            tp = piece('st%d_patch' % n, patch({k: v for k, v in e['tiles'].items() if v != base[k]}, {}))
        c = b''.join(e['spr'][i] for i in range(40))
        if common is None: common = c
        assert c == common, 'sprite patterns 0-39 differ in stage %d' % n
        if n >= 10 and all(e['spr'][i] == ev[('stage', 9)]['spr'][i] for i in e['spr_written']):
            s = stage[9][2]      # bonus stages 10-12: stage 9's patterns (they differ only in ones never shown)
        else:
            s = piece('st%d_spr' % n, b''.join(e['spr'][i] for i in range(40, 64)))
        stage[n] = (t, tp, s, star_attrs(n))
    cs = piece('spr_common', common)
    def one(kind, ns):
        datas = {n: patch(ev[(kind, n)]['tiles'], ev[(kind, n)]['spr']) for n in ns}
        return {n: piece('%s%d' % (kind, n), d) for n, d in datas.items()}
    big = one('bigcore', range(1, 7))
    pre = one('prestage', range(1, 9)); assert len(set(pre.values())) == 1
    go = one('gameover', range(1, 9)); assert len(set(go.values())) == 1
    mar = one('marcador', range(1, 9)); assert len(set(mar.values())) == 1
    dzp = {n: piece('dz%d' % n, patch(ev[('stage', n)]['dz'], {})) for n in (7, 8)}
    title = piece('title', patch(ev[('title', 0)]['tiles'], ev[('title', 0)]['spr']))
    end = piece('ending', patch(ev[('ending',)]['tiles'], ev[('ending',)]['spr']))
    work = max([len(patch(e['tiles'], e['spr'])) for k, e in ev.items() if not e['full']] +
               [len(patch(ev[('stage', n)]['dz'], {})) for n in (7, 8)])
    assert WORK[1] + work <= WORK[2], 'a patch does not fit the work area'
    # place: largest first, each into the region it fills best (the room
    # left smallest), searching on when that leaves a later piece no room
    free = [list(r) for r in REGIONS]; place = {}
    items = sorted(order, key=lambda x: -len(x[1]))
    failed = set()      # (piece, the rooms left, as sizes): known to leave a later piece no room
    print('native_pack: %d pieces, %d bytes, in %d bytes of room' % (
        len(items), sum(len(z) for n, z in items), sum(b - a for p, a, b in REGIONS)), flush=True)
    def fit(i):
        if i == len(items): return True
        key = (i, tuple(sorted(r[2] - r[1] for r in free)))
        if key in failed: return False
        name, z = items[i]
        tried = set()
        for r in sorted((r for r in free if r[2] - r[1] >= len(z)), key=lambda r: r[2] - r[1]):
            if r[2] - r[1] in tried: continue          # the same room again: no new outcome
            tried.add(r[2] - r[1])
            place[name] = (r[0], r[1]); r[1] += len(z)
            if fit(i + 1): return True
            r[1] -= len(z); del place[name]
        failed.add(key)
        return False
    def quick():
        # first-fit, largest piece first, over many orders of the rooms: finds a
        # layout in moments when the room is tight, where the search above can
        # take hours (1.2.1)
        import random
        rnd = random.Random(1)
        for attempt in range(200000):
            rooms = [list(r) for r in REGIONS]
            if attempt: rnd.shuffle(rooms)
            pl = {}
            for name, z in items:
                for r in rooms:
                    if r[2] - r[1] >= len(z):
                        pl[name] = (r[0], r[1]); r[1] += len(z); break
                else:
                    break
            else:
                place.update(pl); return True
        return False
    if not (quick() or fit(0)):
        raise SystemExit('native_pack: the pieces (%d bytes) do not fit the free room (%d bytes in %d regions)' % (
            sum(len(z) for n, z in items), sum(b - a for p, a, b in REGIONS), len(REGIONS)))
    os.makedirs(os.path.join(HERE, 'native'), exist_ok=True)
    asm = ['; generated by native_pack.py: the native build\'s graphics (do not edit)']
    total = 0
    for name, z in order:
        open(os.path.join(HERE, 'native', name + '.zx0'), 'wb').write(z)
        pg, a = place[name]; total += len(z)
        asm += ['    section_data PAGE_%s,0x%04X' % (pg, a), 'nlb_%s:' % name,
                '    incbin "native/%s.zx0"' % name, 'nlb_%s_end:' % name]
    asm += ['    assert page_c_end <= 0xE0C7', '    assert page_d_end <= 0xE680', '    assert section_A_end <= 0xFEE8']
    for pg, a, b in REGIONS:
        users = [n for n in place if place[n][0] == pg and a <= place[n][1] < b]
        if users:
            last = max(users, key=lambda n: place[n][1])
            asm.append('    assert nlb_%s_end <= 0x%04X' % (last, b & 0xFFFF if b < 0x10000 else 0xFFFF))
    def d(name): return '    db PAGE_%s\n    dw nlb_%s' % (place[name][0], name)
    tab = ['\n; tables (fixed memory: native.asm includes this part)', 'nl_tables:']
    tab.append('nl_stage_tab:      ; stage 1-12: tiles, tiles patch (page FF: none), sprites 40-63, star attributes')
    for n in range(1, 13):
        t, tp, s, sa = stage[n]
        tab += [d(t), d(tp) if tp else '    db 0xFF\n    dw 0', d(s), '    db ' + ','.join('0x%02X' % x for x in sa)]
    tab += ['nl_spr_common:', d(cs), 'nl_bigcore_tab:'] + [d(big[n]) for n in range(1, 7)]
    for n in (7, 8):         # the stages with Konami's dissolve: tiles stored the other way round
        m = bytearray(96)
        for k in ev[('stage', n)]['inv']: m[k >> 3] |= 1 << (k & 7)
        tab += ['nl_inv%d:' % n] + ['    db ' + ','.join('0x%02X' % x for x in m[i:i + 16]) for i in range(0, 96, 16)]
    tab += ['nl_dz7_d:', d(dzp[7]), 'nl_dz8_d:', d(dzp[8])]     # the dissolve's colour pass: 1.0's tiles where dz_col's rule is not
    tab += ['nl_title_d:', d(title), 'nl_prestage_d:', d(pre[1]), 'nl_gameover_d:', d(go[1]),
            'nl_marcador_d:', d(mar[1]), 'nl_ending_d:', d(end)]
    open(os.path.join(HERE, 'native_data.asm'), 'w').write('\n'.join(asm) + '\n')
    open(os.path.join(HERE, 'native_tables.asm'), 'w').write('\n'.join(tab) + '\n')
    print('native graphics: %d pieces, %d bytes packed; largest patch %d bytes unpacked' % (len(order), total, work))
    for pg, a, b in free:
        if b > a: print('  free: page %s %04X-%04X (%d)' % (pg, a, b - 1, b - a))

if __name__ == '__main__':
    main()

"""Build-time conversion of Konami's graphics for the native 128K build
(claude/native-128k-plan.md, step 1): every load event replayed from the
cartridge ROM in msxsim, and every character it writes converted to a
Spectrum tile as 1.0 converts it at run time (tilemodel.py).

Events (the census of 8 November 2026 found no others):
  stage N     (1-12)  Konami's stage load, 0:422A; a complete set
  bigcore N   (1-6)   the Big Core's characters, 0:4A6D; a patch
  prestage N  (1-8)   the screen before each life, 0:53D4-0:543F and 0:5874
  gameover N  (1-8)   0:5874
  title N     (0, 8)  the title's loads from boot (after game over: stage 8's rules)
  ending              0:4B04-0:4B2C (bank 10's graphics, sprites)
  marcador N  (1-8)   0:5851 alone (the ending's 0:4C2E)
A complete set gives every character; a patch only those the event writes
(the rest stay as the screen had them, as on the MSX).  Sprite patterns:
the 64 as the event leaves them (stage loads) or those it writes.

usage: native_sets.py OUT.pkl   (prints the sizes, ZX0, of each event's data)
"""
import os, sys, pickle, subprocess, tempfile
NEM = os.environ.get('NEM_ROOT') or os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
sys.path.insert(0, NEM + '/spec'); sys.path.insert(0, NEM + '/msxsim'); sys.path.insert(0, NEM + '/reloc')
_argv = sys.argv; sys.argv = ['x']
import gfxcap, msxsim
import lockstep_spec as LS
sys.argv = _argv
import tilemodel
from tilemodel import convert
INV = None          # a set: the characters converted the other way round are added to it

MOAI = set()     # stage 3: characters 1.0 first shows before distance 195h (the census), (third, char)
for l in open(os.path.join(NEM, 'spec', 'native_moai.txt')):
    l = l.split('#')[0].strip()
    if l: t, c = l.split(':'); MOAI.add((int(t), int(c, 16)))

class Tracked(bytearray):
    """VRAM that notes which bytes are written."""
    def __init__(self, b):
        bytearray.__init__(self, b); self.w = set()
    def __setitem__(self, a, v):
        bytearray.__setitem__(self, a, v); self.w.add(a)

ROM_PATCH = None    # [(ROM index, old, new)]: the Next's data changes (native_next.py)

def patch_rom(m):
    if ROM_PATCH:
        m.mem.rom = bytearray(m.mem.rom)
        for i, old, new in ROM_PATCH:
            assert m.mem.rom[i] in (old, new), 'ROM %05X is %02X, expected %02X' % (i, m.mem.rom[i], old)
            m.mem.rom[i] = new

def machine():
    m = gfxcap.boot_to_idle()
    patch_rom(m)
    m.vdp.vram = Tracked(m.vdp.vram)
    return m

def run(m, start, end, limit=20_000_000):
    """Run from start until PC == end, from Konami's idle point."""
    regs = m.sim.registers; ops = m.sim.opcodes; mem = m.mem
    saved = list(regs); regs[24] = start; regs[26] = 0
    for _ in range(limit):
        pc = regs[24]
        if pc == end: break
        if pc < 0x4000 and pc not in msxsim.STUB_RANGE: raise msxsim.Unknown('%04X' % pc)
        ops[mem[pc]]()
        regs[26] = 0
    else:
        raise RuntimeError('%04X did not reach %04X' % (start, end))
    sp = regs[12]; regs[:] = saved
    return m

def written(v):
    """Characters (third*256+char) and sprite patterns an event wrote."""
    ch = set(); sp = set()
    for a in v.w:
        if a < 0x1800: ch.add((a >> 11) * 256 + ((a >> 3) & 255))
        elif a < 0x2000: sp.add((a - 0x1800) >> 5)
        elif a < 0x3800: b = a - 0x2000; ch.add((b >> 11) * 256 + ((b >> 3) & 255))
    v.w = set()
    return ch, sp

S3_TILES = {}    # stage 3's load: our tiles for the Moai heads and the rocks (1.2.1)
for l in open(os.path.join(NEM, 'spec', 'stage3_tiles.txt')):
    l = l.split('#')[0].split()
    if l:
        t, c = l[0].split(':')
        S3_TILES[int(t) * 256 + int(c, 16)] = bytes(int(x, 16) for x in l[1:10])

def tile(v, k, state, stage, dist=None):
    t, c = divmod(k, 256); o = t * 0x800 + c * 8
    pat = [v[0x2000 + o + r] for r in range(8)]; col = [v[o + r] for r in range(8)]
    if dist is None: dist = 0 if (stage != 3 or (t, c) in MOAI) else 0x195
    rows, attr = convert(pat, col, t, c, state, stage, dist)
    if INV is not None and tilemodel.LAST_INVERTED: INV.add(k)
    return bytes(rows) + bytes([attr])

def spr(v, i): return bytes(v[0x1800 + i * 32:0x1820 + i * 32])

def events():
    ev = {}
    # title: the MSX from power-on to its title (the Spectrum build's front end)
    # (after the first tick, which clears the video memory: after a game over
    # the title's loads go over what the game left, so they are a patch)
    o = LS.Orig(); LS.patch_front_end(o); o.vdp.vram = Tracked(o.vdp.vram); o.boot()
    regs = o.sim.registers; ops = o.sim.opcodes
    while regs[24] != 0x5749:                  # past arranca_la_maquina's FILVRM (0:5746)
        ops[o.mem[regs[24]]](); regs[25] += 1
    assert len(o.vdp.vram.w) == 0x4000, 'the video memory should have been cleared'
    o.vdp.vram.w = set()
    for i in range(40): LS.TICK[0] = i; LS.sync_tick(o)
    ch, sp = written(o.vdp.vram)
    # the Spectrum title's own full stop after the version (title_dot,
    # plat_spec.asm): character 0E of the top third
    v = o.vdp.vram
    for r, (p_, c_) in enumerate(zip((0, 0, 0, 0, 0, 0, 0x18, 0x18), (0xF0,) * 8)):
        bytearray.__setitem__(v, 0x2070 + r, p_); bytearray.__setitem__(v, 0x0070 + r, c_)
    ch.add(0x0E)
    for sg in range(9):
        ev[('title', sg)] = dict(full=False, tiles={k: tile(o.vdp.vram, k, 1, sg) for k in ch}, spr={})
    # the stages, each after the one that comes before it in play (for the
    # sprite patterns it leaves alone: bonus stage 9 shows stage 2's pattern 50)
    before = {9: 2, 10: 3, 11: 4, 12: 7}
    for n in range(1, 13):
        m = machine()
        p = before.get(n, n - 1)
        if p:
            m.mem[0xE061] = p; gfxcap.call(m, 0x422A); written(m.vdp.vram)
        m.mem[0xE061] = n; gfxcap.call(m, 0x422A)
        ch, sp = written(m.vdp.vram)
        v = m.vdp.vram
        global INV
        INV = set()
        tl = {k: (tile(v, k, 5, n) if k in ch else bytes(9)) for k in range(768)}
        if n == 3: tl.update(S3_TILES)     # (1.2.1) the Moai heads and their rocks: our tiles
        inv, INV = INV, None
        ev[('stage', n)] = dict(full=True, tiles=tl, inv=inv,
                                 spr={i: spr(v, i) for i in range(64)}, spr_written=set(sp))
        if n in (7, 8): ev[('stage', n)]['dz'] = dz_patch(v, tl, inv)
        if n <= 6:
            gfxcap.call(m, 0x4A6D); ch, sp = written(m.vdp.vram)
            ev[('bigcore', n)] = dict(full=False, tiles={k: tile(v, k, 5, n, 0x195 if n == 3 else 0) for k in ch},
                                       spr={i: spr(v, i) for i in sp})
        if n <= 8:
            pm = machine(); pm.mem[0xE061] = n
            run(pm, 0x53D4, 0x543F); gfxcap.call(pm, 0x5874)
            ch, sp = written(pm.vdp.vram)
            ev[('prestage', n)] = dict(full=False, tiles={k: tile(pm.vdp.vram, k, 4, n) for k in ch}, spr={})
            gm = machine(); gm.mem[0xE061] = n; gfxcap.call(gm, 0x5874)
            ch, sp = written(gm.vdp.vram)
            ev[('gameover', n)] = dict(full=False, tiles={k: tile(gm.vdp.vram, k, 7, n) for k in ch}, spr={})
        mm = machine(); mm.mem[0xE061] = n; gfxcap.call(mm, 0x5851)      # the status line and font alone (0:4C2E)
        ch, sp = written(mm.vdp.vram)
        if n <= 8: ev[('marcador', n)] = dict(full=False, tiles={k: tile(mm.vdp.vram, k, 5, n) for k in ch}, spr={})
    em = machine(); em.mem[0xE061] = 8
    run(em, 0x4B04, 0x4B2C)
    ch, sp = written(em.vdp.vram)
    ev[('ending',)] = dict(full=False, tiles={k: tile(em.vdp.vram, k, 5, 8) for k in ch},
                           spr={i: spr(em.vdp.vram, i) for i in sp})
    return ev

def dz_dissolved(k):
    """Konami's dissolve works on characters 00-F5 of each third, except
    00-43 of the bottom third (the score and the bar)."""
    t, c = divmod(k, 256)
    return c <= 0xF5 and not (t == 2 and c < 0x44)

def dz_rule(rows, attr, inv):
    """The native colour pass (native.asm, dz_col): a tile stored the other
    way round goes back to ink on paper with its old paper as the ink; then
    black paper, bright kept."""
    if inv:
        return [r ^ 0xFF for r in rows], (attr & 0x40) | ((attr >> 3) & 7)
    return list(rows), attr & 0x47

def dz_patch(v, tl, inv):
    """The characters whose tile after the dissolve's colour pass is not
    what dz_rule gives (as shown: the attribute of a tile with no pixels does
    not count): 1.0's (tilemodel.dz_post) for them."""
    out = {}
    for k in range(768):
        if not dz_dissolved(k) or tl[k] == bytes(9): continue      # (characters the load leaves alone are blank)
        t, c = divmod(k, 256); o = t * 0x800 + c * 8
        pat = [v[0x2000 + o + r] for r in range(8)]; col = [v[o + r] for r in range(8)]
        rows, attr = list(tl[k][:8]), tl[k][8]
        pr, pa = tilemodel.dz_post(pat, col, rows, attr)
        qr, qa = dz_rule(rows, attr, k in inv)
        if pr != qr or (any(pr) and pa != qa):
            out[k] = bytes(pr) + bytes([pa])
    return out

# ---- the Spectrum Next (claude/native-128k-plan.md, step 3) --------------------
# The Next draws characters outside its pool from its own store of TMS-style
# rows (pages C and D, E800: a colour and a pattern byte a row) and Konami's
# sprite patterns from bank 7's F800.  Its events are what Konami's loaders
# wrote, byte for byte (always whole characters: checked), not converted.

def raw(v):
    """The bytes an event wrote below the name table: {address: value}."""
    w = {a for a in v.w if a < 0x3800}; v.w = set()
    return {a: v[a] for a in w}

def next_patch(d):
    """An event's writes as the Next's pieces: (colours, patterns, sprites),
    each {index: bytes} (character third * 256 + char: 8 bytes; sprite
    pattern: 32 bytes), whole characters and patterns only."""
    col, pat, spr = {}, {}, {}
    for a in d:
        if a < 0x1800: col.setdefault(a >> 3, set()).add(a)
        elif a < 0x2000: spr.setdefault((a - 0x1800) >> 5, set()).add(a)
        else: pat.setdefault((a - 0x2000) >> 3, set()).add(a)
    for t, n in ((col, 8), (pat, 8), (spr, 32)):
        for k, ad in t.items():
            assert len(ad) == n, 'a partly written character or sprite pattern: %s' % sorted(ad)
            t[k] = bytes(d[a] for a in sorted(ad))
    return col, pat, spr

def stage_vram(n):
    """Konami's stage n load (after the stage before it in play, as
    events()): video memory 0000-37FF and the addresses it wrote."""
    m = machine()
    p = {9: 2, 10: 3, 11: 4, 12: 7}.get(n, n - 1)
    if p:
        m.mem[0xE061] = p; gfxcap.call(m, 0x422A)
    m.vdp.vram.w = set()
    m.mem[0xE061] = n; gfxcap.call(m, 0x422A)
    return bytes(m.vdp.vram[:0x3800]), {a for a in m.vdp.vram.w if a < 0x3800}

def next_events():
    """The Next's patches (next_patch), by event: title, bigcore 1-6,
    prestage, gameover, marcador (the same for every stage: checked), ending."""
    ev = {}
    o = LS.Orig(); LS.patch_front_end(o); patch_rom(o); o.vdp.vram = Tracked(o.vdp.vram); o.boot()
    regs = o.sim.registers; ops = o.sim.opcodes
    while regs[24] != 0x5749:
        ops[o.mem[regs[24]]](); regs[25] += 1
    o.vdp.vram.w = set()
    for i in range(40): LS.TICK[0] = i; LS.sync_tick(o)
    d = raw(o.vdp.vram)
    for r, (p_, c_) in enumerate(zip((0, 0, 0, 0, 0, 0, 0x18, 0x18), (0xF0,) * 8)):     # title_dot
        d[0x2070 + r] = p_; d[0x0070 + r] = c_
    ev['title'] = next_patch(d)
    for n in range(1, 7):
        m = machine(); m.mem[0xE061] = n; gfxcap.call(m, 0x422A); m.vdp.vram.w = set()
        gfxcap.call(m, 0x4A6D)
        ev['bigcore%d' % n] = next_patch(raw(m.vdp.vram))
    for name, go in (('prestage', lambda m: (run(m, 0x53D4, 0x543F), gfxcap.call(m, 0x5874))),
                     ('gameover', lambda m: gfxcap.call(m, 0x5874)),
                     ('marcador', lambda m: gfxcap.call(m, 0x5851))):
        seen = set()
        for n in range(0, 9):
            m = machine(); m.mem[0xE061] = n; go(m)
            d = raw(m.vdp.vram); seen.add(tuple(sorted(d.items())))
        assert len(seen) == 1, name
        ev[name] = next_patch(d)
    m = machine(); m.mem[0xE061] = 8; run(m, 0x4B04, 0x4B2C)
    ev['ending'] = next_patch(raw(m.vdp.vram))
    return ev

def zx0(b):
    with tempfile.TemporaryDirectory() as d:
        p = os.path.join(d, 'x'); open(p, 'wb').write(b)
        subprocess.run([os.environ.get('ZX0', 'zx0'), '-f', p, p + '.z'], capture_output=True, check=True)
        return len(open(p + '.z', 'rb').read())

def planar(tiles):
    """A complete set in bank 7's layout: per third, 9 rows of 256 bytes."""
    out = bytearray(6912)
    for k, t in tiles.items():
        th, c = divmod(k, 256)
        for r in range(9): out[(9 * th + r) * 256 + c] = t[r]
    return bytes(out)

if __name__ == '__main__':
    ev = events()
    pickle.dump(ev, open(sys.argv[1], 'wb'))
    tot = 0; seen = {}
    for key, e in ev.items():
        if e['full']:
            data = planar(e['tiles']) + b''.join(e['spr'][i] for i in range(64))
        else:
            ks = sorted(e['tiles'])
            mask = bytearray(96)
            for k in ks: mask[k >> 3] |= 1 << (k & 7)
            data = bytes(mask) + b''.join(e['tiles'][k] for k in ks) + b''.join(e['spr'][i] for i in sorted(e['spr']))
        dup = seen.get(data); seen.setdefault(data, key)
        z = 0 if dup else zx0(data); tot += z
        print('%-14s %3d chars %2d sprites  %5d bytes ZX0%s' % (' '.join(map(str, key)), len(e['tiles']), len(e['spr']), z,
              '  (same as %s)' % ' '.join(map(str, dup)) if dup else ''))
    print('total %d bytes' % tot)

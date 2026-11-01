"""After every screen flip, compare the visible buffer with the stage map at the
current world position.  Cells listed in that buffer's sprite erase list are
skipped (they legitimately contain sprites).  usage: emu_verify.py PROJECTDIR SECONDS ROM"""
import sys
sys.path.insert(0, sys.argv[1] + '/tools')
from pathlib import Path
from emu_bench import *
from mini_asm import assemble
from extract import Nemesis
from convert import tile_table

work = Path(sys.argv[1]); secs = float(sys.argv[2])
_, L = assemble((work / 'build/scroller_expanded.asm').read_text())
flip_done = L['wait_and_flip.flip']
# find the instruction after OUT in .flip: scan code for ED 79 after flip label
code = (work / 'build/code.bin').read_bytes()
i = flip_done - 0x8000
while code[i:i+2] != b'\xed\x79': i += 1
stop = 0x8000 + i + 2
n = Nemesis(sys.argv[3] if len(sys.argv) > 3 else str(work / '../nem.rom')); m = n.stage_map(1); gfx = tile_table(n.stage_vram(1))
cols = bytes(m[r][c] for c in range(len(m[0])) for r in range(22))

snap = Snapshot.get(str(work / 'build/nemesis_stage1_scroll_128k.sna'))
snap.sp = (snap.sp + 2) % 65536
sim = from_snapshot(CCMIOSimulator, snap, {}, {'ay': [None]*16}, {'fast_djnz': False, 'fast_ldir': False})
mem = sim.memory; mem.out7ffd(snap.out7ffd)
tr = Tracer(sim, snap.border, snap.out7ffd, snap.outfffd, list(snap.ay), snap.outfe, False); sim.set_tracer(tr)
regs = sim.registers; pc = snap.pc
b2 = mem.banks[2]
def rd(a): return b2[a - 0x8000] if 0x8000 <= a < 0xc000 else None
end = regs[25] + int(secs * 50 * FRAME); flips = bad_flips = 0; worst = None
while regs[25] < end:
    f = (regs[25] // FRAME)
    tr.keyboard = keys_for(f)
    sim.trace(pc, stop, 0, min(end, regs[25] + FRAME), 1, None, None, None, None, None)
    pc = regs[24]
    if pc != stop: continue
    flips += 1
    flag = tr.out7ffd & 8
    scr = mem.banks[7 if flag else 5]
    world = rd(L['world_ptr']) | rd(L['world_ptr'] + 1) << 8
    col0 = (world - 0x9500) // 22
    elist = L['erase_list7'] if flag else L['erase_list5']
    skip = set(); p = elist
    while rd(p) != 0xff:
        cx, cy, w, h = rd(p), rd(p+1), rd(p+2), rd(p+3); p += 4
        skip |= {(cx + a, cy + b) for a in range(w) for b in range(h)}
    errs = []
    for y in range(22):
        third = y >> 3
        for x in range(32):
            if (x, y) in skip: continue
            tid = cols[((col0 + x) % 456) * 22 + y]
            t = gfx[third*2304 + tid*9: third*2304 + tid*9 + 9]
            lo = ((y & 7) << 5) | x
            pix = [scr[((y & 0x18) << 8) + (r << 8) + lo] for r in range(8)]
            at = scr[0x1800 + y*32 + x]
            if pix != list(t[:8]) or at != t[8]: errs.append((x, y))
    if errs:
        bad_flips += 1
        if worst is None or len(errs) > len(worst[1]): worst = (flips, errs[:12], col0)
print(f'flips checked: {flips}, flips with background errors: {bad_flips}')
if worst: print('worst:', worst)

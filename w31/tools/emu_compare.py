"""Run two builds with identical per-tick input and compare the visible screen
right after the flip that shows tick N.  usage: compare.py OLD NEW N1,N2,..."""
import os as _os
NEM_ROOT = _os.environ.get('NEM_ROOT') or _os.path.normpath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '..', '..'))  # the tree's root
import sys
sys.path.insert(0, sys.argv[2] + '/tools')
from pathlib import Path
from emu_bench import *
from mini_asm import assemble

def keys_tick(t):
    kb = [0]*8
    if (t//3) % 2 == 0: kb[7] |= 1
    ph = (t//60) % 4
    if ph == 1: kb[2] |= 1
    if ph == 3: kb[1] |= 1
    if (t//200) % 3 == 1: kb[5] |= 1   # P right
    if (t//200) % 3 == 2: kb[5] |= 2   # O left
    return kb

def screens(work, flip_label, counter_label, ticks):
    work = Path(work)
    _, L = assemble((work / 'build/scroller_expanded.asm').read_text())
    code = (work / 'build/code.bin').read_bytes()
    i = L[flip_label] - 0x8000
    while code[i:i+2] != b'\xed\x79': i += 1
    stop = 0x8000 + i + 2
    snap = Snapshot.get(str(work / 'build/nemesis_stage1_scroll_128k.sna')); snap.sp = (snap.sp + 2) % 65536
    sim = from_snapshot(CCMIOSimulator, snap, {}, {'ay': [None]*16}, {'fast_djnz': False, 'fast_ldir': False})
    mem = sim.memory; mem.out7ffd(snap.out7ffd)
    tr = Tracer(sim, snap.border, snap.out7ffd, snap.outfffd, list(snap.ay), snap.outfe, False); sim.set_tracer(tr)
    b1 = mem.banks[1]
    for j in range(0x2000):
        if b1[j] == 0xED and b1[j+1] == 0x5F: b1[j] = 0x3E; b1[j+1] = 0x00   # ld a,r -> ld a,0
    regs = sim.registers; pc = snap.pc; cnt = L[counter_label] - 0x8000
    done = 0; out = {}; want = sorted(ticks)
    tr.keyboard = keys_tick(0)
    while want:
        sim.trace(pc, stop, 0, 0, 1, None, None, None, None, None); pc = regs[24]
        done += 1                       # this flip shows tick number `done`
        tr.keyboard = keys_tick(done)
        if done == want[0]:
            out[done] = bytes(mem.banks[7 if tr.out7ffd & 8 else 5][:6912]); want.pop(0)
    return out

ticks = [int(x) for x in sys.argv[3].split(',')]
a = screens(sys.argv[1], 'render_sprite_frame', 'frame_counter', ticks)
b = screens(sys.argv[2], 'wait_and_flip.flip', 'frame_counter', ticks)
for t in ticks:
    diff = sum(x != y for x, y in zip(a[t], b[t]))
    print(f'tick {t}: {diff} differing bytes of 6912')
    if diff:
        scr_png(a[t], NEM_ROOT + f'/cmp_old_{t}.png'); scr_png(b[t], NEM_ROOT + f'/cmp_new_{t}.png')

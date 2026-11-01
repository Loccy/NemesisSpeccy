"""The Kempston interface and hold-to-select, run from the build in a bare
simulator: kempston_detect (no interface; an interface at rest; one whose
bits 5 and 7 are not 0 at rest), kempston on random port values against
the expected MSX joystick byte, and fire_hold over random fire sequences
against its rule (trigger B pressed once fire has been held HOLD_TICKS
ticks before this one, until it is let go)."""
import os as _os
NEM_ROOT = _os.environ.get('NEM_ROOT') or _os.path.normpath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '..'))  # the tree's root
import sys, re, random
from skoolkit.simulator import Simulator
from skoolkit.snapshot import Snapshot
syms = {}
for l in open(NEM_ROOT + '/spec/nemesis.sym'):
    m = re.match(r'(\S+):\s+EQU\s+0x([0-9A-F]+)', l)
    if m: syms[m.group(1)] = int(m.group(2), 16) & 0xFFFF
HOLD = int(_os.environ.get('NEM_HOLD', '12'))
snap = Snapshot.get(NEM_ROOT + '/spec/nemesis.sna'); B = snap.memory.banks
base = bytearray(0x10000); base[0x4000:0x8000] = B[5]; base[0x8000:0xC000] = B[2]; base[0xC000:] = B[0]
KB = syms['kb_cache'] + 9

class Port:
    value = 0xFF
    def read_port(self, registers, port):
        return self.value if port & 0xFF == 0x1F else 0xFF

def machine():
    mem = bytearray(base)
    d = syms['kempston_detect']
    i = mem.index(bytes([0xFB, 0x76, 0xF3]), d, d + 8)    # ei / halt / di: not needed here
    mem[i:i + 3] = b'\0\0\0'
    sim = Simulator(mem); p = Port(); sim.set_tracer(p)
    return mem, sim, p

def call(mem, sim, addr):
    r = sim.registers
    r[12] = 0xBF00; mem[0xBF00] = 0; mem[0xBF01] = 0     # return to 0
    r[24] = addr
    while r[24] != 0: sim.run()

bad = 0
# kempston_detect
for idle, want_on, want_b2 in ((0xFF, False, 0xA0), (0x00, True, 0xA0), (0xA0, True, 0x00), (0x20, True, 0x00), (0x80, True, 0x00)):
    mem, sim, p = machine(); p.value = idle
    call(mem, sim, syms['kempston_detect'])
    on = mem[syms['kempston']] == 0; b2 = mem[syms['kemp_b2'] + 1]
    if (on, b2) != (want_on, want_b2):
        bad += 1; print('detect with the port at rest %02X: interface %s, button mask %02X' % (idle, on, b2))
# kempston
for b2_used in (True, False):
    mem, sim, p = machine(); p.value = 0xA0 if not b2_used else 0x00
    call(mem, sim, syms['kempston_detect'])
    for trial in range(2000):
        keys = random.choice([0x3F, random.getrandbits(6)])
        v = random.getrandbits(8)
        mem[KB] = keys; p.value = v
        call(mem, sim, syms['kempston'])
        exp = keys
        for kb, msx in ((3, 0), (2, 1), (1, 2), (0, 3), (4, 4)):
            if v >> kb & 1: exp &= ~(1 << msx)
        if b2_used and v & 0xA0: exp &= ~0x20
        if mem[KB] != exp:
            bad += 1
            if bad < 6: print('kempston: port %02X, keys %02X: got %02X, want %02X' % (v, keys, mem[KB], exp))
# fire_hold
mem, sim, p = machine()
held = 0; checked = 0; presses = 0
for trial in range(20000):
    fire = random.random() < (0.97 if held else 0.2)
    keys = random.getrandbits(6) | 0x30
    if fire: keys &= ~0x10
    mem[KB] = keys
    call(mem, sim, syms['fire_hold'])
    exp = keys & ~0x20 if fire and held >= HOLD else keys
    if fire and held == HOLD - 1: presses += 1          # a hold reaching HOLD ticks
    held = held + 1 if fire and held < HOLD else (held if fire else 0)
    checked += 1
    if mem[KB] != exp:
        bad += 1
        if bad < 6: print('fire_hold: trial %d keys %02X: got %02X, want %02X' % (trial, keys, mem[KB], exp))
print('detect 5 cases, kempston 4000 values, fire_hold %d ticks (%d holds reached %d ticks): %d wrong' % (checked, presses, HOLD, bad))

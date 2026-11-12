"""Check the compiled-sprite build's draws in the simulator: at each call
from draw_sprite16.cs_call, the screen after it against the pattern ORed in
by Python (as draw_sprite16 would)."""
import os as _os; _NEM = _os.environ.get('NEM_ROOT') or _os.path.normpath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '..', '..', '..')); _SCRATCH = _os.environ.get('NEM_SCRATCH') or _os.path.dirname(_NEM)   # the repository, and the folder beside it for working copies
import os, sys
sys.path.insert(0, (_SCRATCH + '/bis_r/spec')); os.environ['NEM_ALL'] = '1'
from emu import Spectrum, _syms, keys_default
s = Spectrum((_SCRATCH + '/night2/real/cspr_real.sna')); sy = _syms((_SCRATCH + '/night2/real/cspr_real.sym'))
s.mem.banks[0][sy['m1_75F0'] - 0xC000] = 0xC9
sim = s.sim; R = s.regs; tr = s.tr; FR = 70908
CALL = sy['draw_sprite16.cs_call']
common = open((_SCRATCH + '/bis_r/spec/native/spr_common.bin'), 'rb').read()
B2 = s.mem.banks[2]; ship = bytes(B2[sy['ship_pat'] - 0x8000: sy['ship_pat'] - 0x8000 + 32])
tabs = {sy['cs_ship_tab']: ship, sy['cs_bul_tab']: common[34 * 32:35 * 32]}
addr2 = {}
for t, pat in tabs.items():
    for o in range(8): addr2[B2[t - 0x8000 + 2 * o] | B2[t - 0x8000 + 2 * o + 1] << 8] = (pat, o)
n = bad = 0; kinds = {}
for f in range(int(sys.argv[1]) * 50):
    s.hook(advance=True); kb = keys_default(f); ph = f % 400
    if ph < 100: kb[5] |= 1
    elif ph < 200: kb[5] |= 2
    elif ph < 300: kb[2] |= 1
    else: kb[1] |= 1
    tr.keyboard = kb
    end = s.t0 + (f + 1) * FR
    while R[25] < end:
        sim.trace(s.pc, CALL, 0, end, 1, None, None, None, None, None); s.pc = R[24]
        if s.pc != CALL: break
        tgt = B2[CALL + 1 - 0x8000] | B2[CALL + 2 - 0x8000] << 8
        pat, sh = addr2[tgt]
        hl = R[6] << 8 | R[7]; bank = s.mem.banks[5] if hl < 0x8000 else s.mem.banks[tr.out7ffd & 7]
        base = 0x4000 if hl < 0x8000 else 0xC000
        before = bytes(bank[0:6144])
        sim.trace(s.pc, CALL + 3, 0, end + FR, 1, None, None, None, None, None); s.pc = R[24]
        exp = bytearray(before); o = hl - base
        y0 = (o >> 5 & 0xC0) | (o >> 2 & 0x38) | (o >> 8 & 7); cx = o & 31
        for r in range(16):
            y = y0 + r
            if y > 191: break
            if sh == 0: bs = [pat[r], pat[16 + r]]
            else:
                v = (pat[r] << 16 | pat[16 + r] << 8) >> sh; bs = [v >> 16 & 255, v >> 8 & 255, v & 255]
            for k, b in enumerate(bs):
                exp[((y & 0xC0) << 5) | ((y & 7) << 8) | ((y & 0x38) << 2) | (cx + k)] |= b
        n += 1; bad += bytes(bank[0:6144]) != bytes(exp); kinds[(pat == ship, sh)] = kinds.get((pat == ship, sh), 0) + 1
    s.frame = f + 1
print('compiled draws checked', n, 'wrong', bad, 'ship/bullet by offset', sorted(kinds.items()))

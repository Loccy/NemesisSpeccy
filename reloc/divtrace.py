"""Instruction-level divergence finder on the virtual clock: run both machines
to tick t0, then record the ORIGINAL address of every executed Konami
instruction (relocated PCs mapped back through the symbol table) and report
the first point where the control flow differs."""
import os as _os
NEM_ROOT = _os.environ.get('NEM_ROOT') or _os.path.normpath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '..'))  # the tree's root
import sys, re
sys.path.insert(0, NEM_ROOT + '/reloc')
from layoutsim import *
import gen as G
GEN = G.Gen(ROM)
PAGE_NUM = {'A': 0, 'B': 3, 'C': 4, 'D': 6, 'E': 1, 'F': 8}

def reverse_map(syms):
    rv = {}
    for k, v in syms.items():
        m = re.match(r'm(\d+)_([0-9A-F]{4})$', k)
        if m:
            b, a = int(m.group(1)), int(m.group(2), 16)
            if (b, a) in GEN.home: rv.setdefault(v, []).append((b, a))
    return rv

def conv_orig(m, pc):
    if 0x4000 <= pc < 0x6000: c = (0, pc)
    elif 0x6000 <= pc < 0xC000: c = (m.mem.bank[(pc - 0x4000) >> 13], pc)
    else: return None
    if c not in GEN.home: return None        # inside a data-classified item: not visible on the relocated side
    r = m.sim.registers
    return (c, r[0], r[6] << 8 | r[7], r[4] << 8 | r[5], r[2] << 8 | r[3])

def make_conv_rel(rv):
    def conv(m, pc):
        for b, a in rv.get(pc, ()):
            sec = GEN.home[(b, a)]
            if pc < 0xC000 or PAGE_NUM.get(sec) == m.mem.page:
                r = m.sim.registers
                return ((b, a), r[0], r[6] << 8 | r[7], r[4] << 8 | r[5], r[2] << 8 | r[3])
        return None
    return conv

def fmt(c): return '%d:%04X' % c

def compare(A, B, label, window=12, need=24):
    """Compare control flow, re-synchronising across short detours (address
    arithmetic carries differ legitimately between the layouts)."""
    i = j = 0; detours = 0
    while i < len(A) and j < len(B):
        if A[i][0] == B[j][0]:
            i += 1; j += 1; continue
        found = None
        for d in range(1, 2 * window):
            for da in range(0, d + 1):
                db = d - da
                if i + da < len(A) and j + db < len(B) and all(
                        i + da + k < len(A) and j + db + k < len(B) and A[i + da + k][0] == B[j + db + k][0]
                        for k in range(need)):
                    found = (da, db); break
            if found: break
        if found:
            detours += 1; i += found[0]; j += found[1]; continue
        print('%s: diverge at steps %d/%d of %d/%d (%d short detours before)' % (label, i, j, len(A), len(B), detours))
        for k in range(-16, 8):
            fa = A[i + k] if 0 <= i + k < len(A) else None
            fb = B[j + k] if 0 <= j + k < len(B) else None
            sa = '%-8s A=%02X HL=%04X DE=%04X BC=%04X' % ((fmt(fa[0]),) + fa[1:]) if fa else ''
            sb = '%-8s A=%02X HL=%04X DE=%04X BC=%04X' % ((fmt(fb[0]),) + fb[1:]) if fb else ''
            print('  %s %-46s | %s' % ('>>' if k == 0 else '  ', sa, sb))
        return False
    print('%s: identical control flow (%d/%d steps, %d short detours)' % (label, len(A), len(B), detours))
    return len(A) == len(B)

if __name__ == '__main__':
    t0 = int(sys.argv[1]); t1 = int(sys.argv[2]) if len(sys.argv) > 2 else t0 + 1
    orig = Original(); orig.boot(); rel = Relocated(); rel.boot()
    for i in range(t0):
        vclock_tick(orig); vclock_tick(rel)
    cr = make_conv_rel(reverse_map(rel.syms))
    for t in range(t0, t1):
        A = []; B = []
        vclock_tick(orig, A, conv_orig)
        try: vclock_tick(rel, B, cr)
        except RuntimeError as e: print('relocated:', e)
        if not compare(A, B, 'tick %d' % t): break

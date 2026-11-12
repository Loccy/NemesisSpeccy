# allow_dissolve.py, and while the dissolve is shown, both builds' shown
# screens saved every DZ_EVERY ticks (default 8), for the first DZ_FOR ticks
# of each dissolve, to DZ_SHOTS, for checking
# the dissolve's look by eye.
import os
_n = [0]
def allow(tick, msx_ram, ref, cand):
    a = ref.syms['dz_on']
    on = ref.m.mem.banks[2][a - 0x8000] != 0
    if on:
        d = os.environ.get('DZ_SHOTS', 'dz'); os.makedirs(d, exist_ok=True)
        sc = [bytes(b.m.mem.banks[7 if b.m.tr.out7ffd & 8 else 5][:6912]) for b in (ref, cand)]
        open(os.path.join(d, 'diff.txt'), 'a').write('%d %d\n' % (tick, sum(x != y for x, y in zip(*sc))))
        if _n[0] % int(os.environ.get('DZ_EVERY', '8')) == 0 and _n[0] < int(os.environ.get('DZ_FOR', '100000')):
            from emu import scr_png
            d = os.environ.get('DZ_SHOTS', 'dz'); os.makedirs(d, exist_ok=True)
            for b, nm in ((ref, 'ref'), (cand, 'cand')):
                bank = 7 if b.m.tr.out7ffd & 8 else 5
                scr_png(bytes(b.m.mem.banks[bank][:6912]), os.path.join(d, 't%d_%s.png' % (tick, nm)))
            open(os.path.join(d, 'shown.txt'), 'a').write('%d %d %d\n' % (tick, ref.m.tr.out7ffd & 8, cand.m.tr.out7ffd & 8))
        _n[0] += 1
    else:
        _n[0] = 0
    return on

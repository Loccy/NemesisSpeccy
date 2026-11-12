# For screen_lockstep.py's ALLOW: the first ticks of Konami's dissolve.  The
# native build turns every background black in the tick Konami does (its
# colour pass); 1.0 converted the changed tiles a few a tick, so its screen
# catches up over the next ticks (3 at most in both dissolves: stage 7's
# boss, stage 8's brain).  After that the screens are identical.
ALLOW_TICKS = 4
_t = [None]
def allow(tick, msx_ram, ref, cand):
    a = ref.syms['dz_on']
    if ref.m.mem.banks[2][a - 0x8000] == 0:
        _t[0] = None; return False
    if _t[0] is None: _t[0] = tick
    return tick - _t[0] < ALLOW_TICKS

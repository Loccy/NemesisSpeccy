"""The loading screen: python3 make_loading.py a  -> loading.scr (the one used).
illustration_msx.png is the MSX attract picture, rendered from the simulated MSX
(state 2, tick 1050 of the attract cycle).  Variants b and c restrict the
fortress to its own colours (rejected: too flat)."""
import os as _os
NEM_ROOT = _os.environ.get('NEM_ROOT') or _os.path.normpath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '..', '..'))  # the tree's root
import sys
sys.path.insert(0, NEM_ROOT + '/spec/tape')
import scr_convert as C
S = C.S
v = sys.argv[1]
# the planet's light quarter and the rock's light face: red
for cx in (3, 4, 5):
    for cy in (15, 16):
        C.FORCE[(cx, cy)] = (0, C.R, C.K)
for k in ((28, 17), (29, 17)):
    C.FORCE[k] = (0, C.R, C.K)
if v in ('b', 'c'):
    # the fortress's body: its own colours only (green, blue, black; cyan for its windows in 'c')
    allow = (C.K, C.BL, C.G) if v == 'b' else (C.K, C.BL, C.G, C.C)
    for cy in range(6, 13):
        for cx in range(2, 30):
            C.ALLOW[(cx, cy)] = allow
    for k in ((13, 8), (14, 8), (13, 7), (14, 7)):     # the red burst by the centre
        C.ALLOW[k] = allow + (C.R,)
C.build(S + ('loading.scr' if v == 'a' else 'loading_%s.scr' % v), S + 'loading_%s.png' % v)
